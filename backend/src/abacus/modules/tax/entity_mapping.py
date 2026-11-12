"""An entity return's account mappings to Form 1065 lines, applied (T-05-T26; T-05 F3; TXP-02;
DEC-4406, DEC-4518). RED: it writes C9 mappings on a tax reviewer's approval.

T-05-T23's `tax.account_mapper` proposes `tax_account_mapping` rows (`account:<code>` → a form-line
key) on the return. Approving that proposal in SHL-10 is a person's decision; this adapter, called
after the decision commits (DEC-4415), applies it for that person:

- **The tax reviewer only.** The approver must hold `tax_mapping.approve` on the return (the
  detail reviewer, manager reviewer or signer function; never the preparer, the agent or the
  system): otherwise 403 `level_not_permitted` and nothing is written.
- **Into the return's tax set.** The return's current trial balance carries a `tax_form_line`
  mapping set pinned to the C21 `tax_form_lines` version in effect (created on first use); each row
  becomes one human `mapping_set_edits` row naming the approver. A key outside the version's
  mappable keys is refused (422 `form_line_key_unknown`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainForbidden, NotFound
from abacus.kernel.uow import uow
from abacus.modules.agents.api import approved_proposal_rows, proposal_approver
from abacus.modules.identity.api import engagement_resource, member_could
from abacus.modules.ledger.api import (
    engagement_trial_balances,
    ensure_tax_mapping_set,
    record_form_line,
)
from abacus.modules.platform.api import tax_form_lines_for

KIND: Final = "tax_account_mapping"
APPROVE: Final = "tax_mapping.approve"
ACCOUNT_PREFIX: Final = "account:"


class MappingLevelNotPermitted(DomainForbidden):
    """The approver does not hold the tax reviewer's function on the return."""

    code = "level_not_permitted"


def account_of(field_key: str) -> str | None:
    """`account:4510-T` → `4510-T`; anything else is not a mapping row."""
    if not field_key.startswith(ACCOUNT_PREFIX):
        return None
    code = field_key.removeprefix(ACCOUNT_PREFIX).strip()
    return code or None


async def apply_account_mapping_proposal(tenant: TenantContext, proposal_id: UUID) -> None:
    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
        approver = await proposal_approver(session, proposal_id)
    if found is None:
        return
    engagement_id, rows = found
    mappings = [
        (code, str(row.after.get("v")), UUID(str(row.field_ref["target_id"])))
        for row in rows
        if isinstance(row.after, dict)
        and row.after.get("v")
        and (code := account_of(str(row.field_ref.get("field_key", "")))) is not None
    ]
    if not mappings:
        return
    if approver is None:
        raise MappingLevelNotPermitted(facts={"proposal_id": str(proposal_id)})
    return_id = mappings[0][2]
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")
    resource = replace(await engagement_resource(system, engagement_id), work_item_id=return_id)
    if not await member_could(tenant.tenant_id, approver, APPROVE, resource):
        raise MappingLevelNotPermitted(facts={"proposal_id": str(proposal_id)})
    async with tenant_session(system) as session:
        facts = (
            await session.execute(
                text("SELECT form, tax_year FROM tax_returns WHERE work_item_id = :r"),
                {"r": return_id},
            )
        ).first()
    if facts is None:
        raise NotFound("tax_return")
    lines = await tax_form_lines_for(
        str(facts.form), int(facts.tax_year), as_of=await today(system)
    )
    tbs = await engagement_trial_balances(system, engagement_id)
    if not tbs:
        raise NotFound("trial_balance")
    current = max(tbs, key=lambda t: t.period_end)
    async with uow(system) as tx:
        set_id = await ensure_tax_mapping_set(
            tx,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            trial_balance_id=current.id,
            reference_set_version_id=lines.reference_set_version_id,
            created_by=approver,
        )
        for code, key, _ in mappings:
            await record_form_line(
                tx,
                tenant_id=tenant.tenant_id,
                mapping_set_id=set_id,
                engagement_id=engagement_id,
                account_code=code,
                form_line_key=key,
                keys=lines.mappable_keys,
                edited_by=approver,
            )
