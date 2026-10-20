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
    walled = await env.walled("firm_admin")
    rows_for = {
        "engagement": env.a.engagement_id,
        "client": env.a.client_id,
        "client_entity": env.a.entity_id,
        "request_item": env.a.item_id,
        "evidence_version": env.a.version_id,
        "finding": finding,
    }
    rows = [_row(kind, target, n) for n, (kind, target) in enumerate(rows_for.items(), 1)]
    other = [_row("engagement", env.b.engagement_id, 90), _row("request_item", env.b.item_id, 91)]
    assert len(await targets.readable(_ctx(env.admin, "firm_admin"), [*rows, *other])) == 8
    # The walled firm administrator loses client A's events and keeps client B's.
    shown = await targets.readable(_ctx(walled, "firm_admin"), [*rows, *other])
    assert [r.seq for r in shown] == [90, 91]
