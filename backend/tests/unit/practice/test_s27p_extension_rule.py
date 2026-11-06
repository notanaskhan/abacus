"""A state line's rule is the row naming its extension form (T-03 §4.2; DEC-2357)."""

from __future__ import annotations

from datetime import date

from abacus.modules.practice.compute.calendar import Offset, Rule, pick_extension_rule


def _rule(form: str, fye_rule: str, extension_form: str | None) -> Rule:
    return Rule(
        form=form,
        fye_rule=fye_rule,  # type: ignore[arg-type] -- a literal in the row's schema
        original=Offset(3, 15),
        extension_form=extension_form,
        extension_months=6 if extension_form else None,
    )


def test_the_row_naming_the_form_answers_and_an_unnamed_form_has_no_rule() -> None:
    rules = [_rule("1040", "any", "4868"), _rule("IT-201", "any", "IT-370")]
    picked = pick_extension_rule(rules, "IT-370", date(2027, 12, 31))
    assert picked is not None and picked.form == "IT-201"
    assert pick_extension_rule(rules, "IL-1065-V", date(2027, 12, 31)) is None


def test_a_fiscal_year_reads_the_fitting_row() -> None:
    rules = [_rule("IT-204", "calendar_year", "IT-370-PF"), _rule("IT-204", "any", None)]
    assert pick_extension_rule(rules, "IT-370-PF", date(2027, 6, 30)) is None
    assert pick_extension_rule(rules, "IT-370-PF", date(2027, 12, 31)) is not None
