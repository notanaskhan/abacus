"""Read-time values for one event and one viewer (G-02-T09; SPEC-349 AC-5, AC-10, AC-11; DEC-60,
ADR-024, DEC-435).

Nothing here is stored: the values section is resolved per request by the module that owns the
target type (`platform.register_audit_value_resolver`) and masked by classification on the way
out (`platform.audit_values`: a Restricted value is only ever masked). In order:

1. `audit_log.values` off for the firm: `withheld`, `not_enabled`.
2. Need to know: an event on an engagement resolves only for a viewer allowed `engagement.read`
   (content, not metadata) on it; a firm-level event only for the QM owner (`quality_partner`).
   Everyone else, `firm_admin` and `security_admin` included, gets `withheld`, `need_to_know`
   ("Values are visible to partners in scope.").
3. Otherwise the owner's resolver answers; no resolver, or a failing one, is `unavailable`
   ("Values not available"): never a guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from abacus.kernel._flags import AUDIT_LOG_VALUES
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.audit_trail.audit_log_contract import (
    AuditValuesOut,
    NotIncludedRow,
    ValueRow,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
)
from abacus.modules.platform.api import AuditEventRef, AuditValues, audit_values

CONTENT_READ: Final = "engagement.read"
# DEC-435: values of a firm-level event, the QM owner's (a matrix row, AUTHZ-002).
FIRM_VALUES: Final = "audit_event.read_firm_values"


async def may_see_values(ctx: AuthContext, event: AuditEventRef) -> bool:
    """ADR-024 need to know: the target's content read, never an admin's metadata right."""
    try:
        if event.engagement_id is None:
            await authorise(ctx, FIRM_VALUES, Resource.firm(ctx.tenant_id))
            return True
        resource = await engagement_resource(ctx.tenant, event.engagement_id)
        await authorise(ctx, CONTENT_READ, resource)
    except (Forbidden, NotFound):
        return False
    return True


def _not_included(facts: Mapping[str, str | int]) -> NotIncludedRow | None:
    label, reason = facts.get("item_label"), facts.get("reason_code")
    if not isinstance(label, str) or not isinstance(reason, str):
        return None
    amount = facts.get("amount")
    return NotIncludedRow(
        item_label=label, reason_code=reason, amount=amount if isinstance(amount, str) else None
    )


def out(values: AuditValues) -> AuditValuesOut:
    """The platform's answer in the contract's shape (already masked by `audit_values`)."""
    if values.status != "resolved":
        return AuditValuesOut(status=values.status, reason=values.reason)
    return AuditValuesOut(
        status="resolved",
        rows=[
            ValueRow(
                item_label=row.item_label or row.field,
                field=row.field,
                amount=row.amount,
                before=row.before,
                after=row.after,
                masked=row.masked,
            )
            for row in values.rows
        ],
        not_included=[r for f in values.not_included if (r := _not_included(f)) is not None],
    )


async def values_for(ctx: AuthContext, event: AuditEventRef) -> AuditValuesOut:
    if not await flag_enabled(ctx.tenant, AUDIT_LOG_VALUES):
        return AuditValuesOut(status="withheld", reason="not_enabled")
    if not await may_see_values(ctx, event):
        return AuditValuesOut(status="withheld", reason="need_to_know")
    return out(await audit_values(ctx, event))


__all__ = ["CONTENT_READ", "FIRM_VALUES", "may_see_values", "out", "values_for"]
