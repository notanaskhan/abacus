"""Retention floors and firm policies (Q-02-T23; Q-02 §4.2, AC-30; DEC-76 / P-62). PROTECTED.

Floors and the default policy set are platform content: staff import a numbered set as a draft
and a different staff member publishes it (`import_set`, `publish_set`; migration 0112's
definers refuse the same person). Nothing here or in a migration holds a floor or a year count.

A firm's policy (`retention_policies`) is at or above its floor: the database refuses a lower
one (`below_floor`) and, while locked, any shortening (`policy_locked`). Until a firm has a
policy for a record type, its published floor applies (`effective_policies`), never a literal.
`retention_apply_defaults()` (0112) gives a firm a policy per published default it lacks; the
back-fill task (`abacus_tools.tenants retention-defaults`) and provisioning call it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Literal

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.storage import StoredObject
from abacus.modules.identity.api import AuthContext, Resource, authorise

SetKind = Literal["floors", "defaults"]
Anchor = Literal[
    "upload",
    "report_release",
    "filing_date",
    "due_or_received_later",
    "relationship_end",
    "client_inactive",
    "message_date",
    "event_date",
    "period_end",
]
ServiceLineOrAny = Literal["audit", "tax", "cas", "advisory", "any"]
_IMPORT = text("SELECT retention_set_import(:kind, :version, CAST(:rows AS jsonb), :staff)")


class BelowFloor(DomainInvalid):
    """The policy keeps records for less time than the published legal floor allows."""

    code = "below_floor"


class PolicyLocked(DomainInvalid):
    """A locked policy can't be shortened; unlock it first (and say why in the basis)."""

    code = "policy_locked"


class SetInvalid(DomainInvalid):
    """The set's rows don't fit the floor or default shape (codes, years, anchors)."""

    code = "retention_set_invalid"


class SetExists(DomainConflict):
    """That set version is already imported: import the next version."""

    code = "retention_set_exists"


class SamePerson(DomainConflict):
    """The person who imported a set can't also publish it: a second staff member approves."""

    code = "retention_two_person"


# --- platform sets (staff routes) -------------------------------------------------------------


async def import_set(
    kind: SetKind, version: int, rows: Sequence[Mapping[str, object]], staff: str
) -> int:
    """A draft set; the number of rows imported."""
    try:
        async with platform_transaction(f"staff:{staff}") as conn:
            return int(
                (
                    await conn.execute(
                        _IMPORT,
                        {
                            "kind": kind,
                            "version": version,
                            "rows": json.dumps(rows),
                            "staff": staff,
                        },
                    )
                ).scalar_one()
            )
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise SetExists from None
        raise SetInvalid from None
    except DBAPIError:
        raise SetInvalid from None


async def publish_set(kind: SetKind, version: int, staff: str) -> int:
    """Publish a draft set as a second staff member; the previous published set is superseded."""
    try:
        async with platform_transaction(f"staff:{staff}") as conn:
            published = int(
                (
                    await conn.execute(
                        text("SELECT retention_set_publish(:kind, :version, :staff)"),
                        {"kind": kind, "version": version, "staff": staff},
                    )
                ).scalar_one()
            )
    except DBAPIError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == "42501":
            raise SamePerson from None
        raise
    if published == 0:
        raise NotFound("retention_set")
    return published


# --- a firm's policies ------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectivePolicy:
    """What applies to one record type and service line: the firm's policy, or the floor."""

    record_type: str
    service_line: str
    legal_floor_years: Decimal | None
    anchor: str | None
    authority: str | None
    firm_years: Decimal
    clock_start_event: str
    lock: bool
    basis: str | None
    version: int | None  # None: no firm policy yet, the floor applies
    source: Literal["policy", "floor"]


_FLOORS = text("SELECT * FROM retention_floors_published()")
_POLICIES = text(
    "SELECT record_type, service_line, firm_years, clock_start_event, lock, basis, version "
    "FROM retention_policies ORDER BY record_type, service_line"
)


async def effective_policies(ctx: AuthContext) -> list[EffectivePolicy]:
    await authorise(ctx, "retention_policy.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        floors = {
            (f["record_type"], f["service_line"]): f
            for f in (await session.execute(_FLOORS)).mappings().all()
        }
        policies = {
            (p["record_type"], p["service_line"]): p
            for p in (await session.execute(_POLICIES)).mappings().all()
        }
    out: list[EffectivePolicy] = []
    for key in sorted(set(floors) | set(policies)):
        f, p = floors.get(key), policies.get(key)
        floor = f or floors.get((key[0], "any"))
        if p is not None:
            out.append(
                EffectivePolicy(
                    key[0],
                    key[1],
                    None if floor is None else floor["legal_floor_years"],
                    None if floor is None else floor["anchor"],
                    None if floor is None else floor["authority"],
                    p["firm_years"],
                    p["clock_start_event"],
                    p["lock"],
                    p["basis"],
                    p["version"],
                    "policy",
                )
            )
        elif f is not None:
            out.append(
                EffectivePolicy(
                    key[0],
                    key[1],
                    f["legal_floor_years"],
                    f["anchor"],
                    f["authority"],
                    f["legal_floor_years"],
                    f["anchor"],
                    False,
                    None,
                    None,
                    "floor",
                )
            )
    return out


@dataclass(frozen=True)
class PolicyChange:
    record_type: str
    service_line: ServiceLineOrAny
    firm_years: Decimal
    clock_start_event: Anchor
    lock: bool = False
    basis: str | None = None


def _constraint(exc: DBAPIError) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None), "constraint_name", None
    )


async def set_policy(ctx: AuthContext, change: PolicyChange) -> int:
    """Insert or change one policy, with fresh MFA; the new version. One audit event."""
    await authorise(ctx, "retention_policy.update", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                version = int(
                    (
                        await tx.session.execute(
                            text(
                                "INSERT INTO retention_policies (tenant_id, record_type, "
                                "service_line, firm_years, clock_start_event, lock, basis, "
                                "updated_by) VALUES (:tenant, :record_type, :line, :years, "
                                ":clock, :lock, :basis, :by) "
                                "ON CONFLICT (tenant_id, record_type, service_line) DO UPDATE SET "
                                "firm_years = EXCLUDED.firm_years, "
                                "clock_start_event = EXCLUDED.clock_start_event, "
                                "lock = EXCLUDED.lock, basis = EXCLUDED.basis, "
                                "updated_by = EXCLUDED.updated_by RETURNING version"
                            ),
                            {
                                "tenant": ctx.tenant_id,
                                "record_type": change.record_type,
                                "line": change.service_line,
                                "years": change.firm_years,
                                "clock": change.clock_start_event,
                                "lock": change.lock,
                                "basis": change.basis,
                                "by": f"user:{ctx.user_id}",
                            },
                        )
                    ).scalar_one()
                )
        except DBAPIError as exc:
            named = _constraint(exc)
            if named == "retention_policies_below_floor":
                raise BelowFloor from None
            if named == "retention_policies_locked":
                raise PolicyLocked from None
            raise SetInvalid from None
        tx.record(
            "retention_policy.updated",
            target=Target("firm", ctx.tenant_id),
            after=Ref(version=version),
        )
    return version


# --- retain-until per record class (Q-02-T24) -------------------------------------------------

# The record classes code stores; floors and defaults name them by these codes (their years are
# content). A class with no published floor or policy falls back to `evidence_retention_days`.
RECORD_TYPES: Final = frozenset(
    {"client_document", "derived_rendering", "chain_anchor", "seal_manifest"}
    | {"consent_evidence", "signature_evidence"}
    # Q-02-T41 (ADR-169 §3; Q-02 §7.3): run records, anchored on the engagement's report release
    # or filing date; their floor and default years are content, imported like every other's.
    | {"agent_run_records"}
)
_DAYS_PER_YEAR: Final = Decimal("365.25")
_EFFECTIVE_YEARS = text(
    "SELECT greatest("
    "(SELECT p.firm_years FROM retention_policies p WHERE p.record_type = :type "
    "AND p.service_line IN (:line, 'any') ORDER BY (p.service_line = :line) DESC LIMIT 1), "
    "retention_floor_of(:type, :line))"
)


async def retain_until_for(
    tenant: TenantContext, record_type: str, service_line: str, anchor_at: datetime
) -> datetime | None:
    """When a record of this class, anchored at `anchor_at`, may first be released: the longer of
    the firm's policy and the published floor. None when neither exists yet."""
    if record_type not in RECORD_TYPES:
        raise ValueError(f"unknown record type {record_type!r}")
    async with tenant_session(tenant) as session:
        years = (
            await session.execute(_EFFECTIVE_YEARS, {"type": record_type, "line": service_line})
        ).scalar_one_or_none()
    if years is None:
        return None
    return anchor_at + timedelta(days=float(Decimal(years) * _DAYS_PER_YEAR))


__all__ = [
    "RECORD_TYPES",
    "BelowFloor",
    "EffectivePolicy",
    "PolicyChange",
    "PolicyLocked",
    "SamePerson",
    "SetExists",
    "SetInvalid",
    "effective_policies",
    "extend_retention_for",
    "import_set",
    "publish_set",
    "retain_until_for",
    "set_policy",
]


async def extend_retention_for(
    tenant: TenantContext,
    versions: Sequence[tuple[str, str]],
    record_type: str,
    service_line: str,
    anchor_at: datetime,
) -> int:
    """An anchor event (a report release, a filing date) moved these stored versions' policy
    expiry: lock each `(storage_key, storage_version_id)` until at least the new date, and audit
    `retention.extended` as the system. How many; 0 when no policy or floor applies yet."""
    until = await retain_until_for(tenant, record_type, service_line, anchor_at)
    if until is None or not versions:
        return 0
    for key, version_id in versions:
        await storage.extend_retention(StoredObject(key, version_id, "", 0), until)
    async with uow(TenantContext(tenant.tenant_id, "system", "retention_clock")) as tx:
        tx.record(
            "retention.extended",
            target=Target("firm", tenant.tenant_id),
            after=Ref(objects=len(versions), days=(until - anchor_at).days),
        )
    return len(versions)
