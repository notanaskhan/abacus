"""T-02-T10 (TASK-2216; SPEC-502 AC-18, AC-19): the TPL-01 due-rule mapping, without a database.

Every tax form code maps to the form C21's rule rows name, and the Due popover's rule text reads
as TPL-01 writes it ("15th day, 3rd month + 6 months"; a 1041's 7004 "+ 5½ months")."""

from __future__ import annotations

from datetime import date
from typing import get_args

from abacus.modules.practice.compute.calendar import Offset, Rule, rule_text
from abacus.modules.tax.due_dates import FORM_FOR_RULES, period_end
from abacus.modules.tax.returns_contract import Form


def test_ac18_every_form_code_maps_to_a_rule_form() -> None:
    assert set(FORM_FOR_RULES) == set(get_args(Form))
    assert FORM_FOR_RULES["1120s"] == "1120-S" and FORM_FOR_RULES["1040x"] == "1040"


def test_ac18_the_rule_text_reads_as_tpl_01() -> None:
    f1065 = Rule("1065", "calendar_year", Offset(3, 15), "7004", 6)
    f1041 = Rule("1041", "calendar_year", Offset(4, 15), "7004", 5, 30)
    f5500 = Rule("5500", "any", Offset(7, 31), "5558", 3, 15)
    assert rule_text(f1065, extended=True) == "15th day, 3rd month + 6 months"
    assert rule_text(f1065, extended=False) == "15th day, 3rd month"
    assert rule_text(f1041, extended=True) == "15th day, 4th month + 5½ months"
    assert rule_text(f5500, extended=True) == "31st day, 7th month + 2½ months"


def test_ac18_the_period_end_is_the_fiscal_year_end_or_december_31() -> None:
    assert period_end(2025, None) == date(2025, 12, 31)
    assert period_end(2025, date(2026, 6, 30)) == date(2026, 6, 30)
