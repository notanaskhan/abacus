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

from dataclasses import dataclass, replace
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainForbidden, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import approved_proposal_rows, proposal_approver
from abacus.modules.identity.api import AuthContext, engagement_resource, member_could
from abacus.modules.ledger.api import (
    FormLineKeyUnknown,
    engagement_trial_balances,
    ensure_tax_mapping_set,
    record_form_line,
)
from abacus.modules.platform.api import tax_form_lines_for
from abacus.modules.review.api import raise_review_note
from abacus.modules.tax.workbook_service import WORKBOOK

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
    engagement, rows = found
    if engagement is None:  # a tax mapping is an engagement's; never applied as a no-op
        raise NotFound("engagement")
    engagement_id: UUID = engagement
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


# --- A person's pick in TXP-02's line picker (T-05-T37 rest; DEC-4629) ---------------------------

_SCHEDULE: Final = {
    "L": "Schedule L",
    "K": "Schedule K",
    "8825": "Form 8825",
    "M-1": "Schedule M-1",
    "M-2": "Schedule M-2",
    "M-3": "Schedule M-3",
}
MAX_LINES: Final = 200


@dataclass(frozen=True)
class FormLineChoice:
    key: str
    label: str  # "Schedule L · line 5 Tax-exempt securities"


async def form_line_choices(
    ctx: AuthContext, form: str, tax_year: int, q: str | None
) -> list[FormLineChoice]:
    """The picker's list: the published set's mappable lines for the form and year (a total is
    computed, never mapped), filtered by `q` on the key or label. No published set: 404."""
    try:
        found = await tax_form_lines_for(form, tax_year, as_of=await today(ctx.tenant))
    except LookupError:
        raise NotFound("tax_form_lines") from None
    needle = (q or "").strip().casefold()
    out: list[FormLineChoice] = []
    for line in found.lines:
        if not line.mappable:
            continue
        label = f"{_SCHEDULE.get(line.schedule, line.schedule)} · line {line.line} {line.label}"
        if needle and needle not in line.key.casefold() and needle not in label.casefold():
            continue
        out.append(FormLineChoice(line.key, label))
        if len(out) >= MAX_LINES:
            break
    return out


@dataclass(frozen=True)
class PickOutcome:
    state: Literal["mapped", "flagged"]
    note_id: UUID | None = None
    mapping_set_id: UUID | None = None  # the set a mapped pick wrote to (DEC-4824)


async def pick_form_line(
    ctx: AuthContext,
    return_id: UUID,
    engagement_id: UUID,
    account_code: str,
    form_line_key: str,
    rationale: str | None,
) -> PickOutcome:
    """DEC-4629. The route authorised `account_mapping.edit` on the return.

    - A person holding the tax reviewer's function (`tax_mapping.approve`) maps the account: the
      pick is the mapping judgment and its approval in one human act, written as that person's
      `mapping_set_edits` row (C9; human only) with the audit event `tax.mapping_recorded`.
    - Anyone else's pick maps nothing: a review note anchored on the account's mapping proposes
      the line to the reviewer, who picks it in turn (TXP-02's "Proposed" state).
    A key outside the published set's mappable keys is 422 `form_line_key_unknown` either way."""
    async with tenant_session(ctx.tenant) as session:
        facts = (
            await session.execute(
                text("SELECT form, tax_year FROM tax_returns WHERE work_item_id = :r"),
                {"r": return_id},
            )
        ).first()
    if facts is None:
        raise NotFound("tax_return")
    lines = await tax_form_lines_for(
        str(facts.form), int(facts.tax_year), as_of=await today(ctx.tenant)
    )
    if form_line_key not in lines.mappable_keys:
        raise FormLineKeyUnknown(facts={"field": "form_line_key"})
    resource = replace(
        await engagement_resource(ctx.tenant, engagement_id), work_item_id=return_id
    )
    if not await member_could(ctx.tenant_id, ctx.user_id, APPROVE, resource):
        note = await raise_review_note(
            ctx,
            WORKBOOK,
            return_id,
            anchor_kind="field",
            anchor_ref=f"{ACCOUNT_PREFIX}{account_code}",
            body=f"Proposed line for {account_code}: {form_line_key}"
            + (f" ({rationale})" if rationale else ""),
            assignee=None,
        )
        return PickOutcome("flagged", note.note.id)
    tbs = await engagement_trial_balances(ctx.tenant, engagement_id)
    if not tbs:
        raise NotFound("trial_balance")
    current = max(tbs, key=lambda t: t.period_end)
    async with uow(ctx.tenant) as tx:
        set_id = await ensure_tax_mapping_set(
            tx,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            trial_balance_id=current.id,
            reference_set_version_id=lines.reference_set_version_id,
            created_by=ctx.user_id,
        )
        await record_form_line(
            tx,
            tenant_id=ctx.tenant_id,
            mapping_set_id=set_id,
            engagement_id=engagement_id,
            account_code=account_code,
            form_line_key=form_line_key,
            keys=lines.mappable_keys,
            edited_by=ctx.user_id,
        )
        tx.record(
            "tax.mapping_recorded",
            target=Target(WORKBOOK, return_id),
            after=Ref(mapping_set=set_id),  # IDs only: the code and key are in the edit row
        )
    return PickOutcome("mapped", mapping_set_id=set_id)
