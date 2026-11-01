"""A-03-T14 (TASK-2714; A-03 F6 US-6.4; DEC-1765) over HTTP against Postgres: a mapping follows
its trial balance's new version.

Row acceptance: "Adopting Granite Peak TB version 2 with one new account leaves version 1 and its
snapshot untouched, shows one unmapped account, makes the L1 sign-off compute stale and notifies
Caleb Dunn and Hannah Leclerc once." Here on the A-02 books: the senior prepares (L1, after
mapping Suspense by hand) and the manager reviews (L2); version 2 adds account 1950, which no
range maps; the subscriber runs on the outbox's own `trial_balance.version_created`.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, cast

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import mapping as assurance_mapping
from abacus.modules.review.api import stale_of

from .support import Net
from .tb_support import NEWER, snapshot
from .test_a03t08_mapping_http import _world  # pyright: ignore[reportPrivateUsage] -- T08's books

Json = dict[str, Any]  # Any: JSON bodies
NEW_ACCOUNT = ("1950", "Other receivable", "1000.00", "0")
# NEWER with one new account; net assets carry it, so the version still balances.
V2 = (
    *[line for line in NEWER if line[0] != "3000"],
    NEW_ACCOUNT,
    ("3000", "Net assets", "0", "16210170.00"),
)


async def _outbox(net: Net, tenant: uuid.UUID, event_type: str) -> list[Json]:
    rows = await net.seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY seq",
        tenant,
        event_type,
    )
    return [
        {
            "id": r["id"],
            "payload": json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
        }
        for r in rows
    ]


def _event(tenant: uuid.UUID, row: Json) -> OutboxEvent:
    return OutboxEvent(
        row["id"], tenant, "trial_balance.version_created", cast(Json, row["payload"])
    )


async def test_ac_a_new_version_is_followed_and_its_signers_are_told_once(net: Net) -> None:
    world, tb_id, base = await _world(net)
    senior, manager = world.senior, world.manager
    ran = await net.call("POST", base, senior, body={"trial_balance_id": str(tb_id)})
    msid = cast(str, ran.json()["mapping_set_id"])
    before = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", senior)).json())
    investments = next(r["fs_line_id"] for r in before["rows"] if r["account_code"] == "1210")
    edited = await net.call(
        "PUT",
        f"/v1/mapping-sets/{msid}/accounts/1900",
        senior,
        body={"fs_line_id": investments, "seen_version": 0},
    )
    assert edited.status_code == 200, edited.text
    now = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", senior)).json())
    seen = now["summary"]["content_hash"]
    confirmed = await net.call(
        "POST", f"/v1/mapping-sets/{msid}/confirm", senior, body={"seen_hash": seen}
    )
    assert confirmed.status_code == 200, confirmed.text
    reviewed = await net.call(
        "POST",
        "/v1/sign-offs",
        manager,
        body={
            "target_type": "mapping_set",
            "target_id": msid,
            "level": "L2_reviewer",
            "seen_hash": f"sha256:{seen}",
            "statement_version": "reviewer-v1",
        },
    )
    assert reviewed.status_code == 201, reviewed.text

    seed = net.seed
    v1 = await seed.rows(
        "SELECT snapshot_id FROM trial_balance_versions WHERE trial_balance_id = $1 "
        "AND version_no = 1",
        tb_id,
    )
    v1_snapshot = v1[0]["snapshot_id"]
    lines_before = await seed.value(
        "SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", v1_snapshot
    )
    newer = await snapshot(world.tenant_id, senior.user_id, world.site.entity_id, V2)
    adopted = await world.reversion(tb_id, snapshot_id=newer, who=senior)
    assert adopted.status_code in (200, 201), adopted.text

    [created] = [
        r
        for r in await _outbox(net, world.tenant_id, "trial_balance.version_created")
        if cast(Json, r["payload"]).get("version_no") == 2
    ]
    event = _event(world.tenant_id, created)
    assert await assurance_mapping.on_tb_version(event) is True
    assert await assurance_mapping.on_tb_version(event) is False  # a replay changes nothing

    # Version 1 and its snapshot are untouched (ADR-004).
    again = await seed.rows(
        "SELECT snapshot_id FROM trial_balance_versions WHERE trial_balance_id = $1 "
        "AND version_no = 1",
        tb_id,
    )
    assert again[0]["snapshot_id"] == v1_snapshot
    lines_after = await seed.value(
        "SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", v1_snapshot
    )
    assert lines_after == lines_before

    # One unmapped account (the new one); the person's edit to Suspense stands.
    read = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", senior)).json())
    states = {r["account_code"]: r["state"] for r in read["rows"]}
    assert read["summary"]["tallies"]["need_review"] == 1
    assert states["1950"] == "unmapped" and states["1900"] == "edited"

    # L1 (and L2) compute stale against the new content.
    tenant = TenantContext(world.tenant_id, "system", "test")
    stale = await stale_of(
        tenant, "mapping_set", {uuid.UUID(msid): read["summary"]["content_hash"]}
    )
    assert {s.level for s in stale} >= {1}

    # Its signers are told once: one announcement naming both, however often it is replayed.
    [went] = await _outbox(net, world.tenant_id, "mapping_set.went_stale")
    told = set(cast(list[str], cast(Json, went["payload"])["recipient_user_ids"]))
    assert told == {str(senior.user_id), str(manager.user_id)}
    actions = await seed.actions(world.tenant_id)
    assert actions.count("mapping_set.version_followed") == 1
    assert actions.count("mapping_set.went_stale") == 1
