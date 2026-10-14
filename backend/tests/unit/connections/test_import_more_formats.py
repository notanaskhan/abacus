"""SPEC-028 AC-1 to AC-6 (TASK-068): QuickBooks Desktop, NetSuite and Sage Intacct trial balance
exports parse into the common model, their periods are read, and a file from another system is
refused by name."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.connections.import_formats import FORMATS
from abacus.modules.connections.import_parse import ParsedImport, parse_export
from abacus.modules.ledger.api import NormaliseError, validate
from abacus_tools.synthetic.ledger_exports import (
    intacct_trial_balance_csv,
    netsuite_trial_balance_csv,
    qbd_trial_balance_xlsx,
    qbo_trial_balance_csv,
    xero_trial_balance_xlsx,
)
from abacus_tools.synthetic.model import TrialBalance, TrialBalanceLine

START, END = date(2026, 1, 1), date(2026, 12, 31)
TB = TrialBalance(
    END,
    (
        TrialBalanceLine("1000", "Checking", Decimal("12345.67"), Decimal(0)),
        TrialBalanceLine("1200", "Accounts Receivable (A/R)", Decimal("5000.00"), Decimal(0)),
        TrialBalanceLine("2000", "Accounts Payable", Decimal(0), Decimal("3345.67")),
        TrialBalanceLine("4000", "Sales", Decimal(0), Decimal("14000.00")),
    ),
)
EXPECTED = [
    ("1000", "Checking", Decimal("12345.67"), Decimal(0)),
    ("1200", "Accounts Receivable (A/R)", Decimal("5000.00"), Decimal(0)),
    ("2000", "Accounts Payable", Decimal(0), Decimal("3345.67")),
    ("4000", "Sales", Decimal(0), Decimal("14000.00")),
]


def _lines(parsed: ParsedImport) -> list[tuple[str, str, Decimal, Decimal]]:
    return [
        (x.account_code, x.account_name, x.debit, x.credit) for x in parsed.trial_balance.lines
    ]


def _checked(parsed: ParsedImport) -> None:
    tb = parsed.trial_balance
    assert _lines(parsed) == EXPECTED
    assert (tb.declared_debit, tb.declared_credit) == (Decimal("17345.67"), Decimal("17345.67"))
    assert not parsed.totals_from_lines and tb.currency == "USD"
    assert tb.period_end == END
    assert validate(tb, period_start=START, period_end=END) is None


def test_ac5_quickbooks_desktop_xlsx_with_middle_dot_codes() -> None:
    _checked(parse_export(qbd_trial_balance_xlsx(TB), "qbd_tb_xlsx", START, END))


@pytest.mark.parametrize("by_month", [True, False])
@pytest.mark.parametrize("amount_headers", [True, False])
def test_ac5_netsuite_csv_by_month_or_date(by_month: bool, amount_headers: bool) -> None:
    content = netsuite_trial_balance_csv(TB, by_month=by_month, amount_headers=amount_headers)
    _checked(parse_export(content, "netsuite_tb_csv", START, END))


def test_ac5_netsuite_a_month_period_ends_on_its_last_day() -> None:
    november = netsuite_trial_balance_csv(TB, as_of=date(2026, 11, 30))
    parsed = parse_export(november, "netsuite_tb_csv", START, END)
    assert parsed.trial_balance.period_end == date(2026, 11, 30)  # the year-end check refuses it


def test_ac5_sage_intacct_csv_with_its_own_code_column() -> None:
    _checked(parse_export(intacct_trial_balance_csv(TB), "intacct_tb_csv", START, END))


EXPORTS = {
    "qbo_tb_csv": qbo_trial_balance_csv(TB),
    "xero_tb_xlsx": xero_trial_balance_xlsx(TB),
    "qbd_tb_xlsx": qbd_trial_balance_xlsx(TB),
    "netsuite_tb_csv": netsuite_trial_balance_csv(TB),
    "intacct_tb_csv": intacct_trial_balance_csv(TB),
}


@pytest.mark.parametrize("made", sorted(EXPORTS))
@pytest.mark.parametrize("chosen", sorted(EXPORTS))
def test_ac2_a_file_from_another_system_is_refused_by_name(made: str, chosen: str) -> None:
    if made == chosen:
        assert parse_export(EXPORTS[made], chosen, START, END).trial_balance.lines
        return
    with pytest.raises(NormaliseError) as refused:
        parse_export(EXPORTS[made], chosen, START, END)
    assert str(refused.value) == f"looks_like_{FORMATS[made].system_key}"


def test_ac6_each_new_system_has_numbered_steps_ending_in_the_upload() -> None:
    for format_id in ("qbd_tb_xlsx", "netsuite_tb_csv", "intacct_tb_csv"):
        steps = FORMATS[format_id].steps
        assert len(steps) == 4 and steps[-1].startswith("Upload the")
