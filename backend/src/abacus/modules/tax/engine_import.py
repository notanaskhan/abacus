"""Engine imports and the sync chip (T-01-T19; T-01 §3.9, §3.10; TAX-09 c, d, e; DEC-1363). Red.

- **Upload** (`engine_import.create`, a person): the engine file is scanned, typed and stored
  write-once (evidence's staging) before anything reads it, then parsed in the isolated child
  (`engine_adapter`, ADR-052). A values file names its return (`2025I:FeldJ`) and version: the
  first import links the return; a different engine return is 409 `engine_return_mismatch`; a
  version older than the one Accrued took is 409 `engine_version_behind`.
- **Values**: the diff is code against Accrued's current field values. Differences wait as a P-04
  import checkpoint, "Import pending approval" (`review.api.record_import_proposal`); nothing on
  the return changes. One import waits at a time (409 `import_pending`). A file that matches
  Accrued is taken at once: the link moves to its version.
- **Approve** (`engine_import.approve`, a person, never the agent or the system): the accepted rows
  only, at the version seen (409 `stale_version`); the checkpoint follows
  (`review.api.decide_import`: all rows approve it; some make "Engine import Vn" of just those),
  each accepted value is written as an `engine_import` value naming that checkpoint, and the link
  moves to the version. **Reject** needs a reason.
- **Diagnostics**: the rows are kept per upload; an error makes the chip read failed. Raising the
  `engine_diagnostic` issue for an error is T-01-T26's (`issue_id` stays empty here).
- **The chip** is derived, never stored: pending import, then a failed diagnostics run, then never
  synced, out of sync (Accrued changed a field after the last sync by anything but an import),
  synced.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.evidence.api import screen_and_stage
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    engagement_resource,
    names_of,
)
from abacus.modules.review.api import (
    Json,
    ProposedChange,
    changed_since,
    content_hash,
    current_values,
    decide_import,
    record_import_proposal,
    record_value,
)
from abacus.modules.tax import engine_repository as repo
from abacus.modules.tax.engine_adapter import (
    DiagnosticsFile,
    DiffRow,
    EngineFileInvalid,
    ValuesFile,
    differences,
    parse_diagnostics,
    parse_values,
    typed,
)
from abacus.modules.tax.engine_repository import TextRow
from abacus.modules.tax.engine_sync import EngineSyncFailed, chip_state, facts_for, sync_facts

TARGET: Final = "tax_return"
CREATE: Final = "engine_import.create"
DECIDE: Final = "engine_import.approve"
READ: Final = "tax_return.read"
SUBJECT: Final = "engine_import"
Kind = Literal["values", "diagnostics", "pdfs", "acks"]
SyncState = Literal[
    "not_yet_exported",
    "ready_for_export",
    "exporting",
    "synced",
    "out_of_sync",
    "import_pending_approval",
    "failed",
]


class EngineFileRefused(DomainInvalid):
    """422: the file is not the engine's file of that kind (`facts.reason`, never its content)."""

    code = "engine_file_invalid"


class KindNotBuilt(DomainInvalid):
    """422: PDFs and acknowledgements arrive with the delivery and e-file tasks."""

    code = "import_kind_unavailable"


class EngineReturnMismatch(DomainConflict):
    code = "engine_return_mismatch"


class EngineVersionBehind(DomainConflict):
    code = "engine_version_behind"


class ImportPending(DomainConflict):
    code = "import_pending"


class ImportDecided(DomainConflict):
    code = "import_decided"


class ImportStale(DomainConflict):
    code = "stale_version"


class NothingAccepted(DomainInvalid):
    code = "nothing_accepted"


@dataclass(frozen=True)
class ImportView:
    id: UUID
    return_id: UUID
    kind: Kind
    status: Literal["pending_approval", "approved", "rejected", "routed"]
    rows: tuple[dict[str, object], ...]
    uploaded_at: datetime
    row_version: int
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class SyncEvent:
    id: UUID
    kind: str
    actor_name: str | None
    at: datetime
    engine_version: str | None
    field_keys: tuple[str, ...]
    errors: int | None
    informational: int | None


@dataclass(frozen=True)
class SyncView:
    return_id: UUID
    state: SyncState
    engine_return_id: str | None
    history: tuple[SyncEvent, ...]
    diagnostics: tuple[dict[str, object], ...]
    allowed_actions: tuple[str, ...]
    synced_at: datetime | None


def _person(ctx: AuthContext, action: str) -> None:
    """INV-1: a live person; a client principal never sees a return (INV-4)."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _resource(ctx: AuthContext, return_id: UUID) -> tuple[Resource, UUID]:
    """The return's engagement as the resource (with the return as the work item), when the
    viewer may see it; 404 otherwise."""
    for item in await work_item_facts(ctx, TARGET):
        if item.work_item_id == return_id:
            base = await engagement_resource(ctx.tenant, item.engagement_id)
            return replace(base, work_item_id=return_id), item.engagement_id
    raise NotFound(TARGET)


def _row_out(r: DiffRow) -> dict[str, object]:
    return {
        "field_key": r.field_key,
        "accrued": r.accrued,
        "engine": r.engine,
        "cause_code": r.cause_code,
    }


def _hash_after(accrued: dict[str, dict[str, object]], rows: Sequence[dict[str, object]]) -> str:
    state: dict[str, object] = dict(accrued)
    for r in rows:
        state[str(r["field_key"])] = r["engine"]
    return "sha256:" + content_hash(cast(Json, state))


async def _parse[T](parser: Callable[[bytes], T], content: bytes) -> T:
    try:
        return await asyncio.to_thread(run_isolated, parser, content)
    except EngineFileInvalid as bad:
        raise EngineFileRefused(facts={"reason": bad.code}) from None
    except IsolationFailed:
        raise EngineFileRefused(facts={"reason": "unreadable"}) from None


async def import_file(
    ctx: AuthContext, return_id: UUID, kind: Kind, file_name: str, content: bytes
) -> ImportView:
    _person(ctx, CREATE)
    resource, engagement_id = await _resource(ctx, return_id)
    await authorise(ctx, CREATE, resource)
    if kind in ("pdfs", "acks"):  # T-01-T26: the engine's PDFs and e-file status report
        from abacus.modules.tax import engine_files

        routed = await engine_files.import_other(
            ctx, return_id, engagement_id, kind, file_name, content
        )
        return ImportView(routed, return_id, kind, "routed", (), datetime.min, 1, ())
    view = await _import_parsed(ctx, return_id, engagement_id, kind, file_name, content)
    if kind == "diagnostics":  # T-01-T26: an error raises one issue per code and field
        from abacus.modules.tax import engine_files

        await engine_files.diagnostic_issues(ctx, return_id, view.id)
    return view


async def _import_parsed(
    ctx: AuthContext,
    return_id: UUID,
    engagement_id: UUID,
    kind: Kind,
    file_name: str,
    content: bytes,
) -> ImportView:
    screened = await screen_and_stage(ctx.tenant_id, content, file_name, None)
    parsed: ValuesFile | DiagnosticsFile = (
        await _parse(parse_values, content)
        if kind == "values"
        else await _parse(parse_diagnostics, content)
    )
    accrued = await current_values(ctx.tenant, TARGET, return_id) if kind == "values" else {}
    file = {
        "file_name": screened.file_name,
        "file_key": screened.stored.key,
        "file_version": screened.stored.version_id,
        "file_size": screened.stored.size,
        "payload_sha256": screened.sha256,
    }
    async with uow(ctx.tenant) as tx:
        link = await repo.link_of(tx.session, return_id)
        if link is None:
            await repo.insert_link(tx.session, ctx.tenant_id, return_id, parsed.engine_return_id)
            taken = 0
        elif link.engine_return_id != parsed.engine_return_id:
            raise EngineReturnMismatch(facts={"work_item_id": str(return_id)})
        else:
            taken = int(link.version)
        base = {
            "tenant_id": ctx.tenant_id,
            "return_id": return_id,
            "engine_return_id": parsed.engine_return_id,
            "version": parsed.version,
            "actor_user_id": ctx.user_id,
        }
        if isinstance(parsed, DiagnosticsFile):
            errors = sum(1 for d in parsed.diagnostics if d.severity == "error")
            event_id = await repo.insert_event(
                tx.session,
                {
                    **base,
                    **file,
                    "kind": "diagnostics",
                    "summary": {
                        "errors": errors,
                        "informational": len(parsed.diagnostics) - errors,
                    },
                },
            )
            await repo.insert_diagnostics(
                tx.session,
                [
                    {
                        "tenant_id": ctx.tenant_id,
                        "return_id": return_id,
                        "sync_event_id": event_id,
                        "code": d.code,
                        "severity": d.severity,
                        "field_key": d.field_key,
                        "message_text": d.message,
                    }
                    for d in parsed.diagnostics
                ],
            )
            tx.record(
                "engine_sync.diagnostics",
                target=Target(TARGET, return_id),
                after=Ref(event=event_id, errors=errors, rows=len(parsed.diagnostics)),
            )
            if errors:  # T-01-T27: `export_failed` to the person who carried the file
                tx.emit(
                    EngineSyncFailed(
                        work_item_id=return_id,
                        engagement_id=engagement_id,
                        errors=errors,
                        recipient_user_ids=[ctx.user_id],
                    )
                )
            return ImportView(
                event_id, return_id, kind, "routed", (), datetime.min, 1, ()
            )  # the chip and history carry diagnostics; no diff to review
        if parsed.version < taken:
            raise EngineVersionBehind(facts={"version": parsed.version})
        if await repo.pending_of(tx.session, return_id) is not None:
            raise ImportPending(facts={"work_item_id": str(return_id)})
        rows = [_row_out(r) for r in differences(accrued, parsed)]
        event_id = await repo.insert_event(
            tx.session,
            {**base, **file, "kind": "import_uploaded", "summary": {"differing": len(rows)}},
        )
        if not rows:
            await repo.set_link_version(tx.session, return_id, parsed.version)
            await repo.insert_event(
                tx.session, {**base, "kind": "import_approved", "summary": {"accepted": 0}}
            )
            tx.record(
                "engine_import.matched",
                target=Target(TARGET, return_id),
                after=Ref(event=event_id, version=parsed.version),
            )
            return ImportView(event_id, return_id, kind, "approved", (), datetime.min, 1, ())
        checkpoint_id = await record_import_proposal(
            tx,
            ctx,
            TARGET,
            return_id,
            [
                ProposedChange(
                    str(r["field_key"]),
                    cast(dict[str, object] | None, r["accrued"]),
                    cast(dict[str, object], r["engine"]),
                    "engine_import",
                )
                for r in rows
            ],
            content_hash=_hash_after(accrued, rows),
            engine_sync_event_id=event_id,
        )
        import_id = await repo.insert_diff(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "return_id": return_id,
                "sync_event_id": event_id,
                "checkpoint_id": checkpoint_id,
                "engine_return_id": parsed.engine_return_id,
                "version": parsed.version,
                "rows": rows,
            },
        )
        tx.record(
            "engine_import.uploaded",
            target=Target(SUBJECT, import_id),
            after=Ref(return_id=return_id, version=parsed.version, rows=len(rows)),
        )
    return await import_view(ctx, import_id)


async def _view(ctx: AuthContext, row: TextRow) -> ImportView:
    resource, _eid = await _resource(ctx, cast(UUID, row.return_id))
    may = await allowed_actions(ctx, resource, [DECIDE])
    acts = ("approve", "reject") if row.status == "pending_approval" and DECIDE in may else ()
    return ImportView(
        row.id,
        row.return_id,
        "values",
        row.status,
        tuple(cast(list[dict[str, object]], row.rows)),
        row.uploaded_at,
        row.row_version,
        acts,
    )


async def import_view(ctx: AuthContext, import_id: UUID) -> ImportView:
    async with tenant_session(ctx.tenant) as session:
        row = await repo.diff_of(session, import_id)
    if row is None:
        raise NotFound(SUBJECT)
    resource, _eid = await _resource(ctx, cast(UUID, row.return_id))
    await authorise(ctx, READ, resource)
    return await _view(ctx, row)


async def resolve_import(
    ctx: AuthContext,
    import_id: UUID,
    *,
    accepted: Sequence[str],
    seen_version: int,
    reason: str | None,
) -> ImportView:
    """Approve the accepted rows (`reason` None) or reject the import (`reason`, no rows)."""
    _person(ctx, DECIDE)
    rejecting = reason is not None
    if not rejecting and not accepted:
        raise NothingAccepted(facts={"field": "accepted_field_keys"})
    async with tenant_session(ctx.tenant) as session:
        found = await repo.diff_of(session, import_id)
    if found is None:
        raise NotFound(SUBJECT)
    resource, engagement_id = await _resource(ctx, cast(UUID, found.return_id))
    await authorise(ctx, DECIDE, resource)
    async with uow(ctx.tenant) as tx:
        row = await repo.diff_of(tx.session, import_id, lock=True)
        if row is None:
            raise NotFound(SUBJECT)
        if row.status != "pending_approval":
            raise ImportDecided(facts={"status": str(row.status)})
        if row.row_version != seen_version:
            raise ImportStale(facts={"import_id": str(import_id)})
        rows = cast(list[dict[str, object]], row.rows)
        keep = frozenset(accepted) if not rejecting else frozenset[str]()
        if keep - {str(r["field_key"]) for r in rows}:
            raise DomainInvalid(facts={"field": "accepted_field_keys"})
        taken = [r for r in rows if r["field_key"] in keep]
        accrued = await current_values(ctx.tenant, TARGET, row.return_id)
        approved_id = await decide_import(
            tx,
            ctx,
            row.checkpoint_id,
            keep,
            content_hash=_hash_after(accrued, taken),
            name=f"Engine import V{row.version}",
            reason=reason,
        )
        for r in taken:
            await record_value(
                tx,
                engagement_id=engagement_id,
                target_type=TARGET,
                target_id=row.return_id,
                field_key=str(r["field_key"]),
                value=cast(dict[str, object], r["engine"]),
                value_source="engine_import",
                cause="import",
                checkpoint_id=approved_id,
            )
        status = "rejected" if rejecting else "approved"
        await repo.decide_diff(
            tx.session,
            import_id,
            status=status,
            approved_checkpoint_id=approved_id,
            decided_by=ctx.user_id,
        )
        if not rejecting:
            await repo.set_link_version(tx.session, row.return_id, row.version)
        await repo.insert_event(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "return_id": row.return_id,
                "kind": "import_rejected" if rejecting else "import_approved",
                "engine_return_id": row.engine_return_id,
                "version": row.version,
                "actor_user_id": ctx.user_id,
                "summary": {"accepted": len(taken), "of": len(rows)},
            },
        )
        tx.record(
            f"engine_import.{status}",
            target=Target(SUBJECT, import_id),
            after=Ref(return_id=row.return_id, accepted=len(taken), of=len(rows)),
        )
    return await import_view(ctx, import_id)


# --- the chip ------------------------------------------------------------------------------------


def _count(summary: dict[str, object], key: str) -> int | None:
    value = summary.get(key)
    return value if isinstance(value, int) else None


async def sync_view(ctx: AuthContext, return_id: UUID) -> SyncView:
    """TAX-09's chip, history and diagnostics (the state is derived, never stored)."""
    if ctx.client:
        raise NotFound(TARGET)
    resource, _eid = await _resource(ctx, return_id)
    await authorise(ctx, READ, resource)
    async with tenant_session(ctx.tenant) as session:
        link = await repo.link_of(session, return_id)
        events = list(await repo.events_of(session, return_id))
        latest_diag = next((e for e in events if e.kind == "diagnostics"), None)
        diagnostics = (
            list(await repo.diagnostics_of(session, latest_diag.id)) if latest_diag else []
        )
    names = await names_of([e.actor_user_id for e in events if e.actor_user_id])
    synced = next((e for e in events if e.kind in ("import_approved", "marked_exported")), None)
    # T-01-T27: the chip is `engine_sync.chip_state` over facts read in one statement.
    async with tenant_session(ctx.tenant) as session:
        found = await sync_facts(session, return_id)
    if found is None:
        raise NotFound(TARGET)
    changed = found.last_synced_at is not None and bool(
        await changed_since(ctx.tenant, TARGET, return_id, found.last_synced_at)
    )
    state: SyncState = chip_state(facts_for(found, changed_since_sync=changed))
    may = await allowed_actions(ctx, resource, [CREATE, DECIDE])
    history = tuple(
        SyncEvent(
            e.id,
            e.kind,
            names.get(e.actor_user_id) if e.actor_user_id else None,
            e.at,
            f"{e.engine_return_id}:V{e.version}" if e.engine_return_id and e.version else None,
            (),
            _count(e.summary, "errors"),
            _count(e.summary, "informational"),
        )
        for e in events
    )
    return SyncView(
        return_id,
        state,
        link.engine_return_id if link else None,
        history,
        tuple(
            {
                "code": d.code,
                "severity": d.severity,
                "field_key": d.field_key,
                "message_text": d.message_text,
                "issue_id": d.issue_id,
            }
            for d in diagnostics
        ),
        tuple(sorted(may)),
        synced.at if synced and state == "synced" else None,
    )


__all__ = [
    "EngineFileRefused",
    "EngineReturnMismatch",
    "EngineVersionBehind",
    "ImportDecided",
    "ImportPending",
    "ImportStale",
    "ImportView",
    "KindNotBuilt",
    "NothingAccepted",
    "SyncEvent",
    "SyncView",
    "import_file",
    "import_view",
    "resolve_import",
    "sync_view",
    "typed",
]
