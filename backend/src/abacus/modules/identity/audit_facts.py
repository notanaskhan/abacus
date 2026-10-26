"""What ADM-07's values section may say about identity's own audit targets (G-02-T09 gap;
SPEC-349 AC-5, AC-10, AC-11; DEC-60, DEC-459).

Identity depends on no module, so it cannot register into `platform`'s value-resolver slot;
`platform/audit_resolvers.py` registers for it over these readers, as it does for walls. Each
answers facts the event pins only, as codes, ISO dates or names (the SPA words the codes), and
None when it can say nothing (the platform answers "Values not available"):

- **membership** (`membership.*` events on a `user` target): the role template, firm role,
  security role or deactivation reason the event's references carry; for
  `membership.attributes_changed`, the changed attributes' current values only while the
  membership still stands at the version the event left it (else None: never a value that has
  changed since).
- **support_session**: `requested`: the request's scope, minutes, emergency and reason (set once,
  never changed); `approved` and `emergency_approved`: the status and the window; `ended`,
  `revoked` and `expired`: the status. Other events (a request through the session, an
  acknowledgement) carry no values.

Read-only; the caller (`audit_trail.values`) has already applied the flag and need to know.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity import people_repository
from abacus.modules.identity.people import DEACTIVATION_REASONS, TEMPLATES
from abacus.modules.identity.repository import get_support_session
from abacus.modules.identity.slots import firm_offices
from abacus.modules.identity.staff import FIRM_ROLES_BY_INDEX

FactClass = Literal["internal", "confidential"]
Refs = Mapping[str, str | int]


@dataclass(frozen=True)
class AuditFact:
    """One field's before and after, as codes or text; classified (ADR-031)."""

    field: str
    before: str | None
    after: str | None
    classification: FactClass = "internal"


_REASONS: Final = DEACTIVATION_REASONS
_ROLES: Final = FIRM_ROLES_BY_INDEX
# `membership.attributes_changed` names its changed attributes as reference keys.
_ATTRIBUTES: Final[dict[str, tuple[str, FactClass]]] = {
    "title": ("job_title", "confidential"),
    "office_id": ("office_id", "internal"),
    "service_lines": ("service_lines", "internal"),
    "access_ends_on": ("access_ends_on", "internal"),
    "offshore": ("offshore", "internal"),
}


def _int(refs: Refs, key: str) -> int | None:
    value = refs.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return str(value)


async def _attributes(tenant: TenantContext, user_id: UUID, after: Refs) -> tuple[AuditFact, ...]:
    version = _int(after, "version")
    changed = [key for key in _ATTRIBUTES if _int(after, key) == 1]
    if version is None or not changed:
        return ()
    async with tenant_session(tenant) as session:
        member = await people_repository.staff_row(session, user_id)
    if member is None or int(member["version"]) != version:
        return ()  # changed since: its current values are not this event's
    offices = dict(await firm_offices(tenant)) if "office_id" in changed else {}
    facts: list[AuditFact] = []
    for key in changed:
        column, classification = _ATTRIBUTES[key]
        value = member[column]
        if column == "office_id" and value is not None:
            value = offices.get(value)
            if value is None:
                continue  # an office the firm no longer lists: nothing to name
        facts.append(AuditFact(column, None, _text(value), classification))
    return tuple(facts)


async def membership_audit_facts(
    tenant: TenantContext, action: str, user_id: UUID, after: Refs | None
) -> tuple[AuditFact, ...]:
    after = after or {}
    if action in ("membership.role_changed", "membership.profile_set"):
        template = _int(after, "template")
        if template is not None and 1 <= template <= len(TEMPLATES):
            return (AuditFact("role_template", None, TEMPLATES[template - 1]),)
        role = _int(after, "role")
        if role is not None and (role == 0 or role in _ROLES):
            return (AuditFact("firm_role", None, _ROLES.get(role)),)
        return ()
    if action == "membership.security_role_changed":
        flag = _int(after, "security_admin")
        return (AuditFact("security_admin", None, _text(bool(flag))),) if flag is not None else ()
    if action == "membership.deactivated":
        reason = _REASONS.get(_int(after, "reason") or 0)
        return (AuditFact("reason", None, reason),) if reason is not None else ()
    if action == "membership.attributes_changed":
        return await _attributes(tenant, user_id, after)
    return ()


_CLOSED: Final = {
    "support_session.ended": "ended",
    "support_session.revoked": "revoked",
    "support_session.expired": "expired",
}


async def support_session_audit_facts(
    tenant: TenantContext, action: str, session_id: UUID
) -> tuple[AuditFact, ...]:
    if action in _CLOSED:
        return (AuditFact("status", None, _CLOSED[action]),)
    if action not in (
        "support_session.requested",
        "support_session.approved",
        "support_session.emergency_approved",
    ):
        return ()
    async with tenant_session(tenant) as session:
        row = await get_support_session(session, session_id)
    if row is None:
        return ()
    if action == "support_session.requested":
        return (
            AuditFact("scope", None, _text(row["scope"])),
            AuditFact("duration_minutes", None, _text(row["duration_minutes"])),
            AuditFact("emergency", None, _text(row["emergency"])),
            AuditFact("reason", None, _text(row["reason"]), "confidential"),
        )
    if row["starts_at"] is None:
        return ()  # revoked before it started: no window to show
    return (
        AuditFact("status", "requested", "active"),
        AuditFact("starts_at", None, _text(row["starts_at"])),
        AuditFact("expires_at", None, _text(row["expires_at"])),
    )


__all__ = ["AuditFact", "membership_audit_facts", "support_session_audit_facts"]
