"""N-04-T07 (TASK-3218; DEC-2218): the intake's rules.

Row acceptance: "The Santos CP14 fixture yields eight matched fields, a 0.71 respond-by blocks
Create notice with 409 until confirmed, and the notice is created as New by Grace Holloway."
Pinned here: a low-confidence value blocks until a person confirms it, and a TIN never travels
whole on the sheet.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.notices.contract import (
    _intake_out,  # pyright: ignore[reportPrivateUsage] -- the private helper under test
)
from abacus.modules.notices.intake import FieldValue, Intake


def _value(
    key: str, conf: str | None, *, confirmed: bool = False, low: bool = False
) -> FieldValue:
    return FieldValue(
        key=key,
        value_text="2026-09-21" if key == "notice.respond_by" else "x",
        last4="2208" if key == "taxpayer.tin" else None,
        confidence=None if conf is None else Decimal(conf),
        low_confidence=low,
        origin="code_map",
        confirmed=confirmed,
        citation_id=None,
    )


def _santos(*, confirmed: bool) -> Intake:
    keys = (
        "notice.code",
        "notice.tax_year",
        "notice.form",
        "notice.date",
        "notice.amount_total",
        "taxpayer.name",
        "taxpayer.tin",
        "agency.name",
    )
    fields = (
        *(_value(k, "0.98") for k in keys),
        _value("notice.respond_by", "0.71", confirmed=confirmed, low=True),
    )
    return Intake(
        id=uuid.uuid4(),
        status="ready",
        source="upload",
        evidence_version_id=uuid.uuid4(),
        extraction_mode="code_map",
        client_id=None,
        match={},
        authorization={},
        duplicate_of=None,
        assignee_user_id=None,
        notify_user_ids=(),
        created_work_item_id=None,
        row_version=1,
        fields=fields,
    )


def test_ac_a_low_confidence_respond_by_blocks_until_confirmed() -> None:
    assert _santos(confirmed=False).unconfirmed == ["notice.respond_by"]
    assert _santos(confirmed=True).unconfirmed == []


def test_ac_eight_matched_fields_and_no_whole_tin_on_the_sheet() -> None:
    out = _intake_out(_santos(confirmed=False))
    assert sum(1 for f in out.fields if not f.low_confidence) == 8
    tin = next(f for f in out.fields if f.key == "taxpayer.tin")
    assert tin.value_text is None
