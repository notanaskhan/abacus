"""P-10-T36 (TASK-6721; F-04.21; ADR-085): run #4127's committed fixture JSON at the 9:41 snapshot
is what `make seed-demo --slice agent_runs` + the API answer, byte for byte; and the projection the
dock draws from it is the handoff's (14 = 1 + 5 + 1 + 4 + 3, the trial balance done, materiality
blocked). Re-export with `make fixtures SNAPSHOT=2026-09-14T09:41`.

Row acceptance: "make seed-demo loads both runs, the goldens foot, and fixture mode and seed-demo
show identical run projections." #4118 stays fixture-only (DEC-3121: a firm-level run, which the
run reads refuse until P-10's firm-scope runs), so this holds #4127.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Final, cast

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic import fixture_export

from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
SNAPSHOT: Final = fixture_export.RUN_SNAPSHOT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


async def test_ac_seed_demo_and_the_committed_run_fixtures_are_identical(own_db: Database) -> None:
    await fixture_export.load(SNAPSHOT, own_db.superuser_dsn, own_db.app_url)
    captured = await fixture_export.capture(
        SNAPSHOT, app_url=own_db.app_url, identity_url=own_db.identity_url, found={}
    )
    rendered = fixture_export.render(SNAPSHOT, captured, {})
    files = fixture_export.exported_files(fixture_export.EXPORTED, SNAPSHOT)
    committed = {p.name: p.read_text(encoding="utf-8") for p in files}
    hint = f"run `make fixtures SNAPSHOT={SNAPSHOT}`"
    assert sorted(committed) == sorted(rendered), hint
    for name, text in rendered.items():
        assert committed[name] == text, f"{name} differs: {hint}"


def test_ac_the_exported_projection_is_the_handoffs() -> None:
    (view,) = [
        p
        for p in fixture_export.exported_files(fixture_export.EXPORTED, SNAPSHOT)
        if p.name.endswith("run-4127.json")
    ]
    body = cast(dict[str, object], json.loads(view.read_text(encoding="utf-8"))["body"])
    levels = cast(list[dict[str, int]], body["levels"])
    assert [lv["total"] for lv in levels] == [1, 5, 1, 4, 3]
    assert [lv["done"] for lv in levels] == [1, 0, 0, 0, 0]
    assert levels[1]["blocked"] == 1
    assert cast(dict[str, object], body["header"])["run_number"] == 4127
