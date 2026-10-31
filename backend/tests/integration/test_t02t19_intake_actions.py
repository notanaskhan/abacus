"""T-02-T19 (TASK-2427; DEC-1475) over HTTP against Postgres: what TAX-03's actions need from the
intake read.

- Each waiting file names the message N-01's triage apply files or ignores it on, so File to
  request, Not this… and Ignore are a person's call on the owner's route.
- A flagged, unresolved duplicate upload (T-02-T17) shows under its request with the version Keep
  newer or Discard duplicate resolves; the row keeps naming the copy it repeats, and Approve
  Document stays on that copy. Once a person resolves it, the duplicate leaves the read.
"""

from __future__ import annotations

import uuid
from typing import cast

from abacus.kernel.clock import frozen

from . import test_t02t09_practice_board as t02t09
from . import test_t02t18_intake as t02t18
from .test_t02t09_practice_board import DEMO, Board, Json
from .test_t02t13_return_overview import manager_on

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

W2 = "2025 W-2 From Mercer Hill Health"


async def _duplicate(b: Board, engagement: uuid.UUID, request: uuid.UUID) -> uuid.UUID:
    """A second client upload of the filed W-2's bytes, flagged `duplicate_hash` (T-02-T17)."""
    original = cast(
        uuid.UUID,
        await b.seed.value(
            "SELECT f.evidence_version_id FROM fulfilments f WHERE f.request_item_id = $1",
            request,
        ),
    )
    fingerprint = await b.seed.value(
        "SELECT fingerprint FROM evidence_versions WHERE id = $1", original
    )
    item = await b.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Claire_Feld_2025_W2_MercerHill (1).pdf', 'human', "
        "'seed') RETURNING id",
        b.tenant,
        engagement,
    )
    version = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method, created_at) VALUES ($1, $2, $3, 1, $4, $5, 'v2', 10, "
            "'application/pdf', 'client_upload', 'uploaded', clock_timestamp() + interval "
            "'1 second') RETURNING id",
            b.tenant,
            engagement,
            item,
            fingerprint,
            f"tenants/{b.tenant}/sha256/{fingerprint}",
        ),
    )
    await b.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id, created_at) VALUES ($1, $2, $3, $4, 'human', 'seed', "
        "clock_timestamp() + interval '1 second')",
        b.tenant,
        engagement,
        request,
        version,
    )
    await b.seed.run(
        "INSERT INTO upload_checks (tenant_id, engagement_id, evidence_version_id, "
        "checker_version, check_code, outcome, audience, reason) VALUES ($1, $2, $3, 'v1', "
        "'duplicate_hash', 'problem', 'firm', 'same_hash')",
        b.tenant,
        engagement,
        version,
    )
    return version


async def test_waiting_files_name_their_message(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    await t02t18._binder(board, feld)  # pyright: ignore[reportPrivateUsage]
    kevin = await manager_on(board, feld)
    client = cast(
        uuid.UUID, await board.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld)
    )
    attachment = await t02t18._waiting(  # pyright: ignore[reportPrivateUsage]
        board, client, "Feld_1095C_2025.pdf", 2025
    )
    message = await board.seed.value(
        "SELECT message_id FROM inbox_attachments WHERE id = $1", attachment
    )
    with frozen(DEMO):
        found = await _as(kevin)("GET", f"/v1/tax-returns/{feld}/intake")
    assert found.status_code == 200, found.text
    row = next(
        w
        for w in cast(list[Json], cast(Json, found.json())["waiting"])
        if w["attachment_id"] == str(attachment)
    )
    assert row["message_id"] == str(message)


async def test_a_pending_duplicate_shows_under_its_request_until_a_person_resolves_it(
    board: Board,
) -> None:
    feld = board.returns["Feld Household 1040"]
    made = await t02t18._binder(board, feld)  # pyright: ignore[reportPrivateUsage]
    kevin = await manager_on(board, feld)
    original = await board.seed.value(
        "SELECT evidence_version_id FROM fulfilments WHERE request_item_id = $1", made[W2]
    )
    duplicate = await _duplicate(board, made["engagement"], made[W2])

    with frozen(DEMO):
        found = await _as(kevin)("GET", f"/v1/tax-returns/{feld}/intake")
    assert found.status_code == 200, found.text
    rows = {r["title"]: r for r in cast(list[Json], cast(Json, found.json())["requests"])}
    w2 = rows[W2]
    assert w2["duplicate"] == {
        "version_id": str(duplicate),
        "file_name": "Claire_Feld_2025_W2_MercerHill (1).pdf",
    }
    # The row keeps naming the filed copy, which Approve Document accepts.
    assert w2["latest_version_id"] == str(original)
    assert w2["file_name"] == f"{W2}.pdf"
    assert all(r["duplicate"] is None for t, r in rows.items() if t != W2)

    await board.seed.run(
        "INSERT INTO duplicate_resolutions (tenant_id, engagement_id, version_id, "
        "kept_version_id, decision, decided_by) VALUES ($1, $2, $3, $4, 'discard_duplicate', $5)",
        board.tenant,
        made["engagement"],
        duplicate,
        original,
        kevin.user_id,
    )
    with frozen(DEMO):
        again = await _as(kevin)("GET", f"/v1/tax-returns/{feld}/intake")
    rows = {r["title"]: r for r in cast(list[Json], cast(Json, again.json())["requests"])}
    assert rows[W2]["duplicate"] is None
