"""The Accrued console's staff API (G-04-T09; SPEC-680 AC-1 to AC-9, AC-12, AC-13; PLT-01;
DEC-5416; red).

- **Who:** a staff member on the staff issuer (`identity.current_staff`, MFA), with a console
  role from the token's claims; `identity.authorise_staff` checks the matrix's staff section
  (and staff MFA within 15 minutes for an entitlement change). No firm, portal, agent or
  break-glass principal reaches a route.
- **Metadata only** (AC-2): the directory (`platform_tenant_directory`) through its definer
  readers: firm display names, tenant codes, counts, module keys and health codes. Nothing here
  reads a client, contact, engagement or document.
- **Entitlements** (AC-7, AC-8): a reason of 20 to 500 characters; a new insert-only
  `plan_entitlements` version written in the firm's context as the staff member (actor kind
  `support`, `staff:<id>`), so the firm's audit trail (ADM-07) names it; the same change goes to
  `platform_audit_events`. Seats below the seats in use answer 409 `seats_below_used`.
- **Plan requests** (AC-45): staff mark a "Request more" applied against the entitlement version
  that carries it.

Provisioning and sandboxes (AC-10 to AC-13) run through `TenantProvisioningWorkflow`, whose firm
creation is `provision_firm` (EXECUTE to `abacus_ops` only); the console's start of it waits on
the ops grant (DEC-5416), so those routes still answer 501.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import Staff, authorise_staff
from abacus.modules.platform.console_contract import (
    EntitlementsPatchIn,
    PlatformPlanRequestOut,
    PlatformPlanRequestsOut,
    PlatformRegionOut,
    PlatformRegionsOut,
    PlatformSessionsOut,
    SeatCountOut,
    SeatsBelowUsed,
    TenantDetailOut,
    TenantRowOut,
    TenantsOut,
    TenantTilesOut,
)

READ: Final = "platform_tenant.read"
UPDATE: Final = "platform_entitlements.update"
_LIBRARY: Final = {"stable": "Stable", "early_access": "Early access"}


class EntitlementsChanged(DomainEvent):
    """`/v1/me` entitlements refresh for the firm (AC-7). Identifiers and counts only."""

    event_type: ClassVar[str] = "tenant.entitlements_changed"

    tenant_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


class PlanRequestNotSent(DomainConflict):
    """Only a request the firm's partner sent to Accrued can be marked applied."""

    code = "plan_request_not_sent"


class EntitlementVersionMissing(DomainConflict):
    code = "entitlement_version_missing"


def _actor(staff: Staff) -> str:
    return f"staff:{staff.id}"


def _staff_tenant(tenant_id: UUID, staff: Staff) -> TenantContext:
    """The firm's context as the staff member (`support`, `staff:<id>`): ADM-07 shows
    "<name> (Accrued)" for it."""
    return TenantContext(tenant_id, "support", _actor(staff))


async def _directory(
    staff: Staff, region: str | None, health: str | None, q: str | None
) -> list[RowMapping]:
    async with platform_transaction(_actor(staff)) as conn:
        return list(
            (
                await conn.execute(
                    text("SELECT * FROM platform_directory_list(:r, :h, :q)"),
                    {"r": region, "h": health, "q": q},
                )
            ).mappings()
        )


async def _plan(tenant_id: UUID, staff: Staff) -> RowMapping | None:
    async with tenant_session(TenantContext(tenant_id, "system", _actor(staff))) as session:
        return (
            (
                await session.execute(
                    text(
                        "SELECT id, renewal_on, seats_total, included_agent_minutes, "
                        "library_channel, policy_principal_available, plan_code, term_start, "
                        "term_end, usage_month_anchor_day, "
                        "(SELECT count(*) FROM plan_entitlements p WHERE p.tenant_id = :t) "
                        "AS version FROM plan_entitlements WHERE tenant_id = :t "
                        "AND valid_from <= abacus_now() ORDER BY valid_from DESC, created_at "
                        "DESC LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            )
            .mappings()
            .first()
        )


def _row(r: RowMapping, codes: Mapping[UUID, str], library: str = "stable") -> TenantRowOut:
    sandbox = cast("UUID | None", r["sandbox_of"])
    return TenantRowOut(
        tenant_code=str(r["tenant_code"]),
        display_name=str(r["display_name"]),
        region=r["region"],
        seats=SeatCountOut(used=int(r["seats_used"]), total=int(r["seats_total"])),
        modules=list(r["modules"] or []),
        health=r["health"],
        health_reason_code=r["health_reason_code"],
        library_channel_label=_LIBRARY.get(library, library),
        support_state=r["support_state"],
        support_state_at=r["support_state_at"],
        synthetic=bool(r["synthetic"]),
        sandbox_of=None if sandbox is None else codes.get(sandbox),
        plan_requests_open=int(r["plan_requests_open"]),
        since=r["since"],
    )


def tiles(rows: Sequence[RowMapping]) -> TenantTilesOut:
    """AC-3: counts over the whole directory (the tile filter never narrows them); seats exclude
    sandboxes."""
    real = [r for r in rows if r["sandbox_of"] is None]
    return TenantTilesOut(
        tenants=len(rows),
        healthy=sum(1 for r in rows if r["health"] == "healthy"),
        degraded=sum(1 for r in rows if r["health"] == "degraded"),
        onboarding=sum(1 for r in rows if r["health"] == "onboarding"),
        seats_used=sum(int(r["seats_used"]) for r in real),
        seats_provisioned=sum(int(r["seats_total"]) for r in real),
    )


async def tenants(
    staff: Staff, *, region: str | None, health: str | None, q: str | None, tile: str | None
) -> TenantsOut:
    authorise_staff(READ, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    rows = await _directory(staff, region, health, q)
    everything = await _directory(staff, None, None, None)
    codes = {cast(UUID, r["tenant_id"]): str(r["tenant_code"]) for r in everything}
    shown = [r for r in rows if tile is None or r["health"] == tile]
    return TenantsOut(items=[_row(r, codes) for r in shown], counts=tiles(everything))


async def _by_code(staff: Staff, tenant_code: str) -> tuple[RowMapping, dict[UUID, str]]:
    everything = await _directory(staff, None, None, None)
    found = next((r for r in everything if r["tenant_code"] == tenant_code), None)
    if found is None:
        raise NotFound("tenant")
    return found, {cast(UUID, r["tenant_id"]): str(r["tenant_code"]) for r in everything}


async def _regions(staff: Staff) -> list[RowMapping]:
    async with platform_transaction(_actor(staff)) as conn:
        return list((await conn.execute(text("SELECT * FROM platform_regions_list()"))).mappings())


async def tenant(staff: Staff, tenant_code: str) -> TenantDetailOut:
    authorise_staff(READ, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    row, codes = await _by_code(staff, tenant_code)
    tenant_id = cast(UUID, row["tenant_id"])
    plan = await _plan(tenant_id, staff)
    if plan is None:
        raise NotFound("plan_entitlements")
    region = next((r for r in await _regions(staff) if r["code"] == row["region"]), None)
    storage = (
        "; ".join(
            str(x)
            for x in (region["storage_label"], region["backup_label"], region["inference_label"])
            if x
        )
        if region is not None
        else ""
    )
    return TenantDetailOut(
        row=_row(row, codes, str(plan["library_channel"])),
        renewal_on=plan["renewal_on"],
        seats_total=int(plan["seats_total"]),
        included_agent_minutes=int(plan["included_agent_minutes"]),
        region_storage_label=storage,
        policy_principal_available=bool(plan["policy_principal_available"]),
        firm_allows_session_requests=row["support_state"] != "declined",
        support_history=[],
        entitlement_version=int(plan["version"]),
    )


def reason_fingerprint(reason: str) -> str:
    """The platform audit keeps a fingerprint of the reason; its text stays in the firm's trail."""
    return hashlib.sha256(reason.encode()).hexdigest()[:16]


_NEW_VERSION: Final = text(
    "INSERT INTO plan_entitlements (tenant_id, plan_code, term_start, term_end, renewal_on, "
    "usage_month_anchor_day, included_agent_minutes, seats_total, library_channel, "
    "policy_principal_available, changed_by_staff, change_reason, plan_request_id) VALUES "
    "(:t, :plan, :ts, :te, :renew, :anchor, :minutes, :seats, :lib, :policy, :staff, :reason, "
    ":request) RETURNING id"
)


async def patch_entitlements(
    staff: Staff, tenant_code: str, body: EntitlementsPatchIn
) -> TenantDetailOut:
    """AC-7, AC-8: a new entitlement version with a reason, in the firm's trail and the platform's.
    Module switches stay the operator's (`tenant_entitlements`, `make entitlement`): a modules
    change is recorded in the platform audit for the operator to apply (DEC-5416)."""
    role = authorise_staff(
        UPDATE, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id
    )
    row, _ = await _by_code(staff, tenant_code)
    tenant_id = cast(UUID, row["tenant_id"])
    current = await _plan(tenant_id, staff)
    if current is None:
        raise NotFound("plan_entitlements")
    seats = body.seats_total if body.seats_total is not None else int(current["seats_total"])
    if seats < int(row["seats_used"]):
        raise SeatsBelowUsed(facts={"seats_used": int(row["seats_used"])})
    renewal = cast(date, body.renewal_on or current["renewal_on"])
    minutes = (
        body.included_agent_minutes
        if body.included_agent_minutes is not None
        else int(current["included_agent_minutes"])
    )
    policy = (
        body.policy_principal_available
        if body.policy_principal_available is not None
        else bool(current["policy_principal_available"])
    )
    version = int(current["version"]) + 1
    async with uow(_staff_tenant(tenant_id, staff)) as tx:
        made = await tx.session.scalar(
            _NEW_VERSION,
            {"t": tenant_id, "plan": current["plan_code"], "ts": current["term_start"],
             "te": max(cast(date, current["term_end"]), renewal), "renew": renewal,
             "anchor": current["usage_month_anchor_day"], "minutes": minutes, "seats": seats,
             "lib": current["library_channel"], "policy": policy, "staff": staff.subject[:200],
             "reason": body.reason, "request": body.plan_request_id},
        )  # fmt: skip
        tx.record(
            "tenant.entitlements_changed",
            target=Target("firm", tenant_id),
            after=Ref(version=version, seats_total=seats, included_agent_minutes=minutes),
        )
        tx.emit(EntitlementsChanged(tenant_id=tenant_id, version=version))
    facts = {
        "version": version,
        "entitlement_id": str(made),
        "seats_total": seats,
        "included_agent_minutes": minutes,
        "modules_requested": sorted(body.modules or []),
    }
    async with platform_transaction(_actor(staff)) as conn:
        await conn.execute(
            text(
                "SELECT platform_audit_record(:s, :role, 'tenant.entitlements_changed', "
                "'tenant', :code, :t, :reason, CAST(:facts AS jsonb))"
            ),
            {"s": staff.subject, "role": role, "code": tenant_code, "t": tenant_id,
             "reason": reason_fingerprint(body.reason), "facts": json.dumps(facts)},
        )  # fmt: skip
    return await tenant(staff, tenant_code)


async def regions(staff: Staff) -> PlatformRegionsOut:
    authorise_staff(READ, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    return PlatformRegionsOut(
        items=[
            PlatformRegionOut(
                code=r["code"],
                label=r["label"],
                status=r["status"],
                planned_label=r["planned_label"],
                storage_label=r["storage_label"],
            )
            for r in await _regions(staff)
        ]
    )


async def support_sessions(staff: Staff, status: str | None) -> PlatformSessionsOut:
    """The directory's support state per tenant (scope kind and history stay in the firm's
    trail; SPEC-681 AC-17). Counts by state."""
    authorise_staff(READ, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    rows = [r for r in await _directory(staff, None, None, None) if r["support_state"]]
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["support_state"])] = counts.get(str(r["support_state"]), 0) + 1
    del status  # history rows land with the session projector (G-04-T10); counts are live now
    return PlatformSessionsOut(items=[], counts=counts)


_REQUESTS: Final = text(
    "SELECT id, kind, from_value, to_value, modules_add, effective_from, decided_by, status, "
    "decided_at, created_at, version FROM plan_change_requests "
    "WHERE status IN ('sent_to_accrued', 'applied') ORDER BY created_at DESC"
)


async def _names(tenant_id: UUID, ids: set[UUID]) -> dict[UUID, str]:
    from abacus.modules.identity.api import names_of

    del tenant_id
    return await names_of(sorted(ids, key=str)) if ids else {}


async def plan_requests(staff: Staff, status: str | None) -> PlatformPlanRequestsOut:
    authorise_staff(READ, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    out: list[PlatformPlanRequestOut] = []
    counts = {"sent_to_accrued": 0, "applied": 0}
    for d in await _directory(staff, None, None, None):
        tenant_id = cast(UUID, d["tenant_id"])
        async with tenant_session(TenantContext(tenant_id, "system", _actor(staff))) as session:
            rows = list((await session.execute(_REQUESTS)).mappings())
        names = await _names(
            tenant_id, {cast(UUID, r["decided_by"]) for r in rows if r["decided_by"]}
        )
        for r in rows:
            counts[str(r["status"])] += 1
            if status is not None and r["status"] != status:
                continue
            out.append(
                PlatformPlanRequestOut(
                    id=r["id"],
                    tenant_code=str(d["tenant_code"]),
                    firm_display_name=str(d["display_name"]),
                    kind=r["kind"],
                    from_value=r["from_value"],
                    to_value=r["to_value"],
                    modules_add=list(r["modules_add"] or []),
                    effective_from=r["effective_from"],
                    approved_by_display_name=names.get(cast(UUID, r["decided_by"]), ""),
                    status=r["status"],
                    sent_at=cast(datetime, r["decided_at"] or r["created_at"]),
                )
            )
    return PlatformPlanRequestsOut(items=out, counts=counts)


async def mark_applied(
    staff: Staff, request_id: UUID, entitlement_version: int
) -> PlatformPlanRequestOut:
    """AC-45: the request's entitlement version is the one staff wrote for it."""
    role = authorise_staff(
        UPDATE, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id
    )
    for d in await _directory(staff, None, None, None):
        tenant_id = cast(UUID, d["tenant_id"])
        ctx = _staff_tenant(tenant_id, staff)
        async with uow(ctx) as tx:
            found = (
                await tx.session.execute(
                    text(
                        "SELECT status, version FROM plan_change_requests WHERE id = :id "
                        "FOR UPDATE"
                    ),
                    {"id": request_id},
                )
            ).first()
            if found is None:
                continue
            if found.status != "sent_to_accrued":
                raise PlanRequestNotSent(facts={"status": str(found.status)})
            version_id = await tx.session.scalar(
                text(
                    "SELECT id FROM plan_entitlements WHERE tenant_id = :t "
                    "ORDER BY valid_from, created_at OFFSET :n LIMIT 1"
                ),
                {"t": tenant_id, "n": entitlement_version - 1},
            )
            if version_id is None:
                raise EntitlementVersionMissing(facts={"version": entitlement_version})
            await tx.session.execute(
                text(
                    "UPDATE plan_change_requests SET status = 'applied', applied_by_staff = :s, "
                    "applied_at = abacus_now(), plan_entitlement_version_id = :v, "
                    "version = version + 1 WHERE id = :id"
                ),
                {"s": staff.subject[:200], "v": version_id, "id": request_id},
            )
            tx.record(
                "plan_request.applied",
                target=Target("plan_change_request", request_id),
                after=Ref(entitlement_version=entitlement_version),
            )
        async with platform_transaction(_actor(staff)) as conn:
            await conn.execute(
                text(
                    "SELECT platform_audit_record(:s, :role, 'plan_request.applied', "
                    "'plan_change_request', :id, :t, NULL, '{}'::jsonb)"
                ),
                {"s": staff.subject, "role": role, "id": str(request_id), "t": tenant_id},
            )
        listed = await plan_requests(staff, None)
        return next(x for x in listed.items if x.id == request_id)
    raise NotFound("plan_change_request")


__all__ = [
    "EntitlementsChanged",
    "mark_applied",
    "patch_entitlements",
    "plan_requests",
    "reason_fingerprint",
    "regions",
    "support_sessions",
    "tenant",
    "tenants",
    "tiles",
]
