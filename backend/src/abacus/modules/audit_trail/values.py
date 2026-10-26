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

from typing import Final

from abacus.kernel._flags import AUDIT_LOG_VALUES
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.audit_trail.audit_log_contract import (
    AuditPersonOut,
    AuditValuesOut,
    NotIncludedRow,
    ValueRow,
)
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    engagement_resource,
)
from abacus.modules.platform.api import AuditEventRef, AuditValues, audit_values

CONTENT_READ: Final = "engagement.read"
# DEC-435: values of a firm-level event, the QM owner's (a matrix row, AUTHZ-002).
FIRM_VALUES: Final = "audit_event.read_firm_values"


async def may_see_values(ctx: AuthContext, event: AuditEventRef) -> bool:
    """ADR-024 need to know: the target's content read, never an admin's metadata right."""
    # L5: probes (`allowed_actions`), not checks: a withheld section logs no `authz.denied`.
    if event.engagement_id is None:
        action, resource = FIRM_VALUES, Resource.firm(ctx.tenant_id)
    else:
        action = CONTENT_READ
        try:
            resource = await engagement_resource(ctx.tenant, event.engagement_id)
        except NotFound:
            return False
    return action in await allowed_actions(ctx, resource, (action,))


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
        # Already classified and masked by `audit_values` (L8).
        not_included=[
            NotIncludedRow(
                item_label=n.item_label,
                reason_code=n.reason_code,
                amount=n.amount,
                routed_to=(
                    AuditPersonOut(user_id=n.routed_to_user_id, display_name="")
                    if n.routed_to_user_id is not None
                    else None
                ),
            )
            for n in values.not_included
        ],
    )


async def values_for(ctx: AuthContext, event: AuditEventRef) -> AuditValuesOut:
    if not await flag_enabled(ctx.tenant, AUDIT_LOG_VALUES):
        return AuditValuesOut(status="withheld", reason="not_enabled")
    if not await may_see_values(ctx, event):
        return AuditValuesOut(status="withheld", reason="need_to_know")
    return out(await audit_values(ctx, event))


__all__ = ["CONTENT_READ", "FIRM_VALUES", "may_see_values", "out", "values_for"]
