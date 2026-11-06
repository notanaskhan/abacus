"""A-06-T28 (TASK-3380; DEC-2373) against Postgres: Northwind's completion loads through the
services, and code's figures foot to AUD-15, AUD-16 and AUD-17."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.review_matrix import matrix
from abacus.modules.assurance.sum_service import sum_view
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    BY_LABEL,
    TENANT,
    engagement_id_of,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database, object_store: str) -> Iterator[Database]:
    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(
                own_db.superuser_dsn, "2026-10-21T14:10", slices=("completion",), wait=False
            )
        finally:
            await dispose_engine()

    with pytest.MonkeyPatch.context() as patch:
        # `could` reads memberships through the identity engine: this database's.
        patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
        settings.cache_clear()
        forget_flags()
        asyncio.run(load())
        yield own_db
    settings.cache_clear()
    forget_flags()


async def _rows(loaded: Database, sql: str) -> list[tuple[object, ...]]:
    seed = Seeder(loaded.superuser_dsn)
    return [tuple(r) for r in await seed.rows(sql, TENANT)]


async def test_ac_nine_findings_in_the_designed_bands(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT f.ref, f.route, d.status, d.severity_concluded FROM audit_findings f "
        "LEFT JOIN deficiencies d ON d.finding_id = f.id WHERE f.tenant_id = $1 ORDER BY f.ref",
    )
    assert [r[0] for r in found] == [f"F-0{n}" for n in range(1, 10)]
    by = {r[0]: r for r in found}
    assert by["F-01"][2:] == ("concluded", "significant_deficiency")
    assert by["F-02"][2:] == ("concluded", "deficiency")
    assert by["F-03"][2] == "proposed"
    assert all(by[f"F-0{n}"][1] == "converted_to_misstatement" for n in range(5, 10))


async def test_ac_the_misstatements_read_as_the_design_and_code_projects_f07(
    loaded: Database,
) -> None:
    found = await _rows(
        loaded,
        "SELECT ref, type, nature, status, amount, projection->>'projected' "
        "FROM audit_misstatements WHERE tenant_id = $1 ORDER BY ref",
    )
    assert [(r[0], r[3]) for r in found] == [
        ("AJE-1", "booked"),
        ("BCT-1", "below_ct"),
        ("PAJE-1", "passed_on_sum"),
        ("PAJE-2", "passed_on_sum"),
        ("PY-1", "confirmed"),
        ("RJE-1", "booked"),
    ]
    paje = next(r for r in found if r[0] == "PAJE-1")
    assert paje[1] == "projected"
    assert (Decimal(str(paje[4])), paje[5]) == (Decimal("35300.00"), "35267.20")


async def test_ac_the_sum_foots_to_aud16(loaded: Database) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    item = await Seeder(loaded.superuser_dsn).value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        engagement_id_of(BY_LABEL["A1"]),
    )
    view = await sum_view(TenantContext(TENANT, "system", "test"), cast(UUID, item), None)
    assert view.result.rollover == Decimal("34150.00")
    assert view.result.iron_curtain == Decimal("22250.00")
    assert view.below_ct_total == Decimal("4210.00")
    await dispose_engine()


async def test_ac_margaret_concluded_on_a_frozen_snapshot(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT status FROM decision_cards WHERE tenant_id = $1 AND kind = 'sum_conclusion'",
    )
    assert found == [("decided",)]


async def test_ac_marcus_l2_on_ebp04_reads_changed_after_ana_changes_the_paper(
    loaded: Database,
) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    engagement = engagement_id_of(BY_LABEL["A1"])
    found = await matrix(TenantContext(TENANT, "system", "test"), engagement)
    row = next(r for r in found.rows if r.code == "EBP-04")
    assert [c.state for c in row.cells[:2]] == ["signed", "stale"]
    await dispose_engine()


async def test_ac_14_notes_in_their_states(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT status, count(*) FROM reviewable_notes n JOIN workpapers w ON w.id = n.target_id "
        "WHERE n.tenant_id = $1 GROUP BY status ORDER BY status",
    )
    assert found == [("cleared", 11), ("open", 2), ("responded", 1)]


async def test_ac_three_statement_versions_and_danas_approval(loaded: Database) -> None:
    versions = await _rows(
        loaded,
        "SELECT version_no FROM statement_versions WHERE tenant_id = $1 ORDER BY version_no",
    )
    assert versions == [(1,), (2,), (3,)]
    approved = await _rows(
        loaded,
        "SELECT event, channel, evidence_version_id IS NOT NULL FROM statement_approvals "
        "WHERE tenant_id = $1",
    )
    assert approved == [("approved_by_management", "record", True)]
