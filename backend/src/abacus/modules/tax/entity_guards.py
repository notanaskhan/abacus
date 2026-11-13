"""The entity return's final-approval guards (T-05-T53; TASK-7904; T-05 F12; TXP-10, TXP-07,
TAX-05, SHL-12 h; ADR-005, ADR-050; DEC-4907). RED: a blocker provider for `tax/approval.py`, the
single owner of the L4 `final_approval` sign-off.

For a return whose form has a workbook (an entity return), final approval is blocked while any of
these hold, each a code and the record it names (never prose; `approval.BLOCKER_WORDS` gives the
words TAX-05 and SHL-12 h show):

- `trial_balance_missing` / `unmapped_accounts`: no trial balance, or an account of the newest
  one without a form line (Unmapped > 0).
- `allocation_structure_not_approved`: the newest allocation structure version is not approved
  (or there is none).
- `tie_out_off_unacknowledged`: a tie-out is off and its section has no current sign-off. A
  section can only be signed while a tie-out is off with a sealed note (T-05-T42), so a current
  (not stale) signed level on the section is the signed note; any edit since makes it stale.
- `workbook_run_in_progress`: a workbook run of the return is open (its cells may still move).
- Open issues whose `blocks` name final approval stay `tax/approval.py`'s own blocker.

A provider that raises blocks (fail closed, `approval.eligibility`). The approve path refuses an
agent, the system and support before reading any of this (`approval._human`, the matrix).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.tax.approval import Blocker
from abacus.modules.tax.workbook_service import WORKBOOK, sheets_of

KIND: Final = "entity_return"
_FORM: Final = text("SELECT form, engagement_id FROM tax_returns WHERE work_item_id = :r")
_SECTION_IDS: Final = text("SELECT key, id FROM tax_workbook_sections WHERE work_item_id = :r")


async def _section_signed(tenant: TenantContext, section_id: UUID, current_hash: str) -> bool:
    from abacus.modules.review.api import sign_off_states
    from abacus.modules.tax.entity_sections import TARGET

    states = (await sign_off_states(tenant, TARGET, [section_id], {section_id: current_hash}))[
        section_id
    ]
    return any(s.signed_by is not None and not s.stale for s in states)


async def entity_blockers(tenant: TenantContext, return_id: UUID) -> list[Blocker]:
    """The provider (module docstring); an individual return's facts, read as the caller."""
    from abacus.modules.agents.api import work_item_runs
    from abacus.modules.review.api import current_values
    from abacus.modules.tax.entity_gates import allocation_approved, unmapped_accounts
    from abacus.modules.tax.entity_sections import SECTIONS, section_hash, tie_outs

    async with tenant_session(tenant) as session:
        row = (await session.execute(_FORM, {"r": return_id})).first()
        sections = {
            str(r.key): UUID(str(r.id))
            for r in await session.execute(_SECTION_IDS, {"r": return_id})
        }
    if row is None or not sheets_of(str(row.form)):
        return []  # not an entity return: nothing to add
    engagement_id = UUID(str(row.engagement_id))
    out: list[Blocker] = []
    unmapped = await unmapped_accounts(tenant, engagement_id)
    if unmapped is None:
        out.append(Blocker("trial_balance_missing"))
    elif unmapped > 0:
        out.append(Blocker("unmapped_accounts"))
    if not await allocation_approved(tenant, return_id):
        out.append(Blocker("allocation_structure_not_approved"))
    values = await current_values(tenant, WORKBOOK, return_id)
    seen: set[str] = set()
    for t in tie_outs(values):
        if t.state != "off" or t.section in seen:
            continue
        seen.add(t.section)
        section = next((p for p in SECTIONS if p.key == t.section), None)
        section_id = sections.get(t.section)
        if section is None or section_id is None:
            out.append(Blocker("tie_out_off_unacknowledged"))
            continue
        if not await _section_signed(tenant, section_id, section_hash(section, values)):
            out.append(Blocker("tie_out_off_unacknowledged", section_id))
    for run in await work_item_runs(tenant, f"tax_return:{return_id}", 5):
        if run.active:
            out.append(Blocker("workbook_run_in_progress", run.run_id))
            break
    return out


def register() -> None:
    """At the tax api's import: the provider joins the final-approval blockers."""
    from abacus.modules.tax.approval import register_final_approval_blocker

    register_final_approval_blocker(KIND, entity_blockers)


__all__ = ["KIND", "entity_blockers", "register"]
