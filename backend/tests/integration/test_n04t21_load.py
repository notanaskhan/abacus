"""N-04-T21 (TASK-3346; DEC-2378) against Postgres: the notices slice loads through the services.

"make seed-demo produces every NOT artboard's data through service APIs." It had never been loaded,
and its first run failed on the intake's source and field keys.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import date
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import analysis, response, sending
from abacus.modules.notices.service import notice
from abacus.modules.reporting.compose import block_texts, compose
from abacus.modules.review.api import decide_card
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale import notices_content as nc
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import bundle

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
            await loader.load(own_db.superuser_dsn, "E0", slices=("notices",), wait=False)
        finally:
            await dispose_engine()

    with pytest.MonkeyPatch.context() as patch:
        # A person's reads go through the identity engine: this database's, not the session's.
        patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
        settings.cache_clear()
        forget_flags()
        asyncio.run(load())
        yield own_db
    settings.cache_clear()
    forget_flags()


def _person(user: UUID) -> AuthContext:
    return AuthContext(
        TenantContext(loader.TENANT, "human", str(user)), user, UUID(int=0), None, system_now()
    )


def loaded_tenant() -> TenantContext:
    return TenantContext(loader.TENANT, "system", "test")


async def test_ac_the_loaded_notices_foot_to_the_seed(loaded: Database) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT status, count(*) AS n FROM notices WHERE tenant_id = $1 GROUP BY status",
        loader.TENANT,
    )
    by = {r["status"]: r["n"] for r in rows}
    assert sum(by.values()) == len(nc.NOTICES)
    for row in nc.NOTICES:
        assert by.get(row.status, 0) >= 1


async def test_ac_mark_sent_and_the_agency_reply_write_their_rows(
    loaded: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """They had never run: each raised on a text `Ref`, so no notice could reach Awaiting IRS or
    close. US-7.3, US-7.4. The chain before them (signature, confirmation) isn't loaded."""
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    found = (
        await seed.rows(
            "SELECT work_item_id, assignee_user_id FROM notices WHERE tenant_id = $1 "
            "AND status = 'response_drafted' ORDER BY work_item_id LIMIT 1",
            loader.TENANT,
        )
    )[0]
    work_item, grace = cast(UUID, found["work_item_id"]), cast(UUID, found["assignee_user_id"])
    ctx = AuthContext(
        TenantContext(loader.TENANT, "human", str(grace)), grace, UUID(int=0), None, system_now()
    )

    async def ready(_ctx: object, _work_item: object) -> object:
        return SimpleNamespace(ready=True, blocking=())

    async def no_signal(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(sending, "readiness", ready)
    monkeypatch.setattr(sending, "signal_workflow", no_signal)
    # The states before these two, as a person's sign-off and signature would leave them.
    template = cast(UUID, await seed.value("SELECT gen_random_uuid()"))
    await seed.run(
        "INSERT INTO notice_responses (tenant_id, work_item_id, template_key, "
        "template_version_id, position_source) VALUES ($1, $2, 'k', $3, 'decided')",
        loader.TENANT,
        work_item,
        template,
    )
    await seed.run("UPDATE notices SET status = 'approved' WHERE work_item_id = $1", work_item)
    sent = await sending.mark_sent(
        ctx,
        work_item,
        channel="dut",
        confirmation_no="AB4821",
        sent_on=date(2026, 9, 17),
        follow_up_days=60,
    )
    assert sent == (date(2026, 9, 17), date(2026, 11, 16), "4821")
    status = "SELECT status FROM notices WHERE work_item_id = $1"
    assert await seed.value(status, work_item) == "awaiting_irs"

    await sending.agency_reply(
        ctx,
        work_item,
        outcome="resolved",
        closed_on=date(2026, 12, 2),
        note="agreed amount assessed and paid",
        evidence_version_id=None,
    )
    assert await seed.value(status, work_item) == "closed"
    assert await seed.value(
        "SELECT closed_on FROM notices WHERE work_item_id = $1", work_item
    ) == (date(2026, 12, 2))
    await dispose_engine()


async def test_ac_the_confirmation_request_reaches_the_client_on_the_senders_click(
    loaded: Database,
) -> None:
    """US-7.1: created in the notice's binder and sent, due when the notice is. It was only ever
    created, so no client saw it and readiness could never turn."""
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    row = (
        await seed.rows(
            "SELECT n.work_item_id, m.user_id AS sender, n.respond_by FROM notices n "
            "JOIN engagement_members m ON m.engagement_id = n.engagement_id "
            "AND m.role = 'manager' "
            "WHERE n.tenant_id = $1 AND n.status = 'analyzing' AND n.respond_by IS NOT NULL "
            "ORDER BY n.work_item_id LIMIT 1",
            loader.TENANT,
        )
    )[0]
    person = cast(UUID, row["sender"])
    ctx = AuthContext(
        TenantContext(loader.TENANT, "human", str(person)), person, UUID(int=0), None, system_now()
    )
    found = await notice(ctx, cast(UUID, row["work_item_id"]))
    helper = sending._with_confirmation_request  # pyright: ignore[reportPrivateUsage] -- under test
    payment = await helper(ctx, found, {"required": True}, ())
    assert payment is not None
    (item,) = await seed.rows(
        "SELECT sent_at IS NOT NULL AS sent, client_visible, due_on FROM request_items "
        "WHERE id = $1",
        UUID(str(payment[sending.CONFIRMATION_ITEM])),
    )
    assert (item["sent"], item["client_visible"], item["due_on"]) == (
        True,
        True,
        row["respond_by"],
    )
    await dispose_engine()


async def test_ac_a_disagree_letter_says_disagree_and_carries_what_the_person_wrote(
    loaded: Database,
) -> None:
    """The chain from analysis to the letter the taxpayers sign, run whole for the first time
    (DEC-2392). It said "we agree" on a Disagree notice and dropped the person's explanation."""
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    found = (
        await seed.rows(
            "SELECT work_item_id, assignee_user_id FROM notices WHERE tenant_id = $1 "
            "AND status = 'analyzing' AND position IS NULL ORDER BY work_item_id LIMIT 1",
            loader.TENANT,
        )
    )[0]
    work_item, kevin = cast(UUID, found["work_item_id"]), cast(UUID, found["assignee_user_id"])
    ctx = _person(kevin)

    await seed.run(  # as code's form map would; a person's entry needs a real citation first
        "INSERT INTO notice_proposed_items (tenant_id, work_item_id, kind, line_key, label, "
        "amount_irs, origin, recorded_actor_kind) "
        "VALUES ($1, $2, 'line_change', 'interest', 'Interest', 753.01, 'code_map', 'system')",
        loader.TENANT,
        work_item,
    )
    version, _status, _reused = await analysis.start(ctx, work_item)
    assert await analysis.complete_run(loader.TENANT, work_item, version) == "ready"
    before = await response.draft(ctx, work_item)
    assert before.position_source == "provisional"
    response_id = before.id

    card = await analysis.request_decision(ctx, work_item, None)
    row = (
        await seed.rows(
            "SELECT version_no, reserved_user_id FROM decision_cards WHERE id = $1", card
        )
    )[0]
    assert row["reserved_user_id"] == loader.user_id_of(
        next(x for x in SEATS if x.initials == "DR")
    )
    await decide_card(
        _person(cast(UUID, row["reserved_user_id"])),
        card,
        option_key="disagree",
        factors=(),
        rationale="The basis is on the return",
        seen_version=int(row["version_no"]),
    )

    # A draft from before the decision answers no position.
    stale = await response.facts(loaded_tenant(), response_id)
    assert stale is not None and stale.blocked_code == "position_mismatch"
    fresh = await response.regenerate(ctx, work_item, before.row_version)
    assert fresh.position_source == "decided"
    text_of = {b.key: b.text for b in fresh.blocks}
    assert "disagree with them" in text_of["clause:disagree"]
    assert text_of["clause:agree"] == ""
    needs = await response.facts(loaded_tenant(), response_id)
    assert needs is not None and needs.blocked_code == "explanation_required"

    written = "The broker reported no basis; Form 8949 shows 13,200.00."
    edited = await response.edit(
        ctx,
        work_item,
        fresh.row_version,
        blocks=[("clause:disagree", written)],
        settings={},
    )
    ready = await response.facts(loaded_tenant(), response_id)
    assert ready is not None and ready.blocked_code is None
    assert edited.row_version > fresh.row_version

    envelope = await sending.send_for_signature(
        _person(cast(UUID, row["reserved_user_id"])), work_item
    )
    assert envelope is not None
    snapshot = await seed.value(
        "SELECT s.snapshot FROM generated_document_snapshots s "
        "JOIN generated_document_versions v ON v.id = s.version_id "
        "JOIN notice_responses r ON r.generated_document_id = v.generated_document_id "
        "WHERE r.work_item_id = $1 ORDER BY v.version_no DESC LIMIT 1",
        work_item,
    )
    sealed = json.loads(cast(str, snapshot))
    assert sealed["clauses"] == {"agree": False, "disagree": True, "partially_agree": False}
    assert sealed["overrides"]["clause:disagree"] == [written]
    assert sealed["variables"]["taxpayer.names"]
    template = bundle("BH Notice Response · CP2000")
    letter = compose(
        layout_key="notice_response",
        body=cast("list[object]", template["body"]),
        clauses=cast("list[object]", template["clauses"]),
        snapshot=sealed,
    )
    words = " ".join(t for _key, _clause, t in block_texts(letter))
    assert written in words
    assert "agree with them" not in words
    await dispose_engine()
