"""A-03-T18 (TASK-2821; ADR-078) over HTTP against Postgres: independent AC tests for the sampling
services (A-03-T07, T10, T13), written apart from their own suites.

Row acceptance: "The suite passes on main and fails when the population_not_tied guard, the
server-seed rule or the per-item third-party grant is removed." (The seed rule's unit half is
`tests/unit/sampling/test_a03t18_seed_policy.py`.) Here:
- the tie guard checks **every** tie: a population with one tie that agrees and one that doesn't
  still answers 409 `population_not_tied`, and approves once the second agrees;
- a draw over HTTP records a server seed (24 bits, `seed_source` server) and two draws differ;
- the third party gets one active `request_item` grant per delegated request and no wider
  grant, and the client contact gets none of the third party's;
- census fields never reach the logs (a participant's name and amount are absent).

Reuses A-03-T10's stand-ins (the census parse stands aside, the draw runs inline) and its people.
"""

from __future__ import annotations

import logging
import uuid
from typing import cast

import pytest

from .support import Net, Seeder
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
from .test_a03t13_item_requests_http import (
    _approved,  # pyright: ignore[reportPrivateUsage] -- A-03-T13's approved version
    _body,  # pyright: ignore[reportPrivateUsage] -- its five templates
    _contact,  # pyright: ignore[reportPrivateUsage] -- its client contacts
)


async def _tie(net: Net, team: Team, pid: str, amount: str, label: str) -> None:
    made = await net.call(
        "POST",
        f"/v1/populations/{pid}/ties",
        team.marcus,
        body={"label": label, "comparisons": [{"label": label, "amount": amount}]},
    )
    assert made.status_code == 201, made.text


async def _drafted(net: Net, seed: Seeder, team: Team, pid: str) -> tuple[str, int, Json]:
    sid = await _set(net, team)
    n = await _draw(net, team, sid, pid)
    view = await _view(net, team.marcus, sid, n)
    await _prepare(net, team, view, await _version_id(seed, sid, n))
    return sid, n, await _view(net, team.marcus, sid, n)


async def test_the_tie_guard_needs_every_tie_to_agree(net: Net, seed: Seeder) -> None:
    team = await _team(seed)
    pid = await _population(net, team)  # one tie that agrees (14,560,000.00)
    await _tie(net, team, pid, "14742300.00", "Trustee statement")  # and one that doesn't
    sid, n, view = await _drafted(net, seed, team, pid)
    refused = await _approve(net, team.hannah, sid, n, view)
    assert (refused.status_code, refused.json()["detail"]) == (409, "population_not_tied")
    assert (
        await seed.value(
            "SELECT count(*) FROM sample_set_versions WHERE sample_set_id = $1 "
            "AND status = 'approved'",
            uuid.UUID(sid),
        )
        == 0
    )


async def test_a_tied_population_approves(net: Net, seed: Seeder) -> None:
    team = await _team(seed)
    pid = await _population(net, team)
    await _tie(net, team, pid, "14560000.00", "Trustee statement")
    sid, n, view = await _drafted(net, seed, team, pid)
    approved = await _approve(net, team.hannah, sid, n, view)
    assert approved.status_code == 200, approved.text


async def test_a_draw_records_a_server_seed_and_two_draws_differ(net: Net, seed: Seeder) -> None:
    team = await _team(seed)
    pid = await _population(net, team)
    sid = await _set(net, team)
    first = await _draw(net, team, sid, pid)
    second = await _draw(net, team, sid, pid)
    rows = await seed.rows(
        "SELECT version_no, seed, seed_source FROM sample_set_versions WHERE sample_set_id = $1 "
        "ORDER BY version_no",
        uuid.UUID(sid),
    )
    assert [r["version_no"] for r in rows] == [first, second]
    assert {r["seed_source"] for r in rows} == {"server"}
    assert all(0 <= cast(int, r["seed"]) < 2**24 for r in rows)
    assert rows[0]["seed"] != rows[1]["seed"]


async def test_the_third_party_holds_one_grant_per_delegated_request_and_nothing_wider(
    net: Net, seed: Seeder
) -> None:
    team, sid, version_no, n = await _approved(net, seed)
    dana = await _contact(seed, team, "Dana Kowalski", "client_person", None)
    sam = await _contact(seed, team, "Sam Ortiz", "third_party", "Keystone")
    made = await net.http.post(
        f"/v1/sample-sets/{sid}/versions/{version_no}/item-requests",
        json=_body(dana, sam),
        headers={**net.headers(team.marcus), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert made.status_code == 201, made.text
    sam_user = await seed.value("SELECT user_id FROM contacts WHERE id = $1", sam)
    dana_user = await seed.value("SELECT user_id FROM contacts WHERE id = $1", dana)
    grants = await seed.rows(
        "SELECT scope_kind, scope_id, role FROM client_access_grants "
        "WHERE tenant_id = $1 AND user_id = $2 AND status = 'active'",
        team.site.tenant_id,
        sam_user,
    )
    assert {(g["scope_kind"], g["role"]) for g in grants} == {("request_item", "delegate")}
    assert len(grants) == n
    delegated = {
        r["request_item_id"]
        for r in await seed.rows(
            "SELECT d.request_item_id FROM request_delegations d WHERE d.contact_id = $1", sam
        )
    }
    assert {g["scope_id"] for g in grants} == delegated
    # The client contact holds none of the third party's requests.
    assert (
        await seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1 AND user_id = $2 "
            "AND scope_kind = 'request_item' AND scope_id = ANY($3::uuid[])",
            team.site.tenant_id,
            dana_user,
            list(delegated),
        )
        == 0
    )


async def test_census_fields_never_reach_the_logs(
    net: Net, seed: Seeder, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    team = await _team(seed)
    pid = await _population(net, team)
    sid = await _set(net, team)
    await _draw(net, team, sid, pid)
    text = caplog.text
    assert "Benjamin Okoro" not in text  # a participant's name (row 158 of the census)
    assert "NW-1158" not in text  # their record key
    assert "35340" not in text  # each participant's compensation in the census
