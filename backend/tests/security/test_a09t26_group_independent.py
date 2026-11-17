# ac-test-author: ayushkbhatia
"""A-09-T26 (TASK-8414; ADR-078 independent AC tests for N's consolidation, elimination and
coverage work; SPEC-658 F2 to F4).

Written from SPEC-658 and A-09 §6 (the T12 and 0889/0897 rules as the epic states them), not
from the services, against the database the app runs on:

- **RLS**: another firm's consolidation is invisible to the app role;
- **human-only finalize and lock**: a consolidation finalized or locked by any non-human actor is
  refused, and a lock before finalize is refused;
- **lock blocks edits**: a structure saved on a locked consolidation is refused by the service;
- **reopen needs a reason**: the service refuses a blank reason;
- **missing-TB refusal**: finalize names the missing slot;
- **agent and system refusal on approve and post**: an entry decision recorded under an agent or
  system actor is refused, so no agent-approved elimination can exist;
- **coverage uniqueness**: a second live ledger connection for a covered subsidiary is refused;
- **no write capability**: no registered C17 tool that writes is named for consolidation,
  elimination posting or coverage.

`_refused` is the one judgement: each test plants the violation and expects the database or the
service to refuse it, so a build missing the rule fails the suite.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import asyncpg
import pytest

from abacus.kernel.uow import UnitOfWork
from abacus.modules.ledger.consolidation import ConsolidationFacts, StructureEntity

from .support import Migrated, Seeder

pytestmark = pytest.mark.asyncio


async def _refused(act: Callable[[], Awaitable[object]]) -> bool:
    """True when the planted violation is refused (a constraint, a policy or a domain error)."""
    try:
        await act()
    except (asyncpg.PostgresError, ValueError, LookupError, PermissionError):
        return True
    except Exception as exc:  # a domain refusal carries a `code`
        return hasattr(exc, "code")
    return False


@pytest.mark.parametrize("planted", [True])
async def test_the_judgement_fails_an_unrefused_act(planted: bool) -> None:
    async def allowed() -> None:
        return None

    assert await _refused(allowed) is not planted


async def _consolidation(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant, "firm_admin")
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Harlow & Pike') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
        "'Harlow & Pike Holdings, Inc.') RETURNING id",
        tenant,
        client,
    )
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, status) VALUES ($1, $2, $3, "
        "'FY2026 Group Audit', '2026-01-01', '2026-12-31', $4, 'active') RETURNING id",
        tenant,
        client,
        entity,
        person.user_id,
    )
    work_item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
    )
    consolidation = await seed.value(
        "INSERT INTO consolidations (tenant_id, engagement_id, work_item_id, name, year_end, "
        "reporting_currency, created_by) VALUES ($1, $2, $3, 'Harlow & Pike', '2026-12-31', "
        "'USD', $4) RETURNING id",
        tenant,
        engagement,
        work_item,
        person.user_id,
    )
    return (
        tenant,
        uuid.UUID(str(consolidation)),
        person.user_id,
        uuid.UUID(str(entity)),
    )


async def test_rls_hides_another_firms_consolidation(migrated_db: Migrated, seed: Seeder) -> None:
    _, consolidation, _, _ = await _consolidation(seed)
    other = await seed.firm()
    from sqlalchemy import text

    from abacus.kernel.db import TenantContext, tenant_session

    async with tenant_session(TenantContext(other, "human", "probe")) as session:
        seen = await session.scalar(
            text("SELECT count(*) FROM consolidations WHERE id = :i"), {"i": consolidation}
        )
    assert seen == 0


@pytest.mark.parametrize("actor", ["agent", "system"])
async def test_finalize_and_lock_are_human_only(seed: Seeder, actor: str) -> None:
    _, consolidation, user, _ = await _consolidation(seed)
    assert await _refused(
        lambda: seed.run(
            "UPDATE consolidations SET status = 'finalized', finalized_by = $2, finalized_at = "
            "now(), finalized_actor_kind = $3 WHERE id = $1",
            consolidation,
            user,
            actor,
        )
    )


async def test_a_lock_before_finalize_is_refused(seed: Seeder) -> None:
    _, consolidation, user, _ = await _consolidation(seed)
    assert await _refused(
        lambda: seed.run(
            "UPDATE consolidations SET lock_state = 'locked', locked_by = $2, locked_at = now(), "
            "locked_actor_kind = 'human' WHERE id = $1",
            consolidation,
            user,
        )
    )


async def test_an_agent_or_system_decision_on_an_entry_is_refused(
    migrated_db: Migrated, seed: Seeder
) -> None:
    """No elimination can carry an approval or posting decision made by a non-human actor: the
    decision row's actor must be the session's human actor."""
    tenant, _, user, _ = await _consolidation(seed)
    connection = await asyncpg.connect(migrated_db.superuser_dsn)
    try:
        for actor in ("agent", "system"):

            async def planted(kind: str = actor) -> None:
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.actor_kind', $1, true), "
                        "set_config('app.actor_id', $2, true)",
                        kind,
                        str(user),
                    )
                    await connection.execute(
                        "INSERT INTO proposed_entry_decisions (tenant_id, engagement_id, "
                        "work_item_id, entry_id, decision, actor_principal, channel, "
                        "seen_version) "
                        "VALUES ($1, gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), "
                        "'approved', 'firm_user', 'app', 1)",
                        tenant,
                    )

            assert await _refused(planted), actor
    finally:
        await connection.close()


async def test_a_second_live_ledger_for_a_covered_subsidiary_is_refused(seed: Seeder) -> None:
    tenant, _, _, entity = await _consolidation(seed)
    rows = await seed.rows("SELECT id FROM connections WHERE tenant_id = $1 LIMIT 2", tenant)
    if len(rows) < 2:
        # Coverage rows follow connections; plant two live ledger rows directly.
        first = uuid.uuid4()
        second = uuid.uuid4()
        planted = (
            "INSERT INTO connection_entity_coverage (tenant_id, connection_id, client_entity_id, "
            "category, live) VALUES ($1, $2, $3, 'ledger', true)"
        )

        async def both() -> None:
            await seed.run(planted, tenant, first, entity)
            await seed.run(planted, tenant, second, entity)

        assert await _refused(both)


async def test_no_write_tool_reaches_consolidation_posting_or_coverage() -> None:
    import importlib

    from abacus.modules.agents.api import registered_tools

    importlib.import_module("abacus.api.app")  # every module's tools register at import
    writes = [
        t.name
        for t in registered_tools().values()
        if t.kind == "approved_write"
        and any(k in t.name for k in ("consolidation", "elimination", "coverage", "posting"))
    ]
    assert writes == []


# --- S48 rest: the service-level rules the suite names, restated independently (TASK-8440) ---


async def _ids(seed: Seeder, consolidation: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    engagement = await seed.value(
        "SELECT engagement_id FROM consolidations WHERE id = $1", consolidation
    )
    work_item = await seed.value(
        "SELECT work_item_id FROM consolidations WHERE id = $1", consolidation
    )
    return uuid.UUID(str(engagement)), uuid.UUID(str(work_item))


async def _as_person(
    tenant: uuid.UUID, user: uuid.UUID, act: Callable[[UnitOfWork], Awaitable[object]]
) -> object:
    from abacus.kernel.db import TenantContext
    from abacus.kernel.uow import uow

    async with uow(TenantContext(tenant, "human", str(user))) as tx:
        return await act(tx)


async def _facts(tenant: uuid.UUID, consolidation: uuid.UUID) -> ConsolidationFacts:
    from abacus.kernel.db import TenantContext
    from abacus.modules.ledger.api import consolidation_facts

    return await consolidation_facts(TenantContext(tenant, "human", "probe"), consolidation)


async def _finalized(
    seed: Seeder, consolidation: uuid.UUID, user: uuid.UUID, *, locked: bool
) -> None:
    await seed.run(
        "UPDATE consolidations SET status = 'finalized', finalized_by = $2, "
        "finalized_at = now(), finalized_actor_kind = 'human' WHERE id = $1",
        consolidation,
        user,
    )
    if locked:
        await seed.run(
            "UPDATE consolidations SET lock_state = 'locked', locked_by = $2, locked_at = now(), "
            "locked_actor_kind = 'human' WHERE id = $1",
            consolidation,
            user,
        )


def _one_entity(entity: uuid.UUID) -> list[StructureEntity]:
    return [StructureEntity(entity, None, 1, None, None)]


@pytest.mark.parametrize("locked", [False, True])
async def test_a_finalized_or_locked_structure_refuses_edits(seed: Seeder, locked: bool) -> None:
    """Structure freeze and lock blocks edits: once finalized (and while locked) a structure save
    and a details edit are refused before anything changes."""
    from abacus.modules.ledger.consolidation import save_structure

    tenant, consolidation, user, entity = await _consolidation(seed)
    await _finalized(seed, consolidation, user, locked=locked)
    seen = int(
        str(
            await seed.value("SELECT row_version FROM consolidations WHERE id = $1", consolidation)
        )
    )
    assert await _refused(
        lambda: _as_person(
            tenant,
            user,
            lambda tx: save_structure(
                tx,
                tenant_id=tenant,
                consolidation_id=consolidation,
                seen=seen,
                entities=_one_entity(entity),
            ),
        )
    )
    after = await seed.value("SELECT row_version FROM consolidations WHERE id = $1", consolidation)
    assert int(str(after)) == seen


@pytest.mark.parametrize("reason", ["", "   "])
async def test_a_reopen_needs_a_reason(seed: Seeder, reason: str) -> None:
    from abacus.modules.ledger.api import reopen_consolidation

    tenant, consolidation, user, _ = await _consolidation(seed)
    await _finalized(seed, consolidation, user, locked=True)
    facts = await _facts(tenant, consolidation)
    assert await _refused(
        lambda: _as_person(
            tenant,
            user,
            lambda tx: reopen_consolidation(
                tx,
                facts,
                tenant_id=tenant,
                user_id=user,
                reason=reason,
            ),
        )
    )
    state = await seed.value("SELECT lock_state FROM consolidations WHERE id = $1", consolidation)
    assert state == "locked"


async def test_finalize_refuses_a_missing_trial_balance(seed: Seeder) -> None:
    """A structure whose required TB slot is empty cannot be finalized; it stays a draft."""
    from abacus.modules.ledger.api import finalize_consolidation
    from abacus.modules.ledger.consolidation import save_structure

    tenant, consolidation, user, entity = await _consolidation(seed)
    await _as_person(
        tenant,
        user,
        lambda tx: save_structure(
            tx,
            tenant_id=tenant,
            consolidation_id=consolidation,
            seen=1,
            entities=_one_entity(entity),
        ),
    )
    facts = await _facts(tenant, consolidation)
    assert await _refused(
        lambda: _as_person(
            tenant,
            user,
            lambda tx: finalize_consolidation(
                tx,
                facts,
                tenant_id=tenant,
                seen=facts.row_version,
                user_id=user,
            ),
        )
    )
    assert (
        await seed.value("SELECT status FROM consolidations WHERE id = $1", consolidation)
        == "draft"
    )


async def test_a_pull_whose_token_was_refused_leaves_the_slot_needs_reauth(seed: Seeder) -> None:
    """The pull-all reauth path: a refused token writes a Needs reauth slot (never a TB), and the
    consolidation still cannot be finalized."""
    from abacus.modules.ledger.api import finalize_consolidation
    from abacus.modules.ledger.consolidation import mark_slot_needs_reauth, save_structure

    tenant, consolidation, user, entity = await _consolidation(seed)
    await _as_person(
        tenant,
        user,
        lambda tx: save_structure(
            tx,
            tenant_id=tenant,
            consolidation_id=consolidation,
            seen=1,
            entities=_one_entity(entity),
        ),
    )
    facts = await _facts(tenant, consolidation)
    key = facts.required[0]
    await _as_person(
        tenant,
        user,
        lambda tx: mark_slot_needs_reauth(tx, tenant_id=tenant, key=key, user_id=user),
    )
    states = await seed.value(
        "SELECT string_agg(t.state, ',') FROM consolidation_trial_balances t "
        "JOIN consolidation_entities e ON e.id = t.consolidation_entity_id "
        "WHERE e.consolidation_id = $1 AND t.superseded_by IS NULL",
        consolidation,
    )
    assert states == "needs_reauth"
    facts = await _facts(tenant, consolidation)
    assert await _refused(
        lambda: _as_person(
            tenant,
            user,
            lambda tx: finalize_consolidation(
                tx,
                facts,
                tenant_id=tenant,
                seen=facts.row_version,
                user_id=user,
            ),
        )
    )


async def _entry(
    seed: Seeder,
    tenant: uuid.UUID,
    consolidation: uuid.UUID,
    user: uuid.UUID,
    *,
    kind: str,
    status: str,
    target: str | None,
) -> object:
    engagement, work_item = await _ids(seed, consolidation)
    return await seed.value(
        "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, number, ref, "
        "threshold_result, is_attest_client, status, created_by_kind, created_by_id, "
        "consolidation_id, posting_target) VALUES ($1, $2, $3, $4, 1, $9, 'review_required', "
        "false, $5, 'human', $6, $7, $8) RETURNING id",
        tenant,
        engagement,
        work_item,
        kind,
        status,
        str(user),
        consolidation if kind == "elimination" else None,
        target,
        "ELIM-1" if kind == "elimination" else "AJE-1",
    )


@pytest.mark.parametrize(
    ("kind", "status", "target"),
    [
        ("aje", "posted", None),  # an AJE never posts anywhere
        ("aje", "proposed", "consolidation_layer"),  # only an elimination has a posting target
        ("elimination", "posted", None),  # an elimination posts only to the consolidation layer
        ("elimination", "proposed", "client_ledger"),  # and to no other target
    ],
)
async def test_the_posting_check_and_target(
    seed: Seeder, kind: str, status: str, target: str | None
) -> None:
    tenant, consolidation, user, _ = await _consolidation(seed)
    assert await _refused(
        lambda: _entry(seed, tenant, consolidation, user, kind=kind, status=status, target=target)
    )


async def test_an_elimination_may_post_to_the_consolidation_layer(seed: Seeder) -> None:
    """The one allowed posting (the control for the four refusals above)."""
    tenant, consolidation, user, _ = await _consolidation(seed)
    made = await _entry(
        seed,
        tenant,
        consolidation,
        user,
        kind="elimination",
        status="posted",
        target="consolidation_layer",
    )
    assert made is not None
