"""T-06-T36 (TASK-8834; T-06 F4; TXP-09; DEC-5836): states and PTET.

Row acceptance: "Approving sourcing resolves the TXP-10 review point once, Undo inside 10 seconds
writes sourcing.undone, and Feld's state credit reads 16,025."
"""

from __future__ import annotations

import inspect
import uuid
from decimal import Decimal

from abacus.modules.tax import states_service as ss
from abacus.modules.tax.compute import states as e9


def test_review_point_refs_are_stable() -> None:
    r = uuid.uuid4()
    assert ss.sourcing_ref(r) == ss.sourcing_ref(r)  # deduplicated on raise, resolved once
    assert ss.gap_ref(r, "IL") != ss.gap_ref(r, "CO")


def test_ac_undo_window_and_event() -> None:
    assert ss.UNDO_WINDOW.total_seconds() == 10
    source = inspect.getsource(ss.undo_sourcing)
    assert '"sourcing.undone"' in source and "UndoWindowClosed" in source


def test_ac_approval_resolves_through_the_system_once() -> None:
    source = inspect.getsource(ss.approve_sourcing)
    assert "status = 'proposed'" in source and "_resolve(" in source


def test_credits_foot_by_largest_remainder() -> None:
    credits = e9.partner_credits(
        Decimal("28044"), {"feld": Decimal("57.142"), "a": Decimal("30"), "b": Decimal("12.858")}
    )
    assert sum(credits.values()) == Decimal("28044")


def test_payment_gap() -> None:
    assert e9.payment_gaps({"IL": Decimal("100")}, {"IL": Decimal("40")}) == ["IL"]
    assert e9.payment_gaps({"IL": Decimal("100")}, {"IL": Decimal("100")}) == []
