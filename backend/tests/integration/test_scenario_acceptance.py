"""P-07-T40 against Postgres (TASK-1316; DEC-412): the `acceptance` slice loaded at the 2026-09-24
snapshot, through the services, then loaded again with nothing written. The figures are typed
from the CLI-06, CLI-07 and CLI-08 handoff specs and the ENG-05 canvas, not from the code:

- CLI-07 a, d: Thornbury's record, started by Grace Holloway from her intake (CLI-06; DEC-412),
  Moderate, three flags (two Medium, one
  Low), decided "Accept with conditions" by Daniel Reyes with three conditions owned by Samuel;
  the questionnaire is the firm's "Tax engagements v2" (nine sections).
- CLI-07 f: Meridian's FY2026 continuance opened on the FY2025 audit, by Margaret Okonkwo.
- ENG-05: budget hours MO 10, HL 37, MD 61, AC 40 and Kira Ross 18 (proposed); Thomas Whitcombe
  is the EQR, not a team member; Margaret's team approval.
- CLI-08 a, c: MO, TW, HL and MD confirmed, Ana Cruz not; seven names searched over Northwind,
  Harborline "Not adverse" by Hannah Leclerc; CLI-06 h: Harborline over the Thornbury client,
  cleared by Samuel Ito.

The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from abacus.kernel.db import configure_engine
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
SNAPSHOT = "2026-09-24"
SLICES = ("acceptance",)
SEATS = {s.initials: s for s in loader.SEATS}
THORNBURY = "Estate returns — final 1040 · 1041 · 706"


def user(initials: str) -> object:
    return loader.user_id_of(SEATS[initials])


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_the_acceptance_slice_loads_through_services_once(own_db: Database) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    slices = loader.expand_slices(SLICES)
    events = build(SNAPSHOT, slices=("audit_core", *slices)).events

    first = await loader.load(own_db.superuser_dsn, SNAPSHOT, slices=SLICES, wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    # The firm's questionnaires (CLI-07: "Tax engagements v2").
    templates = await seed.rows(
        "SELECT t.name, t.family, jsonb_array_length(v.sections) "
        "FROM acceptance_questionnaire_templates t JOIN acceptance_questionnaire_template_versions"
        " v ON v.template_id = t.id WHERE t.tenant_id = $1 ORDER BY t.name",
        TENANT,
    )
    assert [tuple(r) for r in templates] == [
        ("Audit & assurance v3", "audit_assurance", 10),
        ("Tax engagements v2", "tax", 9),
    ]

    # CLI-07 a, d: Thornbury.
    thornbury = await seed.rows(
        "SELECT r.id, r.kind, r.status, r.risk_rating, r.prepared_by FROM acceptance_records r "
        "JOIN engagements e ON e.id = r.engagement_id WHERE r.tenant_id = $1 AND e.name = $2",
        TENANT,
        THORNBURY,
    )
    assert len(thornbury) == 1
    record = thornbury[0]
    assert (record["status"], record["risk_rating"]) == ("decided", "moderate")
    assert record["prepared_by"] == user("GH")
    flags = await seed.rows(
        "SELECT severity, count(*) FROM acceptance_flags WHERE tenant_id = $1 AND record_id = $2 "
        "GROUP BY 1 ORDER BY 1",
        TENANT,
        record["id"],
    )
    assert {r[0]: r[1] for r in flags} == {"low": 1, "medium": 2}
    decision = await seed.rows(
        "SELECT option, decided_by FROM acceptance_decisions WHERE tenant_id = $1 "
        "AND record_id = $2",
        TENANT,
        record["id"],
    )
    assert [tuple(r) for r in decision] == [("accept_with_conditions", user("DR"))]
    owners = await seed.rows(
        "SELECT assignee_user_id FROM acceptance_conditions WHERE tenant_id = $1 "
        "AND record_id = $2 ORDER BY position",
        TENANT,
        record["id"],
    )
    assert [r[0] for r in owners] == [user("SI")] * 3

    # CLI-07 f: Meridian's continuance on the archived FY2025 audit.
    meridian = await seed.rows(
        "SELECT r.kind, r.status, r.prepared_by FROM acceptance_records r JOIN engagements e "
        "ON e.id = r.engagement_id WHERE r.tenant_id = $1 AND e.name = 'FY2026 FS Audit'",
        TENANT,
    )
    assert [tuple(r) for r in meridian] == [("continuance", "draft", user("MO"))]

    # ENG-05: the A1 roster, its hours and the EQR.
    a1 = loader.engagement_id_of(loader.BY_LABEL["A1"])
    roster = await seed.rows(
        "SELECT user_id, role, budget_hours FROM engagement_members WHERE tenant_id = $1 "
        "AND engagement_id = $2",
        TENANT,
        a1,
    )
    by_user = {r["user_id"]: (r["role"], r["budget_hours"]) for r in roster}
    assert by_user[user("TW")][0] == "eqr_reviewer"
    assert {i: by_user[user(i)][1] for i in ("MO", "HL", "MD", "AC", "KR")} == {
        "MO": Decimal("10.0"),
        "HL": Decimal("37.0"),
        "MD": Decimal("61.0"),
        "AC": Decimal("40.0"),
        "KR": Decimal("18.0"),
    }
    approvals = await seed.rows(
        "SELECT approved_by FROM team_approvals WHERE tenant_id = $1 AND engagement_id = $2",
        TENANT,
        a1,
    )
    assert [r[0] for r in approvals] == [user("MO")]

    # CLI-08 a: four of the five confirmed; Ana Cruz not.
    confirmed = await seed.rows(
        "SELECT user_id FROM independence_confirmations WHERE tenant_id = $1 "
        "AND engagement_id = $2 AND status = 'confirmed'",
        TENANT,
        a1,
    )
    assert {r[0] for r in confirmed} == {user(i) for i in ("MO", "TW", "HL", "MD")}

    # CLI-08 c and CLI-06 h: Harborline cleared "Not adverse" by Hannah and by Samuel.
    cleared = await seed.rows(
        "SELECT c.subject_kind, c.names_count, e.assessment, e.cleared_by "
        "FROM conflict_result_events e JOIN conflict_results r ON r.id = e.result_id "
        "JOIN conflict_checks c ON c.id = r.check_id WHERE c.tenant_id = $1 "
        "ORDER BY c.subject_kind",
        TENANT,
    )
    assert {tuple(r) for r in cleared} == {
        ("client", 7, "not_adverse", user("HL")),
        ("client", 1, "not_adverse", user("SI")),
    }

    # CLI-04: Northwind's contacts (Sam Ortiz is the portal slice's), Calloway's custodian.
    contacts = await seed.rows(
        "SELECT cl.name, count(*) FROM contacts c JOIN clients cl ON cl.id = c.client_id "
        "WHERE c.tenant_id = $1 AND cl.name IN ('Northwind Robotics, Inc.', "
        "'Calloway Family Trust') GROUP BY 1",
        TENANT,
    )
    assert {r[0]: r[1] for r in contacts} == {
        "Northwind Robotics, Inc.": 5,
        "Calloway Family Trust": 1,
    }

    second = await loader.load(own_db.superuser_dsn, SNAPSHOT, slices=SLICES, wait=False)
    assert (second.replayed, second.skipped) == (0, len(events))
