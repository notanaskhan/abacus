"""F-04-T31 against Postgres (F-04.21; ADR-085): the committed fixture JSON is what `make
seed-demo` + the API answer at E0 on the exported MVP read paths, byte for byte. Re-export with
`make fixtures SNAPSHOT=E0` when the scenario or a read model changes; this test then holds the
files to the database.

The load gets its own database: the session's `migrated_db` holds other loads."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic import fixture_export
from abacus_tools.synthetic.scenarios.brightwater_hale import (
    SCENARIO_HASH,
    SCENARIO_VERSION,
)

from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_f04_21_the_committed_e0_fixtures_equal_seed_demo_through_the_api(
    own_db: Database,
) -> None:
    await fixture_export.load("E0", own_db.superuser_dsn, own_db.app_url)
    captured = await fixture_export.capture(
        "E0", app_url=own_db.app_url, identity_url=own_db.identity_url
    )
    rendered = fixture_export.render("E0", captured)
    files = fixture_export.exported_files(fixture_export.EXPORTED, "E0")
    committed = {p.name: p.read_text(encoding="utf-8") for p in files}
    assert sorted(committed) == sorted(rendered), "run `make fixtures SNAPSHOT=E0`"
    for name, text in rendered.items():
        assert committed[name] == text, f"{name} differs: run `make fixtures SNAPSHOT=E0`"


def test_f04_21_every_fixture_names_its_scenario_version_snapshot_and_persona() -> None:
    files = fixture_export.exported_files(fixture_export.EXPORTED, "E0")
    assert len(files) == len(fixture_export.READS)
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["scenario"] == {
            "version": SCENARIO_VERSION,
            "hash": SCENARIO_HASH,
            "snapshot": "E0",
            "slices": list(fixture_export.SLICES),
        }, path.name
        assert doc["persona"] and doc["request"].startswith("GET /v1/"), path.name


def test_f04_21_the_exported_reads_are_the_mvp_paths_with_a_persona_each() -> None:
    assert [(r.name, r.persona) for r in fixture_export.READS] == [
        ("firm-clients", "grace-holloway"),
        ("engagements", "hannah-leclerc"),
        ("northwind-request-items", "hannah-leclerc"),
        ("binders", "daniel-reyes"),
        ("portal-home", "claire-feld"),
    ]
