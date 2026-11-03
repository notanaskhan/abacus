"""T-03-T07 (TASK-3263; SPEC-643 AC-7; DEC-2243): extensions.

Row acceptance: "The seed lists foot (79 + 82 = 161; 2 + 1 + 2 = 5), Samuel's single click
approves three payments and sends three confirmation requests attributed to Samuel, and no route
transmits or stores a payment instrument." Here: the counts from visible rows and the absence of
any instrument field; the seeded figures run with the end-review integration suite.
"""

from __future__ import annotations

from uuid import uuid4

from abacus.modules.tax import schedules_contract as sc
from abacus.modules.tax.extensions import ReturnRow, counts


def _row(*statuses: str, likely: bool = False) -> ReturnRow:
    r = ReturnRow(uuid4(), uuid4(), uuid4(), "Feld", 2025)
    r.lines = [{"status": s, "likely_to_extend": likely} for s in statuses]
    return r


def test_counts_come_only_from_the_rows_given() -> None:
    rows = [_row("filed", "prepared"), _row("not_filed", likely=True), _row("accepted")]
    assert counts(rows) == {"extended": 2, "open": 2, "filed": 2, "likely": 1, "acks_pending": 1}
    assert counts([]) == {"extended": 0, "open": 0, "filed": 0, "likely": 0, "acks_pending": 0}


def test_no_extension_or_payment_shape_carries_an_instrument() -> None:
    banned = ("account", "routing", "card", "iban", "instrument", "bank")
    for model in (sc.ExtensionPaymentOut, sc.ProposedPaymentIn, sc.ApproveAndRequestIn):
        for name in model.model_fields:
            assert not any(word in name for word in banned), (model.__name__, name)
