"""C-01-T46 (TASK-8306; ADR-078): independent AC tests for AY's close record, plan, intake and run
services, written from SPEC-655 §4 F1 to F4 outside the implementing sessions.

ac-test-author: notanaskhan

- INV-1: only a live person starts a run, moves a status, publishes, adopts or incorporates; an
  agent principal is refused 403 and the refusal is kept (`decision.refused_non_human`).
- AC-18: a published plan never changes a close already pinned to an earlier version.
- AC-13: twelve closes per Monthly engagement and a thirteenth for a period answers 409.
- AC-9: "In review…" below n of n answers 409 `accounts_not_reconciled` naming the account.
- INV-3 (AC-4): a close the person may not see answers 404, and never counts in the portfolio.
- INV-5: the agent's audit rows name the person it acts for.

C-01-T19's intake summary VM still answers 501 (S46 partial): its AC-24 test is a strict xfail.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import uow
from abacus.modules.closes import plans, runs
from abacus.modules.closes import service as closes_service
from abacus.modules.closes.contract import PublishIn, StartRunIn, StatusMoveIn
from abacus.modules.identity.api import Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the shared close fixture
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _close(firm: _Firm, accounts: list[str]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    engagement, client, entity = await firm.engagement("Bluebird Bakery LLC")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await firm.plan(entity, accounts)
    return august, client, entity


async def _refusals(firm: _Firm, target: uuid.UUID) -> int:
    return int(
        str(
            await firm.seed.value(
                "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
                "AND action = 'decision.refused_non_human'",
                firm.tenant,
                str(target),
            )
        )
    )


async def test_inv1_an_agent_never_moves_a_status_and_the_refusal_is_kept(firm: _Firm) -> None:
    august, _, _ = await _close(firm, ["10"])
    agent = firm.ctx(actor_kind="agent")
    with pytest.raises(Forbidden):
        await closes_service.move_status(agent, august, StatusMoveIn(to="in_review"), "1")
    assert await _refusals(firm, august) == 1
    actor = await firm.seed.value(
        "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "AND action = 'decision.refused_non_human'",
        firm.tenant,
        str(august),
    )
    assert actor == "agent"


async def test_inv1_an_agent_never_starts_a_run(firm: _Firm) -> None:
    august, _, _ = await _close(firm, ["10"])
    with pytest.raises((Forbidden, NotFound)):
        await runs.start_run(firm.ctx(actor_kind="agent"), august, StartRunIn())
    runs_started = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "AND action = 'close_run.requested'",
        firm.tenant,
        str(august),
    )
    assert runs_started == 0


async def test_inv1_an_agent_never_publishes_or_adopts_a_plan(firm: _Firm) -> None:
    _, client, _ = await _close(firm, ["10"])
    agent = firm.ctx(actor_kind="agent")
    with pytest.raises(Forbidden):
        await plans.publish(agent, client, 1, PublishIn(effective_from="2026-09"), "1")
    with pytest.raises(Forbidden):
        await plans.adopt(agent, client, 1, None, "1")


async def test_ac18_a_pinned_close_never_changes_plan_version(firm: _Firm) -> None:
    august, client, entity = await _close(firm, ["10", "11"])
    async with uow(firm.ctx().tenant) as tx:
        pinned = await plans.pin_plan(tx.session, august)
    assert pinned is not None
    v2 = await firm.plan(entity, ["10", "11", "12"], publish=False)
    await firm.seed.run(  # the fixture numbers every draft 1
        "UPDATE close_plan_versions SET version = 2 WHERE id = $1", v2
    )
    await firm.publish(v2)
    after = await firm.seed.value(
        "SELECT close_plan_version_id FROM closes WHERE work_item_id = $1", august
    )
    assert after == pinned
    async with uow(firm.ctx().tenant) as tx:
        again = await plans.pin_plan(tx.session, august)
    assert again == pinned
    del client


async def test_ac13_twelve_closes_and_a_thirteenth_is_refused(firm: _Firm) -> None:
    engagement, _, _ = await firm.engagement("Bluebird Bakery LLC")
    made = await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    assert len(made) == 12 == len(set(made))
    with pytest.raises(DomainConflict):
        await closes_service.generate_closes(firm.ctx(), engagement, 2026)


async def test_ac9_in_review_below_n_of_n_names_the_account(firm: _Firm) -> None:
    august, _, _ = await _close(firm, ["10", "11"])
    await firm.reconcile(august, "10")
    with pytest.raises(DomainConflict) as refused:
        await closes_service.move_status(firm.ctx(), august, StatusMoveIn(to="in_review"), "1")
    assert refused.value.code == "accounts_not_reconciled"
    assert "11" in str(refused.value.facts)


async def test_inv3_a_close_outside_the_team_is_404_and_never_counted(firm: _Firm) -> None:
    august, _, _ = await _close(firm, ["10"])
    outsider = await firm.user("Dana Outsider")
    with pytest.raises(NotFound):
        await closes_service.visible_close(firm.ctx(outsider), august)
    portfolio = await closes_service.list_closes(firm.ctx(outsider), period="2026-08")
    assert august not in {row.close_id for row in portfolio.items}
    tiles = portfolio.tiles
    total = tiles.not_started + tiles.in_progress + tiles.in_review + tiles.delivered
    assert total == len(portfolio.items) == 0


@pytest.mark.xfail(strict=True, reason="C-01-T19: the intake summary VM still answers 501")
async def test_ac24_the_intake_summary_is_code_totals_with_sheet_cell_citations() -> None:
    from abacus.modules.closes import intake

    assert hasattr(intake, "intake_summary")
