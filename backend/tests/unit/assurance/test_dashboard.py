"""SPEC-317 (TASK-460): progress sources register once, report in name order, and the dashboard
is a team read."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import slots
from abacus.modules.engagements.api import ProgressFact
from abacus.modules.identity.authz.matrix import RULES


async def test_progress_sources_report_in_name_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slots, "_PROGRESS", {})

    async def b_source(_t: TenantContext, _e: UUID) -> list[ProgressFact]:
        return [ProgressFact("b", "k", "B", 1, 2, False)]

    async def a_source(_t: TenantContext, _e: UUID) -> list[ProgressFact]:
        return [ProgressFact("a", "k", "A", 0, None, True)]

    slots.register_progress_source("b", b_source)
    slots.register_progress_source("a", a_source)
    slots.register_progress_source("a", a_source)  # the same source again: a no-op
    facts = await slots.progress_of(TenantContext(uuid4(), "system", "test"), uuid4())
    assert [f.source for f in facts] == ["a", "b"]

    async def other(_t: TenantContext, _e: UUID) -> list[ProgressFact]:
        return []

    with pytest.raises(ValueError, match="already registered"):
        slots.register_progress_source("a", other)


def test_the_dashboard_is_the_teams_and_independence_bound() -> None:
    rule = RULES["dashboard.read"]
    assert rule.independence
    assert "agent" not in {r for r, d in rule.decisions.items() if d == "allow"}
    assert "client_admin" not in rule.decisions
