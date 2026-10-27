"""A-02-T23 (TASK-1471; SPEC-333 AC-44; A-02 AC-11.1; C20 v1): the firm's reconnect request over
HTTP, through `create_app()`, the real `authorise`, walls, row-level security and the migrated test
database, on A-02-T16's world (the demo ledger as Tess Moreno's connected system).

The row's acceptance: Hannah Leclerc's request sends one email naming Brightwater Hale to the
entity's owners and adds one POR-02 to-do that clears when Tess Moreno reconnects. Around it: a
second ask answers the open request and sends nothing, a repeated Idempotency-Key answers the
first response, a contributor gets no email and no to-do, a client and another client's people
cannot ask (404 for what they may not see), and the flag off answers 404 after authorisation.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.communications import template_service
from abacus.modules.communications.api import configure_transport
from abacus.modules.communications.render import Block, TemplateContent
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.home import read_home

from . import test_a02t16_entity_connections as t16
from .support import Person

World = t16.World
# A-02-T16's fixtures, applied here too (the demo ledger, no Temporal, the world).
demo_ledger = t16.demo_ledger
no_temporal = t16.no_temporal
world = t16.world

FIRM = "Brightwater Hale LLP"


@dataclass
class Recorder:
    sent: list[dict[str, object]] = field(default_factory=lambda: list[dict[str, object]]())

    def send(self, **kwargs: object) -> None:
        self.sent.append(kwargs)


@pytest.fixture
def recorder() -> Iterator[Recorder]:
    found = Recorder()
    configure_transport(found)
    yield found
    configure_transport(None)


def _ctx(who: Person, *, firm_role: str | None = None, client: bool = False) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded role code
        mfa_at=datetime.now(UTC),
        client=client,
    )


async def _publish_reconnect_template(world: World) -> None:
    """The firm's Reconnect request (POR-20) as a database row: probe wording, never committed
    copy; published by a firm admin through R-01's editor."""
    seed = world.net.seed
    admin = await seed.person(world.tenant, "firm_admin")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'test-seed', 'A-02-T23')",
        world.tenant,
    )
    await seed.run("UPDATE firms SET name = $2 WHERE tenant_id = $1", world.tenant, FIRM)
    ctx = _ctx(admin, firm_role="firm_admin")
    content = TemplateContent(
        subject="{firm_name} asks you to reconnect {connection_name}",
        preheader="One step to keep your books flowing",
        blocks=(
            Block("h1", "heading", "Hi {client_first_name}"),
            Block("p1", "paragraph", "{firm_name} needs {connection_name} reconnected."),
        ),
        cta_label="Reconnect",
        cta_target="connections",
    )
    await template_service.save_draft(ctx, "reconnect_request", content, 0)
    await template_service.publish(ctx, "reconnect_request")


async def _ask(
    world: World, who: Person, connection_id: str, key: str | None = None
) -> httpx.Response:
    headers = world.net.headers(who)
    headers["Idempotency-Key"] = key or f"a02t23-{uuid.uuid4().hex}"
    return await world.net.http.post(
        f"/v1/connections/{connection_id}/reconnect-requests", headers=headers
    )


async def _needs_reauth(world: World, connection_id: str) -> None:
    await world.net.seed.run(
        "UPDATE connections SET status = 'needs_attention', status_reason_code = 'token_expired' "
        "WHERE id = $1",
        uuid.UUID(connection_id),
    )


async def _todos(world: World, who: Person) -> dict[str, tuple[int, str]]:
    view = await read_home(_ctx(who, client=True), None)
    return {t.kind: (t.count, t.state) for t in view.todos}


async def test_ac11_1_one_request_one_email_naming_the_firm_and_a_to_do_that_clears(
    world: World, recorder: Recorder
) -> None:
    await _publish_reconnect_template(world)
    card = await world.connected()
    connection_id = str(card["connection_id"])
    await _needs_reauth(world, connection_id)  # AC-11.1: a connection that needs reauth
    assert "reconnect" not in await _todos(world, world.tess)

    response = await _ask(world, world.manager, connection_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["connection_id"] == connection_id
    assert body["requested_by"]["user_id"] == str(world.manager.user_id)
    assert body["requested_by"]["kind"] == "firm"
    rows = await world.net.seed.rows(
        "SELECT * FROM reconnect_requests WHERE tenant_id = $1", world.tenant
    )
    assert len(rows) == 1 and rows[0]["fulfilled_at"] is None
    # One email, to the entity's owner (Tess), in the firm's name; none to the contributor.
    assert len(recorder.sent) == 1
    mail = recorder.sent[0]
    assert FIRM in cast(str, mail["subject"]) and FIRM in cast(str, mail["body"])
    assert "Demo ledger" in cast(str, mail["subject"])
    recipients = await world.net.seed.rows(
        "SELECT recipient_ref, status FROM messages WHERE tenant_id = $1", world.tenant
    )
    assert [(r["recipient_ref"], r["status"]) for r in recipients] == [
        (f"user:{world.tess.user_id}", "sent")
    ]
    assert "connection.reconnect_requested" in await world.actions("connection.")

    # POR-02: one to-do for the Owner, nothing for the contributor.
    assert (await _todos(world, world.tess))["reconnect"] == (1, "open")
    assert "reconnect" not in await _todos(world, world.contributor)

    # Tess reconnects: the request is fulfilled and the to-do clears.
    await world.connected()
    fulfilled = await world.net.seed.value(
        "SELECT fulfilled_at FROM reconnect_requests WHERE tenant_id = $1", world.tenant
    )
    assert fulfilled is not None
    assert "reconnect" not in await _todos(world, world.tess)


async def test_a_second_ask_answers_the_open_request_and_sends_nothing(
    world: World, recorder: Recorder
) -> None:
    await _publish_reconnect_template(world)
    connection_id = str((await world.connected())["connection_id"])
    first = await _ask(world, world.manager, connection_id)
    second = await _ask(world, world.partner, connection_id)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(recorder.sent) == 1
    assert await world.actions("connection.reconnect_requested") == [
        "connection.reconnect_requested"
    ]
    # A repeated Idempotency-Key answers the first response.
    key = f"a02t23-{uuid.uuid4().hex}"
    replay = [await _ask(world, world.manager, connection_id, key) for _ in range(2)]
    assert replay[0].json() == replay[1].json()
    assert len(recorder.sent) == 1


async def test_without_a_published_template_the_send_is_blocked_not_composed(
    world: World, recorder: Recorder
) -> None:
    connection_id = str((await world.connected())["connection_id"])
    response = await _ask(world, world.manager, connection_id)
    assert response.status_code == 201, response.text
    assert recorder.sent == []
    statuses = await world.net.seed.rows(
        "SELECT status FROM messages WHERE tenant_id = $1", world.tenant
    )
    assert [r["status"] for r in statuses] == ["blocked"]


async def test_who_may_ask(world: World, recorder: Recorder) -> None:
    connection_id = str((await world.connected())["connection_id"])
    # A client may not ask (the matrix allows partner, manager and senior only).
    tess = await _ask(world, world.tess, connection_id)
    assert tess.status_code in (403, 404)
    # Another client's Owner and another firm see nothing.
    stranger = await _ask(world, world.stranger_owner, connection_id)
    assert stranger.status_code == 404
    outsider_firm = await world.net.seed.firm()
    outsider = await world.net.seed.person(outsider_firm, "firm_admin")
    assert (await _ask(world, outsider, connection_id)).status_code == 404
    unknown = await _ask(world, world.manager, str(uuid.uuid4()))
    assert unknown.status_code == 404
    assert (
        await world.net.seed.value(
            "SELECT count(*) FROM reconnect_requests WHERE tenant_id = $1", world.tenant
        )
        == 0
    )
    assert recorder.sent == []


async def test_the_flag_off_answers_404_after_authorisation(world: World) -> None:
    connection_id = str((await world.connected())["connection_id"])
    await world.net.seed.run(
        "DELETE FROM feature_flag_states WHERE tenant_id = $1 AND flag = 'connections.portal_v2'",
        world.tenant,
    )
    forget_flags()
    response = await _ask(world, world.manager, connection_id)
    assert response.status_code == 404
