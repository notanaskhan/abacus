"""The two targets of the QuickBooks Online conformance suite (A-02-T32; ADR-044; chapter 10
§10.7.4): the fake every pull request, the sandbox nightly.

- `fake`: the real connector over A-02-T27's recorded transport (`abacus_tools.fakes.ledgers.
  RecordedQbo`), answering this suite's synthetic recording.
- `sandbox`: the real connector over the kernel's egress client to Intuit's sandbox, only when
  `ABACUS_QBO_SANDBOX_CLIENT_ID`, `_CLIENT_SECRET`, `_REFRESH_TOKEN` and `_REALM_ID` are set (the
  nightly job's secrets). The first call refreshes, so the run starts from a rotation.

Either way every request goes through `Logged`, which records the method and URL, so the suite
can prove the connector only reads.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.egress import EgressClient, EgressResponse, configure_egress
from abacus.modules.connections.connector import Period
from abacus.modules.connections.connectors import quickbooks_online as qbo
from abacus.modules.integrations.api import (
    egress_allowlist,
    egress_hosts_by_connector,
    egress_read_posts,
)
from abacus_tools.fakes.ledgers import RecordedQbo

HERE: Final = Path(__file__).parent
RECORDING: Final = HERE / "recordings" / "qbo-trial_balance-2026-01-01_2026-08-31.json"
GOLDEN: Final = HERE / "golden" / "trial_balance_2026-01-01_2026-08-31.yaml"
FAKE_PERIOD: Final = Period(date(2026, 1, 1), date(2026, 8, 31))
FAKE_REALM: Final = "1234567890123450"  # synthetic (connector_conformance.SYNTHETIC_REALMS)
APP: Final = qbo.QboApp("synthetic-client-id", "synthetic-client-secret", "sandbox")
SANDBOX_ENV: Final = (
    "ABACUS_QBO_SANDBOX_CLIENT_ID",
    "ABACUS_QBO_SANDBOX_CLIENT_SECRET",
    "ABACUS_QBO_SANDBOX_REFRESH_TOKEN",
    "ABACUS_QBO_SANDBOX_REALM_ID",
)


class Transport:
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> EgressResponse: ...


@dataclass
class Logged:
    """Records every request, then hands it to the target's transport."""

    inner: Transport
    sent: list[tuple[str, str]] = field(default_factory=lambda: list[tuple[str, str]]())

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> EgressResponse:
        self.sent.append((method.upper(), url))
        return await self.inner.request(method, url, headers=headers, data=data)


@dataclass
class Target:
    name: str
    period: Period
    transport: Logged
    app: qbo.QboApp
    credentials: bytes
    rotated: list[bytes] = field(default_factory=lambda: list[bytes]())

    def connector(self, credentials: bytes | None = None) -> qbo.QuickBooksOnlineConnector:
        async def on_rotate(blob: bytes) -> None:
            self.rotated.append(blob)

        return qbo.QuickBooksOnlineConnector(
            self.app,
            cast(EgressClient, self.transport),
            credentials or self.credentials,
            on_rotate=on_rotate,
        )


def held(realm: str, *, expires_at: datetime, refresh: str = "synthetic-rt-1") -> bytes:
    return qbo.QboCredentials("synthetic-at-1", refresh, realm, expires_at).sealed_form()


def fake(scratch: Path, *, expires_at: datetime) -> Target:
    connection: UUID = uuid4()
    folder = scratch / str(connection)
    folder.mkdir(parents=True)
    shutil.copyfile(RECORDING, folder / RECORDING.name)
    transport = Logged(cast(Transport, RecordedQbo(scratch, connection)))
    return Target("fake", FAKE_PERIOD, transport, APP, held(FAKE_REALM, expires_at=expires_at))


def sandbox_configured() -> bool:
    return all(os.environ.get(name) for name in SANDBOX_ENV)


def sandbox_period(today: date | None = None) -> Period:
    """The last full calendar year: a sandbox company always has one."""
    year = (today or datetime.now(UTC).date()).year - 1
    return Period(date(year, 1, 1), date(year, 12, 31))


def sandbox() -> Target:
    client_id, secret, refresh, realm = (os.environ[name] for name in SANDBOX_ENV)
    configure_egress(
        egress_allowlist(), egress_read_posts(), by_connector=egress_hosts_by_connector()
    )
    transport = Logged(cast(Transport, EgressClient(qbo.PROVIDER)))
    app = qbo.QboApp(client_id, secret, "sandbox")
    # Expired on purpose: the first read refreshes, as a nightly pull after a day's rest does.
    credentials = held(realm, expires_at=datetime(2000, 1, 1, tzinfo=UTC), refresh=refresh)
    return Target("sandbox", sandbox_period(), transport, app, credentials)
