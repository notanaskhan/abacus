"""A-08-T22 (TASK-8401; SPEC-657 F8): the SSARS workspace's fixed parts: the standard per mode,
the preparation legend, and the review threshold's defaults."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from abacus.modules.assurance import ssars


def test_standards_per_mode() -> None:
    assert ssars.STANDARD == {
        "review": "AR-C 90",
        "compilation": "AR-C 80",
        "preparation": "AR-C 70",
    }
    assert ssars.LEGEND == "No assurance is provided."
    assert ssars.READ_FS_TITLE == "Read the FS for obvious material misstatements"


@pytest.mark.asyncio
async def test_review_threshold_defaults_to_ten_percent_and_fifty_thousand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unset(*_: object) -> None:
        return None

    monkeypatch.setattr(ssars, "stored_value", unset)
    found, policy = await ssars.review_threshold(object(), uuid.uuid4())  # type: ignore[arg-type] -- unused tenant
    assert policy is None
    assert found.pct == Decimal("10") and found.amount == Decimal("50000")  # type: ignore[attr-defined] -- ThresholdFacts
    assert not found.provisional  # type: ignore[attr-defined] -- ThresholdFacts


def test_no_report_for_preparation_is_409() -> None:
    assert ssars.NoReportForPreparation.code == "no_report_for_preparation"
