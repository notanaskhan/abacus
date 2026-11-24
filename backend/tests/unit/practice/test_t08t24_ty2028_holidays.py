"""T-08-T24 (TASK-8917; SPEC-710 AC-19; T-08 AC2.12; K-02 QK-5; T-03 R19; DEC-5919; amber): the
TY2028 reference sets' holidays, with the pilot states.

Row acceptance: "The TY2028 sets are published in production with both founders' handles and no
deploy, and a TY2028 Form 1040 resolves to Tue Apr 17, 2029." Publishing is the operators'
two-person step (the review memo `docs/quality/golden-reviews/ty2028-reference-sets@1.md`); here
the 2029 holiday draft the rollover writes (federal, DC and the pilot states) validates as a
`legal_holidays` payload, and the engine resolves a calendar-year TY2028 Form 1040 to Tue Apr 17,
2029 on it, while an Illinois return due the same day rolls only to Mon Apr 16: a state's
holiday rolls only that state's dates, and DC Emancipation Day only federal ones.
"""

from __future__ import annotations

from datetime import date

from abacus.modules.platform.reference_sets_contract import LegalHolidaysPayload
from abacus.modules.practice.compute import calendar
from abacus.modules.practice.due_dates import counted
from abacus_tools import refdata_rollover as rollover


def _payload(year: int) -> LegalHolidaysPayload:
    rows = rollover.holidays(year) + rollover.state_holidays(year)
    return LegalHolidaysPayload.model_validate({"kind": "legal_holidays", "rows": rows})


def _days(payload: LegalHolidaysPayload, jurisdiction: str) -> frozenset[date]:
    return frozenset(r.date for r in payload.rows if counted(r.jurisdiction, jurisdiction))


RULE_1040 = calendar.Rule(
    form="1040", fye_rule="calendar_year", original=calendar.Offset(4, 15),
    extension_form="4868", extension_months=6,
)  # fmt: skip


def test_a_ty2028_form_1040_resolves_to_tue_apr_17_2029() -> None:
    holidays = _days(_payload(2029), "US")
    found = calendar.due_dates(RULE_1040, date(2028, 12, 31), holidays)
    assert found.original_due_on == date(2029, 4, 17)  # Sun Apr 15; Mon Apr 16 DC


def test_a_state_date_rolls_on_its_own_holidays_only() -> None:
    payload = _payload(2029)
    illinois = calendar.due_dates(RULE_1040, date(2028, 12, 31), _days(payload, "IL"))
    assert illinois.original_due_on == date(2029, 4, 16)  # DC's holiday is not Illinois's
    assert date(2029, 3, 5) in _days(payload, "IL")  # Casimir Pulaski Day
    assert date(2029, 3, 5) not in _days(payload, "US")
    assert date(2029, 3, 5) not in _days(payload, "NY")
    assert date(2029, 11, 6) in _days(payload, "NY") and date(2029, 11, 6) not in _days(
        payload, "IL"
    )


def test_the_pilot_state_rows_by_statute() -> None:
    rows = {(r["date"], r["jurisdiction"]): r["name"] for r in rollover.state_holidays(2028)}
    assert rows[("2028-02-11", "IL")] == "Lincoln's Birthday (observed)"  # Sat Feb 12
    assert rows[("2028-03-06", "IL")] == "Casimir Pulaski Day"
    assert rows[("2028-11-07", "IL")] == "General Election Day"  # an even year
    assert ("2029-11-06", "IL") not in {
        (r["date"], r["jurisdiction"]) for r in rollover.state_holidays(2029)
    }
    assert rows[("2028-03-31", "CO")] == "Cesar Chavez Day"
    assert rows[("2028-10-02", "CO")] == "Frances Xavier Cabrini Day"
    assert rows[("2028-11-07", "NY")] == "Election Day"
    assert rollover.state_holidays(2029, ()) == []


def test_federal_counts_us_and_dc_and_a_state_counts_us_and_its_own() -> None:
    assert counted("US", "US") and counted("DC", "US") and not counted("IL", "US")
    assert counted("US", "IL") and counted("IL", "IL") and not counted("DC", "IL")
    assert not counted("NY", "IL")
