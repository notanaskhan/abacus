"""SPEC-319 AC-21, AC-22 (P-06-T20; DEC-48, DEC-324): the screening aggregate's rule, by code.

Verdicts: any flag → flagged, both checks pass → passed, otherwise not screened. The period check
reads code's facts only: no model input changes it. A flag on a file names the file; a model
flag's region is its first verified citation."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.agents.screening_aggregate import (
    CheckOutcome,
    VersionInput,
    combine,
    compose,
    overall,
    period_verdict,
)

JUNE_1 = date(2026, 6, 1)
SEP_18 = date(2026, 9, 18)

dates = st.one_of(st.none(), st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)))
outcomes = st.one_of(st.none(), st.sampled_from(["passed", "problem", "not_applicable"]))
citations = st.one_of(st.none(), st.lists(st.uuids(), max_size=3).map(tuple))


@st.composite
def files(draw: st.DrawFn) -> VersionInput:
    return VersionInput(
        draw(st.uuids()),
        draw(dates),
        draw(dates),
        draw(dates),
        draw(outcomes),
        reviewed=draw(st.booleans()),
        wrong_document=draw(citations),
    )


def test_ac22_an_empty_batch_is_not_screened() -> None:
    found = compose(JUNE_1, SEP_18, [])
    assert found.verdict == "not_screened"
    assert [c.verdict for c in found.checks] == ["not_run", "not_run"]
    assert found.file_flags == ()


def test_ac22_29_of_31_files_answer_and_2_do_not() -> None:
    region = uuid.uuid4()
    good = [VersionInput(uuid.uuid4(), as_of=date(2026, 8, 1), reviewed=True) for _ in range(29)]
    bad = [
        VersionInput(
            uuid.uuid4(), as_of=date(2026, 8, 31), reviewed=True, wrong_document=(region,)
        ),
        VersionInput(uuid.uuid4(), as_of=date(2026, 8, 5), reviewed=True, wrong_document=()),
    ]
    found = compose(JUNE_1, SEP_18, [*good, *bad])
    assert found.verdict == "flagged"
    document, period = found.checks
    assert (document.key, document.verdict, document.source) == ("right_document", "flag", "model")
    assert document.citation_ids == (region,)
    assert (period.key, period.verdict, period.source) == ("right_period", "pass", "code")
    assert [(f.evidence_version_id, f.reason_code, f.region_ref) for f in found.file_flags] == [
        (bad[0].evidence_version_id, "wrong_document", str(region)),
        (bad[1].evidence_version_id, "wrong_document", None),
    ]


def test_ac22_40_of_40_reviewed_inside_the_period_passes() -> None:
    files_ = [
        VersionInput(uuid.uuid4(), date(2026, 7, 1), date(2026, 7, 31), reviewed=True)
        for _ in range(40)
    ]
    found = compose(JUNE_1, SEP_18, files_)
    assert found.verdict == "passed"
    assert found.file_flags == ()


def test_ac22_a_document_wholly_outside_the_request_period_is_wrong_year() -> None:
    last_year = VersionInput(uuid.uuid4(), date(2025, 7, 1), date(2025, 7, 31), reviewed=True)
    straddles = VersionInput(uuid.uuid4(), date(2026, 5, 15), date(2026, 6, 14), reviewed=True)
    assert period_verdict(JUNE_1, SEP_18, last_year) == "flag"
    assert period_verdict(JUNE_1, SEP_18, straddles) == "pass"
    found = compose(JUNE_1, SEP_18, [last_year, straddles])
    assert found.verdict == "flagged"
    assert [(f.evidence_version_id, f.reason_code) for f in found.file_flags] == [
        (last_year.evidence_version_id, "wrong_year")
    ]


def test_ac22_without_a_request_period_the_upload_check_decides() -> None:
    def one(outcome: str | None) -> VersionInput:
        return VersionInput(uuid.uuid4(), period_check=outcome, reviewed=True)

    assert period_verdict(None, None, one("problem")) == "flag"
    assert period_verdict(None, None, one("passed")) == "pass"
    assert period_verdict(None, None, one("not_applicable")) == "not_run"
    assert period_verdict(None, None, one(None)) == "not_run"


def test_ac22_a_file_without_dates_is_not_run_against_a_request_period() -> None:
    assert period_verdict(JUNE_1, SEP_18, VersionInput(uuid.uuid4(), reviewed=True)) == "not_run"


def test_ac22_an_unreviewed_file_leaves_the_batch_not_screened() -> None:
    files_ = [
        VersionInput(uuid.uuid4(), as_of=date(2026, 7, 1), reviewed=True),
        VersionInput(uuid.uuid4(), as_of=date(2026, 7, 2), reviewed=False),
    ]
    found = compose(JUNE_1, SEP_18, files_)
    assert [c.verdict for c in found.checks] == ["not_run", "pass"]
    assert found.verdict == "not_screened"


@given(st.lists(files(), max_size=8), dates, dates)
def test_ac22_the_verdict_follows_the_rule(
    batch: list[VersionInput], start: date | None, end: date | None
) -> None:
    found = compose(start, end, batch)
    verdicts = [c.verdict for c in found.checks]
    if "flag" in verdicts:
        assert found.verdict == "flagged"
    elif verdicts == ["pass", "pass"]:
        assert found.verdict == "passed"
    else:
        assert found.verdict == "not_screened"
    assert found.evidence_version_ids == tuple(v.evidence_version_id for v in batch)
    flagged = {f.evidence_version_id for f in found.file_flags}
    assert flagged <= set(found.evidence_version_ids)
    assert (found.verdict == "flagged") == bool(flagged)


@given(st.lists(files(), min_size=1, max_size=8), dates, dates, st.data())
def test_ac22_the_period_check_never_reads_the_model(
    batch: list[VersionInput], start: date | None, end: date | None, data: st.DataObject
) -> None:
    """Whatever the reviews say (reviewed, flags, citations), the period check is the same."""
    rewritten = [
        VersionInput(
            v.evidence_version_id,
            v.period_start,
            v.period_end,
            v.as_of,
            v.period_check,
            reviewed=data.draw(st.booleans()),
            wrong_document=data.draw(citations),
        )
        for v in batch
    ]
    before = compose(start, end, batch)
    after = compose(start, end, rewritten)
    assert before.checks[1] == after.checks[1]
    assert [f for f in before.file_flags if f.reason_code == "wrong_year"] == [
        f for f in after.file_flags if f.reason_code == "wrong_year"
    ]


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ([], "not_run"),
        (["pass"], "pass"),
        (["pass", "not_run"], "not_run"),
        (["not_run", "flag"], "flag"),
    ],
)
def test_ac22_a_check_combines_its_files(verdicts: list[str], expected: str) -> None:
    assert combine(verdicts) == expected  # pyright: ignore[reportArgumentType] -- the codes


def test_ac22_overall_is_passed_only_when_both_checks_pass() -> None:
    assert overall([CheckOutcome("a", "pass", "model"), CheckOutcome("b", "pass", "code")]) == (
        "passed"
    )
    assert overall([CheckOutcome("a", "pass", "model"), CheckOutcome("b", "not_run", "code")]) == (
        "not_screened"
    )
    assert overall([]) == "not_screened"
