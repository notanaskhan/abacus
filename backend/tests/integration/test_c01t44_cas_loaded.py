"""C-01-T44 (TASK-8700; DEC-5700) on the loaded Brightwater Hale tenant: the `cas` slice loads the
August portfolio through the closes services, so CLS-01's tiles read 3 + 11 + 5 + 3 with the
initials pairs of the fixture book, Copperleaf's "2026 Close" has twelve closes, its plan reads
v1 the planner's draft (discarded by Raj's v2), v2 and v3 published with v4 a draft (seven
client requests), and the seven exceptions are open; with `--holdout copperleaf` none of
Copperleaf's rows load, so J02 can create the client."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from uuid import UUID

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_slice as cas
from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as close
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

_AUGUST = (
    "SELECT c.status, (SELECT name FROM clients WHERE id = w.client_id) AS client "
    "FROM closes c JOIN work_items w ON w.id = c.work_item_id WHERE c.period = '2026-08'"
)


@pytest.fixture
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


async def _load(
    own_db: Database, monkeypatch: pytest.MonkeyPatch, holdouts: tuple[str, ...]
) -> Seeder:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "E0", holdouts=holdouts, slices=("cas",), wait=False)
    return Seeder(own_db.superuser_dsn)


async def test_ac_the_august_portfolio_loads_through_the_services(
    own_db: Database,
    migrated_db: MigratedDatabase,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_db, object_store
    seed = await _load(own_db, monkeypatch, ())
    august = await seed.rows(_AUGUST)
    assert len(august) == 22
    assert Counter(r["status"] for r in august) == Counter(c.status for c in close.PORTFOLIO)
    copperleaf = [r for r in august if r["client"] == close.COPPERLEAF]
    assert [r["status"] for r in copperleaf] == ["in_progress"]
    year = await seed.value(
        "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'close'",
        UUID(loader.COPPERLEAF_CLOSE_ENGAGEMENT),
    )
    assert year == 12
    versions = await seed.rows(
        "SELECT v.version, v.status, (SELECT count(*) FROM close_plan_rows r "
        "WHERE r.version_id = v.id) AS n FROM close_plan_versions v ORDER BY v.version"
    )
    assert [(r["version"], r["status"], r["n"]) for r in versions] == [
        (1, "discarded", 0),
        (2, "published", 22),
        (3, "published", 23),
        (4, "draft", 23),
    ]
    templates = await seed.value(
        "SELECT count(*) FROM close_templates WHERE key = $1", cas.TEMPLATE_KEY
    )
    assert templates == 1
    open_exceptions = await seed.value(
        "SELECT count(*) FROM issues WHERE work_item_id = $1 AND status = 'open'",
        UUID(loader.COPPERLEAF_CLOSE_ITEM),
    )
    assert open_exceptions == len(close.ISSUES)
    # A second load writes nothing.
    await loader.load(own_db.superuser_dsn, "E0", slices=("cas",), wait=False)
    assert len(await seed.rows(_AUGUST)) == 22


async def test_ac_the_copperleaf_holdout_loads_no_copperleaf_close(
    own_db: Database,
    migrated_db: MigratedDatabase,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_db, object_store
    seed = await _load(own_db, monkeypatch, ("copperleaf",))
    august = await seed.rows(_AUGUST)
    assert len(august) == 21
    assert all(r["client"] != close.COPPERLEAF for r in august)
    assert await seed.value("SELECT count(*) FROM clients WHERE name = $1", close.COPPERLEAF) == 0
