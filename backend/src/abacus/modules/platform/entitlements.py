"""Entitlements (F-03-T28; ADR-148, P-28): which modules a firm may use, read from
`tenant_entitlements` under the firm's row-level security. A module the firm doesn't hold, has
switched off or whose validity has lapsed answers 403 `entitlement_required` naming the module,
so the UI shows the entitlement reason (PLT-01b). Module rollout flags (`ff.*`) are not flags:
the flag registry refuses them."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Final, Literal, get_args

from fastapi import Depends
from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainForbidden
from abacus.modules.identity.api import AuthContext, current_context, is_synthetic_firm

Module = Literal[
    "attest",
    "internal_audit",
    "group_audit",
    "statements_studio",
    "office_addins",
    "insights",
    "tax_returns",  # T-03-T19: Tax Returns and K-1 packages (DEC-2372)
    "ebp_audits",  # A-05-T49: EBP-01 to EBP-09 (ADR P-28; DEC-2603)
    "assurance_completion",  # A-06-T37: AUD-15, AUD-16, AUD-17, AUD-20 (ADR P-28; DEC-2714)
    "tax_entity_returns",  # T-05-T04: TXP-00 to TXP-11, entity returns (ADR P-28; requires_review)
]
MODULES: Final = frozenset(get_args(Module))
# A-05-T49 (ADR P-28; chapter 10 §10.9.4): modules whose engines a CPA signs off. For a firm that
# isn't synthetic the module holds only while its owner's registered check says the review is
# signed; no registered check refuses (fail closed). Synthetic firms are the review's own test bed.
REVIEWED_MODULES: Final = frozenset({"ebp_audits", "tax_entity_returns"})
ReviewCheck = Callable[[], bool]
_reviews: dict[str, ReviewCheck] = {}


def register_module_review(module: Module, check: ReviewCheck) -> None:
    """The module's owner registers whether its CPA review is signed (A-05-T49)."""
    if module not in REVIEWED_MODULES:
        raise ValueError(f"{module!r} is not a reviewed module")
    _reviews[module] = check


_ENTITLEMENT = text(
    "SELECT enabled, seats, agent_minutes_allowance, valid_from, valid_to "
    "FROM tenant_entitlements WHERE module = :module"
)


class EntitlementRequired(DomainForbidden):
    """The firm's plan doesn't include the module (403; the facts name it)."""

    code = "entitlement_required"


@dataclass(frozen=True)
class Entitlement:
    module: str
    seats: int | None
    agent_minutes_allowance: int | None


async def entitlement(tenant: TenantContext, module: Module) -> Entitlement | None:
    """The firm's entitlement to `module` today (business date), or None."""
    if module not in MODULES:
        raise ValueError(f"unknown module {module!r}")
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ENTITLEMENT, {"module": module})).first()
    if row is None or not row.enabled:
        return None
    today: date = await clock.today(tenant)
    if row.valid_from > today or (row.valid_to is not None and row.valid_to < today):
        return None
    if module in REVIEWED_MODULES and not await is_synthetic_firm(tenant):
        check = _reviews.get(module)
        if check is None or not check():
            return None
    return Entitlement(module, row.seats, row.agent_minutes_allowance)


async def check_entitlement(tenant: TenantContext, module: Module) -> Entitlement:
    found = await entitlement(tenant, module)
    if found is None:
        raise EntitlementRequired(facts={"module": module})
    return found


def require_entitlement(module: Module) -> Callable[..., Awaitable[Entitlement]]:
    """A route dependency: `dependencies=[Depends(require_entitlement("attest"))]`."""
    if module not in MODULES:
        raise ValueError(f"unknown module {module!r}")

    async def guard(ctx: Annotated[AuthContext, Depends(current_context)]) -> Entitlement:
        return await check_entitlement(ctx.tenant, module)

    return guard
