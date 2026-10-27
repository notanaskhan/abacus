"""F-04-T29 (ADR-078; F-04.27): the F-04-T12 goldens read back from a database E0 was loaded into.

The goldens are transcribed from the epic and the blueprint, not from the code; this test reads
them from `tests/golden/scenario/brightwater_hale/` and holds the loaded rows to them:

- `clients.json`: every client by name and nothing else, with its kind (in the record's
  vocabulary), office, relationship partner, portal status and every entity (TASK-393); attest is
  derived from the client's engagements (DEC-128), so it is not compared here;
- `practice_counts.yaml`: 184 clients, 46 staff seats by office (22 / 14 / 10), 3 offices, and a
  holdout (Fairhaven, Copperleaf) loading 183;
- `audits.yaml`: the 27 roster rows (engagement entity, type group, phase, engagement partner).

`northwind.yaml` and `granite_peak.yaml` hold financial figures the scenario does not load yet
(their engines own them: A-02, A-04, A-05); they stay arithmetic goldens until then.

Each load gets its own database: the session's `migrated_db` holds the loader test's E0.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

# The three E0 tests read one load in this module's database: one xdist worker runs them all
# (`--dist loadgroup` otherwise hands each test to whichever worker is free, where the module's
# database is fresh and empty), and each loads E0 itself if it runs first.
pytestmark = [pytest.mark.asyncio, pytest.mark.xdist_group(name="f04t29_loaded_goldens")]
TENANT = loader.TENANT
GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "scenario" / "brightwater_hale"
Json = dict[str, object]
# AUD-01's stage words (audits.yaml) as the assurance phase codes.
PHASES = {
    "Planning": "planning",
    "Fieldwork": "fieldwork",
    "In review": "in_review",
    "Ready to release": "ready_to_release",
    "Released": "released",
}
# CLI-01's client kinds (clients.json) in the client record's vocabulary (organisations, 0082).
RECORD_KINDS = {
    "individual": "household",
    "household": "household",
    "business": "business",
    "partnership": "business",
    "exempt_org": "nonprofit",
    "trust": "trust_family",
    "estate": "trust_family",
    "plan": "plan_sponsor",
}
# The F-04.10 type groups as the engagement type codes.
TYPE_GROUPS = {
    "EBP": {"ebp_audit"},
    "FS audit": {"fs_audit"},
    "Review": {"review"},
    "Compilation/preparation": {"compilation", "preparation"},
}


def _cases(name: str) -> dict[str, Json]:
    data = cast(Json, yaml.safe_load((GOLDEN / name).read_text(encoding="utf-8")))
    return {str(c["id"]): c for c in cast(list[Json], data["cases"])}


def _terms(case: Json) -> dict[str, Decimal]:
    terms = cast(dict[str, object], cast(Json, case["inputs"])["terms"])
    return {k: Decimal(str(v)) for k, v in terms.items()}


def _clients() -> list[Json]:
    data = cast(Json, json.loads((GOLDEN / "clients.json").read_text(encoding="utf-8")))
    return cast(list[Json], data["clients"])


def _total(case: Json) -> Decimal:
    return Decimal(str(cast(Json, case["expected"])["total"]))


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def _load(db: Database, holdouts: tuple[str, ...] = ()) -> Seeder:
    configure_engine(db.app_url)
    await loader.load(db.superuser_dsn, "E0", holdouts, wait=False)
    return Seeder(db.superuser_dsn)


async def _e0(db: Database) -> Seeder:
    """E0 in this module's database: loaded here unless an earlier test of the module loaded it."""
    seed = Seeder(db.superuser_dsn)
    if await seed.value("SELECT count(*) FROM clients WHERE tenant_id = $1", TENANT) == 0:
        return await _load(db)
    configure_engine(db.app_url)
    return seed


async def _tally(seed: Seeder, sql: str) -> dict[str, Decimal]:
    return {str(r[0]): Decimal(int(r[1])) for r in await seed.rows(sql, TENANT)}


async def test_the_loaded_e0_matches_the_practice_count_and_client_goldens(
    own_db: Database,
) -> None:
    seed = await _e0(own_db)
    counts = _cases("practice_counts.yaml")

    clients = Decimal(
        int(
            cast(
                int, await seed.value("SELECT count(*) FROM clients WHERE tenant_id = $1", TENANT)
            )
        )
    )
    assert clients == _total(counts["clients-184"])
    by_office = await _tally(
        seed,
        "SELECT o.name, count(*) FROM memberships m JOIN offices o ON o.id = m.office_id "
        "WHERE m.tenant_id = $1 AND m.kind = 'staff' AND m.status = 'active' GROUP BY 1",
    )
    assert by_office == _terms(counts["seats-46-by-office"])
    assert sum(by_office.values()) == _total(counts["seats-46-named-and-generator"])
    offices = await seed.value("SELECT count(*) FROM offices WHERE tenant_id = $1", TENANT)
    assert Decimal(int(cast(int, offices))) == _total(counts["offices-3"])

    golden = _clients()
    rows = await seed.rows(
        "SELECT c.name, array_agg(ce.name ORDER BY ce.name) AS entities FROM clients c "
        "LEFT JOIN client_entities ce ON ce.tenant_id = c.tenant_id AND ce.client_id = c.id "
        "WHERE c.tenant_id = $1 GROUP BY c.id, c.name",
        TENANT,
    )
    loaded = {str(r["name"]): set(r["entities"]) for r in rows}
    assert sorted(loaded) == sorted(str(c["name"]) for c in golden)
    for client in golden:
        # The client's primary entity is there; audits may add a plan entity of their own.
        assert cast(list[str], client["entities"])[0] in loaded[str(client["name"])], client


async def test_the_loaded_clients_carry_the_goldens_facts(own_db: Database) -> None:
    seed = await _e0(own_db)
    rows = await seed.rows(
        "SELECT c.name, c.kind, o.name AS office, m.initials AS partner, c.is_attest_client, "
        "c.portal_status, array_agg(ce.name ORDER BY ce.name) AS entities FROM clients c "
        "LEFT JOIN offices o ON o.id = c.primary_office_id "
        "LEFT JOIN memberships m ON m.tenant_id = c.tenant_id "
        "AND m.user_id = c.relationship_partner_id "
        "LEFT JOIN client_entities ce ON ce.tenant_id = c.tenant_id AND ce.client_id = c.id "
        "WHERE c.tenant_id = $1 GROUP BY c.id, c.name, c.kind, o.name, m.initials, "
        "c.is_attest_client, c.portal_status",
        TENANT,
    )
    loaded = {str(r["name"]): r for r in rows}
    for client in _clients():
        row = loaded[str(client["name"])]
        assert (
            row["kind"],
            row["office"],
            row["partner"],
            row["portal_status"],
            set(cast(list[str], client["entities"])) <= set(row["entities"]),
        ) == (
            RECORD_KINDS[str(client["kind"])],
            client["office"],
            client["partner"],
            client["portal"],
            True,
        ), client["name"]


async def test_the_loaded_e0_matches_the_audit_roster_golden(own_db: Database) -> None:
    seed = await _e0(own_db)
    roster = cast(Json, _cases("audits.yaml")["audits-27-roster-rows"]["inputs"])
    groups = cast(dict[str, str], roster["groups"])
    rows = await seed.rows(
        "SELECT ce.name AS entity, e.type, a.phase, m.initials AS ep FROM engagements e "
        "JOIN client_entities ce ON ce.tenant_id = e.tenant_id AND ce.id = e.client_entity_id "
        "JOIN assurance_work_items a ON a.tenant_id = e.tenant_id AND a.engagement_id = e.id "
        "JOIN engagement_members em ON em.tenant_id = e.tenant_id AND em.engagement_id = e.id "
        "AND em.role = 'engagement_partner' "
        "JOIN memberships m ON m.tenant_id = e.tenant_id AND m.user_id = em.user_id "
        "WHERE e.tenant_id = $1",
        TENANT,
    )
    loaded = sorted(
        (str(r["entity"]), str(r["type"]), str(r["phase"]), str(r["ep"])) for r in rows
    )
    expected: list[tuple[str, str, str, str]] = []
    for ref, entity, type_, phase, ep in cast(list[list[str]], roster["rows"]):
        codes = TYPE_GROUPS[groups[type_]]
        match = next(
            (row for row in loaded if row[0] == entity and row[1] in codes),
            None,
        )
        assert match is not None, f"{ref}: no {type_} engagement for {entity}"
        expected.append((entity, match[1], PHASES[phase], ep))
    assert loaded == sorted(expected)
    by_type = _cases("audits.yaml")["audits-27-by-type"]
    assert Decimal(len(loaded)) == _total(by_type)


HOLDOUTS = ("holdout-fairhaven-183", "holdout-copperleaf-183")


@pytest.fixture(params=HOLDOUTS)
def holdout_db(
    request: pytest.FixtureRequest, migrated_db: MigratedDatabase
) -> Iterator[tuple[Json, Database]]:
    """A database of its own per holdout (provisioned outside the test's event loop)."""
    case = _cases("practice_counts.yaml")[cast(str, request.param)]
    with provisioned_database(roundtrip=False) as database:
        yield case, database
    configure_engine(migrated_db.app_url)


async def test_a_holdout_loads_one_client_fewer(holdout_db: tuple[Json, Database]) -> None:
    case, database = holdout_db
    name = str(cast(Json, case["scenario"])["holdout"])
    seed = await _load(database, (name,))
    clients = await seed.value("SELECT count(*) FROM clients WHERE tenant_id = $1", TENANT)
    assert Decimal(int(cast(int, clients))) == _total(case)
