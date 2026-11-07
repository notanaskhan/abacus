"""A-06-T28 (TASK-3380; DEC-2373) against Postgres: Northwind's completion loads through the
services, and code's figures foot to AUD-15, AUD-16 and AUD-17."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.review_matrix import matrix
from abacus.modules.assurance.sum_service import sum_view
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import statements
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    BY_LABEL,
    TENANT,
    engagement_id_of,
    user_id_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database, object_store: str) -> Iterator[Database]:
    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(
                own_db.superuser_dsn, "2026-10-21T14:10", slices=("completion",), wait=False
            )
        finally:
            await dispose_engine()

    with pytest.MonkeyPatch.context() as patch:
        # `could` reads memberships through the identity engine: this database's.
        patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
        settings.cache_clear()
        forget_flags()
        asyncio.run(load())
        yield own_db
    settings.cache_clear()
    forget_flags()


async def _rows(loaded: Database, sql: str) -> list[tuple[object, ...]]:
    seed = Seeder(loaded.superuser_dsn)
    return [tuple(r) for r in await seed.rows(sql, TENANT)]


async def test_ac_nine_findings_in_the_designed_bands(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT f.ref, f.route, d.status, d.severity_concluded FROM audit_findings f "
        "LEFT JOIN deficiencies d ON d.finding_id = f.id WHERE f.tenant_id = $1 ORDER BY f.ref",
    )
    assert [r[0] for r in found] == [f"F-0{n}" for n in range(1, 10)]
    by = {r[0]: r for r in found}
    assert by["F-01"][2:] == ("concluded", "significant_deficiency")
    assert by["F-02"][2:] == ("concluded", "deficiency")
    assert by["F-03"][2] == "proposed"
    assert all(by[f"F-0{n}"][1] == "converted_to_misstatement" for n in range(5, 10))


async def test_ac_the_misstatements_read_as_the_design_and_code_projects_f07(
    loaded: Database,
) -> None:
    found = await _rows(
        loaded,
        "SELECT ref, type, nature, status, amount, projection->>'projected' "
        "FROM audit_misstatements WHERE tenant_id = $1 ORDER BY ref",
    )
    assert [(r[0], r[3]) for r in found] == [
        ("AJE-1", "booked"),
        ("BCT-1", "below_ct"),
        ("PAJE-1", "passed_on_sum"),
        ("PAJE-2", "passed_on_sum"),
        ("PY-1", "confirmed"),
        ("RJE-1", "booked"),
    ]
    paje = next(r for r in found if r[0] == "PAJE-1")
    assert paje[1] == "projected"
    assert (Decimal(str(paje[4])), paje[5]) == (Decimal("35300.00"), "35267.20")


async def test_ac_the_sum_foots_to_aud16(loaded: Database) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    item = await Seeder(loaded.superuser_dsn).value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        engagement_id_of(BY_LABEL["A1"]),
    )
    view = await sum_view(TenantContext(TENANT, "system", "test"), cast(UUID, item), None)
    assert view.result.rollover == Decimal("34150.00")
    assert view.result.iron_curtain == Decimal("22250.00")
    assert view.below_ct_total == Decimal("4210.00")
    await dispose_engine()


async def test_ac_margaret_concluded_on_a_frozen_snapshot(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT status FROM decision_cards WHERE tenant_id = $1 AND kind = 'sum_conclusion'",
    )
    assert found == [("decided",)]


async def test_ac_marcus_l2_on_ebp04_reads_changed_after_ana_changes_the_paper(
    loaded: Database,
) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    engagement = engagement_id_of(BY_LABEL["A1"])
    found = await matrix(TenantContext(TENANT, "system", "test"), engagement)
    row = next(r for r in found.rows if r.code == "EBP-04")
    assert [c.state for c in row.cells[:2]] == ["signed", "stale"]
    await dispose_engine()


async def test_ac_14_notes_in_their_states(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT status, count(*) FROM reviewable_notes n JOIN workpapers w ON w.id = n.target_id "
        "WHERE n.tenant_id = $1 GROUP BY status ORDER BY status",
    )
    assert found == [("cleared", 11), ("open", 2), ("responded", 1)]


async def test_ac_a25_each_version_names_its_deterministic_run(loaded: Database) -> None:
    found = await _rows(
        loaded,
        "SELECT v.drafted_by_kind, r.agent_id, r.status FROM statement_versions v "
        "JOIN agent_runs r ON r.id = v.run_id WHERE v.tenant_id = $1 ORDER BY v.version_no",
    )
    assert found == [("system", "reporting.fs_draft", "completed")] * 3


async def test_ac_three_statement_versions_and_danas_approval(loaded: Database) -> None:
    versions = await _rows(
        loaded,
        "SELECT version_no FROM statement_versions WHERE tenant_id = $1 ORDER BY version_no",
    )
    assert versions == [(1,), (2,), (3,)]
    approved = await _rows(
        loaded,
        "SELECT event, channel, evidence_version_id IS NOT NULL FROM statement_approvals "
        "WHERE tenant_id = $1",
    )
    assert approved == [("approved_by_management", "record", True)]


async def test_ac_a25_the_workflows_activities_write_a_version_and_a_retry_writes_none(
    loaded: Database,
) -> None:
    """A-06-T25: the request opens the run; the activity, as the system, drafts from the run's own
    row; a retried activity finds the version it already wrote; a tie-out emits its event."""
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    engagement = engagement_id_of(BY_LABEL["A1"])
    item = cast(
        UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        ),
    )
    hannah = user_id_of(next(x for x in SEATS if x.initials == "HL"))
    person = AuthContext(
        TenantContext(TENANT, "human", str(hannah)), hannah, UUID(int=0), None, system_now()
    )
    system = TenantContext(TENANT, "system", "reporting:statements")
    run = await statements.start_draft(person, engagement, item)
    assert await seed.value("SELECT status FROM agent_runs WHERE id = $1", run) == "running"
    first = await statements.draft_in_run(system, run)
    assert await statements.draft_in_run(system, run) == first
    assert await seed.value("SELECT status FROM agent_runs WHERE id = $1", run) == "completed"
    assert first[1] == 4

    failing = await statements.start_draft(person, engagement, item)
    await statements.fail_draft_run(system, failing)
    await statements.fail_draft_run(system, failing)
    assert await seed.value("SELECT failure_code FROM agent_runs WHERE id = $1", failing) == (
        "draft_failed"
    )

    await statements.start_tie_out(person, first[0])
    tied = await statements.run_tie_out(system, first[0])
    assert tied["total"] > 0
    completed = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'tie_out.completed'",
        TENANT,
    )
    assert cast(int, completed) >= 1
    await dispose_engine()


async def test_ac_a25_a_draft_carries_the_firms_published_notes(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT n.number, n.title, n.body, n.unresolved, v.status FROM statement_notes n "
        "JOIN statement_versions s ON s.id = n.statement_version_id "
        "JOIN statement_note_template_versions v ON v.id = n.template_version_id "
        "WHERE n.tenant_id = $1 AND s.version_no = 3 ORDER BY n.number",
        TENANT,
    )
    assert [r["number"] for r in rows] == list(range(1, 12))
    assert {r["status"] for r in rows} == {"published"}
    assert rows[7]["title"] == "Reconciliation to Form 5500"
    assert "{{" not in rows[7]["body"] and rows[7]["body"].startswith(
        "Net assets per the financial statements "
    )
    assert rows[8]["body"].startswith("Participant contributions of $33,540")
    assert all(r["unresolved"] == [] for r in rows)
    refs = await seed.rows(
        "SELECT l.line_key, l.note_ref FROM line_items l "
        "JOIN statement_versions s ON s.id = l.statement_version_id "
        "WHERE l.tenant_id = $1 AND s.version_no = 3 AND l.note_ref IS NOT NULL",
        TENANT,
    )
    assert {r["note_ref"] for r in refs} >= {"Note 3", "Note 5", "Note 8"}


async def test_ac_a25_the_checklist_is_picked_and_answered_97_45_0(loaded: Database) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    answers = await seed.rows(
        "SELECT a.answer, a.state, count(*) AS n, bool_and(a.reviewed_by IS NOT NULL) AS reviewed "
        "FROM disclosure_checklist_answers a WHERE a.tenant_id = $1 GROUP BY 1, 2 ORDER BY 1",
        TENANT,
    )
    assert [tuple(a) for a in answers] == [
        ("na", "reviewed", 45, True),
        ("yes", "reviewed", 97, True),
    ]
    document = cast(
        UUID, await seed.value("SELECT id FROM statement_documents WHERE tenant_id = $1", TENANT)
    )
    hannah = user_id_of(next(x for x in SEATS if x.initials == "HL"))
    person = AuthContext(
        TenantContext(TENANT, "human", str(hannah)), hannah, UUID(int=0), None, system_now()
    )
    view = await statements.disclosure_view(person.tenant, document)
    assert (view.answered, view.total) == (142, 142)
    (option,) = await statements.checklist_options(person.tenant)
    assert option["version"] == 1
    with pytest.raises(statements.ChecklistAnswered):
        await statements.pick_checklist(person, document, option["id"])
    with pytest.raises(NotFound):
        await statements.pick_checklist(person, document, UUID(int=1))
