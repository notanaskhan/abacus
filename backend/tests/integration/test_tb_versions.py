"""A-02-T07 (TASK-1285; SPEC-333 AC-1, AC-4, AC-14) against Postgres: adopting a trial balance of
record and re-adopting a newer snapshot through `ledger.api`.

Granite Peak FY2026 (the golden's lines, `tests/golden/ledger/tb_layers.yaml`) is adopted as v1
with FY2025 as the prior year; a re-pull with the Alpine Ridge Sports credit memo (AR and revenue
each 4,300.00 lower, DEC-342) is adopted as v2 with a reason. v1's row, all three snapshots and
their lines are untouched (same row version, same content), `trial_balance.version_created`
reaches the outbox for both versions, the audit rows are C9 §7's, and the view reads either
version. With no adjustment source registered, AJE, RJE and Final answer `layer_unavailable`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.ledger import trial_balances as tb_module
from abacus.modules.ledger.api import (
    LayerUnavailable,
    adopt_trial_balance,
    adopt_version,
    trial_balance_view,
)

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
GOLDEN = Path(__file__).parents[1] / "golden" / "ledger" / "tb_layers.yaml"
Line = tuple[str, str, Decimal, Decimal]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


def _granite(key: str) -> list[Line]:
    raw = cast(dict[str, object], yaml.safe_load(GOLDEN.read_text()))
    case = next(
        c for c in cast(list[dict[str, object]], raw["cases"]) if c["id"] == "granite-peak-fy2026"
    )
    return [
        (str(r[0]), str(r[1]), Decimal(str(r[2])), Decimal(str(r[3])))
        for r in cast(list[list[object]], case[key])
    ]


def _repull(lines: list[Line]) -> list[Line]:
    memo = Decimal("4300.00")
    out: list[Line] = []
    for code, name, debit, credit in lines:
        if code == "1100":
            debit -= memo
        if code == "4000":
            credit -= memo
        out.append((code, name, debit, credit))
    return out


async def _snapshot(
    seed: Seeder, tenant: uuid.UUID, entity: uuid.UUID, start: date, end: date, lines: list[Line]
) -> uuid.UUID:
    """A snapshot and its lines, in one transaction (lines only arrive with their snapshot)."""
    async with seed.held() as conn, conn.transaction():
        snapshot = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, "
                "period_end, pulled_at, source, raw_fingerprint, line_count, total_debit, "
                "total_credit) VALUES ($1, $2, $3, $4, clock_timestamp(), 'import_netsuite_csv', "
                "$5, $6, $7, $8) RETURNING id",
                tenant,
                entity,
                start,
                end,
                hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                len(lines),
                sum((x[2] for x in lines), Decimal(0)),
                sum((x[3] for x in lines), Decimal(0)),
            ),
        )
        await conn.executemany(
            "INSERT INTO trial_balance_lines (tenant_id, snapshot_id, account_code, "
            "account_name, debit, credit, source_ref) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            [
                (tenant, snapshot, code, name, debit, credit, f"row:{n}")
                for n, (code, name, debit, credit) in enumerate(lines, start=1)
            ],
        )
    return snapshot


async def _state(seed: Seeder, snapshots: list[uuid.UUID]) -> list[tuple[str, str]]:
    """Every snapshot row and line with its row version: an UPDATE changes `xmin`."""
    rows = await seed.rows(
        "SELECT xmin::text AS v, row_to_json(s)::text AS j FROM ledger_snapshots s "
        "WHERE id = ANY($1::uuid[]) UNION ALL "
        "SELECT xmin::text, row_to_json(l)::text FROM trial_balance_lines l "
        "WHERE snapshot_id = ANY($1::uuid[]) ORDER BY 2",
        snapshots,
    )
    return [(str(r["v"]), str(r["j"])) for r in rows]


async def _version_row(seed: Seeder, tb: uuid.UUID, version_no: int) -> tuple[str, str]:
    rows = await seed.rows(
        "SELECT xmin::text AS v, row_to_json(v)::text AS j FROM trial_balance_versions v "
        "WHERE trial_balance_id = $1 AND version_no = $2",
        tb,
        version_no,
    )
    assert len(rows) == 1
    return str(rows[0]["v"]), str(rows[0]["j"])


async def test_ac4_re_adopting_creates_v2_and_touches_neither_v1_nor_any_snapshot(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    simone = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, simone.user_id)
    await seed.member(engagement, simone, "senior")
    # The engagement's one assurance work item (engagements open with it).
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
    fy26 = (date(2025, 7, 1), date(2026, 6, 30))
    current = _granite("current")
    pull_1 = await _snapshot(seed, tenant, entity, *fy26, current)
    pull_2 = await _snapshot(seed, tenant, entity, *fy26, _repull(current))
    prior = await _snapshot(
        seed, tenant, entity, date(2024, 7, 1), date(2025, 6, 30), _granite("prior")
    )
    snapshots = [pull_1, pull_2, prior]
    before = await _state(seed, snapshots)
    ctx = Person(simone.user_id, tenant).context()

    async with uow(ctx.tenant) as tx:
        tb = await adopt_trial_balance(
            tx,
            tenant_id=tenant,
            engagement_id=engagement,
            work_item_id=work_item,
            client_entity_id=entity,
            snapshot_id=pull_1,
            prior_snapshot_id=prior,
            label="standard",
            display_unit="cents",
            user_id=simone.user_id,
            actor_kind="human",
        )
    v1 = await _version_row(seed, tb, 1)

    async with uow(ctx.tenant) as tx:
        version = await adopt_version(
            tx,
            tenant_id=tenant,
            engagement_id=engagement,
            tb_id=tb,
            snapshot_id=pull_2,
            prior_snapshot_id=prior,
            reason="Re-pulled after the Alpine Ridge Sports credit memo",
            seen_version=1,
            user_id=simone.user_id,
            actor_kind="human",
        )
    assert version == 2

    # v1 and every snapshot are as they were (ADR-004): same content, never rewritten.
    assert await _version_row(seed, tb, 1) == v1
    assert await _state(seed, snapshots) == before
    v2 = json.loads((await _version_row(seed, tb, 2))[1])
    assert (v2["snapshot_id"], v2["prior_snapshot_id"]) == (str(pull_2), str(prior))
    assert v2["reason"] == "Re-pulled after the Alpine Ridge Sports credit memo"
    assert await seed.value("SELECT current_version_no FROM trial_balances WHERE id = $1", tb) == 2

    # The outbox announces each version (C9 §7: P-04 stale detection); identifiers only.
    events = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'trial_balance.version_created' ORDER BY (payload->>'version_no')::int",
        tenant,
    )
    payloads = [cast(dict[str, object], json.loads(str(r["payload"]))) for r in events]
    assert [(p["trial_balance_id"], p["version_no"], p["snapshot_id"]) for p in payloads] == [
        (str(tb), 1, str(pull_1)),
        (str(tb), 2, str(pull_2)),
    ]
    assert all(p["engagement_id"] == str(engagement) for p in payloads)
    assert all(p["prior_snapshot_id"] == str(prior) for p in payloads)

    # Audit rows as C9 §7 names them, every one by the person.
    audit = [e for e in await seed.events(tenant) if e.action.startswith("trial_balance.")]
    assert [e.action for e in audit] == [
        "trial_balance.created",
        "trial_balance.version_adopted",
        "trial_balance.version_adopted",
    ]
    assert {(e.actor_kind, e.actor_id) for e in audit} == {("human", str(simone.user_id))}

    # The view reads v2 by default and still reads v1 on request, each footed by code.
    latest = await trial_balance_view(ctx.tenant, engagement, tb)
    first = await trial_balance_view(ctx.tenant, engagement, tb, 1)
    assert (latest.version.version_no, first.version.version_no) == (2, 1)
    receivable = {
        v.version.version_no: next(x for x in v.lines if x.account_code == "1100")
        for v in (latest, first)
    }
    assert (receivable[1].eoy, receivable[2].eoy) == (Decimal("5860000.00"), Decimal("5855700.00"))
    assert receivable[2].boy == Decimal("4720000.00")
    assert first.eoy.debit == first.eoy.credit == Decimal("71910000.00")
    assert latest.eoy.debit == latest.eoy.credit == Decimal("71905700.00")
    assert first.boy is not None and first.boy.debit == Decimal("23200000.00")
    assert [v.version_no for v in latest.versions] == [2, 1]

    # AC-14: with no adjustment source registered, the adjusted layers are refused.
    monkeypatch.setattr(tb_module, "_ADJUSTMENT_SOURCES", [])
    for layer in ("aje", "rje", "final"):
        with pytest.raises(LayerUnavailable):
            await trial_balance_view(ctx.tenant, engagement, tb, None, layer)
    plain = await trial_balance_view(ctx.tenant, engagement, tb)
    assert plain.final is None and set(plain.layer_balances) == {"unadjusted"}
