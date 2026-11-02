"""P-04-T59 (TASK-3018; ADR-079; DEC-2065): review hardening.

Row acceptance: "backend/mutation-thresholds.yaml records the review floor, the p95 budgets hold
under the x25 load profile, and every review table registers its retention record type." Here:
the review scope and its floor are recorded, the x25 profile names its p95 budgets, every review
table maps to a retention record type evidence knows, and A-07's archive lock refuses a sign-off.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from abacus.modules.evidence.retention import RECORD_TYPES
from abacus.modules.review import slots
from abacus.modules.review.registry import RETENTION_RECORD_TYPES, TABLES
from abacus_tools.quality.mutation import SCOPES

BACKEND = Path(__file__).resolve().parents[3]


def test_ac_the_review_scope_and_its_floor_are_recorded() -> None:
    assert SCOPES["review"] == ("src/abacus/modules/review/*.py",)
    text = (BACKEND / "mutation-thresholds.yaml").read_text(encoding="utf-8")
    assert "\n  review: " in text


def test_ac_the_x25_profile_budgets_500_ms() -> None:
    profile = yaml.safe_load(
        (BACKEND / "src/abacus_tools/loadtest/scenarios/review_grammar.yaml").read_text("utf-8")
    )
    assert profile["users"] == 25
    assert {g["p95_ms"] for g in profile["groups"]} == {500}


def test_ac_every_review_table_has_a_retention_record_type() -> None:
    assert set(RETENTION_RECORD_TYPES) == set(TABLES)
    assert set(RETENTION_RECORD_TYPES.values()) <= RECORD_TYPES


async def test_ac_an_archive_locked_engagement_refuses_review_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def locked(_tenant: object, _engagement: uuid.UUID) -> bool:
        return True

    monkeypatch.setattr(slots, "_ARCHIVE_LOCK", [locked])
    with pytest.raises(slots.ArchiveLockedRefused):
        await slots.refuse_if_archived(object(), uuid.uuid4())  # pyright: ignore[reportArgumentType] -- a stand-in tenant
    monkeypatch.setattr(slots, "_ARCHIVE_LOCK", [])
    await slots.refuse_if_archived(object(), uuid.uuid4())  # pyright: ignore[reportArgumentType] -- nothing is locked before A-07
