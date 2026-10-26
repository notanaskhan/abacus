"""A-02-T17 (TASK-1417; SPEC-333 AC-10 to AC-13; A-02 AC-3.2, AC-3.3) on the live routes, through
the real `authorise`, walls, row-level security and the migrated test database.

- An expected value without a citation is refused `citation_required`; nothing is written.
- A check that does not tie links, once, to an issue raised on the same engagement; the link
  shows on the check and as the line's flag; a stale version, a second issue and an issue of
  another engagement are refused; a walled member gets the same 404 as a missing engagement.
- A tie defined or changed after a sign-off makes that sign-off stale (its hash moved), the
  change is announced `tie_out_check.changed` with the trial balance, and the stale detector
  tells the signer; no sign-off row changes.
- `trial_balance` has a field owner for `wp_ref` and `area_override` per line.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Final, cast

import httpx

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import detect_stale, field_owner

from .support import Env, Person, Seeder
from .test_a02t10_tb_read_model import (  # the A-02-T10 suite's seeding, reused
    _flag_on,  # pyright: ignore[reportPrivateUsage]
    _trial_balance,  # pyright: ignore[reportPrivateUsage]
)

TB: Final = "/v1/engagements/{e}/trial-balances/{tb}"


async def _post(env: Env, who: Person, path: str, body: object) -> httpx.Response:
    headers = env.net.headers(who)
    headers["Idempotency-Key"] = f"a02t17-{uuid.uuid4().hex}"
    return await env.net.http.request("POST", path, json=body, headers=headers)


async def _put(env: Env, who: Person, path: str, body: object) -> httpx.Response:
    return await env.net.http.request("PUT", path, json=body, headers=env.net.headers(who))


async def _issue(seed: Seeder, tenant_id: uuid.UUID, engagement_id: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO issues (tenant_id, engagement_id, record_ref, kind, title_sealed) "
            "VALUES ($1, $2, '{}'::jsonb, 'exception', '\\x01'::bytea) RETURNING id",
            tenant_id,
            engagement_id,
        ),
    )


async def _setup(env: Env) -> tuple[Person, uuid.UUID, str]:
    seed = env.net.seed
    await _flag_on(seed, env.tenant_id)
    staff = await seed.person(env.tenant_id)
    await seed.member(env.a, staff, "staff")
    tb = await _trial_balance(seed, env.tenant_id, env.a, env.admin.user_id)
    return staff, tb, TB.format(e=env.a.engagement_id, tb=tb)


def _check(env: Env, *, cited: bool = True, expected: str = "450.00") -> dict[str, object]:
    return {
        "label": "Cash to bank confirmation",
        "kind": "tie",
        "accounts": ["1000"],
        "expected": expected,
        "citation_ids": [str(env.a.version_id)] if cited else [],
    }


async def test_ac12_an_uncited_expected_value_is_refused_citation_required(env: Env) -> None:
    staff, _, base = await _setup(env)
    refused = await _post(env, staff, base + "/checks", _check(env, cited=False))
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "citation_required"
    count = await env.net.seed.value(
        "SELECT count(*) FROM tie_out_checks WHERE tenant_id = $1", env.tenant_id
    )
    assert count == 0


async def test_ac11_an_off_check_links_once_to_an_issue_on_its_engagement(env: Env) -> None:
    staff, _, base = await _setup(env)
    defined = await _post(env, staff, base + "/checks", _check(env))
    assert defined.status_code == 201, defined.text
    check = defined.json()[0]
    assert check["result"]["status"] == "off"
    assert Decimal(check["result"]["difference"]) == Decimal("50.00")
    issue = await _issue(env.net.seed, env.tenant_id, env.a.engagement_id)
    link = base + f"/checks/{check['id']}/issue-link"

    stale = await _post(env, staff, link, {"issue_id": str(issue), "seen_version": 2})
    assert stale.status_code == 409 and stale.json()["detail"] == "tie_out_check_stale"
    elsewhere = await _issue(env.net.seed, env.tenant_id, env.b.engagement_id)
    other_engagement = await _post(
        env, staff, link, {"issue_id": str(elsewhere), "seen_version": 1}
    )
    assert other_engagement.status_code == 404, other_engagement.text

    linked = await _post(env, staff, link, {"issue_id": str(issue), "seen_version": 1})
    assert linked.status_code == 201, linked.text
    assert linked.json()["issue_id"] == str(issue)
    assert linked.json()["linked_by_user_id"] == str(staff.user_id)
    again = await _post(env, staff, link, {"issue_id": str(issue), "seen_version": 1})
    assert again.status_code == 201 and again.json()["linked_at"] == linked.json()["linked_at"]
    second = await _issue(env.net.seed, env.tenant_id, env.a.engagement_id)
    refused = await _post(env, staff, link, {"issue_id": str(second), "seen_version": 1})
    assert refused.status_code == 409 and refused.json()["detail"] == "tie_out_check_issue_linked"

    checks = await env.get(staff, base + "/checks")
    assert checks.json()[0]["issue_id"] == str(issue)
    view = await env.get(staff, base + "/layers/unadjusted")
    assert view.status_code == 200, view.text
    flags = [
        f
        for g in view.json()["groups"]
        for line in g["lines"]
        if line["account_code"] == "1000"
        for f in line["flags"]
    ]
    assert flags == [{"kind": "does_not_tie", "check_id": check["id"], "issue_id": str(issue)}]
    linked_events = await env.net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'tie_out_check.issue_linked'",
        env.tenant_id,
    )
    assert linked_events == 1


async def test_ac11_a_walled_member_gets_the_missing_engagements_404(env: Env) -> None:
    _, tb, _ = await _setup(env)
    manager = await env.walled("manager")
    body = {"issue_id": str(uuid.uuid4()), "seen_version": 1}
    path = TB + "/checks/{c}/issue-link"
    walled = await _post(
        env, manager, path.format(e=env.a.engagement_id, tb=tb, c=uuid.uuid4()), body
    )
    missing = await _post(env, manager, path.format(e=uuid.uuid4(), tb=tb, c=uuid.uuid4()), body)
    assert walled.status_code == missing.status_code == 404
    assert walled.json() == missing.json()
    assert not env.leaks(walled)


async def _events(seed: Seeder, tenant_id: uuid.UUID) -> list[OutboxEvent]:
    rows = await seed.rows(
        "SELECT event_id, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'tie_out_check.changed' ORDER BY created_at",
        tenant_id,
    )
    return [
        OutboxEvent(
            cast(uuid.UUID, r["event_id"]),
            tenant_id,
            "tie_out_check.changed",
            cast(
                dict[str, object],
                json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            ),
        )
        for r in rows
    ]


async def test_ac13_a_tie_changed_after_a_sign_off_makes_it_stale(env: Env) -> None:
    staff, tb, base = await _setup(env)
    signed = await _post(env, staff, base + "/sign-offs/prepare", None)
    assert signed.status_code == 201, signed.text
    before = await env.net.seed.rows(
        "SELECT id, content_hash FROM sign_offs WHERE tenant_id = $1", env.tenant_id
    )
    assert len(before) == 1

    defined = await _post(env, staff, base + "/checks", _check(env, expected="500.00"))
    assert defined.status_code == 201, defined.text
    check = defined.json()[0]
    assert check["result"]["status"] == "tie"
    edited = await _put(
        env,
        staff,
        base + f"/checks/{check['id']}",
        {**_check(env, expected="500.00"), "reason": "Bank letter re-read", "seen_version": 1},
    )
    assert edited.status_code == 200, edited.text

    events = await _events(env.net.seed, env.tenant_id)
    assert len(events) == 2
    assert {str(e.payload["trial_balance_id"]) for e in events} == {str(tb)}
    announced = sum([await detect_stale(e) for e in events])
    assert announced == 1  # the signer is told once
    stale = await env.net.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'sign_off.went_stale'",
        env.tenant_id,
    )
    assert stale == 1
    after = await env.net.seed.rows(
        "SELECT id, content_hash FROM sign_offs WHERE tenant_id = $1", env.tenant_id
    )
    assert [dict(r) for r in after] == [dict(r) for r in before]  # no sign-off row changed


async def test_the_trial_balance_has_a_field_owner_for_its_annotations(env: Env) -> None:
    _, tb, _ = await _setup(env)
    owner = field_owner("trial_balance")
    reader = TenantContext(env.tenant_id, "system", "a02t17-test")
    assert await owner.value_of(reader, tb, "wp_ref:1000") == {"t": "text", "v": None}
    assert await owner.value_of(reader, tb, "area_override:1000") is not None
    assert await owner.value_of(reader, tb, "amount:1000") is None  # amounts are never fields
    assert await owner.value_of(reader, tb, "wp_ref:9999") is None
    assert await owner.value_of(reader, uuid.uuid4(), "wp_ref:1000") is None
