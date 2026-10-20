"""SPEC-044 AC-4 (TASK-109): a person adopts the agent's proposals as results; unclear rows and
rows with a result are left alone; the agent may not adopt."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import adopt as subject
from abacus.modules.fieldwork.session import PLANS
from abacus.modules.identity.authz.matrix import RULES

E, P = uuid.uuid4(), uuid.uuid4()
I1, I2, I3, I4 = (uuid.uuid4() for _ in range(4))


class _Session:
    async def __aenter__(self) -> object:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:  # fakes stand in for typed contexts and calls
    calls: list[dict[str, Any]] = []  # fakes stand in for typed contexts and calls

    async def get_ref(*_: object) -> object:
        return SimpleNamespace(resource=lambda: None)

    async def authorise(*_: object) -> None:
        return None

    async def selection_item_ids(*_: object) -> list[uuid.UUID]:
        return [I1, I2, I3, I4]

    async def items_with_results(*_: object) -> set[uuid.UUID]:
        return {I4}

    async def newest_assessments(*_: object) -> list[object]:
        return [
            SimpleNamespace(
                id=uuid.uuid4(), selected_item_id=I1, shown_verdict="explained", rationale="ok"
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                selected_item_id=I2,
                shown_verdict="not_explained",
                rationale="Amount differs",
            ),
            SimpleNamespace(
                id=uuid.uuid4(), selected_item_id=I3, shown_verdict="unclear", rationale="?"
            ),
            SimpleNamespace(
                id=uuid.uuid4(), selected_item_id=I4, shown_verdict="explained", rationale="ok"
            ),
        ]

    async def record_result(*args: object, **kwargs: object) -> None:
        calls.append({"item": args[3], **kwargs})

    monkeypatch.setattr(subject, "get_ref", get_ref)
    monkeypatch.setattr(subject, "authorise", authorise)
    monkeypatch.setattr(subject, "selection_item_ids", selection_item_ids)
    monkeypatch.setattr(subject, "items_with_results", items_with_results)
    monkeypatch.setattr(subject, "newest_assessments", newest_assessments)
    monkeypatch.setattr(subject, "record_result", record_result)

    def session(*_: object) -> _Session:
        return _Session()

    monkeypatch.setattr(subject, "tenant_session", session)
    return calls


async def test_ac4_explained_is_supported_not_explained_an_exception_unclear_left(
    recorded: list[dict[str, Any]],  # fakes stand in for typed contexts and calls
) -> None:
    tenant = TenantContext(uuid.uuid4(), "human", "u")
    ctx: Any = SimpleNamespace(tenant=tenant)  # a fake stands in for the person's context
    assert await subject.adopt(ctx, E, P, None) == 2
    by_item = {c["item"]: c for c in recorded}
    assert by_item[I1]["result"] == "supported" and by_item[I1]["note"] is None
    assert by_item[I2]["result"] == "exception"
    assert by_item[I2]["note"].startswith("The agent found the support doesn't explain the entry")
    assert I3 not in by_item and I4 not in by_item  # unclear; already has a result
    assert all(c["adopted_assessment_id"] is not None for c in recorded)


def test_ac4_people_adopt_never_the_agent() -> None:
    assert RULES["entry_assessment.adopt"].decisions.get("agent") == "deny"
    assert RULES["entry_assessment.adopt"].decisions.get("staff") == "allow"


def test_ac1_each_definition_has_a_plan_ending_with_the_workpaper() -> None:
    for definition in ("journal_entry_testing", "unrecorded_liabilities"):
        keys = [k for k, _ in PLANS[definition]]
        assert keys[:2] == ["population", "select"] and keys[-1] == "workpaper"
