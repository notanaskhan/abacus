"""Uploading a ledger export (SPEC-028; TASK-052; ADR-107, ADR-108, ADR-110). PROTECTED.

The client (or the firm, on their behalf) picks their system's format and uploads its trial
balance export for the engagement's fiscal period. The file is malware-scanned before anything
parses it; a refused file is never stored or parsed. A clean file is stored write-once and
parsed at once in an isolated child process, so a problem (wrong format, wrong period,
unbalanced) is reported straight away in fixed words (ADR-111). A good import makes the entity's
connection of provider `import` (connecting is never required, ADR-108) and starts retrieval for
the open tier A trial balance items, which then run through the same pipeline as a live
connector.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.scanning import scan
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connector import Period
from abacus.modules.connections.import_formats import FORMATS, Format
from abacus.modules.connections.import_parse import MAX_BYTES, parse_isolated
from abacus.modules.connections.models import LedgerImport
from abacus.modules.connections.repository import (
    import_by_fingerprint,
    insert_connection,
    insert_import,
    latest_import,
    live_connection_for,
)
from abacus.modules.connections.retrievals import trigger_retrieval
from abacus.modules.engagements.api import engagement_metadata, gate_client_data, get_ref
from abacus.modules.evidence.api import stage_content
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, engagement_role_of
from abacus.modules.ledger.api import NormaliseError, validate
from abacus.modules.requests.api import request_items_for

_log = get_logger(__name__)
_CLIENT_ROLES: Final = frozenset({"client_admin", "client_contributor"})


class ImportOff(DomainConflict):
    code = "ledger_import_off"


class FileRefused(DomainInvalid):
    """The scanner refused the file (malware, an archive bomb, unscannable)."""

    code = "file_refused"


class UnknownFormat(DomainInvalid):
    code = "unknown_format"


class FileTooLarge(DomainInvalid):
    code = "payload_too_large"


class EmptyFile(DomainInvalid):
    code = "empty_file"


class AlreadyConnected(DomainConflict):
    """The entity's accounting system is connected; an export isn't needed."""

    code = "already_connected"


@dataclass(frozen=True)
class FormatView:
    id: str
    system: str
    file_type: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class ImportView:
    id: UUID
    format: str
    system: str
    period_start: date
    period_end: date
    status: str  # received | failed
    failure_code: str | None
    totals_from_lines: bool
    on_behalf: bool
    uploaded_at: datetime
    difference: Decimal | None = None
    found_period_end: date | None = None
    duplicate: bool = False


def _view(row: LedgerImport, *, duplicate: bool = False) -> ImportView:
    fmt = FORMATS.get(row.format)
    return ImportView(
        row.id,
        row.format,
        fmt.system if fmt is not None else row.format,
        row.period_start,
        row.period_end,
        row.status,
        row.failure_code,
        row.totals_from_lines,
        row.on_behalf,
        row.created_at,
        row.difference,
        row.found_period_end,
        duplicate,
    )


async def _enabled(tenant: TenantContext) -> bool:
    return await flag_enabled(tenant, _flags.LEDGER_IMPORT)


async def formats(ctx: AuthContext, engagement_id: UUID) -> list[FormatView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "ledger_import.upload", ref.resource())
    return [FormatView(f.id, f.system, f.file_type, f.steps) for f in FORMATS.values()]


async def latest(ctx: AuthContext, engagement_id: UUID) -> ImportView | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await latest_import(session, ref.client_entity_id)
    return _view(found) if found is not None else None


@dataclass(frozen=True)
class Checked:
    failure: str | None
    totals_from_lines: bool = False
    difference: Decimal | None = None  # debits minus credits, when unbalanced
    found_period_end: date | None = None  # what the export covers, when it's another period


def check_export(fmt: Format, content: bytes, period: Period) -> Checked:
    """Parsed in isolation, then validated. Code computes the values the messages show
    (ADR-050; TASK-053 D1)."""
    try:
        parsed = parse_isolated(content, fmt.id, period.start, period.end)
    except NormaliseError as exc:
        return Checked(exc.code)
    tb = parsed.trial_balance
    failure = validate(tb, period_start=period.start, period_end=period.end)
    return Checked(
        failure,
        parsed.totals_from_lines,
        tb.total_debit - tb.total_credit if failure == "unbalanced" else None,
        tb.period_end if failure == "period_mismatch" else None,
    )


async def check_receive(ctx: AuthContext, engagement_id: UUID) -> None:
    """Before the body is read: the flag, the permission and the client data gate."""
    if not await _enabled(ctx.tenant):
        raise ImportOff(str(engagement_id))
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "ledger_import.upload", ref.resource())
    await gate_client_data(ctx, engagement_id, "ledger_import.upload")  # SPEC-025 AC-7


async def receive_export(
    ctx: AuthContext, engagement_id: UUID, *, format_id: str, content: bytes
) -> ImportView:
    await check_receive(ctx, engagement_id)
    ref = await get_ref(ctx, engagement_id)
    fmt = FORMATS.get(format_id)
    if fmt is None:
        raise UnknownFormat(format_id[:50])
    if not content:
        raise EmptyFile(str(engagement_id))
    if len(content) > MAX_BYTES:
        raise FileTooLarge(str(engagement_id))
    async with tenant_session(ctx.tenant) as session:
        live = await live_connection_for(session, ref.client_entity_id)
    if live is not None and live.provider != "import":
        raise AlreadyConnected(str(engagement_id))
    result = await asyncio.to_thread(scan, content)  # ADR-110: before anything parses it
    if not result.clean:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "ledger_import.refused",
                target=Target("engagement", engagement_id),
                after=Ref(size=len(content)),
            )
        _log.info("ledger_import.refused", reason=result.reason)
        raise FileRefused(result.reason or "refused")
    metadata = await engagement_metadata(ctx, engagement_id)
    period = Period(metadata.engagement.fiscal_period_start, metadata.engagement.fiscal_period_end)
    stored = await stage_content(ctx.tenant_id, content)
    async with tenant_session(ctx.tenant) as session:
        existing = await import_by_fingerprint(session, ref.client_entity_id, stored.fingerprint)
    if existing is not None:
        return _view(existing, duplicate=True)  # AC-8: the same file again
    checked = await asyncio.to_thread(check_export, fmt, content, period)
    failure = checked.failure
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    async with uow(ctx.tenant) as tx:
        row = await insert_import(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            client_entity_id=ref.client_entity_id,
            format=fmt.id,
            period_start=period.start,
            period_end=period.end,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            fingerprint=stored.fingerprint,
            size_bytes=stored.size,
            failure_code=failure,
            difference=checked.difference,
            found_period_end=checked.found_period_end,
            totals_from_lines=checked.totals_from_lines,
            uploaded_by=ctx.user_id,
            on_behalf=role not in _CLIENT_ROLES,  # SPEC-028 Q4: the firm uploaded it
        )
        if row is None:
            found = await import_by_fingerprint(
                tx.session, ref.client_entity_id, stored.fingerprint
            )
            if found is None:
                raise NotFound("ledger_import")
            tx.record("ledger_import.duplicate", target=Target("ledger_import", found.id))
            return _view(found, duplicate=True)
        tx.record(
            "ledger_import.received" if failure is None else "ledger_import.failed",
            target=Target("ledger_import", row.id),
            after=Ref(engagement_id=engagement_id, fingerprint=stored.fingerprint),
        )
        if failure is None:
            live = await live_connection_for(tx.session, ref.client_entity_id, lock=True)
            if live is None:
                connection = await insert_connection(
                    tx.session,
                    tenant_id=ctx.tenant_id,
                    client_entity_id=ref.client_entity_id,
                    provider="import",
                    created_by=str(ctx.user_id),
                )
                tx.record("connection.created", target=Target("connection", connection.id))
    if failure is None:
        await _retrieve(ctx, engagement_id, period)
    return _view(row)


async def _retrieve(ctx: AuthContext, engagement_id: UUID, period: Period) -> None:
    """Start the pipeline for the open trial balance items, as the person who uploaded."""
    for item in await request_items_for(ctx, engagement_id):
        if item.status not in ("draft", "requested") or item.dataset != "trial_balance":
            continue
        try:
            await trigger_retrieval(
                ctx, engagement_id=engagement_id, request_item_id=item.id, period=period
            )
        except (DomainConflict, Forbidden, NotFound) as exc:
            _log.info("ledger_import.retrieval_refused", error=type(exc).__name__)
