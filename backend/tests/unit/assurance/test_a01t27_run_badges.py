"""A-01-T27 (TASK-1622; DV-11; DEC-717): the C6 v1 run-summary provider behind AUD-01's
"Processing" pill and AUD-02's audit-bar run time.

"Fixture d and the live read share one shape, live data shows no Processing for v1 policy ticks"
(A-01-T27 acceptance): no engagement-run agent registered (policy ticks and specialists are not
engagement runs) means no badge; an active engagement run maps to its work items with the
starter's name, in `RunSummary`'s shape (the one `AuditRunBadgeOut` and fixture d carry).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import engagement_runs
from abacus.modules.agents.engagement_runs import ActiveRun
from abacus.modules.assurance import run_badges
from abacus.modules.assurance.audits_contract import AuditRunBadgeOut
from abacus.modules.assurance.sections import RunSummary

TENANT = TenantContext(uuid.uuid4(), "system", "a01t27")


async def test_ac_no_engagement_run_agent_means_no_processing_pill() -> None:
    assert engagement_runs.engagement_run_agents() == frozenset()
    assert await engagement_runs.active_engagement_runs(TENANT, [uuid.uuid4()]) == {}


async def test_an_active_engagement_run_maps_to_its_work_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_item, engagement, starter = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    run = ActiveRun(
        uuid.uuid4(),
        engagement,
        4127,
        datetime(2026, 9, 14, 14, 24, tzinfo=UTC),
        starter,
        3,
        6,
        "partner",
    )

    async def engagement_of(_tenant: object, _work_item: uuid.UUID) -> uuid.UUID:
        return engagement

    async def runs(_tenant: object, _ids: object) -> dict[uuid.UUID, ActiveRun]:
        return {engagement: run}

    async def names(_ids: object) -> dict[uuid.UUID, str]:
        return {starter: "Margaret Okonkwo"}

    monkeypatch.setattr(run_badges, "work_item_engagement", engagement_of)
    monkeypatch.setattr(run_badges, "active_engagement_runs", runs)
    monkeypatch.setattr(run_badges, "names_of", names)
    found = await run_badges.run_badges(TENANT, [work_item])
    summary = found[work_item]
    assert isinstance(summary, RunSummary)
    assert (summary.run_number, summary.started_by_name, summary.blocked_on_role) == (
        4127,
        "Margaret Okonkwo",
        "partner",
    )
    badge = AuditRunBadgeOut(**summary.__dict__)
    assert set(AuditRunBadgeOut.model_fields) == set(summary.__dict__)
    assert badge.workpapers_total == 6
