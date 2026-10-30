"""Which DocuSign account a firm's envelope goes through, and only when every switch is on
(N-02-T18; ADR-149; W7; DEC-1179).

`firm_provider(tenant_id)` builds a `DocuSignProvider` for one activity call when:
1. the firm's `signatures.docusign` flag is on (the kill switch; off by default);
2. the W7 capability `esignature_envelope_send` is enabled in `write-capabilities.yaml` (v1:
   declared, never enabled; ADR-150's next schema version opens it, a human decision);
3. the firm has a connected DocuSign install (`firm_integrations`, catalogue key `docusign`)
   whose sealed secret opens: integrations answers 2 and 3 through the slot the worker fills
   (`register_docusign_install`), since signatures may not import integrations (ADR-008).
Any switch off is `ProviderUnavailable`: the send activity records "not sent" and nothing leaves.
The person's approval is the send's grant, consumed by the outbox relay before EnvelopeWorkflow
starts (N-02-T20): an undone send never reaches this module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Final
from uuid import UUID

import httpx
from sqlalchemy import text

from abacus.kernel._flags import SIGNATURES_DOCUSIGN
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled
from abacus.modules.evidence.api import version_content
from abacus.modules.signatures.docusign import (
    DocuSignAccount,
    DocuSignProvider,
    PlacedField,
    SourceFile,
)
from abacus.modules.signatures.provider import EsignProvider, ProviderUnavailable

_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)
# One pooled client for the process: a per-call client would be left open (end review, T18).
_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
    return _http


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "signatures.docusign")


# The firm's opened DocuSign install secret when W7 is enabled and the install is connected, else
# None. signatures may not import integrations (ADR-008), so the worker's composition root
# registers integrations' answer (`docusign_install_secret`); unregistered, nothing is sent.
InstallSecret = Callable[[TenantContext], Awaitable[bytes | None]]
_install_secret: InstallSecret | None = None


def register_docusign_install(source: InstallSecret | None) -> None:
    global _install_secret
    _install_secret = source


async def firm_provider(tenant_id: UUID) -> EsignProvider:
    tenant = _system(tenant_id)
    if _install_secret is None or not await flag_enabled(tenant, SIGNATURES_DOCUSIGN):
        raise ProviderUnavailable
    raw = await _install_secret(tenant)
    if raw is None:
        raise ProviderUnavailable
    account = DocuSignAccount.from_secret(raw)

    async def documents(envelope_id: str) -> Sequence[SourceFile]:
        async with tenant_session(tenant) as session:
            rows = (
                await session.execute(
                    text(
                        'SELECT "order", evidence_version_id, sha256 FROM envelope_documents '
                        'WHERE envelope_id = :id ORDER BY "order"'
                    ),
                    {"id": UUID(envelope_id)},
                )
            ).all()
        files: list[SourceFile] = []
        for row in rows:
            if row.evidence_version_id is None:
                # A generated document (P-11) is rendered by its own store; until then refuse.
                raise ProviderUnavailable
            content = await version_content(tenant, row.evidence_version_id)
            files.append(SourceFile(f"Document {row.order}", content, row.sha256))
        return files

    async def fields(envelope_id: str) -> Sequence[PlacedField]:
        async with tenant_session(tenant) as session:
            rows = (
                await session.execute(
                    text(
                        'SELECT f.signer_id, d."order" AS document, f.kind, f.page, f.x, f.y, '
                        "f.anchor FROM envelope_fields f JOIN envelope_documents d "
                        "ON d.id = f.envelope_document_id WHERE d.envelope_id = :id"
                    ),
                    {"id": UUID(envelope_id)},
                )
            ).all()
        return [
            PlacedField(
                str(r.signer_id),
                int(r.document),
                r.kind,
                r.page,
                float(r.x) if r.x is not None else None,
                float(r.y) if r.y is not None else None,
                r.anchor,
            )
            for r in rows
        ]

    async def signer_order(envelope_id: str) -> str:
        async with tenant_session(tenant) as session:
            found = await session.scalar(
                text("SELECT signer_order FROM envelopes WHERE id = :id"),
                {"id": UUID(envelope_id)},
            )
        return str(found or "sequential")

    return DocuSignProvider(
        account,
        _client(),
        documents=documents,
        fields=fields,
        signer_order=signer_order,
    )
