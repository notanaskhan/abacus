"""C-01-T20 rest (TASK-8445; DEC-5432; SPEC-655 AC-31) against Postgres: the close run raises
its exceptions.

AC-31: "each open item traces to the procedure that raised it". Prepaid Insurance reads GL
3,500.00 against a schedule of 2,800.00 with no entry pending (C-01-T21's fixture), so the run's
amortization step raises one medium `schedule` exception on the close: its creator is the run's
agent, its note names the step, and a rerun raises nothing new. An engagement run without its
provider's `issue.create` is refused.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.agents.api import RunStepFacts
from abacus.modules.agents.engagement_run import AGENT_ID, TASK_SCOPE, run_scope
from abacus.modules.closes import accounts
from abacus.modules.closes import service as closes_service
from abacus.modules.closes.contract_work import ArrangementIn
from abacus.modules.closes.issues import close_issues
from abacus.modules.closes.run_plan import PROVIDER
from abacus.modules.closes.run_steps import amortize_prepaid, clear_third_party_sales
from abacus.modules.identity.api import AgentContext, Forbidden
from abacus.modules.identity.context import agent_context_for_run

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)
from .test_c01t21_accounts_schedules import (
    _month,  # pyright: ignore[reportPrivateUsage] -- the same fixture
    _tb,  # pyright: ignore[reportPrivateUsage] -- the same fixture
)

pytestmark = pytest.mark.asyncio
D = Decimal


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _run_agent(firm: _Firm, engagement: uuid.UUID, scope: list[str]) -> AgentContext:
    run_id = uuid.uuid4()
    await firm.seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope) VALUES ($1, $2, $3, 1, $4, $5, $6)",
        run_id,
        firm.tenant,
        AGENT_ID,
        engagement,
        firm.partner,
        scope,
    )
    return await agent_context_for_run(
        tenant_id=firm.tenant,
        run_id=run_id,
        agent_id=AGENT_ID,
        engagement_id=engagement,
        task_scope=frozenset(scope),
        initiator_user_id=firm.partner,
    )


async def _august_off(firm: _Firm) -> tuple[uuid.UUID, uuid.UUID]:
    engagement, _, entity = await firm.engagement("Brightwater Hale Cafe")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await _month(firm, entity, _tb("3500.00", "4900.00"), [])
    await accounts.create_arrangement(
        firm.ctx(),
        august,
        "41",
        ArrangementIn(
            kind="prepaid",
            description="General liability policy",
            expense_account_ref="66",
            scheduled_total=D("8400.00"),
            start_on=date(2026, 1, 1),
            finish_on=date(2026, 12, 31),
        ),
    )
    return engagement, august


def _facts(run: AgentContext, engagement: uuid.UUID, close: uuid.UUID) -> RunStepFacts:
    return RunStepFacts(
        run_id=run.agent_run_id,
        engagement_id=engagement,
        step_key="close_amortize_prepaid:41",
        level=1,
        arguments={"close_id": str(close), "account": "41"},
    )


def test_only_the_close_runs_gain_issue_create() -> None:
    assert "issue.create" not in TASK_SCOPE  # audit engagement runs keep their scope
    assert run_scope(None) == list(TASK_SCOPE)
    assert run_scope(PROVIDER) == [*TASK_SCOPE, "issue.create"]


async def test_ac31_the_run_raises_the_schedule_exception_once(firm: _Firm) -> None:
    engagement, august = await _august_off(firm)
    run = await _run_agent(firm, engagement, run_scope(PROVIDER))

    first = await amortize_prepaid(run, _facts(run, engagement, august))
    again = await amortize_prepaid(run, _facts(run, engagement, august))

    assert (first.state, again.state) == ("succeeded", "succeeded")
    queue = await close_issues(firm.ctx(), august)
    assert queue.open == 1 and queue.by_severity["medium"] == 1
    item = queue.items[0]
    assert item.title == "Prepaid Insurance does not tie to its schedule"
    assert item.why_surfaced == "Raised by the close run: close_amortize_prepaid:41"
    assert item.account_external_id == "41"
    refs = await firm.seed.rows("SELECT source_ref FROM issues WHERE work_item_id = $1", august)
    assert [r["source_ref"] for r in refs] == ["close:schedule:41:-"]
    actors = await firm.seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 AND action = 'issue.created'",
        firm.tenant,
    )
    assert [r["actor_id"] for r in actors] == [f"agent:{AGENT_ID}:{run.agent_run_id}"]


async def test_a_run_without_its_providers_scope_is_refused(firm: _Firm) -> None:
    engagement, august = await _august_off(firm)
    run = await _run_agent(firm, engagement, list(TASK_SCOPE))
    with pytest.raises(Forbidden):
        await amortize_prepaid(run, _facts(run, engagement, august))
    assert (await close_issues(firm.ctx(), august)).open == 0


async def test_a_clearing_account_that_has_not_netted_raises_bank_rec(firm: _Firm) -> None:
    engagement, august = await _august_off(firm)
    run = await _run_agent(firm, engagement, run_scope(PROVIDER))
    facts = RunStepFacts(
        run_id=run.agent_run_id,
        engagement_id=engagement,
        step_key="close_clear_third_party_sales:35",
        level=1,
        arguments={"close_id": str(august), "account": "35"},
    )
    assert (await clear_third_party_sales(run, facts)).state == "succeeded"
    queue = await close_issues(firm.ctx(), august)
    assert [(i.issue_class, i.title) for i in queue.items] == [
        ("bank_rec", "Operating Checking has not cleared")
    ]
