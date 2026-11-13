"""The Today brief's facts collector (I-02-T07; I-02 §6, F3; SPEC-654; ADR-025, ADR-050, ADR-052,
ADR-230; C13, C19; DEC-4719). Red (agent).

For one engagement and the viewer the run acts for, code gathers what a `briefing.today` run may
say, before any model call:

- **Gates.** The viewer's open C13 gates on the engagement (`review.api.gates_waiting_on` under
  the viewer's own context: what waits on them, walls applied), each with its kind, subject, due
  date and whether something blocks it. Gate titles and any client string are untrusted.
- **Facts.** A per-run registry of figures code computed (ADR-050, P-24): the gates' due dates,
  the engagement's PBC counts (`requests.api.pbc_counts`), the active runs, and every owner's
  registered contribution (`register_briefing_source`: the tax module adds Ridgeline's off
  tie-outs and the §754 placeholder, 6,200 and 28,595). The model may cite a figure only by its id.
- **Candidate citations.** `record_field` for each gate and filing deadline, `workpaper_cell`,
  `tax_form_line` and `request_item` refs the owners offer; T-08's validator verifies the ones a
  sentence uses.
- **Data subjects** (C19). Every owner names its §7216 subjects; when any is TRI and lacks both
  consents in force, the collector refuses with `consent_7216` before any model call.
- **Hash.** `facts_hash` is SHA-256 over the canonical facts, gates and subjects (order-free), so
  the same day's inputs give the same hash across runs (a rebuild with nothing new is a no-op).

Owners register sources fail-closed: a second registration under the same name with a different
function is refused; an owner's failure leaves its contribution out and is logged, never guessed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.logging import get_logger
from abacus.modules.agents.blocks import Fact

_log = get_logger(__name__)
MAX_GATES: Final = 40


class ConsentRequired(DomainConflict):
    """A TRI subject of the engagement lacks the §7216 consents in force: no model call."""

    code = "consent_7216"


@dataclass(frozen=True)
class Subject:
    entity_id: UUID
    tri: bool
    tax_year: int | None = None


@dataclass(frozen=True)
class Candidate:
    kind: str  # record_field, workpaper_cell, tax_form_line, request_item
    ref: str


@dataclass(frozen=True)
class Contribution:
    facts: Sequence[Fact] = ()
    subjects: Sequence[Subject] = ()
    citations: Sequence[Candidate] = ()


BriefingSource = Callable[[TenantContext, UUID], Awaitable[Contribution]]
_SOURCES: dict[str, BriefingSource] = {}


def register_briefing_source(name: str, source: BriefingSource) -> None:
    known = _SOURCES.get(name)
    if known is not None and (known.__module__, known.__qualname__) != (
        source.__module__,
        source.__qualname__,
    ):
        raise ValueError(f"briefing source {name!r} is already registered")
    _SOURCES[name] = source


@dataclass(frozen=True)
class GateFact:
    gate_id: UUID
    kind: str
    subject_type: str
    subject_id: UUID
    work_item_id: UUID | None
    due_on: date | None
    blocked: bool
    blocked_reason: str | None


@dataclass(frozen=True)
class BriefingFacts:
    engagement_id: UUID
    viewer_user_id: UUID
    gates: tuple[GateFact, ...]
    facts: dict[str, Fact]
    citations: tuple[Candidate, ...]
    subjects: tuple[Subject, ...]
    untrusted: tuple[str, ...] = ("gate_titles", "client_strings")
    facts_hash: str = field(default="")


def fact_id(*parts: object) -> str:
    """A registry id from code parts under the blocks' rule (`^[a-z][a-z0-9_]{0,39}$`): a UUID
    part is shortened to its first 8 hex digits ("gate_1a2b3c4d_due")."""
    out: list[str] = []
    for p in parts:
        text = str(p.hex[:8]) if isinstance(p, UUID) else str(p).lower()
        out.append("".join(c if c.isalnum() else "_" for c in text))
    raw = "_".join(out)
    return (raw if raw[:1].isalpha() else f"f_{raw}")[:40]


def hash_of(gates: Sequence[GateFact], facts: dict[str, Fact], subjects: Sequence[Subject]) -> str:
    body = {
        "gates": sorted(
            [str(g.gate_id), g.kind, None if g.due_on is None else g.due_on.isoformat(), g.blocked]
            for g in gates
        ),
        "facts": sorted([f.id, f.kind, f.value] for f in facts.values()),
        "subjects": sorted([str(s.entity_id), s.tri, s.tax_year] for s in subjects),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _consented(tenant: TenantContext, subjects: Sequence[Subject], at: datetime) -> bool:
    from abacus.modules.organisations.api import tri_consent_verdict

    for s in subjects:
        if not s.tri:
            continue
        verdict = await tri_consent_verdict(tenant, [s.entity_id], at, tax_year=s.tax_year)
        if not verdict.valid:
            return False
    return True


async def collect(viewer: object, engagement_id: UUID) -> BriefingFacts:
    """The facts for one engagement as `viewer` (the run's initiator context) may see them."""
    from abacus.kernel import clock
    from abacus.modules.engagements.api import work_item_ids_of
    from abacus.modules.requests.api import pbc_counts
    from abacus.modules.review.api import gates_waiting_on

    tenant: TenantContext = viewer.tenant  # type: ignore[attr-defined] -- an AuthContext
    page = await gates_waiting_on(
        viewer,  # type: ignore[arg-type]
        kind=None, engagement_id=engagement_id, cursor=None, limit=MAX_GATES, sort="deadline",
    )  # fmt: skip
    gates = tuple(
        GateFact(
            g.id, g.kind, g.subject_type, g.subject_id, g.work_item_id, g.due_on, g.blocked,
            g.blocked_reason_code,
        )
        for g in page.items
    )  # fmt: skip
    facts: dict[str, Fact] = {}
    citations: list[Candidate] = []
    for g in gates:
        citations.append(Candidate("record_field", f"{g.subject_type}:{g.subject_id}"))
        if g.due_on is not None:
            fid = fact_id("gate", g.gate_id, "due")
            facts[fid] = Fact(
                id=fid, kind="date", value=g.due_on.isoformat(), basis="C13 gate due date"
            )
    work_items = await work_item_ids_of(tenant, engagement_id)
    counts = await pbc_counts(viewer, work_items)  # type: ignore[arg-type]
    if counts:
        received = sum(r for r, _t in counts.values())
        total = sum(t for _r, t in counts.values())
        facts["pbc_received"] = Fact(
            id="pbc_received", kind="count", value=str(received), basis="requests.pbc_counts"
        )
        facts["pbc_total"] = Fact(
            id="pbc_total", kind="count", value=str(total), basis="requests.pbc_counts"
        )
    subjects: list[Subject] = []
    for name, source in sorted(_SOURCES.items()):
        try:
            found = await source(tenant, engagement_id)
        except Exception:  # an owner's failure leaves its part out; never guessed
            _log.warning("briefing_source_failed", source=name)
            continue
        for f in found.facts:
            facts[f.id] = f
        subjects.extend(found.subjects)
        citations.extend(found.citations)
    now = await clock.now(tenant)
    if not await _consented(tenant, subjects, now):
        raise ConsentRequired(facts={"engagement_id": str(engagement_id)})
    viewer_id: UUID = viewer.user_id  # type: ignore[attr-defined]
    return BriefingFacts(
        engagement_id=engagement_id,
        viewer_user_id=viewer_id,
        gates=gates,
        facts=facts,
        citations=tuple(dict.fromkeys(citations)),
        subjects=tuple(subjects),
        facts_hash=hash_of(gates, facts, subjects),
    )


__all__ = [
    "BriefingFacts",
    "BriefingSource",
    "Candidate",
    "ConsentRequired",
    "Contribution",
    "GateFact",
    "Subject",
    "collect",
    "fact_id",
    "hash_of",
    "register_briefing_source",
]
