"""F-04-T23: independent AC tests for the synthetic mail sink (ADR-078, solo edition: written
from the ACs before the code; SPEC-307 AC-5; F-04.22, F-04.23).

- F-04.22: given a firm with `firms.synthetic = true`, when communications sends any email, the
  recipient is rewritten to the sink before the transport sees it; a non-sink recipient after
  the rewrite is refused and logged without the address. It holds for `brightwaterhale.com`.
- F-04.23: `FakeSesTransport` produces the delivery events the SES adapter would for the mailbox
  simulator's addresses, and the harness's `mail.latest(to)` returns the 6-digit code.
- Acceptance (F-04-T23): rewrite, refusal and address-free logging for synthetic tenants on
  every transport (`LocalMailbox`, `FakeSesTransport`, `SesTransport`).

Sends run as the app role through `communications`' `send_email`, the one path out (COMM-001).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.config import Settings, settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.communications import sink
from abacus.modules.communications.api import (
    LOCAL_SINK_DOMAIN,
    FakeSesEventQueue,
    FakeSesTransport,
    LocalMailbox,
    Transport,
    configure_transport,
    send_email,
)
from abacus.modules.communications.deliveries import configure_ses_event_queue, drain_ses_events
from abacus.modules.communications.transport import SesTransport
from abacus_tools.harness.mailbox import LocalMailboxReader, parse_raw

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

SINK = LOCAL_SINK_DOMAIN  # the scenario's sink (SPEC-307 AC-5): sink.brightwaterhale.test


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    configure_transport(None)
    configure_ses_event_queue(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _firm(seed: Seeder, *, synthetic: bool) -> uuid.UUID:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = $2 WHERE tenant_id = $1", tenant, synthetic)
    return tenant


@dataclass
class _SesClient:
    """Stands in for boto3's SES v2 client: records what would go to AWS."""

    calls: list[dict[str, object]] = field(default_factory=list[dict[str, object]])

    def send_email(self, **kwargs: object) -> dict[str, str]:
        self.calls.append(kwargs)
        return {"MessageId": "fake"}


def _ses_recipients(client: _SesClient) -> list[str]:
    destinations = [cast(dict[str, list[str]], c["Destination"]) for c in client.calls]
    return [to for d in destinations for to in d["ToAddresses"]]


Recipients = Callable[[], list[str]]


def _transports(tmp_path: Path) -> dict[str, tuple[Transport, Recipients]]:
    local, fake = tmp_path / "local", tmp_path / "fake"
    ses = _SesClient()
    return {
        "LocalMailbox": (
            LocalMailbox(local),
            lambda: [m.to for m in LocalMailboxReader(local).messages()],
        ),
        "FakeSesTransport": (
            FakeSesTransport(fake),
            lambda: [m.to for m in LocalMailboxReader(fake).messages()],
        ),
        "SesTransport": (
            SesTransport(
                ses,  # type: ignore[arg-type]  # a recording stand-in for the boto3 client
                configuration_set="abacus-test",
                from_address="no-reply@platform.example.test",
            ),
            lambda: _ses_recipients(ses),
        ),
    }


TRANSPORTS = ("LocalMailbox", "FakeSesTransport", "SesTransport")


async def _send(tenant: uuid.UUID, to: str) -> bool:
    return await send_email(
        tenant_id=tenant,
        message_id=uuid.uuid4(),
        to=to,
        subject="Your sign-in code",
        body="Your code is 482913. It expires in 10 minutes.",
        sender_name="Brightwater Hale",
    )


# --- F-04.22: rewrite --------------------------------------------------------------------------


@pytest.mark.parametrize("name", TRANSPORTS)
@pytest.mark.parametrize(
    "address",
    [
        "claire.feld@brightwaterhale.com",  # may be a real domain
        "Claire.Feld@BRIGHTWATERHALE.COM",
        "dana@northwind.example",
        f"owen@{SINK}.evil.example",  # a look-alike ending
        f"owen@evil-{SINK}",
        f"owen@mail.{SINK}",  # a subdomain is not the sink
    ],
)
async def test_f0422_a_synthetic_firms_recipient_reaches_the_transport_on_the_sink(
    seed: Seeder, tmp_path: Path, name: str, address: str
) -> None:
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)[name]
    configure_transport(transport)
    assert await _send(tenant, address) is True
    (delivered,) = recipients()
    local, _, domain = delivered.rpartition("@")
    assert domain == SINK
    assert local.endswith(f"+{tenant.hex[:8]}")
    assert address.split("@")[1].lower() not in delivered.lower().removesuffix(f"@{SINK}")


@pytest.mark.parametrize("name", TRANSPORTS)
async def test_f0422_an_address_already_on_the_sink_is_kept(
    seed: Seeder, tmp_path: Path, name: str
) -> None:
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)[name]
    configure_transport(transport)
    assert await _send(tenant, f"claire.feld@{SINK}")
    assert recipients() == [f"claire.feld@{SINK}"]


@pytest.mark.parametrize("name", TRANSPORTS)
async def test_f0422_a_real_firms_mail_is_not_rewritten(
    seed: Seeder, tmp_path: Path, name: str
) -> None:
    tenant = await _firm(seed, synthetic=False)
    transport, recipients = _transports(tmp_path)[name]
    configure_transport(transport)
    assert await _send(tenant, "partner@realfirm.example")
    assert recipients() == ["partner@realfirm.example"]


async def test_f0422_a_configured_sink_domain_wins(
    seed: Seeder, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_MAIL_SINK_DOMAIN", "sink.staging.example")
    settings.cache_clear()
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)["SesTransport"]
    configure_transport(transport)
    assert await _send(tenant, "claire.feld@brightwaterhale.com")
    assert recipients() == [f"claire.feld+{tenant.hex[:8]}@sink.staging.example"]


# --- F-04.22: refusal, logged without the address ---------------------------------------------


def _staging_without_sink() -> Settings:
    """Staging that set no sink domain: the configuration a synthetic send must not leave."""
    return settings().model_copy(update={"environment": "staging", "mail_sink_domain": None})


@pytest.mark.parametrize("name", TRANSPORTS)
async def test_f0422_with_no_sink_the_send_is_refused_and_logged_without_the_address(
    seed: Seeder,
    tmp_path: Path,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)[name]
    configure_transport(transport)
    monkeypatch.setattr(sink, "settings", _staging_without_sink)
    capsys.readouterr()
    assert await _send(tenant, "claire.feld@brightwaterhale.com") is False
    assert recipients() == []
    logged = capsys.readouterr()
    text = logged.out + logged.err
    assert "email.sink_refused" in text
    assert str(tenant) in text
    for part in ("claire", "feld", "brightwaterhale.com", "@"):
        assert part not in text.lower().replace(f"{tenant}", "")


@pytest.mark.parametrize("address", ["no-at-sign", "@brightwaterhale.com", "claire.feld@"])
async def test_f0422_an_address_the_sink_cannot_take_is_refused(
    seed: Seeder, tmp_path: Path, address: str
) -> None:
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)["FakeSesTransport"]
    configure_transport(transport)
    assert await _send(tenant, address) is False
    assert recipients() == []


async def test_f0422_rewritten_addresses_keep_one_line_and_a_bounded_local_part(
    seed: Seeder, tmp_path: Path
) -> None:
    tenant = await _firm(seed, synthetic=True)
    transport, recipients = _transports(tmp_path)["LocalMailbox"]
    configure_transport(transport)
    assert await _send(tenant, f"{'x' * 90}+tag<script>@brightwaterhale.com")
    (delivered,) = recipients()
    local = delivered.rpartition("@")[0]
    assert len(local) <= 64
    assert all(c.isalnum() or c in "._-+" for c in local)


# --- F-04.23: the SES-shaped fake and the mailbox reader ---------------------------------------


@pytest.mark.parametrize(
    ("address", "event", "suppressed"),
    [
        ("success@simulator.amazonses.com", "delivered", False),
        ("bounce@simulator.amazonses.com", "bounced", True),
        ("complaint@simulator.amazonses.com", "complained", True),
        ("suppressionlist@simulator.amazonses.com", "bounced", True),
    ],
)
async def test_f0423_the_fake_emits_the_events_ses_would_and_the_drain_records_them(
    seed: Seeder, tmp_path: Path, address: str, event: str, suppressed: bool
) -> None:
    tenant = await _firm(seed, synthetic=False)  # the simulator is not a sink address
    queue = FakeSesEventQueue()
    configure_transport(FakeSesTransport(tmp_path, queue))
    configure_ses_event_queue(queue)
    message = uuid.uuid4()
    assert await send_email(
        tenant_id=tenant, message_id=message, to=address, subject="Hello", body="A note."
    )
    assert len(queue) == 1
    assert await drain_ses_events() == 1
    assert len(queue) == 0
    rows = await seed.rows(
        "SELECT event FROM message_deliveries WHERE tenant_id = $1 AND message_id = $2",
        tenant,
        message,
    )
    assert [r["event"] for r in rows] == [event]
    held = await seed.value("SELECT count(*) FROM email_suppressions WHERE tenant_id = $1", tenant)
    assert held == (1 if suppressed else 0)
    if suppressed:  # the next send to that address is refused before the transport
        assert not await send_email(
            tenant_id=tenant, message_id=uuid.uuid4(), to=address, subject="Hi", body="Again."
        )
        assert len(queue) == 0


async def test_f0423_the_fake_refuses_what_ses_refuses(tmp_path: Path) -> None:
    fake = FakeSesTransport(tmp_path)
    with pytest.raises(ValueError, match="tenant ID and message ID"):
        fake.send(to=f"a@{SINK}", subject="s", body="b")
    with pytest.raises(ValueError, match="line break"):
        fake.send(
            to=f"a@{SINK}",
            subject="s\nBcc: x@evil.example",
            body="b",
            tenant_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )
    assert LocalMailboxReader(tmp_path).messages() == []


async def test_f0423_mail_latest_returns_the_sign_in_code(seed: Seeder, tmp_path: Path) -> None:
    tenant = await _firm(seed, synthetic=True)
    configure_transport(FakeSesTransport(tmp_path))
    to = f"claire.feld@{SINK}"
    for code in ("111111", "482913"):
        assert await send_email(
            tenant_id=tenant,
            message_id=uuid.uuid4(),
            to=to,
            subject="Your sign-in code",
            body=f"Your code is {code}. It expires in 10 minutes.",
        )
    reader = LocalMailboxReader(tmp_path)
    latest = reader.latest(to.upper())
    assert latest is not None and latest.code == "482913"
    assert reader.latest("nobody@" + SINK) is None


def test_f0423_the_staging_reader_parses_what_the_receipt_rule_stores() -> None:
    raw = (
        b"From: Brightwater Hale <no-reply@platform.example.test>\r\n"
        b"To: claire.feld+0a1b2c3d@sink.staging.example\r\n"
        b"Subject: Your sign-in code\r\n"
        b"Date: Mon, 14 Sep 2026 14:24:00 +0000\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Your code is 905114. It expires in 10 minutes.\r\n"
    )
    (mail,) = parse_raw(raw)
    assert (mail.to, mail.sender_name, mail.code) == (
        "claire.feld+0a1b2c3d@sink.staging.example",
        "Brightwater Hale",
        "905114",
    )
