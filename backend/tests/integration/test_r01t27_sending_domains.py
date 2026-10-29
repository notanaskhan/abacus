"""R-01-T27 against Postgres (TASK-1850; C16 v1.1 §sending domains; migration 0340; DEC-950 to
DEC-955).

Acceptance: a firm's domain moves from Pending DNS to Verified on the fake, a real firm's client
mail is blocked before its flip, and a bounced address is suppressed. Around it: one live domain
per firm and per name across firms, the flag gate, 72 hours to Failed, revoke, the From of client
mail, the app role's reach into `firm_mail_policies`, and the operator function's two people.
Brightwater Hale's own domain is not used here: these are probe names."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.clock import frozen, system_now
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.communications import sending_domains
from abacus.modules.communications.deliveries import (
    delivery_status,
    parse_ses_event,
    record_ses_event,
)
from abacus.modules.communications.sending_domains import (
    VERIFY_WINDOW,
    SendingDomainExists,
    check_domain,
    client_mail_open,
    create_domain,
    list_domains,
    revoke_domain,
    sender_for,
)
from abacus.modules.communications.ses_identities import (
    InMemorySesIdentities,
    configure_ses_identities,
)
from abacus.modules.communications.transport import configure_transport

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_r01t19_email_template_versions import (
    Recorder,
    _firm,  # pyright: ignore[reportPrivateUsage] -- the R-01-T19 firm, reused
    _publish,  # pyright: ignore[reportPrivateUsage] -- the R-01-T19 helper, reused
    _send,  # pyright: ignore[reportPrivateUsage] -- the R-01-T19 helper, reused
)


def _name() -> str:
    """A probe domain of the test's own: a live name is unique across firms (DEC-951)."""
    return f"probe-{uuid.uuid4().hex[:10]}.test"


SENDER = "communications.firm_sender_domain"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def recorder() -> Iterator[Recorder]:
    found = Recorder()
    configure_transport(found)
    yield found
    configure_transport(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def ses() -> Iterator[InMemorySesIdentities]:
    fake = InMemorySesIdentities()
    configure_ses_identities(fake)
    yield fake
    configure_ses_identities(None)


async def _sender_on(seed: Seeder, tenant: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'r01t27', 'TASK-1850')",
        tenant,
        SENDER,
    )


async def _close_mail(seed: Seeder, tenant: uuid.UUID) -> None:
    await seed.run(
        "UPDATE firm_mail_policies SET client_mail_enabled = false WHERE tenant_id = $1", tenant
    )


async def _actions(seed: Seeder, tenant: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND action LIKE 'sending_domain.%' "
        "ORDER BY occurred_at",
        tenant,
    )
    return [str(r["action"]) for r in rows]


async def _outbox(seed: Seeder, tenant: uuid.UUID, event_type: str) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2", tenant, event_type
    )
    return [
        json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"] for r in rows
    ]


# --- acceptance --------------------------------------------------------------------------------


async def test_ac1_a_domain_moves_from_pending_dns_to_verified_on_the_fake(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    created = await create_domain(firm.admin, DOMAIN, "clients")
    assert created.status == "pending_dns" and created.mail_from_domain == f"bounce.{DOMAIN}"
    kinds = [r.type for r in created.records]
    assert kinds == ["CNAME", "CNAME", "CNAME", "MX", "TXT"]
    assert all(r.status == "pending" for r in created.records)
    started = await _outbox(seed, firm.tenant, "sending_domain.status_changed")
    assert [(e["domain_id"], e["status"]) for e in started] == [(str(created.id), "pending_dns")]

    ses.set_states(DOMAIN, verification="verified", dkim="verified", mail_from="verified")
    checked = await check_domain(firm.admin, created.id)
    assert checked.status == "verified" and checked.verified_at is not None
    assert all(r.status == "verified" for r in checked.records)
    assert await _actions(seed, firm.tenant) == [
        "sending_domain.created",
        "sending_domain.verified",
    ]
    assert len(await _outbox(seed, firm.tenant, "sending_domain.verified")) == 1
    # With the flag on, client mail goes From the firm's own address (story 8.3).
    sender = await sender_for(firm.tenant)
    assert sender.address == f"clients@{DOMAIN}" and sender.from_domain == DOMAIN


async def test_ac2_a_real_firms_client_mail_is_blocked_before_its_flip(
    seed: Seeder,
    recorder: Recorder,
) -> None:
    firm = await _firm(seed)
    await _close_mail(seed, firm.tenant)
    await _publish(firm, "Reminder")
    outcome = await _send(firm, attempt=1)
    assert (outcome.status, outcome.blocked_reason) == ("blocked", "firm_not_client_facing")
    assert recorder.sent == []
    rows = await seed.rows(
        "SELECT status, violations FROM messages WHERE id = $1", outcome.message_id
    )
    assert rows[0]["status"] == "blocked"
    # The flip opens it (two people named); the next send goes.
    await seed.run(
        "SELECT set_client_mail($1, true, 'probe-one', 'probe-two', 'CR-probe')", firm.tenant
    )
    assert await client_mail_open(firm.tenant)
    assert (await _send(firm, attempt=2)).status == "queued"
    assert len(recorder.sent) == 1


async def test_ac2_a_synthetic_firm_is_open_without_a_flip(seed: Seeder) -> None:
    tenant = await seed.firm()
    assert not await client_mail_open(tenant)  # a real firm, no row: closed
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    assert await client_mail_open(tenant)


async def test_ac3_a_bounced_address_is_suppressed_and_its_status_reads_bounced(
    seed: Seeder,
    recorder: Recorder,
) -> None:
    firm = await _firm(seed)
    await _publish(firm, "Reminder")
    first = await _send(firm, attempt=1)
    assert first.status == "queued"
    address = str(
        await seed.value("SELECT email FROM users WHERE id = $1", firm.recipient.user_id)
    )
    event = parse_ses_event(
        json.dumps(
            {
                "id": "ev-r01t27-bounce",
                "time": "2026-09-14T14:30:00Z",
                "detail": {
                    "eventType": "Bounce",
                    "mail": {
                        "tags": {
                            "tenant_id": [str(firm.tenant)],
                            "message_id": [str(first.message_id)],
                        }
                    },
                    "bounce": {
                        "bounceType": "Permanent",
                        "bouncedRecipients": [{"emailAddress": address}],
                    },
                },
            }
        )
    )
    assert event is not None and await record_ses_event(event)
    assert await delivery_status(firm.admin.tenant, first.message_id) == "bounced"
    changed = await _outbox(seed, firm.tenant, "message.delivery_status_changed")
    assert [c["status"] for c in changed] == ["bounced"]
    later = await _send(firm, attempt=2)
    assert (later.status, later.blocked_reason) == ("blocked", "suppressed")
    assert len(recorder.sent) == 1


# --- around the acceptance -----------------------------------------------------------------------


async def test_one_live_domain_per_firm_and_per_name(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    del ses
    firm, other = await _firm(seed), await _firm(seed)
    for f in (firm, other):
        await _sender_on(seed, f.tenant)
    await create_domain(firm.admin, DOMAIN, "clients")
    with pytest.raises(SendingDomainExists):
        await create_domain(firm.admin, "second-probe.test", "clients")
    with pytest.raises(SendingDomainExists):  # another firm can't claim a live domain (DEC-951)
        await create_domain(other.admin, DOMAIN, "clients")
    assert await list_domains(other.admin) == []  # nor see it


async def test_writes_are_404_with_the_flag_off_and_reads_are_not_gated(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    del ses
    firm = await _firm(seed)
    with pytest.raises(NotFound):
        await create_domain(firm.admin, DOMAIN, "clients")
    assert await list_domains(firm.admin) == []


async def test_72_hours_without_verification_is_failed_and_mail_keeps_the_neutral_sender(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    created = await create_domain(firm.admin, DOMAIN, "clients")
    ses.set_states(DOMAIN, verification="pending", dkim="verified", mail_from="pending")
    with frozen(system_now() + VERIFY_WINDOW + VERIFY_WINDOW):
        checked = await check_domain(firm.admin, created.id)
    assert (checked.status, checked.failure_reason) == ("failed", "mail_from_not_verified")
    assert len(await _outbox(seed, firm.tenant, "sending_domain.failed")) == 1
    sender = await sender_for(firm.tenant)
    # A failed domain is not proven to be the firm's: no From and no Reply-To there.
    assert sender.address is None and sender.reply_to is None


async def test_revoke_ends_the_domain_and_deletes_the_identity(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    created = await create_domain(firm.admin, DOMAIN, "clients")
    revoked = await revoke_domain(firm.admin, created.id)
    assert revoked.status == "revoked"
    assert (await revoke_domain(firm.admin, created.id)).status == "revoked"  # idempotent
    with pytest.raises(LookupError):
        ses.identity_status(domain=DOMAIN)
    assert (await sender_for(firm.tenant)).reply_to is None
    # A revoked domain frees its name for a new request.
    assert (await create_domain(firm.admin, DOMAIN, "clients")).status == "pending_dns"


async def test_a_verified_domain_with_the_flag_off_is_the_reply_to_of_the_neutral_sender(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    created = await create_domain(firm.admin, DOMAIN, "clients")
    ses.set_states(DOMAIN, verification="verified", dkim="verified", mail_from="verified")
    await check_domain(firm.admin, created.id)
    await seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        firm.tenant,
        SENDER,
    )
    forget_flags()
    sender = await sender_for(firm.tenant)
    assert sender.address is None and sender.reply_to == f"clients@{DOMAIN}"  # RK-52


async def test_revoking_a_failed_row_leaves_a_live_identity_of_the_same_name_alone(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    """Security review: a failed row's name can be live again (here, re-added); its revoke must not
    delete the identity the live row now uses."""
    DOMAIN = _name()
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    first = await create_domain(firm.admin, DOMAIN, "clients")
    with frozen(system_now() + VERIFY_WINDOW + VERIFY_WINDOW):
        assert (await check_domain(firm.admin, first.id)).status == "failed"
    again = await create_domain(firm.admin, DOMAIN, "clients")
    await revoke_domain(firm.admin, first.id)
    assert ses.identity_status(domain=DOMAIN).domain == DOMAIN  # still there for `again`
    assert (await check_domain(firm.admin, again.id)).status == "pending_dns"


async def test_another_firms_live_name_is_refused_before_ses_is_asked(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    firm, other = await _firm(seed), await _firm(seed)
    for f in (firm, other):
        await _sender_on(seed, f.tenant)
    await create_domain(firm.admin, DOMAIN, "clients")
    asked: list[str] = []
    real = ses.create_identity

    def spy(*, domain: str, mail_from_subdomain: str):  # noqa: ANN202 -- the port's return
        asked.append(domain)
        return real(domain=domain, mail_from_subdomain=mail_from_subdomain)

    ses.create_identity = spy
    with pytest.raises(SendingDomainExists):
        await create_domain(other.admin, DOMAIN, "clients")
    assert asked == []


async def test_the_app_role_can_neither_read_nor_write_the_mail_policy(seed: Seeder) -> None:
    firm = await _firm(seed)
    async with tenant_session(firm.admin.tenant) as session:
        with pytest.raises(DBAPIError):
            await session.execute(text("SELECT * FROM firm_mail_policies"))
    async with tenant_session(firm.admin.tenant) as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("SELECT set_client_mail(:t, true, 'a', 'b', 'x')"), {"t": firm.tenant}
            )


async def test_the_operator_function_names_two_different_people(seed: Seeder) -> None:
    firm = await _firm(seed)
    with pytest.raises(Exception, match="two different people"):
        await seed.run(
            "SELECT set_client_mail($1, true, 'probe-one', 'probe-one', 'CR')", firm.tenant
        )
    await seed.run("SELECT set_client_mail($1, false, 'probe-one', NULL, 'CR')", firm.tenant)
    actions = await seed.rows(
        "SELECT action, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'firm_mail_policy.%'",
        firm.tenant,
    )
    assert [(r["action"], r["actor_id"]) for r in actions] == [
        ("firm_mail_policy.client_mail_disabled", "operator:probe-one")
    ]


async def test_a_revoked_domain_never_moves_again(
    seed: Seeder, ses: InMemorySesIdentities
) -> None:
    DOMAIN = _name()
    del ses
    firm = await _firm(seed)
    await _sender_on(seed, firm.tenant)
    created = await create_domain(firm.admin, DOMAIN, "clients")
    await revoke_domain(firm.admin, created.id)
    with pytest.raises(Exception, match="not a transition"):
        await seed.run(
            "UPDATE sending_domains SET status = 'verified', verified_at = now() WHERE id = $1",
            created.id,
        )
    assert frozenset({"pending_dns", "verified"}) == sending_domains.LIVE
