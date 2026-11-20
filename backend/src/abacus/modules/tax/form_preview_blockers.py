"""The form-preview diagnostics blocker of final approval (T-06-T37; TASK-8828; T-06 F7; TAX-11;
SPEC-702 AC-33; ADR-005, ADR-050; DEC-5830). RED: a blocker provider for `tax/approval.py`, the
single owner of the L4 `final_approval` sign-off.

Final approval is refused while any of these block, each a code and the record it names (never
prose; `approval.BLOCKER_WORDS` holds the words TAX-11 shows on the disabled button):

- `engine_diagnostic_error`: an `error` diagnostic of the engine's newest diagnostics import for
  the return (T-01-T19; one blocker per diagnostic, naming it). A newer diagnostics import without
  errors clears them; warnings and informational messages never block.
- `item_l_schedule_l_off`: the partners' ending capital (Σ K-1 Item L, sheet 05 column F) is not
  Schedule L line 21, computed by code from sheet 03's form lines as total assets (L1 to L14) less
  total liabilities (L15 to L20), the line-21 identity of a balanced Schedule L (ADR-050). Until
  sheet 03 has a Schedule L line or sheet 05 a partner, the check has nothing to compare and stays
  silent (the entity guards already block on a missing trial balance).
- `section_754_statement_pending`: a §754 card (`basis_adjustment_election`) on the return still
  awaits its decision (open or sent to the client): the statement TAX-11 previews with the return
  is not settled.

When any of these is present the POST answers 409 `blocking_diagnostics` (`approval.approve`)
rather than the generic `final_approval_blocked`, and the eligibility read lists each with its
words. A provider that raises blocks (fail closed, `approval.eligibility`) under its own code,
`form_preview_diagnostics`, which also answers `blocking_diagnostics`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.tax.approval import Blocker

KIND: Final = "form_preview_diagnostics"
ENGINE_ERROR: Final = "engine_diagnostic_error"
ITEM_L_OFF: Final = "item_l_schedule_l_off"
STATEMENT_754: Final = "section_754_statement_pending"
#: The blocker codes that answer 409 `blocking_diagnostics` on the POST.
DIAGNOSTIC_CODES: Final = frozenset({KIND, ENGINE_ERROR, ITEM_L_OFF, STATEMENT_754})
ZERO: Final = Decimal(0)

_ERRORS: Final = text(
    "SELECT d.id FROM engine_diagnostics d WHERE d.return_id = :r AND d.severity = 'error' "
    "AND d.sync_event_id = (SELECT e.id FROM engine_sync_events e WHERE e.return_id = :r "
    "AND e.kind = 'diagnostics' ORDER BY e.at DESC, e.id DESC LIMIT 1) ORDER BY d.code, d.id"
)

Values = dict[str, dict[str, object]]


def _dec(values: Values, key: str) -> Decimal | None:
    cell = values.get(key)
    if cell is None or cell.get("v") in (None, ""):
        return None
    try:
        return Decimal(str(cell["v"]))
    except ArithmeticError:
        return None


def _column(values: Values, sheet: str, col: str) -> list[int]:
    out: list[int] = []
    n = 2
    while f"{sheet}!{col}{n}" in values:
        out.append(n)
        n += 1
    return out


def schedule_l_line_21(values: Values) -> Decimal | None:
    """Line 21 from sheet 03's form lines: assets less liabilities (None: no Schedule L line)."""
    from abacus.modules.tax.entity_tb import group_of

    assets = liabilities = ZERO
    seen = False
    for n in _column(values, "03", "A"):
        cell = values.get(f"03!A{n}")
        key = None if cell is None or cell.get("v") is None else str(cell["v"])
        group = group_of(key)
        if group not in ("assets", "liabilities") or not (key or "").startswith("L"):
            continue
        seen = True
        amount = _dec(values, f"03!C{n}") or ZERO
        if group == "assets":
            assets += amount
        else:
            liabilities -= amount  # credit balances carry a negative net
    return assets - liabilities if seen else None


def item_l_total(values: Values) -> Decimal | None:
    """Σ K-1 Item L: the partners' ending capital on sheet 05 (None: no partner row)."""
    partners = [n for n in _column(values, "05", "A") if values.get(f"05!A{n}", {}).get("v")]
    if not partners:
        return None
    return sum((_dec(values, f"05!F{n}") or ZERO for n in partners), ZERO)


def item_l_off(values: Values) -> Decimal | None:
    """Σ Item L less Schedule L line 21 (None: nothing to compare)."""
    total, line_21 = item_l_total(values), schedule_l_line_21(values)
    if total is None or line_21 is None:
        return None
    return total - line_21


async def form_preview_blockers(tenant: TenantContext, return_id: UUID) -> list[Blocker]:
    """The provider (module docstring), read as the caller's tenant."""
    from abacus.modules.review.api import awaiting_cards
    from abacus.modules.tax.entity_decisions import SECTION_754
    from abacus.modules.tax.entity_schedules import workbook_values

    async with tenant_session(tenant) as session:
        errors = [UUID(str(r.id)) for r in await session.execute(_ERRORS, {"r": return_id})]
    out = [Blocker(ENGINE_ERROR, e) for e in errors]
    off = item_l_off(await workbook_values(tenant, return_id))
    if off is not None and off != ZERO:
        out.append(Blocker(ITEM_L_OFF))
    for card in await awaiting_cards(tenant, return_id, [SECTION_754]):
        out.append(Blocker(STATEMENT_754, card.card_id))
    return out


def is_diagnostic(blockers: list[Blocker]) -> bool:
    return any(b.kind in DIAGNOSTIC_CODES for b in blockers)


def register() -> None:
    """At the tax api's import: the provider joins the final-approval blockers."""
    from abacus.modules.tax.approval import register_final_approval_blocker

    register_final_approval_blocker(KIND, form_preview_blockers)


__all__ = [
    "DIAGNOSTIC_CODES",
    "ENGINE_ERROR",
    "ITEM_L_OFF",
    "KIND",
    "STATEMENT_754",
    "form_preview_blockers",
    "is_diagnostic",
    "item_l_off",
    "item_l_total",
    "register",
    "schedule_l_line_21",
]
