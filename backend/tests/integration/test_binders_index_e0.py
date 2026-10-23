"""P-06-T11 on the loaded Brightwater Hale tenant (SPEC-319 AC-10; P-06 §3.2 Story 2.1; BND-01
a, b, d): Grace Holloway, `client_service` on the tax engagements (DEC-20), opens Binders with
Service │ Tax returns and Season │ TY2025 at Mon Sep 14, 2026, 9:24 AM Central. The tiles read
1 · 48 · 0 · 40 · 152 = 241, the part facet 224 returns · 17 second-part binders, None in 30 days
keeps Fenwick only (Aug 11, 34 days), and TY2026 is empty. Figures typed from BND-01 and P-06
§3.2, not from the code.

The load gets its own database, as the P-06-T08 scenario test does."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.binder_index import IndexFilters, list_binders
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.people import FIRM_ROLES, slug_of
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # 9:24 AM Central
GRACE = uuid.UUID(stable_id(f"user:{slug_of('Grace Holloway')}"))


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_ac10_grace_sees_the_ty2025_tax_binders_footing_to_241(
    own_db: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    await loader.load(own_db.superuser_dsn, "E0", slices=("binders",), wait=False)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'P-06-T11 E0') "
        "ON CONFLICT DO NOTHING",
        TENANT,
    )
    # DEC-20: Grace's need-to-know is client_service on the tax engagements.
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "SELECT DISTINCT tenant_id, engagement_id, $2::uuid, 'client_service' FROM work_items "
        "WHERE tenant_id = $1 AND kind = 'tax_return' ON CONFLICT DO NOTHING",
        TENANT,
        GRACE,
    )
    grace = AuthContext(
        tenant=TenantContext(TENANT, "human", str(GRACE)),
        user_id=GRACE,
        membership_id=uuid.uuid4(),
        firm_role=FIRM_ROLES["GH"],  # firm_admin: no firm-wide binder.read (DEC-20)
        mfa_at=T0 - timedelta(minutes=1),
    )

    with clock.frozen(T0):
        a = await list_binders(
            grace, IndexFilters(service="tax_returns", season="TY2025"), None, 15
        )
        b = await list_binders(
            grace,
            IndexFilters(service="tax_returns", season="TY2025", client_activity="none_30_days"),
            None,
            15,
        )
        d = await list_binders(
            grace, IndexFilters(service="tax_returns", season="TY2026"), None, 15
        )

    # BND-01a: 1 + 48 + 0 + 40 + 152 = 241; "241 TY2025 binders · 224 returns · 17 second-part".
    assert a.counts == {
        "draft": 1,
        "published": 48,
        "unpublished": 0,
        "complete": 40,
        "closed": 152,
    }
    assert a.total == 241 and len(a.items) == 15 and a.next_cursor is not None
    assert {f.value: f.n for f in a.facets["part"]} == {"1": 224, "2+": 17}
    assert {f.value: f.n for f in a.facets["season"]}["TY2025"] == 241
    # Every return sits in one of the three offices (§9.1), so the office chip foots too.
    assert {f.label for f in a.facets["office"]} == {"Chicago", "Denver", "New York"}
    assert sum(f.n for f in a.facets["office"]) == 241
    # BND-01b: Fenwick, silent since Aug 11 (34 days).
    assert [(r.client_name, r.status) for r in b.items] == [
        ("Fenwick Family Foundation", "published")
    ]
    assert b.items[0].last_client_activity_at is not None
    last = b.items[0].last_client_activity_at.astimezone(clock.FIRM_ZONE).date()
    assert (T0.astimezone(clock.FIRM_ZONE).date() - last).days == 34
    # BND-01d: no TY2026 binders yet.
    assert (d.items, d.total) == ([], 0)
    assert sum(d.counts.values()) == 0

    # Ridgeline's first binder is Complete, marked done by Owen Calder on Jun 1.
    ridgeline = [r for r in a.items if r.client_name == "Ridgeline Property Partners, LP"]
    for row in ridgeline:
        if row.status == "complete":
            assert row.marked_done_by_name == "Owen Calder"
    await dispose_engine()
    settings.cache_clear()
    forget_flags()
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
