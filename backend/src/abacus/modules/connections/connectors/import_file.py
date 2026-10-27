"""The import connector: a client's uploaded ledger export (SPEC-028; TASK-052; ADR-107).
PROTECTED.

A connector with reduced capabilities: one dataset (trial balance), no sign-in, no change feed,
no attachments. `pull` returns the entity's latest clean import for the period, exactly as it
was uploaded; the pipeline normalises it by the format its source names.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Credentials,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
)
from abacus.modules.connections.import_formats import FORMATS
from abacus.modules.connections.models import LedgerImport
from abacus.modules.connections.repository import latest_import
from abacus.modules.evidence.api import StoredObject, read_content

CSV_MEDIA_TYPE = "text/csv"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ImportConnector(Connector):
    provider: ClassVar[str] = "import"

    def __init__(self, tenant_id: UUID, client_entity_id: UUID) -> None:
        self._tenant = TenantContext(tenant_id, "system", "connections.import")
        self._entity = client_entity_id

    def capabilities(self) -> Capabilities:
        return Capabilities(
            datasets=frozenset({"trial_balance"}),
            oauth=False,
            incremental=False,
            attachments=False,
        )

    async def authorise_url(
        self, state: str, redirect_uri: str, *, code_challenge: str | None = None
    ) -> str:
        raise NotSupported("oauth")

    async def exchange_code(
        self, code: str, redirect_uri: str, *, code_verifier: str | None = None
    ) -> Credentials | None:
        raise NotSupported("oauth")

    async def revoke(self) -> None:
        raise NotSupported("oauth")  # an upload grants nothing to revoke

    async def refresh(self) -> None:
        return None  # nothing to refresh: no credentials

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        if dataset not in self.capabilities().datasets:
            raise NotSupported("dataset")
        found = await self._latest(period)
        if found is None:
            raise ConnectorError("no_import")
        fmt = FORMATS.get(found.format)
        if fmt is None:
            raise ConnectorError("unknown_format")
        content = await self._content(found)
        media = XLSX_MEDIA_TYPE if fmt.file_type == "xlsx" else CSV_MEDIA_TYPE
        request = f"import {found.id} {period.start.isoformat()}..{period.end.isoformat()}"
        return RawPayload(content, media, fmt.source, system_now(), request)

    async def changes_since(self, since: datetime) -> Sequence[str]:
        raise NotSupported("incremental")

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise NotSupported("attachments")

    async def health(self) -> bool:
        found = await self._latest(None, clean_only=False)
        return found is not None and found.scan_status == "clean" and found.status != "failed"

    async def _latest(
        self, period: Period | None, *, clean_only: bool = True
    ) -> LedgerImport | None:
        async with tenant_session(self._tenant) as session:
            return await latest_import(
                session,
                self._entity,
                period_end=period.end if period is not None else None,
                clean_only=clean_only,
            )

    async def _content(self, found: LedgerImport) -> bytes:
        stored = StoredObject(
            found.storage_key, found.storage_version_id, found.fingerprint, found.size_bytes
        )
        return await read_content(self._tenant, stored)
