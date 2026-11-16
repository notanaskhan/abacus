"""A-08-T12 (TASK-8086; SPEC-657 F1, F3, AC-1.1, AC-1.4; DEC-5068) against Postgres: a proved GL
snapshot becomes a JE test, the firm's criteria score it with reason codes, and a selection of the
top scores plus unpredictable picks is a `je_score_selection` sample-set version drawn by the
sample draw's own function, with its seed and sampler version recorded.

The workflows run inline: `dispatch` is replaced by the activity functions (no worker in tests).
The 412,903-line timing (AC-1.2 on staging) is the staging run's, not this file's.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext
from abacus.modules.sampling import je_tests as svc
from abacus.modules.sampling.draw import run_draw
from abacus.modules.sampling.fieldwork_contract import (
    CriteriaIn,
    JeTestCreateIn,
    PopulationNotTied,
    PostingUserRoleIn,
    PostingUserRolesIn,
    SelectionIn,
)
from abacus.modules.sampling.je_scoring_types import JeScoringInput

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

ENTRIES = 60
CRITERIA: dict[str, object] = {
    "kind": "je_risk_criteria",
    "criteria": [
        {"key": "weekend_holiday", "weight": 20, "params": {}},
        {"key": "round_amount", "weight": 35, "params": {"at_least": "1000", "unit": "1000"}},
        {"key": "post_close", "weight": 30, "params": {}},
        {"key": "manual_by_role", "weight": 25, "params": {"role_class": "senior_management"}},
        {"key": "keywords", "weight": 15, "params": {"words": "bonus, reclass"}},
    ],
}


@dataclass(frozen=True)
class World:
    ctx: AuthContext
    work_item: uuid.UUID
    snapshot: uuid.UUID
    policy_version: uuid.UUID
    seed: Seeder


def _gl_sql(tied: bool) -> str:
    """One statement (one transaction): the snapshot, its two balances and 60 two-line entries.
    Entry n posts on 2026-06-01 + n days: every fifth a round amount, every seventh by the CFO
    by hand, every ninth a bonus; those after Jun 30 are the post-close window's."""
    gap = "0" if tied else "25"
    return f"""
        WITH s AS (
            INSERT INTO gl_snapshots (tenant_id, client_entity_id, period_start, period_end,
                source, raw_fingerprint, tb_snapshot_id, line_count, total_debit, total_credit,
                je_fields_available)
            SELECT $1, $2, '2025-07-01', '2026-07-31', 'netsuite_gl_csv', md5(random()::text)
                || md5(random()::text), gen_random_uuid(), {ENTRIES * 2}, t.total, t.total,
                ARRAY['posted_by', 'source']
            FROM (SELECT sum(CASE WHEN n % 5 = 0 THEN 1000 * n ELSE 100 * n + 37 END)::numeric
                  AS total FROM generate_series(1, {ENTRIES}) n) t
            RETURNING id, total_debit
        ), b AS (
            INSERT INTO gl_account_balances (tenant_id, snapshot_id, account_code, account_name,
                opening, debit, credit, closing, tb_closing, opening_derived)
            SELECT $1, s.id, a.code, a.name, 0, a.debit, a.credit, a.closing, a.closing - a.gap,
                false
            FROM s, LATERAL (VALUES
                ('61000', 'Compensation', s.total_debit, 0::numeric, s.total_debit, {gap}::numeric),
                ('10000', 'Cash', 0::numeric, s.total_debit, -s.total_debit, 0::numeric)
            ) AS a(code, name, debit, credit, closing, gap)
            RETURNING 1
        ), e AS (
            INSERT INTO gl_entries (tenant_id, snapshot_id, line_no, account_code, posted_on,
                reference, kind, description, debit, credit, source_ref, posted_by, source)
            SELECT $1, s.id, 2 * n - 1 + side, CASE side WHEN 0 THEN '61000' ELSE '10000' END,
                DATE '2026-06-01' + n, 'JE-' || lpad(n::text, 4, '0'), 'Journal',
                CASE WHEN n % 9 = 0 THEN 'Year-end bonus accrual' ELSE 'Accrual' END,
                CASE side WHEN 0 THEN amount ELSE 0 END, CASE side WHEN 1 THEN amount ELSE 0 END,
                'row ' || (2 * n - 1 + side),
                CASE WHEN n % 7 = 0 THEN 'R. Vance' ELSE 'A. Lee' END,
                CASE WHEN n % 7 = 0 THEN 'manual' ELSE 'system' END
            FROM s, generate_series(1, {ENTRIES}) n, generate_series(0, 1) side,
                LATERAL (SELECT CASE WHEN n % 5 = 0 THEN 1000 * n ELSE 100 * n + 37 END::numeric
                         AS amount) x
            RETURNING 1
        )
        SELECT s.id FROM s, (SELECT count(*) FROM b) bb, (SELECT count(*) FROM e) ee
    """


async def _world(migrated_db: MigratedDatabase, *, tied: bool = True) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = uuid.UUID(str(await seed.value("INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES ('https://probe.test', $1, $2, 'Simone Park') RETURNING id", uuid.uuid4().hex, f"{uuid.uuid4().hex}@x.test")))
    await seed.run("INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')", tenant, user)
    await seed.run("INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) VALUES ($1, 'audits.fieldwork_testing', 'true', 'a08-t12', 'A-08-T12')", tenant)
    client = await seed.value("INSERT INTO clients (tenant_id, name) VALUES ($1, 'Granite Peak') RETURNING id", tenant)
    entity = await seed.value("INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Granite Peak') RETURNING id", tenant, client)
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, fiscal_period_start, fiscal_period_end, created_by, status) "
        "VALUES ($1, $2, $3, 'FY2026 Audit', '2025-07-01', '2026-06-30', $4, 'active') RETURNING id", tenant, client, entity, user,
    )
    await seed.run("INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, $2, $3, 'engagement_partner')", tenant, engagement, user)
    work_item = uuid.UUID(str(await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) VALUES ($1, $2, $3, 'assurance', 'Journal entries', $4) RETURNING id",
        tenant, engagement, client, user,
    )))  # fmt: skip
    snapshot = uuid.UUID(str(await seed.value(_gl_sql(tied), tenant, entity)))
    policy = await seed.value(
        "INSERT INTO threshold_policies (tenant_id, kind, key, name, owner_id, created_by) VALUES ($1, 'je_risk_criteria', 'bh-je-criteria', 'BH JE criteria', $2, $2) RETURNING id",
        tenant, user,
    )  # fmt: skip
    body = json.dumps(CRITERIA)
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    version = uuid.UUID(str(await seed.value(
        "INSERT INTO threshold_policy_versions (tenant_id, parent_id, version, payload, payload_hash, drafted_by) VALUES ($1, $2, 1, $3::jsonb, $4, $5) RETURNING id",
        tenant, policy, body, digest, user,
    )))  # fmt: skip
    await seed.run(
        "UPDATE threshold_policy_versions SET status = 'published', effective_from = '2025-07-01', published_by = $2, published_actor_kind = 'human', published_at = now() WHERE id = $1",
        version, user,
    )  # fmt: skip
    ctx = AuthContext(TenantContext(tenant, "human", str(user)), user, uuid.uuid4(), None, datetime.now(UTC))
    return World(ctx, work_item, snapshot, version, seed)


@pytest.fixture
async def world(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[World]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)

    async def inline(workflow: type, arg: Any, **_: Any) -> None:  # Any: the workflow inputs
        if isinstance(arg, JeScoringInput):
            await svc.run_scoring(uuid.UUID(arg.tenant_id), uuid.UUID(arg.je_test_id), arg.score_version)
        else:
            await run_draw(uuid.UUID(arg.tenant_id), uuid.UUID(arg.version_id))

    monkeypatch.setattr(svc, "dispatch", inline)
    yield await _world(migrated_db)
    await dispose_engine()


def _create(w: World) -> JeTestCreateIn:
    return JeTestCreateIn(
        gl_snapshot_id=w.snapshot, period_start=date(2025, 7, 1), period_end=date(2026, 6, 30),
        post_close_through=date(2026, 7, 31),
    )  # fmt: skip


async def _scored(w: World) -> uuid.UUID:
    test = await svc.create_je_test(w.ctx, w.work_item, _create(w))
    assert test.tie.result == "tie" and test.tie.accounts_tied == test.tie.accounts_total == 2
    await svc.put_criteria(w.ctx, test.id, CriteriaIn(policy_version_id=w.policy_version))
    await svc.put_posting_user_roles(
        w.ctx, test.id,
        PostingUserRolesIn(roles=[PostingUserRoleIn(posting_user="r. vance", role_class="senior_management")]),
    )  # fmt: skip
    await svc.start_scoring(w.ctx, test.id, uuid.uuid4().hex)
    return test.id


async def test_ac1_scores_every_entry_with_reason_codes(world: World) -> None:
    je_test_id = await _scored(world)
    view = await svc.je_test_view(world.ctx, je_test_id)
    assert view.status == "scored" and view.score_version == 1
    assert view.entries_count == ENTRIES and view.engine_version == "je_scoring/1.0"
    hits = {c.key: c.hit_count for c in view.criteria}
    assert hits["round_amount"] == ENTRIES // 5
    assert hits["manual_by_role"] == ENTRIES // 7
    assert hits["keywords"] == ENTRIES // 9
    assert hits["post_close"] == ENTRIES - 29  # Jul 1 onwards: n >= 30
    assert all(c.availability == "available" for c in view.criteria)
    page = await svc.list_entries(world.ctx, je_test_id, criterion=None, selected=None, cursor=None)
    assert len(page.items) == svc.PAGE and page.next_cursor is not None
    assert all(bool(e.reason_codes) == (e.score > 0) for e in page.items)
    assert [e.score for e in page.items] == sorted((e.score for e in page.items), reverse=True)
    rest = await svc.list_entries(world.ctx, je_test_id, criterion=None, selected=None, cursor=page.next_cursor)
    assert len(page.items) + len(rest.items) == ENTRIES and rest.next_cursor is None
    manual = await svc.list_entries(world.ctx, je_test_id, criterion="manual_by_role", selected=None, cursor=None)
    assert {e.entry_ref for e in manual.items} == {f"JE-{n:04d}" for n in range(7, ENTRIES + 1, 7)}


async def test_ac1_4_the_selection_is_a_je_score_selection_version(world: World) -> None:
    je_test_id = await _scored(world)
    selection = await svc.draw_selection(
        world.ctx, je_test_id, SelectionIn(score_min=None, top_n=10, unpredictable_n=4), uuid.uuid4().hex
    )
    assert (selection.by_score, selection.unpredictable) == (10, 4)
    assert selection.sampler_version == "je_select/1.0" and selection.seed.startswith("0x")
    rows = await world.seed.rows(
        "SELECT v.method, v.status, v.final_size, i.selection_reason FROM sample_set_versions v "
        "JOIN sample_items i ON i.sample_set_version_id = v.id WHERE v.sample_set_id = $1 ORDER BY i.position",
        selection.sample_set_id,
    )  # fmt: skip
    assert {r["method"] for r in rows} == {"je_score_selection"}
    assert {r["status"] for r in rows} == {"draft"} and len(rows) == 14
    assert [r["selection_reason"] for r in rows] == ["risk_score"] * 10 + ["unpredictable"] * 4
    chosen = await svc.list_entries(world.ctx, je_test_id, criterion=None, selected=True, cursor=None)
    assert len(chosen.items) == 14 and all(e.selected for e in chosen.items)


async def test_ac1_1_scoring_waits_for_a_tie(migrated_db: MigratedDatabase, world: World) -> None:
    off = await _world(migrated_db, tied=False)
    test = await svc.create_je_test(off.ctx, off.work_item, _create(off))
    assert test.tie.result == "difference"
    await svc.put_criteria(off.ctx, test.id, CriteriaIn(policy_version_id=off.policy_version))
    with pytest.raises(PopulationNotTied):
        await svc.start_scoring(off.ctx, test.id, uuid.uuid4().hex)


async def test_scoring_needs_the_criteria_first(world: World) -> None:
    test = await svc.create_je_test(world.ctx, world.work_item, _create(world))
    with pytest.raises(svc.CriteriaRequired):
        await svc.start_scoring(world.ctx, test.id, uuid.uuid4().hex)


async def test_a_second_create_answers_the_first(world: World) -> None:
    first = await svc.create_je_test(world.ctx, world.work_item, _create(world))
    again = await svc.create_je_test(world.ctx, world.work_item, _create(world))
    assert first.id == again.id
