"""A-03-T08 (TASK-2612; A-03 §3 F6 US-6.1, US-6.2, US-6.4; C9 v2; ADR-341; DEC-1661) over HTTP
against Postgres: the live mapping set on a trial balance of record.

The row's acceptance: "Granite Peak's 128 accounts are mapped by rule or left Needs review with
no suggested row, confirm returns 409 unmapped_accounts while any remains, and a successful
confirm writes exactly one L1 sign-off and mapping_set.confirmed." Here on the A-02 books (six
accounts; Suspense 1900 is in no range), the 128 in the compute unit test.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.ledger.api import import_grouping_set, publish_version

from .support import Net
from .tb_support import Books, books

Json = dict[str, Any]  # Any: JSON bodies
CSV = (
    "grouping_key,grouping_label,class,fs_line_key,fs_line_label,normal_balance,"
    "account_from,account_to\n"
    "investments,Investments,assets,investments,Investments at fair value,debit,1200,1299\n"
    "liabilities,Liabilities,liabilities,loans,Loans payable,credit,2000,2999\n"
    "net_assets,Net assets,equity,net_assets,Net assets available for benefits,credit,3000,3999\n"
)


async def _world(net: Net) -> tuple[Books, uuid.UUID, str]:
    world = await books(net)
    seed = net.seed
    for flag in ("ledger.tb_mapping", "review.grammar_api"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'a03', 'TASK-2612') ON CONFLICT DO NOTHING",
            world.tenant_id,
            flag,
        )
    margaret = await seed.person(world.tenant_id, "quality_partner")
    person = TenantContext(world.tenant_id, "human", str(margaret.user_id))
    async with uow(person) as tx:
        version = await import_grouping_set(
            tx, tenant_id=world.tenant_id, key="bh-fs", name="BH FS groupings", text=CSV,
            user_id=margaret.user_id,
        )  # fmt: skip
    async with uow(person) as tx:
        await publish_version(
            tx,
            version_id=version,
            user_id=margaret.user_id,
            actor_kind="human",
            effective_from=date(2026, 9, 1),
        )
    tb_id = await world.adopted()
    base = f"/v1/engagements/{world.site.engagement_id}/mapping-sets"
    return world, tb_id, base


async def test_ac1_rules_map_or_leave_need_review_and_confirm_waits_for_none(net: Net) -> None:
    world, tb_id, base = await _world(net)
    senior = world.senior
    ran = await net.call("POST", base, senior, body={"trial_balance_id": str(tb_id)})
    assert ran.status_code == 202, ran.text
    run = cast(Json, ran.json())
    assert run["run_status"] == "ready"
    assert run["run_done"] == run["run_total"] == 6
    msid = run["mapping_set_id"]

    again = await net.call("POST", base, senior, body={"trial_balance_id": str(tb_id)})
    assert again.status_code == 409 and again.json()["detail"] == "mapping_run_in_progress"

    read = await net.call("GET", f"/v1/mapping-sets/{msid}", senior)
    assert read.status_code == 200, read.text
    body = cast(Json, read.json())
    states = {r["account_code"]: (r["state"], r["method"], r["confidence"]) for r in body["rows"]}
    assert states["1900"] == ("unmapped", None, None)
    assert states["1210"] == ("rule", "number_range", "medium")
    assert {s for s, _, _ in states.values()} <= {"rule", "unmapped"}  # never `suggested`
    tallies = body["summary"]["tallies"]
    assert (tallies["accounts"], tallies["mapped"], tallies["need_review"]) == (6, 5, 1)
    assert tallies["tb_balanced"] == 1
    assert body["summary"]["status"] == "in_progress"

    refused = await net.call(
        "POST",
        f"/v1/mapping-sets/{msid}/confirm",
        senior,
        body={"seen_hash": body["summary"]["content_hash"]},
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "unmapped_accounts"

    listing = await net.call("GET", base, senior)
    assert listing.status_code == 200 and listing.json()["total"] == 1


async def test_ac2_edit_then_confirm_writes_one_l1_and_the_event(net: Net) -> None:
    world, tb_id, base = await _world(net)
    senior = world.senior
    ran = await net.call("POST", base, senior, body={"trial_balance_id": str(tb_id)})
    msid = ran.json()["mapping_set_id"]
    before = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", senior)).json())
    investments = next(r["fs_line_id"] for r in before["rows"] if r["account_code"] == "1210")

    edited = await net.call(
        "PUT",
        f"/v1/mapping-sets/{msid}/accounts/1900",
        senior,
        body={"fs_line_id": investments, "seen_version": 0},
    )
    assert edited.status_code == 200, edited.text
    row = cast(Json, edited.json())
    assert (row["state"], row["method"], row["confidence"]) == ("edited", "manual", None)
    assert row["seen_version"] == 1

    stale = await net.call(
        "PUT",
        f"/v1/mapping-sets/{msid}/accounts/1900",
        senior,
        body={"fs_line_id": investments, "seen_version": 0},
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"

    changed = await net.call(
        "POST",
        f"/v1/mapping-sets/{msid}/confirm",
        senior,
        body={"seen_hash": before["summary"]["content_hash"]},
    )
    assert changed.status_code == 409 and changed.json()["detail"] == "content_changed"

    now = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", senior)).json())
    assert now["summary"]["tallies"]["need_review"] == 0
    confirmed = await net.call(
        "POST",
        f"/v1/mapping-sets/{msid}/confirm",
        senior,
        body={"seen_hash": now["summary"]["content_hash"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    summary = cast(Json, confirmed.json())
    assert summary["status"] == "prepared"
    assert [c["level"] for c in summary["sign_offs"]] == [1]

    seed = net.seed
    l1 = await seed.value(
        "SELECT count(*) FROM sign_offs WHERE target_type = 'mapping_set' AND target_id = $1 "
        "AND level = 1",
        uuid.UUID(msid),
    )
    assert l1 == 1
    actions = await seed.actions(world.tenant_id)
    assert actions.count("mapping_set.confirmed") == 1


async def test_ac4_the_mapped_trial_balance_is_computed_per_fs_line(net: Net) -> None:
    world, tb_id, base = await _world(net)
    ran = await net.call("POST", base, world.senior, body={"trial_balance_id": str(tb_id)})
    msid = ran.json()["mapping_set_id"]
    mapped = await net.call("GET", f"/v1/mapping-sets/{msid}/trial-balance", world.senior)
    assert mapped.status_code == 200, mapped.text
    body = cast(Json, mapped.json())
    nets = {line["fs_line_key"]: Decimal(line["net"]) for line in body["lines"]}
    assert nets["investments"] == Decimal("16500000.00")  # 1210 + 1220 + 1230
    assert nets["loans"] == Decimal("-312400.00")
    assert body["unmapped"] == 1  # Suspense
    view = await net.call("GET", f"/v1/mapping-sets/{msid}", world.senior)
    assert body["content_hash"] == view.json()["summary"]["content_hash"]


async def test_a_person_off_the_engagement_never_reads_the_set(net: Net) -> None:
    world, tb_id, base = await _world(net)
    ran = await net.call("POST", base, world.senior, body={"trial_balance_id": str(tb_id)})
    stranger = await net.seed.person(world.tenant_id)
    read = await net.call("GET", f"/v1/mapping-sets/{ran.json()['mapping_set_id']}", stranger)
    assert read.status_code in (403, 404), read.text
