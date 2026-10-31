"""T-02-T23 (TASK-2429; DEC-1477) against Postgres: the `tax_content` slice loads through the
import and decision paths at E0.

The row's acceptance: "Every POR-05, TXP-12 and POR-13 figure foots in seed tests and no content is
loaded by a migration." Here the loaded tenant agrees with the slice's own figures: nine K-1
packages (Ridgeline 5 drafts, Bluestem 2 finals, Calloway 2 drafts) whose recipients name their
delivery contacts, Ridgeline's two drafts shared with the Feld and Shah 1040s, the organizer at 22
of 24 on the Feld 2025 return, Kevin's team question, Dana's four inquiries and Luis's two
questions sent; Nora Calloway and the Pell Street member sign in as client users.
The load gets its own database (the session's `migrated_db` holds other loads)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

TENANT = loader.TENANT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database) -> Database:
    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(own_db.superuser_dsn, "E0", slices=("tax_content",), wait=False)
        finally:
            await dispose_engine()

    asyncio.run(load())
    return own_db


async def test_ac1_the_loaded_tenant_foots_to_the_slice(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    packages = await seed.rows(
        "SELECT c.name, p.status, p.is_final_set, r.contact_id IS NOT NULL AS has_contact "
        "FROM k1_packages p JOIN k1_recipients r ON r.id = p.recipient_id "
        "JOIN work_items w ON w.id = p.work_item_id JOIN clients c ON c.id = w.client_id "
        "WHERE p.tenant_id = $1",
        TENANT,
    )
    by_client: dict[str, int] = {}
    for row in packages:
        by_client[row["name"]] = by_client.get(row["name"], 0) + 1
    assert by_client == {
        "Ridgeline Property Partners, LP": 5,
        "Bluestem Analytics, LLC": 2,
        "Calloway Family Trust": 2,
    }
    assert all(row["has_contact"] for row in packages)
    finals = {row["name"] for row in packages if row["is_final_set"]}
    assert finals == {"Bluestem Analytics, LLC"}
    shared = await seed.value(
        "SELECT count(*) FROM k1_handoffs WHERE tenant_id = $1 AND status = 'draft_shared'",
        TENANT,
    )
    assert shared == 2
    answered = await seed.value(
        "SELECT count(DISTINCT a.question_id) FROM answer_versions a JOIN questions x "
        "ON x.id = a.question_id JOIN questionnaires q ON q.id = x.questionnaire_id "
        "WHERE q.tenant_id = $1 AND q.kind = 'organizer'",
        TENANT,
    )
    total = await seed.value(
        "SELECT count(*) FROM questions x JOIN questionnaires q ON q.id = x.questionnaire_id "
        "WHERE q.tenant_id = $1 AND q.kind = 'organizer'",
        TENANT,
    )
    assert (answered, total) == (22, 24)
    sent = await seed.rows(
        "SELECT q.kind, q.title, count(x.id) AS n FROM questionnaires q JOIN questions x "
        "ON x.questionnaire_id = q.id WHERE q.tenant_id = $1 AND q.kind <> 'organizer' "
        "AND x.sent_at IS NOT NULL GROUP BY q.kind, q.title ORDER BY q.title",
        TENANT,
    )
    assert [(r["title"], r["n"]) for r in sent] == [
        ("FY2026 audit — questions", 2),
        ("PY2025 audit — fraud risk inquiries", 4),
        ("Questions from your team", 1),
    ]
    people = await seed.value(
        "SELECT count(*) FROM contacts WHERE tenant_id = $1 AND user_id IS NOT NULL "
        "AND display_name IN ('Nora Calloway', 'Pell Street Ventures LLC · authorized member')",
        TENANT,
    )
    assert people == 2
