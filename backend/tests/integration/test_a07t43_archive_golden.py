"""A-07-T43 (TASK-6736; ADR-078, author notanaskhan): the archive golden figures on the loaded
Brightwater Hale tenant. The `archive` slice loads Northwind to Fri Oct 9, 2026 at 10:05 AM; the
binder the archive will index (26 workpapers in A to E, 24 source documents, 23 run logs,
5 independence confirmations) and the letter's paragraph mapping (DF-27: 12, 13 and 15 on, the
going-concern 14 off) are read back from the services that compute them and held to
`brightwater_hale/archive_figures.json`. A one-row drift fails.

Two drifts are recorded as findings (strict xfail, so each flips to a failure the day it is
fixed and the mark must come off), found by this test at the S35 round 2 end pass:
- representations 12 (late remittance) and 15 (related party) are off: no slice seeds
  `ebp_late_remittances` or `related_parties` for Northwind (A-05's AUD-27 and the PI papers);
- binder sections A to E count 2, 3, 5, 0, 0 rail rows with a state, not 6, 3, 7, 6, 4: the
  planning, completion and reporting papers have no section provider yet.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, Final, cast

import pytest
import pytest_asyncio

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.archive_gate import binder_sections
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio(loop_scope="module")
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
FINDING: Final = pytest.mark.xfail(
    strict=True,
    reason="A-07-T43 finding (TASK-6740): the scenario drifts from the design",
)


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def loaded(
    own_db: Database, migrated_db: MigratedDatabase, object_store: str
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID, Seeder]]:
    del migrated_db, object_store
    patch = pytest.MonkeyPatch()
    patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
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
    yield engagement, item, seed
    patch.undo()


async def _included(seed: Seeder, item: uuid.UUID) -> dict[int, bool]:
    reps = cast(
        str,
        await seed.value(
            "SELECT representations::text FROM representation_letter_versions "
            "WHERE work_item_id = $1 ORDER BY version_no DESC LIMIT 1",
            item,
        ),
    )
    return {
        int(r["n"]): bool(r["included"])
        for r in cast(list[dict[str, Any]], json.loads(reps))  # Any: JSON
        if int(r["n"]) > BOOK["rep_letter"]["general"]
    }


async def test_ac_df27_certified_investments_on_and_going_concern_off(
    loaded: tuple[uuid.UUID, uuid.UUID, Seeder],
) -> None:
    _engagement, item, seed = loaded
    included = await _included(seed, item)
    assert sorted(included) == BOOK["rep_letter"]["specific"]
    assert included[13] is True  # Harborline's certification (limited scope, 103(a)(3)(C))
    assert included[14] is False  # no substantial doubt: the going-concern representation is off


@FINDING
async def test_ac_df27_late_remittance_and_related_party_are_on(
    loaded: tuple[uuid.UUID, uuid.UUID, Seeder],
) -> None:
    _engagement, item, seed = loaded
    included = await _included(seed, item)
    assert sorted(n for n, on in included.items() if on) == BOOK["rep_letter"]["northwind_on"]


@FINDING
async def test_ac_the_binder_holds_26_workpapers_24_documents_23_logs_5_confirmations(
    loaded: tuple[uuid.UUID, uuid.UUID, Seeder],
) -> None:
    engagement, item, _seed = loaded
    book = BOOK["binder"]
    sections = await binder_sections(
        TenantContext(TENANT, "system", "a07t43-golden"), engagement, item
    )
    by = {s.section: s for s in sections}
    assert [by[k].workpapers if k in by else 0 for k in "ABCDE"] == book["sections"]
    assert sum(s.source_documents for s in sections) == book["source_documents"]
    assert sum(s.run_logs for s in sections) == book["agent_run_logs"]
    assert sum(s.independence for s in sections) == book["independence"]
