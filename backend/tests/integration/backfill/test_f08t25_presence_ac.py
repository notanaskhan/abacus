# ac-test-author: ayushkbhatia
"""F-08-T25 (TASK-8938; F-08 §3 F1; ADR-078): presence anchors, black-box over HTTP on the
migrated Postgres. An object kind no module registered is refused (404, fail closed); an object
the caller cannot read is refused (404, INV-3: absent, never forbidden); a heartbeat is gone after
45 s; what fans out names people by id only (no names, emails or object contents); the viewer never
sees themself. Boundary: `PUT /v1/presence` and `GET /v1/presence` (docs/contracts/presence.md);
the 45 s window is reached by ageing the heartbeat row through the superuser seeder, as a clock
would."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
P = "/v1/presence"


async def _work_item(seed: Seeder, site: Site, by: Person) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'tax_return', $4, $5) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            f"Form 1065 {site.marker}",
            by.user_id,
        ),
    )


async def _two_on_one(net: Net, seed: Seeder) -> tuple[Person, Person, Site, uuid.UUID]:
    tenant = await seed.firm()
    simone = await seed.person(tenant)
    cole = await seed.person(tenant)
    site = await seed.site(tenant, simone.user_id, "Granite")
    await seed.member(site, simone, "manager")
    await seed.member(site, cole, "senior")
    item = await _work_item(seed, site, simone)
    return simone, cole, site, item


def _beat(
    item: uuid.UUID, kind: str = "work_item", key: str | None = "SURL-12"
) -> dict[str, object]:
    body: dict[str, object] = {"object_kind": kind, "object_id": str(item), "anchor_kind": "cell"}
    if key is not None:
        body["anchor_key"] = key
    return body


async def test_ac_f1_an_unregistered_kind_is_refused(net: Net, seed: Seeder) -> None:
    simone, _cole, _site, item = await _two_on_one(net, seed)
    refused = await net.call("PUT", P, simone, body=_beat(item, kind="unregistered_thing"))
    assert refused.status_code == 404, refused.text
    read = await net.call("GET", f"{P}?object_kind=unregistered_thing&object_id={item}", simone)
    assert read.status_code == 404, read.text


async def test_ac_f1_an_unreadable_object_is_refused_as_absent(net: Net, seed: Seeder) -> None:
    _simone, _cole, _site, item = await _two_on_one(net, seed)
    # A person of another firm, and a person of this firm on no engagement team.
    stranger_firm = await seed.firm()
    stranger = await seed.person(stranger_firm)
    outsider = await seed.person(_site.tenant_id)
    for who in (stranger, outsider):
        put = await net.call("PUT", P, who, body=_beat(item))
        assert put.status_code == 404, (who, put.text)
        get = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", who)
        assert get.status_code == 404, (who, get.text)


async def test_ac_f1_a_heartbeat_shows_to_others_and_never_to_the_viewer(
    net: Net, seed: Seeder
) -> None:
    simone, cole, _site, item = await _two_on_one(net, seed)
    put = await net.call("PUT", P, simone, body=_beat(item))
    assert put.status_code == 200, put.text
    assert put.json() == {"heartbeat_seconds": 15, "ttl_seconds": 45}
    seen = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", cole)
    assert seen.status_code == 200, seen.text
    items = seen.json()["items"]
    assert [i["user_id"] for i in items] == [str(simone.user_id)]
    assert items[0]["anchor_kind"] == "cell" and items[0]["anchor_key"] == "SURL-12"
    mine = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", simone)
    assert mine.json()["items"] == []


async def test_ac_f1_a_heartbeat_vanishes_after_45_seconds(net: Net, seed: Seeder) -> None:
    simone, cole, _site, item = await _two_on_one(net, seed)
    assert (await net.call("PUT", P, simone, body=_beat(item))).status_code == 200
    await seed.run(
        "UPDATE presence_heartbeats SET seen_at = seen_at - interval '44 seconds' "
        "WHERE user_id = $1",
        simone.user_id,
    )
    still = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", cole)
    assert len(still.json()["items"]) == 1
    await seed.run(
        "UPDATE presence_heartbeats SET seen_at = seen_at - interval '2 seconds' "
        "WHERE user_id = $1",
        simone.user_id,
    )
    gone = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", cole)
    assert gone.json()["items"] == []


async def test_ac_f1_presence_carries_identifiers_only_and_is_not_audited(
    net: Net, seed: Seeder
) -> None:
    simone, cole, site, item = await _two_on_one(net, seed)
    before = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1", site.tenant_id
    )
    assert (await net.call("PUT", P, simone, body=_beat(item))).status_code == 200
    seen = await net.call("GET", f"{P}?object_kind=work_item&object_id={item}", cole)
    entry = seen.json()["items"][0]
    assert set(entry) == {"user_id", "anchor_kind", "anchor_key", "seen_at"}
    assert site.marker not in seen.text  # no object content travels with presence
    after = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1", site.tenant_id
    )
    assert after == before  # the documented exception: heartbeats are not audited
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE payload::text LIKE '%' || $1 || '%'", str(item)
    )
    assert outbox == 0


async def test_ac_f1_a_client_principal_never_heartbeats(net: Net, seed: Seeder) -> None:
    _simone, _cole, site, item = await _two_on_one(net, seed)
    client = await seed.client_contact(site)
    refused = await net.call("PUT", P, client, body=_beat(item))
    assert refused.status_code in (403, 404), refused.text
