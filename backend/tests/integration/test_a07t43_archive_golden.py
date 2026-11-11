"""A-07-T43 (TASK-6736; ADR-078, author notanaskhan): the archive golden figures on the loaded
Brightwater Hale tenant. The `archive` slice loads Northwind to Fri Oct 9, 2026 at 10:05 AM;
the binder the archive will index (26 workpapers in A to E, 24 source documents, 23 run logs,
5 independence confirmations) and the letter's paragraph mapping (DF-27: 12, 13 and 15 on, the
going-concern 14 off) are read back from the services that compute them and held to
`brightwater_hale/archive_figures.json`. A one-row drift on either side fails."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.archive_gate import binder_sections
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
BOOK: Final = cast(
    dict[str, dict[str, Any]],  # Any: JSON
    json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "golden"
            / "scenario"
            / "brightwater_hale"
            / "archive_figures.json"
        ).read_text(encoding="utf-8")
    ),
)


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_ac_the_binder_and_the_letters_mapping_on_seed_demo(
    own_db: Database,
    migrated_db: MigratedDatabase,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del migrated_db, object_store
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "2026-10-09T10:05", slices=("archive",), wait=False)
    seed = Seeder(own_db.superuser_dsn)
    engagement = loader.engagement_id_of(BY_LABEL["A1"])
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
    book = BOOK["binder"]
    sections = await binder_sections(
        TenantContext(TENANT, "system", "a07t43-golden"), engagement, item
    )
    by = {s.section: s for s in sections}
    assert [by[k].workpapers for k in "ABCDE"] == book["sections"]
    assert sum(s.workpapers for s in sections) == book["workpapers"]
    assert sum(s.source_documents for s in sections) == book["source_documents"]
    assert sum(s.run_logs for s in sections) == book["agent_run_logs"]
    assert sum(s.independence for s in sections) == book["independence"]
    letter = BOOK["rep_letter"]
    reps = cast(
        str,
        await seed.value(
            "SELECT representations::text FROM representation_letter_versions "
            "WHERE work_item_id = $1 ORDER BY version_no DESC LIMIT 1",
            item,
        ),
    )
    included = {
        int(r["n"]): bool(r["included"])
        for r in cast(list[dict[str, Any]], json.loads(reps))  # Any: JSON
        if int(r["n"]) > letter["general"]
    }
    assert sorted(n for n, on in included.items() if on) == letter["northwind_on"]
    assert sorted(n for n, on in included.items() if not on) == letter["northwind_off"]
