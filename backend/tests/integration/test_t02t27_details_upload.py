"""POR-13 d (TASK-2537; S20e; T-02 §3.7, DV-10; ADR-162 §5) against Postgres: a K-1 recipient's
signed W-9 or W-8 arrives as the recipient's own upload and becomes a change for the firm.

- The upload is filed as a client upload under its own key (detached), in the issuing return's
  engagement, and the pending change names that version.
- The address route no longer takes a W-9 or W-8 by version id: naming any evidence version there
  is refused (the S20e review found any id was accepted).
- Another recipient's record answers 404; an oversized file answers 413; nothing is stored then.

The released Ridgeline packages and their signed-in recipients are T-02-T26's harness. The scan
and the object store stand in (`screen_and_stage_detached`); the version and its key rows are real.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import cast

import pytest

from abacus.kernel.crypto import DetachedKey
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.signed_copies import ScreenedFile
from abacus.modules.evidence.storage import StoredObject, detached_path
from abacus.modules.tax import k1_portal

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from . import test_t02t26_portal_k1 as t02t26
from .test_t02t09_practice_board import Board

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer
_released = t02t26._released  # pyright: ignore[reportPrivateUsage] -- T-02-T26's release

W9 = b"%PDF-1.7\n% a signed Form W-9 (synthetic)\n%%EOF\n"


@pytest.fixture
def staged(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """The scan and the store as `screen_and_stage_detached` leaves them: the object at the
    version's own path, under its own key."""
    made: list[uuid.UUID] = []

    async def stage(
        tenant_id: uuid.UUID, version_id: uuid.UUID, content: bytes, file_name: str
    ) -> tuple[ScreenedFile, DetachedKey]:
        made.append(version_id)
        digest = hashlib.sha256(content).hexdigest()
        stored = StoredObject(detached_path(tenant_id, version_id), "v1", digest, len(content))
        return ScreenedFile(file_name, "application/pdf", digest, stored), DetachedKey(
            f"key-{version_id}", b"0123456789abcdef0123"
        )

    monkeypatch.setattr(k1_portal, "screen_and_stage_detached", stage)
    return made


async def _recipient(b: Board, package: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await b.seed.value("SELECT recipient_id FROM k1_packages WHERE id = $1", package),
    )


async def test_a_signed_w9_is_the_recipients_own_upload_and_a_pending_change(
    board: Board, sent: t02t21.Sent, signer: None, staged: list[uuid.UUID]
) -> None:
    finals, (first, _second) = await _released(board)
    recipient = await _recipient(board, finals[0])
    change = await k1_portal.upload_details_change(first, recipient, "w9", "w9-signed.pdf", W9)
    assert (change.kind, change.status, change.evidence_version_id) == ("w9", "pending", staged[0])
    version = (
        await board.seed.rows(
            "SELECT v.storage_mode, v.source, v.engagement_id, i.title FROM evidence_versions v "
            "JOIN evidence_items i ON i.id = v.evidence_item_id WHERE v.id = $1",
            staged[0],
        )
    )[0]
    engagement = await board.seed.value(
        "SELECT w.engagement_id FROM k1_packages p JOIN work_items w ON w.id = p.work_item_id "
        "WHERE p.id = $1",
        finals[0],
    )
    assert (version["storage_mode"], version["source"]) == ("detached_key", "client_upload")
    assert version["engagement_id"] == engagement
    assert str(version["title"]).startswith("Form W-9")
    keys = await board.seed.value(
        "SELECT count(*) FROM evidence_object_keys WHERE evidence_version_id = $1", staged[0]
    )
    assert keys == 1


async def test_the_address_route_takes_no_evidence_version(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    recipient = await _recipient(board, finals[0])
    someone_elses = cast(
        uuid.UUID, await board.seed.value("SELECT id FROM evidence_versions LIMIT 1")
    )
    for kind in ("w9", "w8"):
        with pytest.raises(k1_portal.DetailsChangeInvalid):
            await k1_portal.submit_details_change(first, recipient, kind, someone_elses, None)
    count = await board.seed.value(
        "SELECT count(*) FROM recipient_details_changes WHERE recipient_id = $1", recipient
    )
    assert count == 0


async def test_another_recipient_and_an_oversized_file_store_nothing(
    board: Board, sent: t02t21.Sent, signer: None, staged: list[uuid.UUID]
) -> None:
    finals, (first, _second) = await _released(board)
    theirs = await _recipient(board, finals[1])
    with pytest.raises(NotFound):
        await k1_portal.upload_details_change(first, theirs, "w9", "w9.pdf", W9)
    mine = await _recipient(board, finals[0])
    with pytest.raises(k1_portal.FormTooLarge):
        await k1_portal.upload_details_change(
            first, mine, "w8", "w8.pdf", b"0" * (k1_portal.MAX_FORM_BYTES + 1)
        )
    assert staged == []
