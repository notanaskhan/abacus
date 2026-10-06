"""The fake connector (TASK-010 design §3). PROTECTED. Local runs and tests only.

Serves provider-shaped JSON written by `abacus_tools.synthetic.connector_fixtures` from
`<fake_connector_dir>/<connection_id>/trial_balance-<start>_<end>.json`, byte for byte. A file
may instead hold `{"fault": "unavailable"}` to simulate a provider outage. Product code can't
import the synthetic generator (ADR-101), so the directory is the hand-over.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, cast
from uuid import UUID

from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
    Unavailable,
)

MEDIA_TYPE = "application/json"
SOURCE = "fake"


def fixture_path(directory: Path, connection_id: UUID, dataset: str, period: Period) -> Path:
    name = f"{dataset}-{period.start.isoformat()}_{period.end.isoformat()}.json"
    return directory / str(connection_id) / name


class FakeConnector(Connector):
    provider: ClassVar[str] = "fake"

    def __init__(self, connection_id: UUID, directory: Path) -> None:
        self._connection_id = connection_id
        self._directory = directory

    def capabilities(self) -> Capabilities:
        return Capabilities(
            datasets=frozenset({"trial_balance"}),
            oauth=False,
            incremental=False,
            attachments=False,
        )

    async def authorise_url(self, state: str, redirect_uri: str) -> str:
        raise NotSupported("oauth")

    async def exchange_code(self, code: str, redirect_uri: str) -> None:
        raise NotSupported("oauth")

    async def refresh(self) -> None:
        return None  # nothing to refresh: no credentials

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        if dataset not in self.capabilities().datasets:
            raise NotSupported("dataset")
        path = fixture_path(self._directory, self._connection_id, dataset, period)
        try:
            content = await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            raise ConnectorError("no_data") from None
        if _is_fault(content):
            raise Unavailable("provider_unavailable")
        return RawPayload(content, MEDIA_TYPE, SOURCE, datetime.now(UTC))

    async def changes_since(self, since: datetime) -> Sequence[str]:
        raise NotSupported("incremental")

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise NotSupported("attachments")

    async def health(self) -> bool:
        return self._directory.is_dir()


def _is_fault(content: bytes) -> bool:
    try:
        document = cast(object, json.loads(content))
    except ValueError:
        return False  # malformed data is the normaliser's to reject, not an outage
    return isinstance(document, dict) and cast(dict[str, object], document).get("fault") == (
        "unavailable"
    )
