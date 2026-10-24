"""R-01-T08 against Postgres: the client's ignore note and the two Undos (R-01 Stories 3.1, 4.1;
contract portal-pbc §2, §6, §7; DEC-24, DEC-334).

Acceptance: "Undo returns Claire's ignored 1099-B to To do and Kevin's BND-02 row to Requested,
while undo after Kevin waived the request answers 409." The Undo contract itself (one
compensating row by the same person, a second Undo refused, nobody else's) is the shared suite's
(`tests/contracts/undo`, cases `client_ignore` and `client_mark_done`).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.portal.documents import read_binder
from abacus.modules.requests.binders import mark_done, undo_mark_done
from abacus.modules.requests.client_undo import FirmAlreadyActed, NothingToUndo
from abacus.modules.requests.lifecycle import ignore_item, undo_ignore, waive_item

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_portal_documents import (
    World,
    client_ctx,
    client_person,
    feld_world,
    grant_access,
    rows_of,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _status(w: World, key: str) -> tuple[str, object]:
    rows = await w.seed.rows(
        "SELECT status, client_ignored_at FROM request_items WHERE id = $1", w.items[key]
    )
    return str(rows[0]["status"]), rows[0]["client_ignored_at"]


async def test_ac_undo_returns_the_ignored_1099b_to_to_do_and_requested(seed: Seeder) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    await ignore_item(claire, w.items["1099b"], "not_this_year", "Sold nothing in 2025.")
    row = rows_of(await read_binder(claire, w.binder, "all", None))[w.items["1099b"]]
    assert row.client_status == "ignored" and "undo_ignore" in row.allowed_actions
    assert "ignore" not in row.allowed_actions

    await undo_ignore(claire, w.items["1099b"])

    assert await _status(w, "1099b") == ("requested", None)  # Kevin's BND-02 row: Requested
    row = rows_of(await read_binder(claire, w.binder, "all", None))[w.items["1099b"]]
    assert row.client_status == "to_do" and "ignore" in row.allowed_actions
    actions = [
        r["action"]
        for r in await seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2 ORDER BY seq",
            w.tenant,
            str(w.items["1099b"]),
        )
    ]
    assert actions == [
        "request_item.ignored",
        "request_item.ignore_note_added",
        "request_item.ignore_undone",
    ]
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'request_item.ignore_undone'",
        w.tenant,
    )
    assert outbox == 1


async def test_ac_the_note_is_a_shared_comment_that_the_undo_leaves_in_the_thread(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    await ignore_item(claire, w.items["1099b"], "not_this_year", "Sold nothing in 2025.")
    await undo_ignore(claire, w.items["1099b"])
    rows = await seed.rows(
        "SELECT origin, visibility, author_side, author_user_id, body_sealed, body_fingerprint "
        "FROM comments WHERE request_item_id = $1",
        w.items["1099b"],
    )
    assert [(r["origin"], r["visibility"], r["author_side"]) for r in rows] == [
        ("ignore_note", "shared", "client")
    ]
    assert rows[0]["author_user_id"] == w.claire.user_id
    body = await open_sealed(w.tenant, rows[0]["body_sealed"], rows[0]["body_fingerprint"])
    assert body.decode() == "Sold nothing in 2025."
    notes = await seed.rows(
        "SELECT kind, note FROM client_item_responses WHERE request_item_id = $1 "
        "ORDER BY created_at",
        w.items["1099b"],
    )
    assert [(r["kind"], r["note"]) for r in notes] == [
        ("not_applicable", None),
        ("withdrawn", None),
    ]
    sheet_comments = await seed.value(
        "SELECT count(*) FROM comments WHERE request_item_id = $1 AND visibility = 'shared'",
        w.items["1099b"],
    )
    assert sheet_comments == 1


async def test_ac_undo_after_kevin_waived_the_request_is_409_firm_already_acted(
    seed: Seeder,
) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    await ignore_item(claire, w.items["1099b"], "not_this_year", None)
    await waive_item(
        w.partner.context(), w.engagement, w.items["1099b"], "firm_waived", "Not needed this year"
    )
    row = rows_of(await read_binder(claire, w.binder, "all", None))[w.items["1099b"]]
    assert "undo_ignore" not in row.allowed_actions
    with pytest.raises(FirmAlreadyActed) as refused:
        await undo_ignore(claire, w.items["1099b"])
    assert refused.value.facts == {"request_item_id": str(w.items["1099b"])}
    assert (await _status(w, "1099b"))[0] == "not_applicable"
    with pytest.raises(NothingToUndo):
        await undo_ignore(claire, w.items["1095"])  # never ignored


async def test_inv4_a_contributor_without_the_request_cannot_undo_it(seed: Seeder) -> None:
    w = await feld_world(seed)
    await ignore_item(client_ctx(w.claire), w.items["1099b"], "not_this_year", None)
    pat = await client_person(seed, w.tenant, "Pat Contributor")
    await grant_access(seed, pat, "contributor", "engagement", w.engagement)
    with pytest.raises(NotFound):
        await undo_ignore(client_ctx(pat), w.items["1099b"])
    with pytest.raises(NotFound):
        await undo_ignore(client_ctx(pat), uuid.uuid4())


async def test_ac_undo_of_mark_as_done_publishes_the_binder_again(seed: Seeder) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    await mark_done(claire, w.binder)
    marked = await read_binder(claire, w.binder, "all", None)
    assert marked.mark_done.state == "marked" and marked.mark_done.marked_by_name == "Claire Feld"
    assert "undo_mark_done" in marked.allowed_actions
    assert (
        "undo_mark_done"
        not in (await read_binder(client_ctx(w.jonah), w.binder, "all", None)).allowed_actions
    )

    undone = await undo_mark_done(claire, w.binder)

    assert undone.mark_done == "tonal"  # two requests are still open
    stamps = await seed.rows(
        "SELECT status, marked_done_at, marked_done_by FROM request_lists WHERE id = $1",
        w.binder,
    )
    assert tuple(stamps[0].values()) == ("published", None, None)
    after = await read_binder(claire, w.binder, "all", None)
    assert after.mark_done.state == "tonal" and "mark_done" in after.allowed_actions
    with pytest.raises(NothingToUndo):
        await undo_mark_done(claire, w.binder)


async def test_ac_undo_of_mark_as_done_after_the_firm_acted_is_409(seed: Seeder) -> None:
    w = await feld_world(seed)
    claire = client_ctx(w.claire)
    await mark_done(claire, w.binder)
    await waive_item(
        w.partner.context(), w.engagement, w.items["1099b"], "firm_waived", "Not needed this year"
    )
    assert (
        "undo_mark_done" not in (await read_binder(claire, w.binder, "all", None)).allowed_actions
    )
    with pytest.raises(FirmAlreadyActed):
        await undo_mark_done(claire, w.binder)
