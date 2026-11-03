"""A-06-T09 (TASK-3012; A-06 §4.3; SPEC-642; DEC-2061): the adjustments service, part 1.

Row acceptance: "An attest-client entry is always review_required, adjusted_tb(final) equals the
snapshot plus approved entries with debits equal to credits per layer, and nothing is ever stored
as a layer." The ledger computes the layers over the snapshot from the source this module
registers (its own suites hold the arithmetic); here: the balance rule, that the ledger reads this
module's entries, that only approved AJEs and RJEs are layered, and that no table stores a layer.
The attest rule is also 0643's `pe_attest_review_required` CHECK.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

import abacus.modules.adjustments.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the source
from abacus.modules.adjustments import entries
from abacus.modules.adjustments.entries import NewLine, UnbalancedEntry, balance
from abacus.modules.adjustments.registry import INSERT_COLUMNS, UPDATE_COLUMNS
from abacus.modules.ledger.trial_balances import (
    _ADJUSTMENT_SOURCES,  # pyright: ignore[reportPrivateUsage] -- the registry under test
)


def test_ac_aje_1_balances_at_48_600() -> None:
    lines = (
        NewLine("1250", D("48600"), D(0)),
        NewLine("4100", D(0), D("33540")),
        NewLine("4200", D(0), D("15060")),
    )
    assert balance(lines) == D("48600")


@pytest.mark.parametrize(
    "lines",
    [
        (NewLine("1250", D("100"), D(0)), NewLine("4100", D(0), D("99"))),
        (NewLine("1250", D("100"), D("100")), NewLine("4100", D(0), D(0))),
        (NewLine("1250", D("100"), D(0)),),
    ],
)
def test_ac_an_unbalanced_or_two_sided_entry_is_refused(lines: tuple[NewLine, ...]) -> None:
    with pytest.raises(UnbalancedEntry):
        balance(lines)


def test_ac_the_ledger_reads_this_modules_entries() -> None:
    assert entries.recorded_entries in _ADJUSTMENT_SOURCES


def test_ac_only_approved_ajes_and_rjes_are_layered() -> None:
    assert frozenset({"approved", "client_approved"}) == entries.RECORDED
    assert frozenset({"aje", "rje"}) == entries.LAYERED
    assert not entries.RECORDED & entries.PENDING


def test_ac_no_adjustments_table_stores_a_layer() -> None:
    columns = {c for cols in (*INSERT_COLUMNS.values(), *UPDATE_COLUMNS.values()) for c in cols}
    assert not columns & {"layer", "final", "adjusted", "aje_total", "rje_total"}
