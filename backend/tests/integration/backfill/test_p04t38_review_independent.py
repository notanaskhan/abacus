# ac-test-author: p04t38-independent
"""P-04-T38 (TASK-2023; ADR-078): independent acceptance tests for issues, checkpoints and field
history (P-04-T31, T32, T35), written from the review-grammar contract, not the builders' tests.

- Restore never deletes: every checkpoint, diff and decision row there before a restore is still
  there, unchanged, after it; the restore only adds.
- An import checkpoint (`engine_import`) stays proposed and out of Current until a person
  approves it; then it is Current.
- Client wording never carries the internal note: the request item a send makes holds the
  wording only; the internal title appears in no client-visible column.
The field-write half is `tests/unit/review/test_p04t38_field_writes_only_through_record_value.py`.

Boundary: `create_app()` over HTTP; the import checkpoint through `review.api.propose_checkpoint`
as the engine import calls it; outcomes through SQL.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Final, cast

import pytest

from abacus.modules.review.api import ProposedChange, propose_checkpoint

from . import test_p04t28_proposals_independent as t28
from . import test_p04t32_checkpoints as t32
from .p04t28_support import PROBE, World, probe

pytestmark = pytest.mark.asyncio
world = t28.world
# The checkpoint suite's own setup, shared (the targets and seeding, not its assertions).
return_ = t32._return  # pyright: ignore[reportPrivateUsage]
save_ = t32._save  # pyright: ignore[reportPrivateUsage]
propose_ = t32._propose  # pyright: ignore[reportPrivateUsage]
change_ = t32._change  # pyright: ignore[reportPrivateUsage]
decide_ = t32._decide  # pyright: ignore[reportPrivateUsage]
history_ = t32._history  # pyright: ignore[reportPrivateUsage]
bot_ = t32._bot  # pyright: ignore[reportPrivateUsage]
Body = dict[str, Any]  # a response body as the contract shapes it
CHECKPOINTS: Final = "/v1/checkpoints"
INTERNAL: Final = "Internal: the trust's K-1 still shows the old allocation"
WORDING: Final = "Please send the corrected 2025 K-1 from the trust."


async def _rows(world: World, target: uuid.UUID) -> dict[str, list[tuple[object, ...]]]:
    """Every checkpoint-side row of the target, as stored."""
    out: dict[str, list[tuple[object, ...]]] = {}
    for name, sql in (
        ("checkpoints", "SELECT id, status, content_hash FROM checkpoints WHERE target_id = $1"),
        (
            "diffs",
            "SELECT d.id, d.field_key FROM checkpoint_diffs d JOIN checkpoints c "
            "ON c.id = d.checkpoint_id WHERE c.target_id = $1",
        ),
        (
            "decisions",
            "SELECT x.id, x.decision FROM checkpoint_decisions x JOIN checkpoints c "
            "ON c.id = x.checkpoint_id WHERE c.target_id = $1",
        ),
    ):
        out[name] = sorted(tuple(r) for r in await world.seed.rows(sql, target))
    return out


async def test_restore_only_adds_rows_and_changes_none(world: World) -> None:
    target = await return_(world)
    first = await save_(world, target, "ana", "Before the K-1")
    checkpoint, seen = await propose_(
        world,
        target,
        change_(t32.INT, "100.00", "120.00", "20.00"),
        tag="p04t38-a",
    )
    await decide_(world, checkpoint, seen)
    before = await _rows(world, target)

    restored = await world.call(
        "POST",
        f"{CHECKPOINTS}/{first['id']}/restore",
        "samuel",
        {"seen_hash": first["content_hash"]},
    )
    assert restored.status_code == 200, restored.text
    after = await _rows(world, target)
    for name, rows in before.items():
        assert set(rows) <= set(after[name]), f"a {name} row changed or went"
    assert len(after["checkpoints"]) == len(before["checkpoints"]) + 1


async def test_an_import_checkpoint_waits_for_a_person(world: World) -> None:
    target = await return_(world)
    digest = hashlib.sha256(f"{target}:import".encode()).hexdigest()
    imported = await propose_checkpoint(
        await bot_(world),
        PROBE,
        target,
        (
            ProposedChange(
                field_key=t32.DIV,
                old=None,
                new={"t": "decimal", "v": "410.00"},
                cause="engine_import",
                delta_facts=None,
            ),
        ),
        author_kind="agent",
        cause="engine_import",
        content_hash=digest,
    )
    status = await world.seed.value("SELECT status FROM checkpoints WHERE id = $1", imported)
    assert status == "proposed"
    history = await history_(world, target)
    current = [c for c in history["items"] if c.get("is_current")]
    assert all(c["id"] != str(imported) for c in current)

    await decide_(world, imported, f"sha256:{digest}")
    history = await history_(world, target)
    current = [c for c in history["items"] if c.get("is_current")]
    assert [c["id"] for c in current] == [str(imported)]
    decided_by = await world.seed.value(
        "SELECT actor_kind FROM checkpoint_decisions WHERE checkpoint_id = $1", imported
    )
    assert decided_by == "human"


async def test_the_client_wording_never_carries_the_internal_note(world: World) -> None:
    target = probe(world.site, (world["samuel"],))
    made = await world.call(
        "POST",
        "/v1/issues",
        "ana",
        {
            "record_type": PROBE,
            "record_id": str(target),
            "kind": "waiting_on_client",
            "title": INTERNAL,
        },
    )
    assert made.status_code == 201, made.text
    issue = cast(Body, made.json()["issue"])
    await world.seed.run(
        "INSERT INTO engagement_letters (tenant_id, engagement_id, status, letter_date, "
        "recorded_by) VALUES ($1, $2, 'signed', '2026-04-02', 'test-seed') "
        "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET status = 'signed'",
        world.tenant_id,
        world.site.engagement_id,
    )
    sent = await world.call_with(
        "POST",
        f"/v1/issues/{issue['id']}/send-to-client",
        "hannah",
        {
            "seen_version": issue["version"],
            "client_wording": WORDING,
            "contact_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"contact:{issue['id']}")),
        },
        {"Idempotency-Key": f"p04t38-{issue['id']}"},
    )
    assert sent.status_code in (200, 201), sent.text
    rows = await world.seed.rows(
        "SELECT to_jsonb(r) AS row FROM request_items r "
        "WHERE r.tenant_id = $1 AND r.created_at > now() - interval '5 minutes'",
        world.tenant_id,
    )
    assert rows, "the send made no request item"
    for row in rows:
        stored = str(row["row"])
        assert INTERNAL not in stored
    assert any(WORDING in str(row["row"]) for row in rows)
