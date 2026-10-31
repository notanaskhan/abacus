# ac-test-author: ayushkbhatia
"""N-02-T22 (TASK-2232; ADR-078; DEC-1284): independent AC tests for N-02-T18 to T20 against the
database, written from the backlog rows and ADR-342.

Acceptance (the task row): "The suite passes and fails if an agent principal or an unconsumed
grant reaches the adapter." EnvelopeWorkflow's send activity is driven as the worker drives it,
for a send whose grant is unconsumed, voided, consumed for someone else, or consumed for its
sender: only the last reaches the provider, and its draft becomes Sent. An agent cannot be the
sender (the database refuses it). A webhook hint changes no envelope state; only a poll does.
The e-file family's identity methods have no SMS at the database either.

Boundary: the activity functions called as the worker calls them; the fake provider records
every call; outcomes through SQL.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.flags import forget_flags
from abacus.modules.signatures import activities, status_poll
from abacus.modules.signatures.api import EnvelopeInput, configure_provider
from abacus.modules.signatures.status_poll import ProviderEvent, record_provider_hint
from abacus_tools.fakes.esign import FakeEsign

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
Grant = Literal["none", "unconsumed", "voided", "other_approver", "consumed"]
DIGEST: Final = "f" * 64


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeEsign]:
    settings.cache_clear()
    forget_flags()
    provider = FakeEsign()
    configure_provider(provider)
    hinted: list[uuid.UUID] = []

    async def hint(_tenant: uuid.UUID, envelope_id: uuid.UUID) -> None:
        hinted.append(envelope_id)

    monkeypatch.setattr(status_poll, "hint_envelope", hint)
    yield provider
    configure_provider(None)
    forget_flags()


@dataclass(frozen=True)
class Draft:
    net: Net
    tenant: uuid.UUID
    grace: Person
    other: Person
    site: Site
    envelope: uuid.UUID
    signer: uuid.UUID

    @property
    def given(self) -> EnvelopeInput:
        return EnvelopeInput(str(self.tenant), str(self.envelope))


async def _draft(net: Net, grant: Grant) -> Draft:
    """A draft Grace sent (as `builder.send` leaves it: still a draft, `sent_by` and `sent_at`
    set) whose grant is in the state named."""
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    other = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Kowal")
    await seed.member(site, grace, "manager")
    envelope, signer, now = uuid.uuid4(), uuid.uuid4(), datetime.now(UTC)
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Irene Kowal', 'client_person') RETURNING id",
        tenant,
        site.client_id,
    )
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, status, drafted_by_kind, drafted_by, sent_by, "
            "sent_at) VALUES ($1, $2, 2, 'form_8879', 'efile_authorization', $3, $4, "
            "'TY2025 Form 8879', 'fake', 'draft', 'human', $5, $5, $6)",
            (envelope, tenant, site.client_id, site.engagement_id, grace.user_id, now),
        ),
        (
            'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
            "evidence_version_id, sha256) VALUES ($1, $2, 1, $3, $4)",
            (tenant, envelope, site.version_id, "a" * 64),
        ),
        (
            'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
            "contact_id, identity_method) VALUES ($1, $2, $3, 1, 'contact', $4, 'kba')",
            (signer, tenant, envelope, contact),
        ),
    ]
    if grant != "none":
        approver = other.user_id if grant == "other_approver" else grace.user_id
        used = now if grant in ("consumed", "other_approver") else None
        statements.append(
            (
                "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, "
                "approver_user_id, engagement_id, payload_sha256, not_before, expires_at, "
                "used_at, consumer_ref, voided_at) VALUES ($1, 'envelope', $2, 'envelope.send', "
                "$3, $4, $5, $6, $7, $8, $9, $10)",
                (
                    tenant,
                    envelope,
                    approver,
                    site.engagement_id,
                    DIGEST,
                    now - timedelta(seconds=30),
                    now + timedelta(hours=1),
                    used,
                    uuid.uuid4() if used is not None else None,
                    now if grant == "voided" else None,
                ),
            )
        )
    await seed.run_untriggered_many(statements)
    return Draft(net, tenant, grace, other, site, envelope, signer)


async def _status(d: Draft) -> str:
    return str(await d.net.seed.value("SELECT status FROM envelopes WHERE id = $1", d.envelope))


# --- The acceptance ------------------------------------------------------------------------------


@pytest.mark.parametrize("grant", ["none", "unconsumed", "voided", "other_approver"])
async def test_ac_no_grant_consumed_for_the_sender_never_reaches_the_adapter(
    net: Net, fake: FakeEsign, grant: Grant
) -> None:
    d = await _draft(net, grant)
    plan = await activities.envelope_send(d.given)
    assert plan.status == "not_sent"
    assert fake.calls == []  # the adapter was never reached
    assert await _status(d) == "draft"
    kinds = await net.seed.rows(
        "SELECT kind FROM envelope_events WHERE envelope_id = $1", d.envelope
    )
    assert [k["kind"] for k in kinds] == ["envelope.send_refused"]
    assert "envelope.send_refused" in await net.seed.actions(d.tenant)


async def test_ac_a_grant_consumed_for_its_sender_sends_once_and_the_draft_is_sent(
    net: Net, fake: FakeEsign
) -> None:
    d = await _draft(net, "consumed")
    assert (await activities.envelope_send(d.given)).status == "sent"
    assert (await activities.envelope_send(d.given)).status == "sent"  # a retried activity
    assert fake.calls.count("create_and_send") == 1
    assert await _status(d) == "sent"
    calls = await net.seed.value(
        "SELECT count(*) FROM envelope_provider_calls WHERE envelope_id = $1", d.envelope
    )
    assert calls == 1


_AS = (
    "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true), "
    "set_config('app.actor_kind', $4::text, true), set_config('app.actor_id', $2::text, true)) "
    "UPDATE envelopes SET sent_by = $2::uuid, sent_at = now() FROM t WHERE id = $3"
)


async def test_ac_an_agent_principal_can_never_be_the_sender(net: Net) -> None:
    d = await _draft(net, "none")
    await net.seed.run_untriggered_many(
        [("UPDATE envelopes SET sent_by = NULL, sent_at = NULL WHERE id = $1", (d.envelope,))]
    )
    for kind in ("agent", "system"):
        with pytest.raises(asyncpg.PostgresError):
            await net.seed.run(_AS, str(d.tenant), str(d.other.user_id), d.envelope, kind)
    # The same write as that person succeeds: the refusal is the principal's kind.
    await net.seed.run(_AS, str(d.tenant), str(d.other.user_id), d.envelope, "human")
    sent_by = await net.seed.value("SELECT sent_by FROM envelopes WHERE id = $1", d.envelope)
    assert sent_by == d.other.user_id


# --- Webhooks never change state without a poll ------------------------------------------------


async def test_a_webhook_hint_changes_nothing_until_the_poll_reads_the_provider(
    net: Net, fake: FakeEsign
) -> None:
    d = await _draft(net, "consumed")
    await activities.envelope_send(d.given)
    pid = str(
        await net.seed.value(
            "SELECT provider_envelope_id FROM envelopes WHERE id = $1", d.envelope
        )
    )
    fake.sign(pid, str(d.signer))  # the provider has it signed; we have not looked
    assert await record_provider_hint(d.tenant, d.envelope, ProviderEvent(pid, "e" * 64))
    assert await _status(d) == "sent"
    signer = await net.seed.value("SELECT status FROM envelope_signers WHERE id = $1", d.signer)
    assert signer == "pending"
    assert await activities.envelope_poll(d.given) == "completed"  # the poll is the truth


# --- No SMS for the e-file family, at the database --------------------------------------------


async def test_the_database_refuses_an_sms_identity_method(net: Net) -> None:
    d = await _draft(net, "none")
    with pytest.raises(asyncpg.CheckViolationError):
        await net.seed.run(
            "UPDATE envelope_signers SET identity_method = 'sms_code' WHERE id = $1", d.signer
        )
