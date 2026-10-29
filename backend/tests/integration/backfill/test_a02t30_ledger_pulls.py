# ac-test-author: ayushkbhatia
"""A-02-T30 (TASK-1739; A-02 AC-46; DEC-829): on-demand ledger pulls.

Acceptance (the task row): "Simone Baptiste's pull against the QBO sandbox on staging records an
on_demand sync run and a snapshot AUD-06 can adopt, and every earlier retrieval history still
replays." Here, against the fake connector: the pull records one `on_demand` run with its label
and no request item, audited `ledger.pull_requested`, and its workflow is started; a second pull
while it runs answers the same run; no live ledger is 409 `connector_not_available`; a connection
that needs the client to sign in again is 409 `connection_needs_reauth`; the flag off is 404; a
staff member without `ledger.pull` is refused. The snapshot end and the replay of every earlier
history run in the batch review against Temporal (`tests/workflows/test_retrieval_replay.py`).

Boundary: `create_app()` over HTTP as each person; the workflow start is observed, not run.
"""

from __future__ import annotations

import uuid
from typing import Final

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.connections import pulls

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
FLAG: Final = "connections.live_ledger"


@pytest.fixture(autouse=True)
def started(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    seen: list[uuid.UUID] = []

    async def record(_ctx: object, run_id: uuid.UUID, *, created: bool) -> None:
        del created
        seen.append(run_id)

    monkeypatch.setattr(pulls, "ensure_workflow", record)
    return seen


async def _world(net: Net) -> tuple[uuid.UUID, Person, Person, Site]:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'A-02-T30')",
        tenant,
        FLAG,
    )
    forget_flags()
    admin = await seed.person(tenant, "firm_admin")
    simone = await seed.person(tenant)
    staff = await seed.person(tenant)
    site = await seed.site(tenant, admin.user_id, "Pull")
    await seed.member(site, simone, "manager")
    await seed.member(site, staff, "staff")
    return tenant, simone, staff, site


async def _connect(net: Net, site: Site, reason: str | None = None) -> None:
    await net.seed.run(
        "INSERT INTO connections (tenant_id, client_entity_id, provider, scopes, created_by, "
        "category, status, status_reason_code) VALUES ($1, $2, 'fake', '{}', 'seed', 'ledger', "
        "'active', $3)",
        site.tenant_id,
        site.entity_id,
        reason,
    )


async def _pull(
    net: Net, who: Person, site: Site, attempt: str = "ledger-pull-1", label: str = "standard"
) -> httpx.Response:
    return await net.http.post(
        f"/v1/engagements/{site.engagement_id}/connection/pulls",
        json={"period_end": "2026-12-31", "label": label},
        headers={**net.headers(who), "Idempotency-Key": attempt},
    )


async def test_ac_a_pull_records_one_on_demand_run(net: Net, started: list[uuid.UUID]) -> None:
    tenant, simone, _, site = await _world(net)
    await _connect(net, site)
    made = await _pull(net, simone, site)
    assert made.status_code == 202, made.text
    run = uuid.UUID(made.json()["sync_run_id"])
    rows = await net.seed.rows(
        "SELECT trigger, label, request_item_id, period_start::text AS s, period_end::text AS e "
        "FROM sync_runs WHERE id = $1",
        run,
    )
    assert (rows[0]["trigger"], rows[0]["label"], rows[0]["request_item_id"]) == (
        "on_demand",
        "standard",
        None,
    )
    assert (rows[0]["s"], rows[0]["e"]) == ("2026-01-01", "2026-12-31")
    assert started == [run]
    audited = await net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = "
        "'ledger.pull_requested'",
        tenant,
    )
    assert audited == 1


async def test_a_second_pull_while_one_runs_answers_it(net: Net) -> None:
    _, simone, _, site = await _world(net)
    await _connect(net, site)
    first = await _pull(net, simone, site, attempt="ledger-pull-a")
    again = await _pull(net, simone, site, attempt="ledger-pull-b")
    assert first.json()["sync_run_id"] == again.json()["sync_run_id"]
    prior = await _pull(net, simone, site, attempt="ledger-pull-c", label="prior")
    assert prior.json()["sync_run_id"] != first.json()["sync_run_id"]


async def test_no_live_ledger_is_connector_not_available(net: Net) -> None:
    _, simone, _, site = await _world(net)
    refused = await _pull(net, simone, site)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "connector_not_available"


async def test_a_connection_needing_sign_in_is_refused(net: Net) -> None:
    _, simone, _, site = await _world(net)
    await _connect(net, site, reason="token_expired")
    refused = await _pull(net, simone, site)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "connection_needs_reauth"


async def test_the_flag_off_is_404(net: Net) -> None:
    tenant, simone, _, site = await _world(net)
    await _connect(net, site)
    await net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        tenant,
        FLAG,
    )
    forget_flags()
    assert (await _pull(net, simone, site)).status_code == 404


async def test_staff_without_ledger_pull_is_refused(net: Net) -> None:
    _, _, staff, site = await _world(net)
    await _connect(net, site)
    assert (await _pull(net, staff, site)).status_code in (403, 404)


async def test_a_replay_of_the_same_key_answers_the_same_run(net: Net) -> None:
    _, simone, _, site = await _world(net)
    await _connect(net, site)
    first = await _pull(net, simone, site, attempt="ledger-pull-replay")
    again = await _pull(net, simone, site, attempt="ledger-pull-replay")
    assert (first.status_code, again.status_code) == (202, 202)
    assert first.json()["sync_run_id"] == again.json()["sync_run_id"]
