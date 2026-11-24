"""Q-05-T24 (TASK-8934; DEC-5936; AUD-30 a, b, d): the case read carries its opener, release and
rationale; a decision on a case with a source logs a pending archive addition (AUD-30 b "Addition
logged") in the decision's transaction, linked to the case; an omitted procedure (AU-C 585) is
decided among its two code options without a comparison; AUD-23 g reads a reissue's dual date."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from abacus.modules.assurance import post_issuance as pi
from abacus.modules.assurance.archive_additions import PreparedAddition
from abacus.modules.assurance.post_issuance_contract import (
    PostIssuanceCaseOut,
    PostIssuanceDecisionIn,
)
from abacus.modules.assurance.release_contract import ArchiveAdditionOut, ReportVersionOut
from abacus.modules.assurance.report_builder import ReportState


def _case(**over: object) -> pi.Case:
    base: dict[str, object] = {
        "case_id": uuid4(),
        "work_item_id": uuid4(),
        "ref": "PI-01",
        "type": "subsequent_fact",
        "standard": "au_c_560",
        "source_kind": "inbox_evidence",
        "source_evidence_version_id": uuid4(),
        "received_at": datetime(2027, 1, 19, 15, 24, tzinfo=UTC),
        "description": (
            "Harborline issued a corrected 2025 certification for the Stable Value Fund"
        ),
        "status": "awaiting_decision",
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "comparison": (),
        "evaluation": None,
        "options": (),
        "recommended": None,
    }
    base.update(over)
    return pi.Case(**base)  # type: ignore[arg-type]


def test_addition_description_takes_the_persons_words_else_the_cases() -> None:
    found = _case()
    assert (
        pi.addition_description(found, "Corrected certification and evaluation (PI-01)")
        == "Corrected certification and evaluation (PI-01)"
    )
    assert pi.addition_description(found, "  ") == (
        "Harborline issued a corrected 2025 certification for the Stable Value Fund (PI-01)"
    )
    assert len(pi.addition_description(found, "x" * 5000)) == 2000


def test_decision_reasons_follow_the_standard() -> None:
    assert pi._REASON["subsequent_fact"] == "au_c_560_subsequently_discovered_fact"
    assert pi._REASON["omitted_procedure"] == "au_c_585_omitted_procedure"
    assert "reissuance_request" not in pi._REASON  # "other"


def test_omitted_procedure_offers_two_options_and_no_recommendation() -> None:
    assert pi.OMITTED_OPTIONS == ("no_action", "revise_and_reissue")
    assert "notify_users" not in pi.OMITTED_OPTIONS


def test_case_fields_are_additive_with_defaults() -> None:
    found = _case()
    assert found.created_by is None and found.rationale is None
    out = PostIssuanceCaseOut.model_fields
    for name in (
        "source_name",
        "raised_by_name",
        "opened_at",
        "report_released_at",
        "decided_by_name",
        "rationale",
    ):
        assert out[name].default is None
    assert PostIssuanceDecisionIn.model_fields["addition_description"].default is None


def test_addition_links_the_case() -> None:
    assert PreparedAddition.__dataclass_fields__["post_issuance_event_id"].default is None
    assert ArchiveAdditionOut.model_fields["post_issuance_case_id"].default is None


def test_report_state_carries_the_reissue_dates() -> None:
    st = ReportState(None, "audit", "draft", 2, "a" * 64, {}, (), None, 1)
    assert st.dual_date is None and st.reissue_of_release_id is None
    rel = uuid4()
    st2 = ReportState(
        None, "audit", "draft", 2, "a" * 64, {}, (), None, 1, None, (),
        date(2026, 10, 9), date(2027, 1, 25), rel,
    )  # fmt: skip
    assert st2.dual_date == date(2027, 1, 25) and st2.reissue_of_release_id == rel
    assert ReportVersionOut.model_fields["dual_date"].default is None
