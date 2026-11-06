"""A-05-T21: mode `ebp_attribute` and the census-to-HR comparison by code (A-05 §3 F4; DEC-2070).
PROTECTED (red).

EBP-03 and EBP-05 test sampled participants census-to-HR. The model reads the HR and payroll
records (masked page text, P-03-T15) and extracts what a record shows (name, hire date, election,
distribution packet fields) with region citations; it never sees an SSN or a date of birth:

- **By code** (`compare`): the HR roster is imported and sealed like the census (A-05-T19's
  `hr_roster` kind), so SSN and date of birth are compared on their firm-keyed fingerprints, and
  name and hire date on the stored values. Any difference is **Needs human**; a hire-date
  difference carries the eligibility engine's note when both dates give the same entry ("No effect
  on entry"), computed under the verified entry rule (none until it is verified, DEC-2387) with the
  census date of birth opened by code, never shown or logged.
- **The mode's inputs** (`attribute_inputs`): the HR and payroll records as documents and code's
  results as facts (participant key, attribute, result, note): tokens only. `assert_masked`
  refuses inputs that carry an SSN pattern or a participant's date of birth before any run.
- **Drafts only**: the finding and the opt-out request wording the mode suggests are drafts; a
  person marks results (the DB refuses an agent `pass`, `exception` or `no_effect`) and sends.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid
from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.compute.ebp import eligibility
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.assurance.ebp_participants import binding
from abacus.modules.assurance.ebp_provisions import entry_rule_read
from abacus.modules.engagements.api import assurance_item
from abacus.modules.identity.api import AgentContext

MODE: Final = "ebp_attribute"
# The PBC areas whose fulfilled requests are the HR and payroll records the mode reads.
ATTRIBUTE_AREAS: Final = frozenset({"eligibility", "participant_data", "distributions"})
MAX_CHECK_FACTS: Final = 60
Attribute = Literal["name", "hire_date", "ssn", "dob"]
Result = Literal["match", "needs_human"]
_SSN: Final = re.compile(r"(?<!\d)\d{3}[- ]?\d{2}[- ]?\d{4}(?!\d)")


class UnmaskedModelInput(DomainInvalid):
    """A mode input carried an SSN pattern or a participant's date of birth: refused, no run."""

    code = "unmasked_model_input"


@dataclass(frozen=True)
class Check:
    participant_key: str
    attribute: Attribute
    result: Result
    note: str | None = None


@dataclass(frozen=True)
class _Row:
    key: str
    name: str
    hire_on: date | None
    ssn_fp: str | None
    dob_fp: str | None
    dob_sealed: bytes | None
    import_id: UUID


_LATEST: Final = text(
    "SELECT p.participant_key, p.name, p.hire_on, p.ssn_fp, p.dob_fp, p.dob_sealed, p.import_id "
    "FROM ebp_participants p WHERE p.work_item_id = :w AND p.import_id = ("
    "SELECT i.id FROM ebp_source_imports i WHERE i.work_item_id = :w AND i.kind = :kind "
    "AND i.status = 'imported' ORDER BY i.created_at DESC LIMIT 1)"
)


async def _rows(tenant: TenantContext, work_item_id: UUID, kind: str) -> dict[str, _Row]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_LATEST, {"w": work_item_id, "kind": kind})).all()
    return {
        r.participant_key: _Row(
            r.participant_key,
            r.name,
            r.hire_on,
            r.ssn_fp,
            r.dob_fp,
            None if r.dob_sealed is None else bytes(r.dob_sealed),
            r.import_id,
        )
        for r in found
    }


def _same_name(a: str, b: str) -> bool:
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


async def _dob(tenant: TenantContext, row: _Row) -> date | None:
    """The census date of birth, opened by code for the entry computation only."""
    if row.dob_sealed is None:
        return None
    opened = await open_sealed(
        tenant.tenant_id, row.dob_sealed, binding(row.import_id, row.key, "dob")
    )
    return date.fromisoformat(opened.decode())


def hire_check(
    key: str,
    dob: date | None,
    census: date,
    hr: date,
    rule: eligibility.EntryRule | None = eligibility.STANDARD_RULE,
) -> Check:
    """A hire-date difference is Needs human; with a date of birth and a verified entry rule, code
    says whether it moves the entry date (the engine's note)."""
    if census == hr:
        return Check(key, "hire_date", "match")
    note = None if dob is None or rule is None else eligibility.review(dob, census, hr, rule).note
    return Check(key, "hire_date", "needs_human", note)


async def compare(tenant: TenantContext, work_item_id: UUID) -> list[Check]:
    """Census against the HR roster, participant by participant (the roster's keys), by code."""
    return (await _compare(tenant, work_item_id))[0]


async def _compare(tenant: TenantContext, work_item_id: UUID) -> tuple[list[Check], list[date]]:
    """The checks, and the dates of birth code opened for them (so the mode's guard can refuse an
    input that carries one; end-pass review S3)."""
    census = await _rows(tenant, work_item_id, "census")
    roster = await _rows(tenant, work_item_id, "hr_roster")
    item = await assurance_item(tenant, work_item_id)
    rule = (await entry_rule_read(tenant, item.engagement_id, work_item_id)).rule
    out: list[Check] = []
    opened: list[date] = []
    for key in sorted(roster):
        hr, c = roster[key], census.get(key)
        if c is None:
            out.append(Check(key, "name", "needs_human", "Not on the census"))
            continue
        out.append(Check(key, "name", "match" if _same_name(c.name, hr.name) else "needs_human"))
        if c.hire_on is not None and hr.hire_on is not None:
            # Opened with or without a rule: the mode's guard scans for it even when no note uses it.
            dob = await _dob(tenant, c) if c.hire_on != hr.hire_on else None
            if dob is not None:
                opened.append(dob)
            out.append(hire_check(key, dob, c.hire_on, hr.hire_on, rule))
        pairs: tuple[tuple[Attribute, str | None, str | None], ...] = (
            ("ssn", c.ssn_fp, hr.ssn_fp),
            ("dob", c.dob_fp, hr.dob_fp),
        )
        for attribute, a, b in pairs:
            if a is not None and b is not None:
                out.append(Check(key, attribute, "match" if a == b else "needs_human"))
    return out, opened


def check_facts(checks: Iterable[Check]) -> tuple[tuple[str, dict[str, object]], ...]:
    """Code's results as facts the drafts cite: only the ones a person must look at, then the
    counts. Keys and codes only: never a value of an SSN or a date of birth."""
    flagged = [c for c in checks if c.result == "needs_human"]
    facts: list[tuple[str, dict[str, object]]] = [
        ("attribute_checks_needing_a_person", {"t": "decimal", "v": str(len(flagged))}),
    ]
    for c in flagged[:MAX_CHECK_FACTS]:
        shown = c.attribute if c.note is None else f"{c.attribute}: {c.note}"
        facts.append((f"needs_human_{c.participant_key}", {"t": "text", "v": shown}))
    return tuple(facts)


def assert_masked(inputs: ModeInputs, dobs: Sequence[date] = ()) -> None:
    """Fail closed before a run: no SSN pattern and no participant's date of birth anywhere in
    the documents, cells or facts the model would read."""
    texts: list[str] = [page.text for d in inputs.documents for page in d.pages]
    texts += [str(c.value.get("v")) for c in inputs.cells if c.value is not None]
    texts += [str(v.get("v")) for _, v in inputs.facts]
    shown = {d.isoformat() for d in dobs} | {d.strftime("%m/%d/%Y") for d in dobs}
    for body in texts:
        if _SSN.search(body) or any(s in body for s in shown):
            raise UnmaskedModelInput(facts={"mode": MODE})


async def attribute_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`ebp_attribute`'s inputs: the HR and payroll records (masked) and code's comparison."""
    documents = await documents_for_areas(actor, paper, ATTRIBUTE_AREAS)
    checks, dobs = await _compare(actor.tenant, paper.work_item_id)
    inputs = ModeInputs(documents=documents.documents, facts=check_facts(checks))
    assert_masked(inputs, dobs)
    return inputs
