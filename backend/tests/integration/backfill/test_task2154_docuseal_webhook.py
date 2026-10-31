"""TASK-2154 (ADR-152 accepted with its amendment; ADR-342, ADR-041; DEC-1281) against Postgres and
the real route: `POST /v1/webhooks/docuseal/{tenant_id}/{install_id}`.

A delivery signed with the install's key becomes one hint, recorded once per provider event and
signalled once, and changes no envelope state; a forged, stale or unsigned delivery, a delivery
for another install or another firm, a firm whose kill switch is off and an install with no
webhook key are refused 401 with nothing written; an oversized body is 413; a submission the
firm has no open envelope for is acknowledged and dropped; one envelope takes at most ten hints a
minute; and no answer has a body.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.modules.integrations.api import connect_esign_install
from abacus.modules.platform.api import operator_context
from abacus.modules.signatures import status_poll, webhook
from abacus_tools import esign_install as tool

from .support import Migrated, Net

pytestmark = pytest.mark.asyncio
OPERATOR = "probe-op"
API_KEY = "synthetic0key0for0webhooks0not0a0secret"
HOOK = "whsec_synthetic0webhook0key0not0a0secret"


def _ops(migrated_db: Migrated) -> str:
    url = migrated_db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _firm(
    net: Net, migrated_db: Migrated, *, hooks: tuple[str, ...] = (HOOK,)
) -> dict[str, uuid.UUID]:
    """A firm with an envelope open at DocuSeal (submission 41) and a connected install."""
    seed = net.seed
    await tool.ensure_catalogue_row(_ops(migrated_db), OPERATOR)
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
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
                    admin.user_id,
                    now,
                    now + timedelta(days=20),
                ),
            )
        ]
    )
    install = await connect_esign_install(
        operator_context(tenant, OPERATOR), admin.user_id, tool.secret_of(API_KEY, hooks)
    )
    return {"tenant": tenant, "install": install, "envelope": envelope}


def _body(kind: str = "form.completed", submission: int = 41, actor: int = 101) -> bytes:
    return json.dumps(
        {
            "event_type": kind,
            "timestamp": "2027-06-01T09:40:12.000Z",
            "data": {"id": actor, "status": "completed", "submission": {"id": submission}},
        }
    ).encode()


def _signed(body: bytes, key: str = HOOK, at: int | None = None) -> str:
    stamp = str(at if at is not None else int(time.time()))
    digest = hmac.new(key.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"{stamp}.{digest}"


async def _post(
    net: Net, firm: dict[str, uuid.UUID], body: bytes, header: str | None, **over: uuid.UUID
) -> tuple[int, bytes]:
    tenant, install = over.get("tenant", firm["tenant"]), over.get("install", firm["install"])
    headers = {"Content-Type": "application/json"}
    if header is not None:
        headers["X-Docuseal-Signature"] = header
    got = await net.http.post(
        f"/v1/webhooks/docuseal/{tenant}/{install}", content=body, headers=headers
    )
    return got.status_code, got.content


async def _hints(net: Net, envelope: uuid.UUID) -> int:
    found = await net.seed.value(
        "SELECT count(*) FROM envelope_events WHERE envelope_id = $1 "
        "AND kind = 'envelope.provider_hint'",
        envelope,
    )
    return int(str(found))


@pytest.fixture
def signalled(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    seen: list[uuid.UUID] = []

    async def capture(_tenant: uuid.UUID, envelope_id: uuid.UUID) -> None:
        seen.append(envelope_id)

    async def on(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(status_poll, "hint_envelope", capture)
    monkeypatch.setattr(webhook, "flag_enabled", on)
    return seen


async def test_a_signed_delivery_is_one_hint_and_changes_no_state(
    net: Net, migrated_db: Migrated, signalled: list[uuid.UUID]
) -> None:
    firm = await _firm(net, migrated_db)
    body = _body()
    assert await _post(net, firm, body, _signed(body)) == (202, b"")
    assert await _post(net, firm, body, _signed(body)) == (202, b"")  # DocuSeal's retry
    assert await _hints(net, firm["envelope"]) == 1
    assert signalled == [firm["envelope"]]
    status = await net.seed.value("SELECT status FROM envelopes WHERE id = $1", firm["envelope"])
    assert status == "sent"  # the body said completed; only the poll may say so (ADR-041)


async def test_forged_stale_or_unsigned_deliveries_are_refused_and_write_nothing(
    net: Net, migrated_db: Migrated, signalled: list[uuid.UUID]
) -> None:
    firm = await _firm(net, migrated_db)
    body = _body()
    refused = [
        _signed(body, key="whsec_not0the0install0key0at0all"),
        _signed(body, at=int(time.time()) - 600),  # outside the five-minute window
        _signed(body)[:-2] + "00",
        "not-a-signature",
        None,
    ]
    for header in refused:
        assert await _post(net, firm, body, header) == (401, b"")
    assert await _hints(net, firm["envelope"]) == 0
    assert signalled == []


async def test_another_install_or_firm_in_the_path_is_refused(
    net: Net, migrated_db: Migrated, signalled: list[uuid.UUID]
) -> None:
    firm = await _firm(net, migrated_db)
    other = await _firm(net, migrated_db)
    body = _body()
    assert await _post(net, firm, body, _signed(body), install=uuid.uuid4()) == (401, b"")
    assert await _post(net, firm, body, _signed(body), install=other["install"]) == (401, b"")
    assert await _post(net, firm, body, _signed(body), tenant=other["tenant"]) == (401, b"")
    assert await _hints(net, firm["envelope"]) == 0 and signalled == []


async def test_the_kill_switch_and_a_keyless_install_refuse(
    net: Net, migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch
) -> None:
    keyless = await _firm(net, migrated_db, hooks=())
    body = _body()
    assert await _post(net, keyless, body, _signed(body)) == (401, b"")

    async def off(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(webhook, "flag_enabled", off)
    firm = await _firm(net, migrated_db)
    assert await _post(net, firm, body, _signed(body)) == (401, b"")
    assert await _hints(net, firm["envelope"]) == 0


async def test_an_oversized_or_unknown_delivery_is_refused_or_dropped(
    net: Net, migrated_db: Migrated, signalled: list[uuid.UUID]
) -> None:
    firm = await _firm(net, migrated_db)
    big = b'{"pad": "' + b"x" * (webhook.MAX_BODY_BYTES + 1) + b'"}'
    assert (await _post(net, firm, big, _signed(big)))[0] == 413
    stranger = _body(submission=999)
    assert await _post(net, firm, stranger, _signed(stranger)) == (202, b"")
    shapeless = b'{"event_type": "template.created", "timestamp": "x", "data": {}}'
    assert await _post(net, firm, shapeless, _signed(shapeless)) == (202, b"")
    assert await _hints(net, firm["envelope"]) == 0 and signalled == []


async def test_one_envelope_takes_at_most_ten_hints_a_minute(
    net: Net, migrated_db: Migrated, signalled: list[uuid.UUID]
) -> None:
    firm = await _firm(net, migrated_db)
    for actor in range(webhook.HINTS_PER_MINUTE + 3):
        body = _body(kind="form.viewed", actor=actor)
        assert await _post(net, firm, body, _signed(body)) == (202, b"")
    assert await _hints(net, firm["envelope"]) == webhook.HINTS_PER_MINUTE
    assert len(signalled) == webhook.HINTS_PER_MINUTE
