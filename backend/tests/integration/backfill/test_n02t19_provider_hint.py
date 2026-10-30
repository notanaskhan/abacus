# ac-test-author: ayushkbhatia
"""N-02-T19 rework (TASK-2150; ADR-342, ADR-041; DEC-1277): a verified DocuSeal webhook is a hint.

Acceptance (the task row): "A webhook (if mounted) changes nothing until the poll confirms, a
forged one is refused, and a duplicate state change is recorded once." The forged half is the
pure suite `tests/unit/signatures/test_n02t19_webhook_hint.py`; this drives the recording against
the database: a delivery is recorded once per provider event id, a retried delivery records
nothing more and signals nothing, and the envelope's status is untouched (only the poll moves it).

Boundary: `status_poll.record_provider_hint` as the receiver will call it; outcomes through SQL;
the workflow signal captured.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.modules.signatures import status_poll
from abacus.modules.signatures.status_poll import record_provider_hint, webhook_event

from .support import Net

pytestmark = pytest.mark.asyncio


async def _sent_at_docuseal(net: Net) -> tuple[uuid.UUID, uuid.UUID]:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Kowal")
    envelope = uuid.uuid4()
    now = datetime.now(UTC)
    await seed.run_untriggered_many(
        [
            (
                "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
                "engagement_id, title, provider, provider_envelope_id, status, drafted_by_kind, "
                "drafted_by, sent_by, sent_at, expires_at, reminder_cadence) VALUES ($1, $2, 1, "
                "'engagement_letter', 'engagement_letter', $3, $4, 'Engagement letter', "
                "'docuseal', '41', 'sent', 'human', $5, $5, $6, $7, 'daily')",
                (
                    envelope,
                    tenant,
                    site.client_id,
                    site.engagement_id,
                    grace.user_id,
                    now,
                    now + timedelta(days=20),
                ),
            )
        ]
    )
    return tenant, envelope


def _delivery(kind: str) -> bytes:
    return json.dumps(
        {
            "event_type": kind,
            "timestamp": "2027-06-01T09:40:12.000Z",
            "data": {"id": 101, "status": "completed", "submission": {"id": 41}},
        }
    ).encode()


async def test_ac_a_duplicate_is_recorded_once_and_the_hint_changes_no_state(
    net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, envelope = await _sent_at_docuseal(net)
    signalled: list[uuid.UUID] = []

    async def capture(_tenant: uuid.UUID, envelope_id: uuid.UUID) -> None:
        signalled.append(envelope_id)

    monkeypatch.setattr(status_poll, "hint_envelope", capture)
    event = webhook_event(_delivery("form.completed"))
    assert event is not None and event.provider_envelope_id == "41"

    assert await record_provider_hint(tenant, envelope, event) is True
    assert await record_provider_hint(tenant, envelope, event) is False  # a retried delivery
    assert signalled == [envelope]

    seed = net.seed
    hints = await seed.rows(
        "SELECT source, provider_event_id FROM envelope_events "
        "WHERE envelope_id = $1 AND kind = 'envelope.provider_hint'",
        envelope,
    )
    assert [(h["source"], h["provider_event_id"]) for h in hints] == [
        ("provider_webhook", event.event_id)
    ]
    # The body said "completed"; only the poll may say so (ADR-041).
    assert await seed.value("SELECT status FROM envelopes WHERE id = $1", envelope) == "sent"
    assert (
        await seed.value(
            "SELECT count(*) FROM envelope_signers WHERE envelope_id = $1 AND status = 'signed'",
            envelope,
        )
        == 0
    )


async def test_a_different_event_for_the_same_submission_is_its_own_hint(
    net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, envelope = await _sent_at_docuseal(net)

    async def ignore(_tenant: uuid.UUID, _envelope: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(status_poll, "hint_envelope", ignore)
    viewed = webhook_event(_delivery("form.viewed"))
    completed = webhook_event(_delivery("form.completed"))
    assert viewed is not None and completed is not None
    assert await record_provider_hint(tenant, envelope, viewed) is True
    assert await record_provider_hint(tenant, envelope, completed) is True
    count = await net.seed.value(
        "SELECT count(*) FROM envelope_events "
        "WHERE envelope_id = $1 AND kind = 'envelope.provider_hint'",
        envelope,
    )
    assert count == 2
