"""What can be reviewed (P-04; SPEC-313). Each owner registers a provider that lists its
reviewables on an engagement with their current content hash; the matrix and the G5 gate read
every registered provider. Fail closed: an unregistered type has nothing to review, and a
provider that raises makes the gate unmet."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, ServiceUnavailable

# The levels every reviewable needs before completion (L1 preparer, L2 reviewer). K-02's
# methodology policies will set more per area and risk.
REQUIRED_LEVELS: Final = (1, 2)


@dataclass(frozen=True)
class Reviewable:
    target_type: str
    target_id: UUID
    code: str
    title: str
    content_hash: str
    has_content: bool


ReviewableProvider = Callable[[TenantContext, UUID], Awaitable[list[Reviewable]]]
_PROVIDERS: dict[str, ReviewableProvider] = {}


def register_reviewable(target_type: str, provider: ReviewableProvider) -> None:
    known = _PROVIDERS.get(target_type)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"reviewable {target_type!r} is already registered")
    _PROVIDERS[target_type] = provider


def reviewable_types() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


async def reviewables_of(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Every registered type's reviewables, by type then code (callers authorised first)."""
    out: list[Reviewable] = []
    for target_type in reviewable_types():
        found = await _PROVIDERS[target_type](tenant, engagement_id)
        out.extend(sorted(found, key=lambda r: r.code))
    return out


# --- P-04-T06 (ADR-160): the other review slots. Each fails closed: an unregistered kind is
# refused (422 `unregistered_kind`), and an owner that isn't there answers 503.


class UnregisteredKind(DomainInvalid):
    """A decision kind, gate kind, field owner or fix runner nobody registered."""

    code = "unregistered_kind"


DecisionOptions = Callable[[TenantContext, UUID], Awaitable[list[str]]]
GateCheck = Callable[[TenantContext, UUID], Awaitable[bool]]
FieldValue = Callable[[TenantContext, UUID, str], Awaitable[dict[str, object] | None]]
FixRunner = Callable[[TenantContext, UUID], Awaitable[None]]


@dataclass(frozen=True)
class DecisionKind:
    """A decision card's kind (A-04 materiality, T-04 treatment, ...): who it is reserved to
    and how its options are computed (by code, never a model: ADR-050)."""

    code: str
    reserved_role: str
    options: DecisionOptions


@dataclass(frozen=True)
class FieldOwner:
    """The module that owns a target type's fields: their current value, and whether a field
    holds tax-return information (TRI facts resolve behind C19's consent gate)."""

    target_type: str
    value_of: FieldValue
    tri_fields: frozenset[str] = frozenset()


_DECISION_KINDS: dict[str, DecisionKind] = {}
_GATE_KINDS: dict[str, GateCheck] = {}
_FIELD_OWNERS: dict[str, FieldOwner] = {}
_FIX_RUNNERS: dict[str, FixRunner] = {}
_RESERVED_ROLES: Final = frozenset({"engagement_partner", "manager", "eqr_reviewer", "signer"})
_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")


def _name(f: object) -> tuple[object, object]:
    return (getattr(f, "__module__", None), getattr(f, "__qualname__", None))


def _register[T](registry: dict[str, T], what: str, code: str, value: T, same: bool) -> None:
    if not _CODE.fullmatch(code):
        raise ValueError(f"{what} {code!r} must be snake_case")
    if code in registry and not same:
        raise ValueError(f"{what} {code!r} is already registered")
    registry[code] = value


def register_decision_kind(kind: DecisionKind) -> None:
    if kind.reserved_role not in _RESERVED_ROLES:
        raise ValueError(f"decision kind {kind.code!r}: unknown reserved role")
    known = _DECISION_KINDS.get(kind.code)
    same = known is not None and (known.reserved_role, _name(known.options)) == (
        kind.reserved_role,
        _name(kind.options),
    )
    _register(_DECISION_KINDS, "decision kind", kind.code, kind, same)


def decision_kind(code: str) -> DecisionKind:
    found = _DECISION_KINDS.get(code)
    if found is None:
        raise UnregisteredKind
    return found


def register_gate_kind(code: str, check: GateCheck) -> None:
    known = _GATE_KINDS.get(code)
    _register(
        _GATE_KINDS, "gate kind", code, check, known is not None and _name(known) == _name(check)
    )


async def gate_met(tenant: TenantContext, code: str, engagement_id: UUID) -> bool:
    """Fail closed: an unregistered gate kind is refused; an owner that raises is unmet."""
    check = _GATE_KINDS.get(code)
    if check is None:
        raise UnregisteredKind
    try:
        return await check(tenant, engagement_id)
    except Exception:
        return False


def register_field_owner(owner: FieldOwner) -> None:
    known = _FIELD_OWNERS.get(owner.target_type)
    same = known is not None and (_name(known.value_of), known.tri_fields) == (
        _name(owner.value_of),
        owner.tri_fields,
    )
    _register(_FIELD_OWNERS, "field owner", owner.target_type, owner, same)


def field_owner(target_type: str) -> FieldOwner:
    found = _FIELD_OWNERS.get(target_type)
    if found is None:
        raise UnregisteredKind
    return found


def register_fix_runner(issue_kind: str, runner: FixRunner) -> None:
    known = _FIX_RUNNERS.get(issue_kind)
    _register(
        _FIX_RUNNERS,
        "fix runner",
        issue_kind,
        runner,
        known is not None and _name(known) == _name(runner),
    )


async def run_fix(tenant: TenantContext, issue_kind: str, issue_id: UUID) -> None:
    """A registered runner applies the fix; with none, the fix is unavailable (503)."""
    runner = _FIX_RUNNERS.get(issue_kind)
    if runner is None:
        raise ServiceUnavailable
    await runner(tenant, issue_id)
