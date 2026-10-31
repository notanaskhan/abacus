# ac-test-author: ayushkbhatia
"""N-02-T24 (TASK-2234; N-02 §4.8; DEC-1286): N-02's registrations against the database.

Acceptance (the task row): "Claire's Sign to-do appears on POR-02, the firm CSP is unchanged, and
no email copy lives in code." Claire, a named signer on an envelope out for signature, sees the
Sign to-do on her home; Jonah, on the same engagement but not on that envelope, does not. The CSP
and the committed-copy halves are `tests/unit/signatures/test_n02t24_registrations.py`.

Also: the `envelope_signer` floor predicate holds for a signer of an open envelope only, and a
decline the poll reads is the sender's `envelope_declined` notification.

Boundary: POR-02 over HTTP as the client person; the predicate and the poll called as identity
and the worker call them; outcomes through the response, SQL and the outbox.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.signatures import activities
from abacus.modules.signatures.api import EnvelopeInput, configure_provider
from abacus.modules.signatures.signer_facts import envelope_signer_mfa
from abacus_tools.fakes.esign import FakeEsign

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
FLAGS: Final = ("signatures.envelopes", "portal.home_v2")


@pytest.fixture
def fake() -> Iterator[FakeEsign]:
    settings.cache_clear()
    forget_flags()
    provider = FakeEsign()
    configure_provider(provider)
    yield provider
    configure_provider(None)
    forget_flags()


async def _world(net: Net) -> tuple[uuid.UUID, Person, Site, Person, Person]:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T24')",
            tenant,
            flag,
        )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Feld")
    await seed.member(site, grace, "manager")
    people: list[Person] = []
    for name in ("Claire Feld", "Jonah Feld"):
        who = await seed.client_contact(site)
        await seed.run(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
            "VALUES ($1, $2, $3, 'client_person', $4)",
            tenant,
            site.client_id,
            name,
            who.user_id,
        )
        people.append(who)
    return tenant, grace, site, people[0], people[1]


async def _envelope_to(
    net: Net, tenant: uuid.UUID, site: Site, sender: Person, signer: Person, *, due: date
) -> tuple[uuid.UUID, uuid.UUID]:
    envelope, signer_id, now = uuid.uuid4(), uuid.uuid4(), datetime.now(UTC)
    contact = await net.seed.value(
        "SELECT id FROM contacts WHERE tenant_id = $1 AND user_id = $2", tenant, signer.user_id
    )
    await net.seed.run_untriggered_many(
        [
            (
                "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, "
                "client_id, engagement_id, title, provider, status, drafted_by_kind, drafted_by, "
                "sent_by, sent_at, due_on) VALUES ($1, $2, 13, 'engagement_letter', "
                "'engagement_letter', $3, $4, 'Engagement letter', 'fake', 'sent', 'human', $5, "
                "$5, $6, $7)",
                (envelope, tenant, site.client_id, site.engagement_id, sender.user_id, now, due),
            ),
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method) VALUES ($1, $2, $3, 1, 'contact', $4, "
                "'email_code')",
                (signer_id, tenant, envelope, contact),
            ),
        ]
    )
    return envelope, signer_id


def _sign_todos(home: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in cast(list[dict[str, Any]], home["todos"]) if t["kind"] == "sign"]


async def test_ac_claires_sign_todo_appears_on_her_home_and_not_on_jonahs(net: Net) -> None:
    tenant, grace, site, claire, jonah = await _world(net)
    due = date.today() + timedelta(days=5)
    await _envelope_to(net, tenant, site, grace, claire, due=due)

    mine = await net.call("GET", "/v1/portal/home", claire)
    assert mine.status_code == 200, mine.text
    (todo,) = _sign_todos(mine.json())
    assert (todo["count"], todo["state"], todo["due_date"]) == (1, "open", due.isoformat())
    assert todo["target"]["screen"] == "POR-06"

    his = await net.call("GET", "/v1/portal/home", jonah)
    assert his.status_code == 200, his.text
    assert _sign_todos(his.json()) == []  # Claire's envelope is not Jonah's to sign


async def test_the_floor_covers_a_signer_of_an_open_envelope_only(net: Net) -> None:
    tenant, grace, site, claire, jonah = await _world(net)
    floor = TenantContext(tenant, "system", "portal:mfa")
    assert not await envelope_signer_mfa(floor, claire.user_id)
    envelope, _ = await _envelope_to(net, tenant, site, grace, claire, due=date.today())
    assert await envelope_signer_mfa(floor, claire.user_id)
    assert not await envelope_signer_mfa(floor, jonah.user_id)
    await net.seed.run_untriggered_many(
        [
            (
                "UPDATE envelopes SET status = 'completed', completed_at = now() WHERE id = $1",
                (envelope,),
            )
        ]
    )
    assert not await envelope_signer_mfa(floor, claire.user_id)


async def test_a_decline_the_poll_reads_tells_the_sender(net: Net, fake: FakeEsign) -> None:
    tenant, grace, site, claire, _ = await _world(net)
    envelope, signer = await _envelope_to(net, tenant, site, grace, claire, due=date.today())
    given = EnvelopeInput(str(tenant), str(envelope))
    await net.seed.run_untriggered_many(
        [
            (
                "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, "
                "approver_user_id, engagement_id, payload_sha256, not_before, expires_at, "
                "used_at, consumer_ref) VALUES ($1, 'envelope', $2, 'envelope.send', $3, $4, "
                "$5, now() - interval '1 minute', now() + interval '1 hour', "
                "now() - interval '1 minute', gen_random_uuid())",
                (tenant, envelope, grace.user_id, site.engagement_id, "e" * 64),
            )
        ]
    )
    assert (await activities.envelope_send(given)).status == "sent"
    pid = str(
        await net.seed.value("SELECT provider_envelope_id FROM envelopes WHERE id = $1", envelope)
    )
    fake.decline(pid, str(signer), "something_wrong")
    assert await activities.envelope_poll(given) == "declined"
    rows = await net.seed.rows(
        "SELECT payload->>'sent_by' AS sent_by FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'envelope.declined'",
        tenant,
    )
    assert [r["sent_by"] for r in rows] == [str(grace.user_id)]
