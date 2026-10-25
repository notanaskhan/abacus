"""R-01-T07 (DEC-333): the portal read model's pure rules: category codes, the binder's year, the
client words, receipt kinds, return reasons and the filters."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from abacus.modules.evidence.api import PortalFile, SentBack
from abacus.modules.portal.documents import (
    client_status,
    code_of,
    keep,
    receipt_kind,
    return_reason,
    row_kind,
    year_of,
)
from abacus.modules.requests.api import PortalItem

ME = uuid.uuid4()
AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


BASE = PortalItem(
    id=uuid.uuid4(),
    engagement_id=uuid.uuid4(),
    binder_id=uuid.uuid4(),
    category_id=None,
    title="Form 1095-C From Mercer Hill Health",
    group="Health insurance",
    kind="client_upload",
    status="requested",
    client_visible=True,
    client_assignee_user_id=None,
    due_on=date(2026, 9, 18),
    requested_at=AT,
    client_ignored_at=None,
    ignored_by=None,
    guidance=None,
    links=(),
    uploading=0,
    comment_count=0,
)


def _item(**changes: object) -> PortalItem:
    return replace(BASE, **changes)


def _file(arrived: str, *, by: uuid.UUID | None = ME, accepted: bool = False) -> PortalFile:
    return PortalFile(
        version_id=uuid.uuid4(),
        name="Feld_2025_Donations.pdf",
        size_bytes=2048,
        arrived=arrived,
        uploader_user_id=by,
        created_at=AT,
        withdrawable_kind=True,
        accepted=accepted,
        sent_back=None,
    )


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("Health & Medical", "health_medical"),
        ("Personal & Household Information", "personal_household_information"),
        ("Charitable & Donations", "charitable_donations"),
        ("Census & Payroll", "census_payroll"),
        ("Café — Ünïcode", "cafe_unicode"),
        ("&&&", "uncategorised"),
    ],
)
def test_a_category_code_is_its_label_folded(name: str, code: str) -> None:
    assert code_of(name) == code


def test_the_year_comes_from_the_binder_name() -> None:
    assert year_of("2025 Binder") == 2025
    assert year_of("PY2025 Audit requests") is None  # not a bare year
    assert year_of("Intake") is None


@pytest.mark.parametrize(
    ("changes", "word"),
    [
        ({}, "to_do"),
        ({"status": "returned"}, "returned"),
        ({"status": "uploaded"}, "done"),
        ({"status": "received"}, "done"),
        ({"status": "not_applicable"}, "ignored"),
        ({"client_ignored_at": AT}, "ignored"),
        ({"kind": "firm_provided"}, "done"),
    ],
)
def test_the_client_words_never_carry_a_firm_code(changes: dict[str, object], word: str) -> None:
    assert client_status(_item(**changes)) == word


def test_receipts_have_one_kind_per_arrival() -> None:
    other = uuid.uuid4()
    assert receipt_kind(_file("client_upload"), "human", ME) == "uploaded"
    assert receipt_kind(_file("client_upload", by=other), "human", ME) == (
        "uploaded_by_other_contact"
    )
    assert receipt_kind(_file("email"), "human", ME) == "emailed"
    assert receipt_kind(_file("firm"), "human", ME) == "received"
    assert receipt_kind(_file("client_upload"), "rule", ME) == "rule_linked_pending"
    # once a person accepts the rule link, the Suggested line goes (Story 2.2)
    assert receipt_kind(_file("client_upload", accepted=True), "rule", ME) == "uploaded"


def test_a_wrong_period_reads_wrong_year_on_a_household_binder() -> None:
    assert return_reason("wrong_period", "organizer") == "wrong_year"
    assert return_reason("wrong_period", "pbc") == "wrong_period"
    assert return_reason("illegible", "organizer") == "other"
    assert return_reason(None, "pbc") == "other"


def test_a_connected_or_firm_provided_row_has_its_own_kind() -> None:
    assert row_kind(_item(kind="firm_provided"), []) == "firm_provided"
    assert row_kind(_item(), [_file("connection")]) == "provided_by_connection"
    assert row_kind(_item(), [_file("client_upload")]) == "request"


def test_the_filters() -> None:
    today = date(2026, 9, 20)
    waived = _item(status="not_applicable")
    late = _item(due_on=date(2026, 9, 18))
    assert not keep(waived, "ignored", False, today, "requested")
    assert keep(waived, "ignored", False, today, "all")
    assert keep(late, "to_do", False, today, "needs_follow_up")
    assert not keep(late, "to_do", False, date(2026, 9, 1), "needs_follow_up")
    assert keep(_item(status="returned"), "returned", False, today, "needs_follow_up")
    assert keep(late, "to_do", True, today, "uploaded_by_me")
    assert not keep(late, "to_do", False, today, "uploaded_by_me")


def test_a_send_back_carries_only_codes_and_the_firms_note() -> None:
    back = SentBack("wrong_period", "This is the 2024 form.", ME, AT)
    assert (back.reason_code, back.note) == ("wrong_period", "This is the 2024 form.")
