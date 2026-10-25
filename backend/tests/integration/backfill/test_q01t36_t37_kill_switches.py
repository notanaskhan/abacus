"""Q-01-T36 and T37 (P-66; Q-01 F8; platform-ops contract section 3.7) against Postgres and the
app over HTTP:

- `read_only` for a firm: its writes answer 503 `read_only`, its reads and sign-out keep working,
  another firm writes as usual; for the platform: every firm's writes answer 503, sign-in does
  not.
- `email_pause` for a firm: its sends are refused as `platform_paused` before the transport.
- The operator command sets a control through `set_platform_control` as `abacus_ops`; a firm's
  change lands in its audit trail; `list` shows the active rows.

Each test turns its switches off again and drops the controls cache, so no switch outlives it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from abacus.kernel.controls import forget_controls
from abacus.modules.communications.deliveries import PLATFORM_PAUSED, deliver
from abacus.modules.communications.transport import configure_transport
from abacus_tools.platform_control import ControlChange, active_controls, set_control

from .support import Migrated, Net, Person, Seeder

PREFERENCES = "/v1/me/preferences"


async def _switch(seed: Seeder, control: str, tenant: uuid.UUID | None, active: bool) -> None:
    await seed.value(
        "SELECT set_platform_control($1, $2, $3, NULL, $4, 'drill', 'ana', NULL)",
        control,
        "firm" if tenant is not None else "platform",
        tenant,
        active,
    )
    forget_controls()


@pytest.fixture
async def clean_controls(seed: Seeder) -> AsyncIterator[None]:
    forget_controls()
    yield
    await seed.run("UPDATE platform_controls SET active = false")
    forget_controls()


async def _member(seed: Seeder) -> tuple[uuid.UUID, Person]:
    tenant = await seed.firm()
    return tenant, await seed.person(tenant, "firm_admin")


async def test_t37_a_firm_in_read_only_mode_reads_but_never_writes(
    net: Net, seed: Seeder, clean_controls: None
) -> None:
    tenant, admin = await _member(seed)
    other_tenant, other = await _member(seed)
    body = {"default_office_id": None}
    assert (await net.call("PUT", PREFERENCES, admin, body=body)).status_code == 200
    await _switch(seed, "read_only", tenant, True)
    refused = await net.call("PUT", PREFERENCES, admin, body=body)
    assert refused.status_code == 503 and refused.json() == {"detail": "read_only"}
    assert (await net.call("GET", "/v1/me", admin)).status_code == 200
    assert (await net.call("PUT", PREFERENCES, other, body=body)).status_code == 200
    signed_out = await net.call("POST", "/v1/auth/sign-out", admin)
    assert signed_out.status_code != 503
    await _switch(seed, "read_only", tenant, False)
    assert (await net.call("PUT", PREFERENCES, admin, body=body)).status_code == 200
    assert other_tenant != tenant


async def test_t37_the_platform_in_read_only_mode_refuses_every_firms_writes_but_sign_in(
    net: Net, seed: Seeder, clean_controls: None
) -> None:
    _, admin = await _member(seed)
    await _switch(seed, "read_only", None, True)
    refused = await net.call("PUT", PREFERENCES, admin, body={"default_office_id": None})
    assert refused.status_code == 503 and refused.json() == {"detail": "read_only"}
    started = await net.http.post(
        "/v1/portal/auth/start", json={"email": "nobody@example.test"}, headers={"host": "x.test"}
    )
    assert started.status_code != 503  # sign-in is never read-only
    assert (await net.call("GET", "/v1/me", admin)).status_code == 200


class _Recording:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, **kwargs: object) -> None:
        self.sent.append(str(kwargs["message_id"]))


async def test_t36_a_firm_with_email_paused_sends_nothing(
    seed: Seeder, clean_controls: None
) -> None:
    tenant = await seed.firm()
    transport = _Recording()
    configure_transport(transport)
    try:
        await _switch(seed, "email_pause", tenant, True)
        blocked = await deliver(
            tenant_id=tenant,
            message_id=uuid.uuid4(),
            to="someone@example.test",
            subject="Hello",
            body="Plain words.",
        )
        assert blocked == PLATFORM_PAUSED and transport.sent == []
    finally:
        configure_transport(None)


def _ops_url(db: Migrated) -> str:
    # bootstrap-local.sql gives abacus_ops the local password; the role has EXECUTE only.
    return db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)


async def test_t36_the_operator_command_sets_a_firm_control_and_audits_it(
    migrated_db: Migrated, seed: Seeder, clean_controls: None
) -> None:
    tenant = await seed.firm()
    change = ControlChange("ai_pause", "firm", tenant, None, True, "ana", "drill")
    assert await set_control(_ops_url(migrated_db), change) >= 1
    listed = await active_controls(migrated_db.app_url)
    assert {"control": "ai_pause", "scope": "firm", "tenant_id": str(tenant), "route": None} in (
        listed
    )
    actions = await seed.rows(
        "SELECT action, actor_id FROM audit_events WHERE tenant_id = $1", tenant
    )
    assert ("platform_control.changed", "operator:ana") in {
        (r["action"], r["actor_id"]) for r in actions
    }


async def test_t37_ending_access_and_reads_sent_as_posts_still_work_in_read_only_mode(
    net: Net, seed: Seeder, clean_controls: None
) -> None:
    """Security review (DEC-338): revoking a person, a staff invitation or a support session,
    and knowledge search (a read with a body), are never answered `read_only`."""
    tenant, admin = await _member(seed)
    await _switch(seed, "read_only", tenant, True)
    await _switch(seed, "read_only", None, True)
    for path, body in (
        (f"/v1/firm/staff/{uuid.uuid4()}/revoke", {}),
        (f"/v1/firm/staff/invitations/{uuid.uuid4()}/revoke", {}),
        (f"/v1/support-sessions/{uuid.uuid4()}/revoke", {}),
        ("/v1/knowledge/search", {"query": "lease terms", "k": 3}),
    ):
        answered = await net.call("POST", path, admin, body=body)
        assert answered.json() != {"detail": "read_only"}, path
    refused = await net.call("PUT", PREFERENCES, admin, body={"default_office_id": None})
    assert refused.json() == {"detail": "read_only"}
