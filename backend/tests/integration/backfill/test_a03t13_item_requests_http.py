"""A-03-T13 (TASK-2712; A-03 F4 US-4.1; DEC-1763) over HTTP against Postgres: the item-request
fan-out from an approved sample set version.

Row acceptance: "Creating from Version 2 writes exactly 125 requests (100 for Dana Kowalski, 25
delegated to Sam Ortiz), a replay creates none, and a Draft version answers 409
sample_not_approved." Here the drawn size is the census's own (n items), so five templates — four
to Dana, one to Sam — write 5n requests: 4n to POR-03 and n delegated to Sam, each linked to its
sample item in the `sample` wave, with one `sample_set.requests_generated` audit.
"""

from __future__ import annotations

import uuid
from typing import cast

from .support import Net, Person, Seeder
from .test_a03t10_sample_sets_http import (
    Json,
    Team,
    _approve,  # pyright: ignore[reportPrivateUsage] -- A-03-T10's suite helpers
    _draw,  # pyright: ignore[reportPrivateUsage] -- as above
    _population,  # pyright: ignore[reportPrivateUsage] -- as above
    _prepare,  # pyright: ignore[reportPrivateUsage] -- as above
    _set,  # pyright: ignore[reportPrivateUsage] -- as above
    _team,  # pyright: ignore[reportPrivateUsage] -- as above
    _version_id,  # pyright: ignore[reportPrivateUsage] -- as above
    _view,  # pyright: ignore[reportPrivateUsage] -- as above
    stand_ins,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- the autouse stand-ins
)

DESCRIPTIONS = ("Enrollment form", "Deferral election", "Payroll register", "Beneficiary form")


async def _contact(seed: Seeder, team: Team, name: str, kind: str, org: str | None) -> uuid.UUID:
    """A contact of the engagement's client with a portal sign-in (a client membership)."""
    who: Person = await seed.client_contact(team.site, "client_contributor")
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, organisation_name, "
            "contact_kind, user_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            team.site.tenant_id,
            team.site.client_id,
            name,
            org,
            kind,
            who.user_id,
        ),
    )


async def _approved(net: Net, seed: Seeder) -> tuple[Team, str, int, int]:
    team = await _team(seed)
    pid = await _population(net, team)
    sid = await _set(net, team)
    version_no = await _draw(net, team, sid, pid)
    view = await _view(net, team.marcus, sid, version_no)
    await _prepare(net, team, view, await _version_id(seed, sid, version_no))
    view = await _view(net, team.marcus, sid, version_no)
    approved = await _approve(net, team.hannah, sid, version_no, view)
    assert approved.status_code == 200, approved.text
    return team, sid, version_no, cast(int, view["items_total"])


def _body(dana: uuid.UUID, sam: uuid.UUID) -> Json:
    templates: list[Json] = [{"description": d, "contact_id": str(dana)} for d in DESCRIPTIONS]
    templates.append({"description": "SOC 1 bridge letter", "third_party_contact_id": str(sam)})
    return {"templates": templates, "due_on": "2026-10-01", "wave": "sample"}


async def test_ac_create_writes_the_fan_out_once_and_a_replay_creates_none(
    net: Net, seed: Seeder
) -> None:
    team, sid, version_no, n = await _approved(net, seed)
    dana = await _contact(seed, team, "Dana Kowalski", "client", None)
    sam = await _contact(seed, team, "Sam Ortiz", "third_party", "Keystone")
    body = _body(dana, sam)
    path = f"/v1/sample-sets/{sid}/versions/{version_no}/item-requests"
    preview = await net.call("POST", f"{path}/preview", team.marcus, body=body)
    assert preview.status_code == 200, preview.text
    shown = cast(Json, preview.json())
    assert (shown["total"], shown["by_surface"]) == (5 * n, {"POR-03": 4 * n, "POR-14": n})
    assert [(r["name"], r["surface"], r["requests"]) for r in shown["recipients"]] == [
        ("Dana Kowalski", "POR-03", 4 * n),
        ("Sam Ortiz", "POR-14", n),
    ]
    assert "seed" not in preview.text and "inputs_hash" not in preview.text  # INV-4
    key = str(uuid.uuid4())
    headers = {**net.headers(team.marcus), "Idempotency-Key": key}
    made = await net.http.post(path, json=body, headers=headers)
    assert made.status_code == 201, made.text
    out = cast(Json, made.json())
    assert (out["created"], out["by_surface"]) == (5 * n, {"POR-03": 4 * n, "POR-14": n})
    count = (
        "SELECT count(*) FROM request_items WHERE engagement_id = $1 AND wave = 'sample' "
        "AND linked_ref->>'type' = 'sample_item' AND linked_ref->>'batch_id' = $2"
    )
    assert await seed.value(count, team.site.engagement_id, out["batch_id"]) == 5 * n
    delegated = await seed.value(
        "SELECT count(*) FROM request_delegations d JOIN request_items i "
        "ON i.tenant_id = d.tenant_id AND i.id = d.request_item_id "
        "WHERE i.engagement_id = $1 AND d.contact_id = $2 AND d.grant_id IS NOT NULL",
        team.site.engagement_id,
        sam,
    )
    assert delegated == n
    due = await seed.value(
        "SELECT count(*) FROM request_items WHERE engagement_id = $1 AND due_on = '2026-10-01'",
        team.site.engagement_id,
    )
    assert due == 5 * n
    replay = await net.http.post(path, json=body, headers=headers)
    assert replay.status_code == 201 and replay.json() == out
    assert await seed.value(count, team.site.engagement_id, out["batch_id"]) == 5 * n
    total = await seed.value(
        "SELECT count(*) FROM request_items WHERE engagement_id = $1", team.site.engagement_id
    )
    assert total == 5 * n + 1  # and the site's own request
    audits = await seed.rows(
        "SELECT after FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'sample_set.requests_generated'",
        team.site.tenant_id,
    )
    assert len(audits) == 1


async def test_ac_a_draft_version_answers_409_sample_not_approved(net: Net, seed: Seeder) -> None:
    team = await _team(seed)
    pid = await _population(net, team)
    sid = await _set(net, team)
    version_no = await _draw(net, team, sid, pid)
    dana = await _contact(seed, team, "Dana Kowalski", "client", None)
    sam = await _contact(seed, team, "Sam Ortiz", "third_party", "Keystone")
    made = await net.http.post(
        f"/v1/sample-sets/{sid}/versions/{version_no}/item-requests",
        json=_body(dana, sam),
        headers={**net.headers(team.marcus), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert (made.status_code, made.json()["code"]) == (409, "sample_not_approved")


async def test_a_recipient_who_is_not_the_clients_contact_is_refused(
    net: Net, seed: Seeder
) -> None:
    team, sid, version_no, _ = await _approved(net, seed)
    dana = await _contact(seed, team, "Dana Kowalski", "client", None)
    preview = await net.call(
        "POST",
        f"/v1/sample-sets/{sid}/versions/{version_no}/item-requests/preview",
        team.marcus,
        body=_body(dana, uuid.uuid4()),
    )
    assert (preview.status_code, preview.json()["code"]) == (422, "recipient_not_contact")
