"""Fake ledgers and feeds for synthetic environments (A-02-T27; A-02 §5.3; ADR-101).

Registered into `connections.CONNECTORS` by `install_fake_ledgers()` under `fake_*` providers,
which reach no host (`connections.is_networkless`). Refused outside local, test and evaluation
(`SYNTHETIC_ENVIRONMENTS`), so no fake can serve a real firm. Product code never imports this.

- `fake_quickbooks_online`: the **real** QuickBooks Online connector over a recorded transport.
  Its requests are answered from `<dir>/<connection_id>/qbo-trial_balance-<start>_<end>.json`
  (a TrialBalance report) and its OAuth calls with synthetic tokens, so the real connector's
  code, normaliser and pipeline dispatch run end to end.
- `fake_netsuite`: serves a NetSuite trial balance CSV export from
  `<dir>/<connection_id>/netsuite-trial_balance-<start>_<end>.csv`, parsed by the import
  format `netsuite_tb_csv` (the SPEC-028 pipeline).
- `fake_bank_feed`, `fake_card_feed`, `fake_sales_feed`: connected feeds with no dataset yet
  (POR-16a shows them connected; pulls answer `NotSupported`).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Final, cast
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.egress import EgressClient, EgressResponse
from abacus.modules.connections.api import (
    CONNECTORS,
    Capabilities,
    Connection,
    Connector,
    ConnectorError,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
)
from abacus.modules.connections.api import quickbooks_online as qbo

FAKE_QBO: Final = "fake_quickbooks_online"
FAKE_NETSUITE: Final = "fake_netsuite"
FAKE_FEEDS: Final = ("fake_bank_feed", "fake_card_feed", "fake_sales_feed")
SYNTHETIC_APP: Final = qbo.QboApp("synthetic-client-id", "synthetic-client-secret", "sandbox")
SYNTHETIC_REALM: Final = "4620816365171234567"


class FakeLedgersRefused(RuntimeError):
    """Fakes are for synthetic environments only."""


def _file(directory: Path, connection_id: UUID, prefix: str, period: Period, ext: str) -> Path:
    name = f"{prefix}-trial_balance-{period.start.isoformat()}_{period.end.isoformat()}.{ext}"
    return directory / str(connection_id) / name


class RecordedQbo:
    """A recorded Intuit: answers the connector's reads from files, OAuth with synthetic tokens."""

    def __init__(self, directory: Path, connection_id: UUID) -> None:
        self._directory = directory
        self._connection_id = connection_id

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> EgressResponse:
        if qbo.OAUTH_PATH in url or qbo.REVOKE_PATH in url:
            tokens = {"access_token": "fake-at", "refresh_token": "fake-rt", "expires_in": 3600}
            return EgressResponse(200, {}, json.dumps(tokens).encode())
        if "/companyinfo/" in url:
            return EgressResponse(200, {}, b'{"CompanyInfo": {"Id": "1"}}')
        if "/reports/TrialBalance" in url and method.upper() == "GET":
            query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
            period = Period(
                datetime.fromisoformat(query["start_date"]).date(),
                datetime.fromisoformat(query["end_date"]).date(),
            )
            path = _file(self._directory, self._connection_id, "qbo", period, "json")
            try:
                return EgressResponse(200, {}, await asyncio.to_thread(path.read_bytes))
            except FileNotFoundError:
                return EgressResponse(404, {}, b"")
        return EgressResponse(404, {}, b"")


class FakeNetSuiteConnector(Connector):
    provider: ClassVar[str] = FAKE_NETSUITE

    def __init__(self, connection_id: UUID, directory: Path) -> None:
        self._connection_id = connection_id
        self._directory = directory

    def capabilities(self) -> Capabilities:
        return Capabilities(
            frozenset({"trial_balance"}), oauth=True, incremental=False, attachments=False
        )

    async def authorise_url(
        self, state: str, redirect_uri: str, *, code_challenge: str | None = None
    ) -> str:
        return f"{redirect_uri}?state={state}&code=demo"

    async def exchange_code(
        self, code: str, redirect_uri: str, *, code_verifier: str | None = None
    ) -> bytes | None:
        return b"fake-netsuite-credentials"

    async def revoke(self) -> None:
        return None

    async def refresh(self) -> None:
        return None

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        path = _file(self._directory, self._connection_id, "netsuite", period, "csv")
        try:
            content = await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            raise ConnectorError("no_data") from None
        request = f"trial_balance {period.start.isoformat()}..{period.end.isoformat()}"
        return RawPayload(content, "text/csv", "import_netsuite_tb_csv", system_now(), request)

    async def changes_since(self, since: datetime) -> Sequence[str]:
        raise NotSupported("incremental")

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise NotSupported("attachments")

    async def health(self) -> bool:
        return self._directory.is_dir()


class FakeFeedConnector(FakeNetSuiteConnector):
    """A connected feed with no dataset yet (bank, card, sales)."""

    provider: ClassVar[str] = "fake_feed"

    def capabilities(self) -> Capabilities:
        return Capabilities(frozenset(), oauth=True, incremental=False, attachments=False)

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        raise NotSupported("dataset")


def install_fake_ledgers(directory: Path) -> None:
    """Register the fakes; refused outside synthetic environments."""
    if settings().environment not in SYNTHETIC_ENVIRONMENTS:
        raise FakeLedgersRefused(settings().environment)

    def fake_qbo(connection: Connection, credentials: bytes | None) -> Connector:
        transport = cast(EgressClient, RecordedQbo(directory, connection.id))
        blob = (
            credentials
            or qbo.QboCredentials(
                "fake-at", "fake-rt", SYNTHETIC_REALM, system_now()
            ).sealed_form()
        )
        return qbo.QuickBooksOnlineConnector(SYNTHETIC_APP, transport, blob)

    CONNECTORS[FAKE_QBO] = fake_qbo
    CONNECTORS[FAKE_NETSUITE] = lambda c, _cred: FakeNetSuiteConnector(c.id, directory)
    for name in FAKE_FEEDS:
        CONNECTORS[name] = lambda c, _cred: FakeFeedConnector(c.id, directory)


def uninstall_fake_ledgers() -> None:
    for name in (FAKE_QBO, FAKE_NETSUITE, *FAKE_FEEDS):
        CONNECTORS.pop(name, None)
