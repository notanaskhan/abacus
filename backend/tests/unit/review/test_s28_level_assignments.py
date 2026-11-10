"""S28 (TASK-3399, DEC-2398): the firm's review_levels standard assigns each kind of reviewable its
required levels, by requirement key, and `reviewable_facts` applies them in one place, so AUD-17's
matrix, the G5 gate and the sign-off rules read the same levels."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from abacus.kernel.db import TenantContext
from abacus.modules.methodology.standards_contract import LevelAssignment, ReviewLevelsPayload
from abacus.modules.review import slots
from abacus.modules.review.slots import ReviewableFacts

TENANT = TenantContext(uuid4(), "system", "test")


def _facts(target_type: str, target_id: UUID, key: str | None) -> ReviewableFacts:
    return ReviewableFacts(
        target_type, target_id, uuid4(), "h", 1, frozenset(), requirement_key=key
    )


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch) -> dict[str, str | None]:
    """A registered owner whose facts carry the requirement key the test sets."""
    state: dict[str, str | None] = {"key": None}

    async def provider(_tenant: TenantContext, target_id: UUID) -> ReviewableFacts:
        return _facts("probe_kind", target_id, state["key"])

    monkeypatch.setitem(slots._FACTS, "probe_kind", provider)  # pyright: ignore[reportPrivateUsage] -- the registry under test
    return state


@pytest.fixture
def assigned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    async def port(_tenant: TenantContext, key: str) -> tuple[int, ...] | None:
        asked.append(key)
        return {"workpaper:ebp_contributions": (1, 2, 3, 4), "probe_kind": (1, 3)}.get(key)

    monkeypatch.setitem(slots._LEVELS, "port", port)  # pyright: ignore[reportPrivateUsage] -- the registry under test
    return asked


async def test_ac_a_kind_the_standard_names_gets_its_levels(
    owner: dict[str, str | None], assigned: list[str]
) -> None:
    owner["key"] = "workpaper:ebp_contributions"
    found = await slots.reviewable_facts(TENANT, "probe_kind", uuid4())
    assert found.required_levels == (1, 2, 3, 4)
    assert assigned == ["workpaper:ebp_contributions"]


async def test_ac_no_key_reads_as_the_target_type(
    owner: dict[str, str | None], assigned: list[str]
) -> None:
    found = await slots.reviewable_facts(TENANT, "probe_kind", uuid4())
    assert found.required_levels == (1, 3)
    assert assigned == ["probe_kind"]


async def test_ac_a_kind_the_standard_doesnt_name_keeps_the_owners_levels(
    owner: dict[str, str | None], assigned: list[str]
) -> None:
    owner["key"] = "workpaper:ebp_plan"
    found = await slots.reviewable_facts(TENANT, "probe_kind", uuid4())
    assert found.required_levels == slots.REQUIRED_LEVELS


def test_ac_a_payload_without_assignments_reads_as_before() -> None:
    tiers = [{"tier": 1, "name": "Standard", "required_levels": ["L1", "L2"],
              "second_partner_review": False}]  # fmt: skip
    parsed = ReviewLevelsPayload.model_validate({"kind": "review_levels", "tiers": tiers})
    assert parsed.assignments == []


@pytest.mark.parametrize("key", ["Trial Balance", "workpaper:", ":ebp", "a:b:c", ""])
def test_ac_a_key_is_a_snake_case_kind_with_an_optional_sub_kind(key: str) -> None:
    with pytest.raises(ValidationError):
        LevelAssignment.model_validate({"key": key, "required_levels": ["L1"]})
    assert LevelAssignment.model_validate(
        {"key": "workpaper:ebp_contributions", "required_levels": ["L1", "L4"]}
    ).required_levels == ["L1", "L4"]
