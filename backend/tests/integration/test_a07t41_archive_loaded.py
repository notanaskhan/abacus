"""A-07-T41 (TASK-6735; DEC-3302) on the loaded Brightwater Hale tenant: the `archive` slice
loads Northwind to Fri Oct 9, 2026 at 10:05 AM (AUD-24 a) through the services, and the release
snapshot reads G5, G6 and G7 met with every also-required row ticked, from the gate providers.
The release at 10:07 and the archive after it need a relay and a worker (`make seed-demo
SLICE=archive`); this load runs without them (`wait=False`)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Literal, cast

import asyncpg
import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance import completion_reads as reads
from abacus.modules.assurance.api import a07_shadow_facts, release_snapshot
from abacus.modules.identity.api import AuthContext
from abacus_tools.a07_shadow import compare
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner", "security_admin"]
TENANT = loader.TENANT


async def _row(seed: Seeder, sql: str, *args: object) -> asyncpg.Record | None:
    found = await seed.rows(sql, *args)
    return found[0] if found else None


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_ac_northwind_is_ready_to_release_at_10_05_through_the_services(
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
    # G6: Thomas concurred at 4:40 PM on Oct 5, as a person, with both EQR notes cleared.
    concurred = await _row(
        seed,
        "SELECT concurred_by, actor_kind, concurrence_date FROM eqr_concurrences "
        "WHERE work_item_id = $1",
        item,
    )
    assert concurred is not None and concurred["actor_kind"] == "human"
    assert concurred["concurrence_date"].isoformat() == "2026-10-05"
    # G7: the letter signed on the report date.
    letter = await _row(
        seed,
        "SELECT status, dated_as_of FROM representation_letters WHERE work_item_id = $1",
        item,
    )
    assert letter is not None and letter["status"] == "signed"
    assert letter["dated_as_of"].isoformat() == "2026-10-09"
    # The report approved, dated Oct 9 in Chicago; the AU-C 260 completion letter sent.
    report = await _row(
        seed, "SELECT report_date, city FROM audit_reports WHERE work_item_id = $1", item
    )
    assert report is not None and report["report_date"].isoformat() == "2026-10-09"
    assert (
        await seed.value(
            "SELECT status FROM governance_communications WHERE work_item_id = $1 "
            "AND kind = 'completion_260'",
            item,
        )
        == "sent"
    )
    snap = await release_snapshot(TenantContext(TENANT, "system", "a07t41-test"), item)
    assert {c.gate: c.met for c in snap.gates} == {"G5": True, "G6": True, "G7": True}, snap
    assert all(a.met for a in snap.also_required), snap.also_required
    assert snap.report_approved
    assert snap.blockers == ()
    # Nothing released yet at 10:05.
    assert (
        await seed.value("SELECT count(*) FROM report_releases WHERE work_item_id = $1", item) == 0
    )
    # Q-04-T136 (synthetic, PF-X1): the shadow at 10:05 reads every gate met, and nothing yet to
    # compare with the firm tool's release, documentation date or lock.
    facts = await a07_shadow_facts(TenantContext(TENANT, "system", "a07t41-shadow"), item)
    tool = {"report_released_on": "2026-10-09", "documentation_completion_date": "2026-12-08",
            "archived_on": "2026-12-03"}  # fmt: skip
    accrued = {"report_released_on": facts.released_on,
               "documentation_completion_date": facts.documentation_completion_date,
               "archived_on": facts.archived_on}  # fmt: skip
    outcomes = {c.key: c.outcome for c in compare(accrued, dict(facts.gates), tool)}
    assert outcomes == {
        "report_released_on": "not_yet",
        "documentation_completion_date": "not_yet",
        "archived_on": "not_yet",
        "gates_at_release": "match",
    }
    # S35 follow-up (item 3): AUD-18, AUD-19 and AUD-21 read the loaded rows, not fixtures.
    await _reads_answer_the_loaded_rows(own_db, item)


async def _person(seed: Seeder, initials: str) -> AuthContext:
    seat = next(s for s in loader.SEATS if s.initials == initials)
    user = loader.user_id_of(seat)
    role = await seed.value(
        "SELECT firm_role FROM memberships WHERE tenant_id = $1 AND user_id = $2", TENANT, user
    )
    return AuthContext(
        TenantContext(TENANT, "human", str(user)),
        user,
        uuid.UUID(int=0),
        cast("FirmRole | None", role),  # the membership's own value (NULL for a staff seat)
        system_now(),
    )


async def _reads_answer_the_loaded_rows(own_db: Database, item: uuid.UUID) -> None:
    seed = Seeder(own_db.superuser_dsn)
    manager = await _person(seed, "HL")
    eqr = await _person(seed, "TW")
    # AUD-18: Thomas's review, concurred, 10 of 10, both notes cleared; the viewer is the EQR.
    review = await reads.eqr_review(eqr, item)
    assert review.status == "concurred" and review.viewer_is_eqr
    assert (review.checklist_done, review.checklist_total) == (10, 10)
    assert review.concurrence is not None
    assert review.concurrence.concurrence_date.isoformat() == "2026-10-05"
    assert [n.status for n in review.notes] == ["cleared", "cleared"]
    assert review.blockers == [] and "eqr.concur" not in review.allowed_actions
    assert not (await reads.eqr_review(manager, item)).viewer_is_eqr
    # AUD-19 a: every counted item is listed with the firm template's wording.
    checklist = await reads.completion(manager, item)
    assert checklist.items and all(i.title != i.item_key for i in checklist.items)
    assert checklist.total == len(checklist.items) - checklist.not_applicable
    # AUD-21: the letter as signed on the report date, its paper the composed version's.
    letter = await reads.representation_letter(manager, item)
    assert letter.status == "signed" and letter.g7_met
    assert letter.dated_as_of is not None and letter.dated_as_of.isoformat() == "2026-10-09"
    assert letter.current_version is not None and letter.watermark == "none"
    assert letter.paragraphs and all(p.text for p in letter.paragraphs)
    versions = await reads.letter_versions(manager, item)
    assert versions[-1].version_no == letter.current_version.version_no
    # AUD-19 b, c: the reads answer whatever the load recorded, never a 501.
    await reads.subsequent_events(manager, item)
    await reads.legal_letter(manager, item)
