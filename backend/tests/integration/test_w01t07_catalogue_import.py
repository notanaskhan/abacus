"""W-01-T07 (SPEC-659 AC-1, AC-4, AC-31 to AC-33) against Postgres: migration 0901's readers and
the operator's v2 catalogue import.

A dry run writes nothing (AC-32); an apply adds the workbench columns, logs one import row with
the document's SHA-256, and a second identical apply writes nothing; a workbench row the document
drops is unpublished, never deleted; the app can read the workbench catalogue but not run the
import; a key that becomes available tells the person who asked (Notify me) exactly once (AC-33);
and the read is honest: with no adapter registered in this process nothing is available (AC-4).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations.api import CatalogDocumentV2
from abacus.modules.integrations.connect_catalog import catalogue, interest
from abacus_tools import integration_catalog as ops

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.usefixtures("engine")

OPERATOR = "probe-op"
SHA = "a" * 64


def _row(key: str, **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "key": key,
        "name": key.title(),
        "categories": ["practice"],
        "ownership_mode": "firm",
        "surfaces": ["workbench"],
        "adapter_key": key,
        "listing_status": "available",
        "scopes": {"read": [{"code": "projects.read", "label": "Projects"}]},
        "icon": "briefcase",
        "tone": "olive",
        "sort_order": 10,
        "description": "Workflow, time and billing.",
        "auth_line": "Firm connection",
        "published_at": "2026-01-01T00:00:00-06:00",
    }
    row.update(over)
    return row


def _doc(*rows: dict[str, object]) -> CatalogDocumentV2:
    return CatalogDocumentV2.model_validate({"version": 2, "rows": list(rows)})


def _ops(db: MigratedDatabase) -> str:
    return db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)


@pytest.fixture
def db(migrated_db: MigratedDatabase) -> MigratedDatabase:
    return migrated_db


@pytest.fixture
async def engine(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    # Fresh pools on this test's loop (the identity engine, for names_of, rebuilds from the
    # settings), disposed after it.
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


async def _person(db: MigratedDatabase, role: str | None = "firm_admin") -> AuthContext:
    """A firm person; `None` is a staff member with no firm role."""
    seed = Seeder(db.superuser_dsn)
    tenant_id = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant_id)
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Probe person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    membership = await seed.value(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, $3, 'active') RETURNING id",
        tenant_id,
        user_id,
        role,
    )
    tenant = TenantContext(tenant_id, "human", str(user_id))
    return AuthContext(tenant, user_id, cast(uuid.UUID, membership), role, datetime.now(UTC))  # type: ignore[arg-type] -- a matrix role code


async def _apply(
    db: MigratedDatabase, document: CatalogDocumentV2, *, dry_run: bool = False
) -> object:
    return await ops.import_v2(
        _ops(db), document, SHA, OPERATOR, "W-01-T07 probe", environment="test", dry_run=dry_run
    )


async def _log(db: MigratedDatabase) -> int:
    seed = Seeder(db.superuser_dsn)
    return int(cast(int, await seed.value("SELECT count(*) FROM integration_catalog_imports")))


async def test_ac32_a_dry_run_writes_nothing_and_an_apply_logs_one_import(
    db: MigratedDatabase,
) -> None:
    before = await _log(db)
    planned = cast(ops.ImportResult, await _apply(db, _doc(_row("karbon")), dry_run=True))
    assert planned.plan.added == ("karbon",) and planned.written == ()
    assert await _log(db) == before
    applied = cast(ops.ImportResult, await _apply(db, _doc(_row("karbon"))))
    assert applied.written == (("karbon", "added"),) and applied.matches_plan
    assert await _log(db) == before + 1
    again = cast(ops.ImportResult, await _apply(db, _doc(_row("karbon"))))
    assert again.written == () and not again.plan.writes
    assert await _log(db) == before + 1


async def test_ac32_a_dropped_workbench_row_is_unpublished_not_deleted(
    db: MigratedDatabase,
) -> None:
    await _apply(db, _doc(_row("karbon"), _row("canopy")))
    result = cast(ops.ImportResult, await _apply(db, _doc(_row("karbon"))))
    assert ("canopy", "unpublished") in result.written
    status = await Seeder(db.superuser_dsn).value(
        "SELECT listing_status FROM integration_catalog WHERE key = 'canopy'"
    )
    assert status == "hidden"


async def test_the_app_reads_the_workbench_but_cannot_import(db: MigratedDatabase) -> None:
    await _apply(db, _doc(_row("karbon")))  # its own row: not another test's (alone, xdist)
    app = Seeder(db.app_url.replace("postgresql+asyncpg://", "postgresql://"))
    rows = await app.rows("SELECT key FROM integration_catalog_workbench()")
    assert "karbon" in {r["key"] for r in rows}
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.rows(
            "SELECT * FROM integration_catalog_import('[]'::jsonb, 'x', 'test', $1, 'n')", SHA
        )


async def test_ac4_ac1_with_no_adapter_registered_nothing_is_available(
    db: MigratedDatabase,
) -> None:
    await _apply(db, _doc(_row("karbon"), _row("adp", listing_status="coming_soon")))
    viewer = await _person(db)
    found = await catalogue(viewer)
    by_key = {t.row.key: t for t in found.tiles}
    assert by_key["karbon"].status == "coming_soon" and by_key["adp"].status == "coming_soon"
    assert found.counts["available"] == 0
    assert found.counts["all"] == found.counts["coming_soon"] + found.counts["connected"]
    search = await catalogue(viewer, q="KARB")
    assert [t.row.key for t in search.tiles] == ["karbon"]
    assert search.categories == found.categories  # catalogue totals ignore the search (AC-2)


async def test_ac31_ac33_notify_me_then_availability_tells_once(db: MigratedDatabase) -> None:
    await _apply(db, _doc(_row("karbon"), _row("adp", listing_status="coming_soon")))
    viewer = await _person(db, None)
    assert await interest(viewer, "adp") is True
    assert await interest(viewer, "adp") is False  # idempotent
    told = cast(ops.ImportResult, await _apply(db, _doc(_row("karbon"), _row("adp"))))
    assert told.plan.became_available == ("adp",) and told.told == 1
    seed = Seeder(db.superuser_dsn)
    notified = await seed.value(
        "SELECT notified_at FROM integration_interest WHERE tenant_id = $1", viewer.tenant_id
    )
    events = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'integration.available'",
        viewer.tenant_id,
    )
    assert notified is not None and events == 1
    # A later apply that changes the row again tells nobody twice.
    again = cast(
        ops.ImportResult,
        await _apply(db, _doc(_row("karbon"), _row("adp", description="Payroll."))),
    )
    assert again.told == 0
