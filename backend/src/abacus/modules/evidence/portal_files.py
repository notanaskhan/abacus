"""R-01-T07: the files on a request as the portal PBC read model shows them to a client (C5
section `portal-pbc`; POR-03, POR-04).

Per live version: its file name and size, how it arrived (uploaded by a client, added by the firm,
retrieved through a connection, emailed), who uploaded it, whether it can be withdrawn by its kind
(a client's own detached-key upload nobody ever accepted, ADR-162 §8), whether the firm accepted
it, and the firm's effective send-back with its reason code and its client-visible note (SPEC-031
Q4). A withdrawn version is never returned (ADR-162 §4, DEC-298). Nothing here carries a screening
verdict, a confidence or an amount. For a caller that authorised `portal_documents.read` on the
request's binder (the request's versions come from requests' live fulfilments).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.repository import (
    client_problem_codes,
    ever_accepted,
    item_versions_with_decisions,
)
from abacus.modules.evidence.uploads import SOURCE

# How a connected source's version arrived (SPEC-031 AC-4: "Provided from your accounting system").
CONNECTED_METHODS: Final = frozenset({"retrieved", "imported"})
EMAILED_SOURCES: Final = frozenset({"email", "client_email"})


@dataclass(frozen=True)
class SentBack:
    reason_code: str | None
    note: str | None  # the firm's client-visible send-back note
    by_user_id: UUID | None
    at: datetime


@dataclass(frozen=True)
class PortalFile:
    version_id: UUID
    name: str
    size_bytes: int
    arrived: str  # client_upload | firm | connection | email
    uploader_user_id: UUID | None
    created_at: datetime
    withdrawable_kind: bool
    accepted: bool  # the effective decision is an accept
    sent_back: SentBack | None


def _user(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None


def _arrived(source: str, method: str) -> str:
    if method in CONNECTED_METHODS:
        return "connection"
    if source in EMAILED_SOURCES:
        return "email"
    if source == SOURCE:
        return "client_upload"
    return "firm"


async def portal_files(
    tenant: TenantContext, request_item_id: UUID, version_ids: Sequence[UUID]
) -> list[PortalFile]:
    """The request's live versions among `version_ids`, newest first."""
    async with tenant_session(tenant) as session:
        rows = await item_versions_with_decisions(session, request_item_id, version_ids)
        accepted_ever = await ever_accepted(session, [v.id for v, _, _ in rows])
    out: list[PortalFile] = []
    for version, item, decision in rows:
        sent_back = None
        if decision is not None and decision.decision == "send_back":
            sent_back = SentBack(
                decision.reason_code,
                decision.note,
                _user(decision.actor_id),
                decision.created_at,
            )
        out.append(
            PortalFile(
                version_id=version.id,
                name=item.title,
                size_bytes=version.size_bytes,
                arrived=_arrived(version.source, version.method),
                uploader_user_id=_user(item.created_by_id)
                if item.created_by_kind == "human"
                else None,
                created_at=version.created_at,
                withdrawable_kind=version.source == SOURCE
                and version.storage_mode == "detached_key"
                and version.id not in accepted_ever,
                accepted=decision is not None and decision.decision == "accept",
                sent_back=sent_back,
            )
        )
    return out


async def client_pre_checks(tenant: TenantContext, version_id: UUID) -> list[str]:
    """The mechanical pre-checks a client reads in fixed words (DEC-58 e), by code: the
    client-audience problems of the version's latest check run."""
    async with tenant_session(tenant) as session:
        return await client_problem_codes(session, version_id)
