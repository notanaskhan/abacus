"""T-08-T21 (TASK-9016; SPEC-710; DEC-6022) on the migrated database. Row acceptance: "Exports
re-render byte-identical and carry no TIN or amount, and each deadline yields at most one notice
per threshold."

Feld's 1040 is due Wed Apr 15, 2026. Swept on Apr 1 nothing is told; on Apr 8 (T-7) its owners
are told once, however often the sweep runs; on Apr 14 (T-1) once more; a re-run tells nobody.
A deadline first seen a day out is told once, at T-1. A partner walled from the client is never
told; a done deadline is never told. The xlsx and the ics each re-render byte for byte, with no
TIN and no amount in them."""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.practice import deadline_alerts as alerts
from abacus.modules.practice import deadlines_service as svc

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_t08t09_season_service import admin_of, as_admin, client_with_return

pytestmark = pytest.mark.asyncio

TIN_SHAPE = re.compile(r"\b\d{2}-\d{7}\b|\b\d{3}-\d{2}-\d{4}\b")


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


async def _office(seed: Seeder, tenant: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, 'Chicago', "
            "'America/Chicago') RETURNING id",
            tenant,
        ),
    )


async def _told(seed: Seeder, tenant: uuid.UUID) -> list[tuple[str, list[str]]]:
    rows = await seed.rows(
        "SELECT payload->>'threshold' AS th, payload->'recipient_user_ids' AS who FROM outbox "
        "WHERE tenant_id = $1 AND event_type = 'filing_deadline.approaching' ORDER BY seq",
        tenant,
    )
    return [(str(r["th"]), sorted(json.loads(r["who"]))) for r in rows]


async def test_t08t21_acceptance_each_deadline_is_told_once_per_threshold(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    office = await _office(seed, tenant)
    partner = await seed.person(tenant)
    await client_with_return(seed, tenant, partner, "Feld", office, "1040")
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-04-15' WHERE tenant_id = $1", tenant
    )
    assert await svc.recompute(tenant) == 1

    assert await alerts.sweep(tenant, today=date(2026, 4, 1)) == 0  # 14 days out
    assert await alerts.sweep(tenant, today=date(2026, 4, 8)) == 1  # T-7
    assert await alerts.sweep(tenant, today=date(2026, 4, 8)) == 0
    assert await alerts.sweep(tenant, today=date(2026, 4, 10)) == 0  # still the T-7 window
    assert await alerts.sweep(tenant, today=date(2026, 4, 14)) == 1  # T-1
    assert await alerts.sweep(tenant, today=date(2026, 4, 14)) == 0
    assert await alerts.sweep(tenant, today=date(2026, 4, 15)) == 0  # due today: told already
    assert await alerts.sweep(tenant, today=date(2026, 4, 16)) == 0  # overdue: never told

    assert await _told(seed, tenant) == [
        ("t_minus_7", [str(partner.user_id)]),
        ("t_minus_1", [str(partner.user_id)]),
    ]
    events = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'filing_deadline.approaching'",
        tenant,
    )
    assert events == 2
    assert await seed.value(
        "SELECT count(*) FROM filing_deadline_alerts WHERE tenant_id = $1", tenant
    ) == 2  # fmt: skip

    # The date moves (an extension): a new due date may be told again, once per threshold.
    await seed.run(
        "UPDATE tax_returns SET extended = true, extended_due_on = '2026-10-15' "
        "WHERE tenant_id = $1",
        tenant,
    )
    assert await svc.recompute(tenant) == 1
    assert await alerts.sweep(tenant, today=date(2026, 10, 8)) == 1
    assert await alerts.sweep(tenant, today=date(2026, 10, 8)) == 0


async def test_t08t21_a_deadline_first_seen_a_day_out_is_told_once_at_t_minus_1(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    await client_with_return(seed, tenant, partner, "Feld", await _office(seed, tenant), "1040")
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-04-15' WHERE tenant_id = $1", tenant
    )
    await svc.recompute(tenant)
    assert await alerts.sweep(tenant, today=date(2026, 4, 14)) == 1
    assert await alerts.sweep(tenant, today=date(2026, 4, 14)) == 0
    assert [t for t, _ in await _told(seed, tenant)] == ["t_minus_1"]
    passed = await seed.rows(
        "SELECT threshold FROM filing_deadline_alerts WHERE tenant_id = $1 ORDER BY threshold",
        tenant,
    )
    assert [r["threshold"] for r in passed] == ["t_minus_1", "t_minus_7"]


async def test_t08t21_walled_owners_and_done_deadlines_are_never_told(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    office = await _office(seed, tenant)
    partner = await seed.person(tenant)
    feld = await client_with_return(seed, tenant, partner, "Feld", office, "1040")
    await client_with_return(seed, tenant, partner, "Ostrander", office, "1040")
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-04-15' WHERE tenant_id = $1", tenant
    )
    await svc.recompute(tenant)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        partner.user_id,
        feld,
        partner.user_id,
    )
    await seed.run(
        "UPDATE filing_deadlines SET done_at = now() WHERE tenant_id = $1 AND client_id <> $2",
        tenant,
        feld,
    )
    assert await alerts.sweep(tenant, today=date(2026, 4, 8)) == 1
    assert await _told(seed, tenant) == [("t_minus_7", [])]  # Feld's partner is walled


def _xlsx_text(body: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        return "".join(z.read(n).decode() for n in sorted(z.namelist()))


async def test_t08t21_acceptance_exports_re_render_byte_identical_with_no_tin_or_amount(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    await client_with_return(
        seed, tenant, partner, '=HYPERLINK("x"),Feld;\nX', await _office(seed, tenant), "1040"
    )
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-04-15' WHERE tenant_id = $1", tenant
    )
    await svc.recompute(tenant)
    admin = as_admin(await admin_of(seed, tenant))  # filing_deadline.export, fresh MFA
    window = (date(2026, 4, 1), date(2026, 4, 30))
    for fmt in ("xlsx", "ics"):
        first = await svc.export_deadlines(admin, fmt, *window)
        second = await svc.export_deadlines(admin, fmt, *window)
        assert first == second, fmt
        body = _xlsx_text(first) if fmt == "xlsx" else first.decode()
        assert not TIN_SHAPE.search(body), fmt  # no TIN (the export never reads one)
        assert not re.search(r"\$\s?\d|\d,\d{3}\.\d{2}", body), fmt  # no amount
        if fmt == "ics":
            assert 'SUMMARY:=HYPERLINK("x")\\,Feld\\;\\nX · Form 1040 · 2025' in body
        else:
            assert "<f>" not in body  # a client name is never a formula
