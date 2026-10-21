"""SPEC-002 AC-5, DEC-121 against Postgres: every owner lookup behind the audit explorer's wall
filter runs, fails closed on an unknown id, and places real rows with their engagement, so a
walled reader loses the events about the walled client and keeps the others."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import AuditRow
from abacus.modules.audit_trail import targets
from abacus.modules.identity.api import AuthContext

from .support import Env, FirmRole, Person


def _row(kind: str, target: uuid.UUID, seq: int = 1) -> AuditRow:
    return AuditRow(
        seq, datetime(2026, 10, 20, tzinfo=UTC), "human", "u", "x.done", kind, str(target),
        None, None, None,
    )  # fmt: skip


def _ctx(who: Person, firm_role: str | None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=cast(FirmRole | None, firm_role),
        mfa_at=datetime.now(UTC),
    )


KINDS = sorted(
    targets.known_kinds() - targets.FIRM_LEVEL - {targets.WALLS} - targets.OPTIONAL_OWNER
)


@pytest.mark.parametrize("kind", KINDS)
async def test_every_owner_lookup_runs_and_an_unknown_id_is_hidden(env: Env, kind: str) -> None:
    admin = _ctx(env.admin, "firm_admin")
    assert await targets.readable(admin, [_row(kind, uuid.uuid4())]) == []


async def test_real_rows_are_placed_with_their_engagement_and_walls_hide_them(env: Env) -> None:
    seed = env.net.seed
    finding = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO findings (tenant_id, engagement_id, title, raised_by) "
            "VALUES ($1, $2, 'Cut-off', $3) RETURNING id",
            env.tenant_id,
            env.a.engagement_id,
            env.admin.user_id,
        ),
    )
    work_item = await seed.value(  # an engagement has its assurance work item from creation
        "SELECT id FROM work_items WHERE engagement_id = $1", env.a.engagement_id
    )
    trial_balance = await seed.value(
        "INSERT INTO trial_balances (tenant_id, engagement_id, work_item_id, client_entity_id, "
        "period_start, period_end, created_by) "
        "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
        env.tenant_id,
        env.a.engagement_id,
        work_item,
        env.a.entity_id,
        env.admin.user_id,
    )
    tie_out_check = await seed.value(
        "INSERT INTO tie_out_checks (tenant_id, engagement_id, target_type, target_id, key, kind, "
        "created_by) VALUES ($1, $2, 'trial_balance', $3, 'balanced', 'balanced', $4) "
        "RETURNING id",
        env.tenant_id,
        env.a.engagement_id,
        trial_balance,
        env.admin.user_id,
    )
    statement_dataset = await seed.value(
        "INSERT INTO statement_datasets (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, format, account_kind, opening, closing, opening_source, "
        "closing_source, included_total, line_count, excluded_count, approved_by, actor_kind) "
        "VALUES ($1, $2, $3, $4, 'csv', 'bank', 0, 10, 'entered', 'entered', 10, 1, 0, $5, "
        "'human') RETURNING id",
        env.tenant_id,
        env.a.engagement_id,
        env.a.item_id,
        env.a.version_id,
        env.admin.user_id,
    )
    walled = await env.walled("firm_admin")
    rows_for = {
        "engagement": env.a.engagement_id,
        "client": env.a.client_id,
        "client_entity": env.a.entity_id,
        "request_item": env.a.item_id,
        "evidence_version": env.a.version_id,
        "finding": finding,
        "trial_balance": cast(uuid.UUID, trial_balance),
        "tie_out_check": cast(uuid.UUID, tie_out_check),
        "statement_dataset": cast(uuid.UUID, statement_dataset),
    }
    rows = [_row(kind, target, n) for n, (kind, target) in enumerate(rows_for.items(), 1)]
    other = [_row("engagement", env.b.engagement_id, 90), _row("request_item", env.b.item_id, 91)]
    assert len(await targets.readable(_ctx(env.admin, "firm_admin"), [*rows, *other])) == 11
    # The walled firm administrator loses client A's events and keeps client B's.
    shown = await targets.readable(_ctx(walled, "firm_admin"), [*rows, *other])
    assert [r.seq for r in shown] == [90, 91]
