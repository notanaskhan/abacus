"""TASK-2152 (ADR-342; DEC-1279): migration 0407, the e-signature catalogue category.

Before 0407 an `esignature` catalogue row is refused by the category CHECK; after it, it is
accepted; a downgrade is refused while such a row exists and passes once it is gone; up again
leaves the CHECK in place.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0406"
_ROW = (
    "INSERT INTO integration_catalog (key, name, category, ownership_mode, surfaces, "
    "listing_status, scopes, icon, tone, sort_order, loaded_by) VALUES ('probe_esign', "
    "'Probe', 'esignature', 'firm', ARRAY['workbench'], 'hidden', "
    '\'{"read": [{"code": "submissions.read", "label": "Status"}]}\'::jsonb, '
    "'signature', 'espresso', 1, 'probe-op')"
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_0407_admits_esignature_and_downgrades_only_without_it(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(seed.run(_ROW))
    migrate(private_db.owner_url, "0407")
    asyncio.run(seed.run(_ROW))
    with pytest.raises(Exception, match="integration_catalog_category_check"):
        migrate(private_db.owner_url, BEFORE, down=True)
    asyncio.run(seed.run("DELETE FROM integration_catalog WHERE key = 'probe_esign'"))
    migrate(private_db.owner_url, BEFORE, down=True)
    migrate(private_db.owner_url, "head")
    asyncio.run(seed.run(_ROW))
