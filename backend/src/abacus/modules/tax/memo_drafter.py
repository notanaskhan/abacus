"""`tax.memo_drafter` v1: the entity return's preparer memo, drafted from code's figures (T-05-T48;
T-05 F9, §6.4; TXP-01; SPEC-651; ADR-019, ADR-050, ADR-052, ADR-230; DEC-4708). Red (agent).

The model writes prose; code has the last word before anything is stored:

- **Inputs** are code's only (ADR-050): the figures the memo may state (each a handle, a label and
  the decimal string code computed: TB totals, Schedule K lines, capital, M-2) and the citation
  handles it may cite (a handle, a short label and the verified quote of a cell or a document).
  No raw ledger, no client file. The sources' quotes sit inside an untrusted block.
- **Segments.** The answer is AgentBlocks-shaped (ADR-230): per section, segments of text with the
  handles they cite. Code stores each section as `{key, segments [{text, citations [{n, start,
  end}]}], human_owned}` (0830): `n` is the source's position among the memo's sources and
  `start`/`end` the segment's span in the section's text.
- **Number provenance.** Every number in a segment must be one of the given figures' values or
  appear in a quote the segment cites. A segment that fails is repaired by dropping it; a section
  left empty reads "Unsupported" (the reviewer sees it, never an invented figure).
- **Citations.** A handle not given is dropped from the segment; a segment that asserts a figure
  without any citation keeps it only when the figure is one of the given figures (code's).
- **Regenerate.** With `affected` keys only those sections are redrafted; every section a person
  owns (edited by a person, P-24) is carried over untouched whatever the model answers.
- **Consent.** The partnership is the §7216 subject (`entity_tri.entity_return_subjects`); the
  gateway refuses the call without both consents (C19, condition 6) and nothing is drafted.
- **Never decides.** Drafting writes a version (`cause` draft or regenerate, `created_by_kind`
  agent, the run and the person it acted for); adopting (L1) and approving (L2) are people's
  (0830's CHECKs; T-05-T54's service).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext

CAPABILITY: Final = "tax.memo_drafter"
UNSUPPORTED: Final = "Unsupported"
SECTION_KEYS: Final = (
    "overview",
    "structural_events",
    "balance_sheet",
    "book_to_tax",
    "depreciation",
    "liabilities_752",
    "states_ptet",
    "distributions",
    "capital",
    "open_items",
    "opportunities",
)
MAX_FACTS: Final = 120
MAX_SOURCES: Final = 80
Int = classified("internal")
Tri = classified("restricted", tri=True)
# A figure, not a form or schedule's name: "M-2", "K-1" and "§754" are names (S41 CI fix, DEC-4735).
_NUMBER: Final = re.compile(r"(?<![\w.§])(?<![A-Za-z]-)\d[\d,]*(?:\.\d+)?")
_KEY: Final = r"^[a-z][a-z0-9_]{0,39}$"
_HANDLE: Final = r"^[a-z][a-z0-9_:!-]{0,59}$"  # a cell handle is `cell:01!f18` (S41 CI fix, DEC-4735)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class MemoFact(BaseModel):
    """One figure code computed (the memo may state it)."""

    model_config = _cfg()

    handle: Annotated[str, Field(pattern=_HANDLE), Int]
    label: Annotated[str, Field(min_length=1, max_length=120), Int]
    value: Annotated[str, Field(min_length=1, max_length=40), Tri]


class MemoSource(BaseModel):
    """A citation handle: a workbook cell or a document passage, with its verified quote."""

    model_config = _cfg()

    handle: Annotated[str, Field(pattern=_HANDLE), Int]
    label: Annotated[str, Field(min_length=1, max_length=120), Int]
    quote: Annotated[str, Field(min_length=1, max_length=600), Tri]


class DraftMemoInput(BaseModel):
    model_config = _cfg()

    entity_name: Annotated[str, Field(min_length=1, max_length=200), Tri]
    tax_year: Annotated[int, Int]
    sections: Annotated[list[str], Field(min_length=1, max_length=len(SECTION_KEYS)), Int]
    facts: Annotated[list[MemoFact], Field(max_length=MAX_FACTS), Tri]
    sources: Annotated[list[MemoSource], Field(max_length=MAX_SOURCES), Tri]


class MemoSegment(BaseModel):
    model_config = _cfg()

    text: Annotated[str, Field(min_length=1, max_length=1200), Tri]
    citations: Annotated[list[str], Field(max_length=8), Int] = Field(default_factory=list[str])


class MemoSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(pattern=_KEY), Int]
    segments: Annotated[list[MemoSegment], Field(max_length=20), Tri]


class DraftMemoOutput(BaseModel):
    model_config = _cfg()

    sections: Annotated[list[MemoSectionOut], Field(max_length=len(SECTION_KEYS)), Tri]


# --- code's settlement -------------------------------------------------------------------------


def _digits(number: str) -> str:
    return number.replace(",", "").lstrip("0") or "0"


def numbers_in(value: str) -> set[str]:
    """The numbers a text states, as bare digit strings ("6,866,200" → "6866200")."""
    return {_digits(m.group(0)) for m in _NUMBER.finditer(value)}


@dataclass(frozen=True)
class Stored:
    """A section as 0830 stores it."""

    key: str
    segments: tuple[Mapping[str, object], ...]
    human_owned: bool
    unsupported: bool = False

    def as_json(self) -> dict[str, object]:
        return {
            "key": self.key,
            "segments": [dict(s) for s in self.segments],
            "human_owned": self.human_owned,
        }


@dataclass(frozen=True)
class Settled:
    sections: tuple[Stored, ...]
    dropped: tuple[tuple[str, str], ...]  # (section, reason)

    @property
    def number_provenance(self) -> float:
        kept = sum(len(s.segments) for s in self.sections if not s.unsupported)
        total = kept + sum(1 for _s, reason in self.dropped if reason == "number_unsupported")
        return 1.0 if total == 0 else kept / total


def settle(
    answer: DraftMemoOutput | None,
    given: DraftMemoInput,
    *,
    human_owned: Mapping[str, Mapping[str, object]] | None = None,
    affected: Sequence[str] | None = None,
    previous: Mapping[str, Mapping[str, object]] | None = None,
) -> Settled:
    """Code's version of the model's draft (module docstring). `human_owned` and `previous` are
    the current version's sections by key; `affected` limits a regenerate."""
    human = dict(human_owned or {})
    prior = dict(previous or {})
    allowed_numbers = {_digits(f.value) for f in given.facts} | {
        n for f in given.facts for n in numbers_in(f.value)
    }
    order = [s.handle for s in given.sources]
    quotes = {s.handle: s.quote for s in given.sources}
    by_key = {s.key: s for s in (answer.sections if answer is not None else [])}
    dropped: list[tuple[str, str]] = []
    out: list[Stored] = []
    for key in given.sections:
        if key in human:
            out.append(
                Stored(
                    key,
                    tuple(cast(list[Mapping[str, object]], human[key].get("segments") or [])),
                    True,
                )
            )
            continue
        if affected is not None and key not in affected and key in prior:
            kept_prior = prior[key]
            out.append(
                Stored(
                    key,
                    tuple(cast(list[Mapping[str, object]], kept_prior.get("segments") or [])),
                    bool(kept_prior.get("human_owned")),
                )
            )
            continue
        section = by_key.get(key)
        segments: list[Mapping[str, object]] = []
        offset = 0
        for segment in [] if section is None else section.segments:
            cited = [h for h in segment.citations if h in quotes]
            if len(cited) != len(segment.citations):
                dropped.append((key, "citation_unknown"))
            stated = numbers_in(segment.text)
            backed = allowed_numbers | {n for h in cited for n in numbers_in(quotes[h])}
            if not stated <= backed:
                dropped.append((key, "number_unsupported"))
                continue
            body = segment.text.strip()
            start = offset + (1 if segments else 0)
            end = start + len(body)
            segments.append(
                {
                    "text": body,
                    "citations": [
                        {"n": order.index(h) + 1, "start": start, "end": end} for h in cited
                    ],
                }
            )
            offset = end
        if not segments:
            dropped.append((key, "section_empty"))
            out.append(Stored(key, ({"text": UNSUPPORTED, "citations": []},), False, True))
            continue
        out.append(Stored(key, tuple(segments), False))
    return Settled(tuple(out), tuple(dropped))


def content_hash_of(sections: Sequence[Stored]) -> str:
    body = json.dumps([s.as_json() for s in sections], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def fingerprint_of(facts: Sequence[MemoFact]) -> str:
    """SHA-256 over the figures the memo was drafted from (staleness compares it, T-05-T54)."""
    body = json.dumps(sorted((f.handle, f.value) for f in facts), separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


# --- the run ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DrafterResult:
    outcome: str  # drafted · refused
    version_no: int | None
    settled: Settled | None


async def _judge(
    agent: AgentContext, given: DraftMemoInput, return_id: UUID
) -> DraftMemoOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2
    from abacus.modules.tax.entity_tri import entity_return_subjects

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("sources",))  # quotes of the client's documents
        .subjects(*await entity_return_subjects(agent.tenant, return_id))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=DraftMemoOutput,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, CAPABILITY, agent.agent_run_id
                ),
                context=context,
                work_class=spec.work_class,
                essential=spec.essential,
                routes=spec.routes,
                cheaper_tiers=spec.cheaper_tiers,
                max_output_tokens=spec.limits.max_output_tokens,
                timeout_seconds=spec.limits.max_seconds,
            )
        )
    except Exception:  # a refused call (consent, boundary, budget, schema): nothing is drafted
        return None
    return cast(DraftMemoOutput, result.output)


_MEMO: Final = text(
    "SELECT id, current_version_no FROM preparer_memos WHERE work_item_id = :r FOR UPDATE"
)
_NEW_MEMO: Final = text(
    "INSERT INTO preparer_memos (tenant_id, engagement_id, work_item_id) "
    "VALUES (:t, :e, :r) ON CONFLICT (work_item_id) DO NOTHING"
)
_CURRENT: Final = text(
    "SELECT sections FROM preparer_memo_versions WHERE memo_id = :m AND version_no = :v"
)
_VERSION: Final = text(
    "INSERT INTO preparer_memo_versions (tenant_id, engagement_id, work_item_id, memo_id, "
    "version_no, sections, cause, created_by_kind, agent_run_id, on_behalf_of_user_id, "
    "content_hash, figure_fingerprint) VALUES (:t, :e, :r, :m, :v, CAST(:sections AS jsonb), "
    ":cause, 'agent', :run, :by, :hash, :fp)"
)
_MOVE: Final = text(
    "UPDATE preparer_memos SET current_version_no = :v, drafted_run_id = :run, "
    "content_hash = :hash, figure_fingerprint = :fp, updated_at = clock_timestamp() "
    "WHERE id = :m"
)
_EVENT: Final = text(
    "INSERT INTO preparer_memo_events (tenant_id, engagement_id, work_item_id, memo_id, event, "
    "version_no, ref) VALUES (:t, :e, :r, :m, :event, :v, CAST(:ref AS jsonb))"
)


async def draft_memo(
    agent: AgentContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    on_behalf_of: UUID,
    given: DraftMemoInput,
    affected: Sequence[str] | None = None,
) -> DrafterResult:
    """One run: the model's draft, settled by code, stored as the memo's next version (a person's
    sections and, on a regenerate, every unaffected section carried over)."""
    from abacus.kernel.uow import Ref, Scope, Target, uow

    answer = await _judge(agent, given, return_id)
    if answer is None:
        return DrafterResult("refused", None, None)
    async with uow(agent.tenant) as tx:
        await tx.session.execute(
            _NEW_MEMO, {"t": agent.tenant_id, "e": engagement_id, "r": return_id}
        )
        memo = (await tx.session.execute(_MEMO, {"r": return_id})).mappings().one()
        current: list[Mapping[str, object]] = []
        if memo["current_version_no"]:
            raw = await tx.session.scalar(
                _CURRENT, {"m": memo["id"], "v": memo["current_version_no"]}
            )
            current = cast(list[Mapping[str, object]], raw or [])
        human = {str(s["key"]): s for s in current if s.get("human_owned")}
        previous = {str(s["key"]): s for s in current}
        settled = settle(
            answer, given, human_owned=human, affected=affected,
            previous=previous if affected is not None else None,
        )  # fmt: skip
        version = int(memo["current_version_no"]) + 1
        digest = content_hash_of(settled.sections)
        fp = fingerprint_of(given.facts)
        cause = "regenerate" if affected is not None and current else "draft"
        scope = {"t": agent.tenant_id, "e": engagement_id, "r": return_id, "m": memo["id"]}
        await tx.session.execute(
            _VERSION,
            {
                **scope, "v": version,
                "sections": json.dumps([s.as_json() for s in settled.sections]),
                "cause": cause, "run": agent.agent_run_id, "by": on_behalf_of,
                "hash": digest, "fp": fp,
            },
        )  # fmt: skip
        await tx.session.execute(
            _MOVE,
            {"m": memo["id"], "v": version, "run": agent.agent_run_id, "hash": digest, "fp": fp},
        )
        await tx.session.execute(
            _EVENT,
            {
                **scope, "event": "regenerated" if cause == "regenerate" else "drafted",
                "v": version,
                "ref": json.dumps(
                    {"dropped": len(settled.dropped), "run": str(agent.agent_run_id)}
                ),
            },
        )  # fmt: skip
        tx.record(
            "tax_memo.regenerated" if cause == "regenerate" else "tax_memo.drafted",
            target=Target("preparer_memo", memo["id"]),
            after=Ref(version_no=version, content_hash=digest, run=agent.agent_run_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return DrafterResult("drafted", version, settled)


__all__ = [
    "CAPABILITY",
    "SECTION_KEYS",
    "UNSUPPORTED",
    "DraftMemoInput",
    "DraftMemoOutput",
    "DrafterResult",
    "MemoFact",
    "MemoSectionOut",
    "MemoSegment",
    "MemoSource",
    "Settled",
    "Stored",
    "content_hash_of",
    "draft_memo",
    "fingerprint_of",
    "numbers_in",
    "settle",
]
