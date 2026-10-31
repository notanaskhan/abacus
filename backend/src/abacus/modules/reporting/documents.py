"""The generated-document service (P-11-T08; C11 v1; P-11 §4.2 to §4.4; ADR-320).

A consumer asks for a render inside its own unit of work (`render(tx, request)`): the kind's
variables provider resolves the values from the database, only the keys the template version
declares are kept (a whitelist; a declared key with no value refuses with `missing_variable`,
never a blank), and the sealed snapshot (variables, clause states, section overrides, layout and
template version) is hashed into the version's `content_hash`. The version row, its render job
and the audit event commit with the consumer's change; the bytes are rendered by the render job
(the `RenderWorkflow`'s activity) and stored as an evidence version by P-11-T09.

A final render is a person's, with an approval whose content hash is a draft's of this document
and which the kind's approval provider confirms as a human's (`approval_hash_mismatch`,
`final_requires_approval`). An agent's request is always a draft (C11 §4; INV-1), enforced here
and by the 0430 CHECKs. A locked document takes no render (`document_locked`). A source event a
kind subscribes to marks its documents out of date (changed keys, never values) within one relay
cycle: the relay delivers it to `SUBSCRIPTIONS`, which this module builds from the registrations.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, cast
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.methodology.api import report_template_variable_keys
from abacus.modules.reporting.render.core import engine_version
from abacus.modules.reporting.render.layouts import LAYOUT_VERSION

TARGET = "generated_document"

DocumentStatus = Literal["drafting", "draft", "approved", "locked"]


class GeneratedDocumentRenderRequested(DomainEvent):
    """A version waits for its bytes: the RenderWorkflow's activity renders it (identifiers
    only)."""

    event_type = "generated_document.render_requested"
    generated_document_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]


class GeneratedDocumentMarkedOutOfDate(DomainEvent):
    event_type = "generated_document.marked_out_of_date"
    generated_document_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class GeneratedDocumentView:
    """What `generated_document(tx, id)` answers (C11 §6, the in-process half)."""

    id: UUID
    kind: str
    owner_type: str
    owner_id: UUID
    status: DocumentStatus
    out_of_date: bool
    out_of_date_reasons: tuple[str, ...]
    current_version: int | None
    content_hash: str | None


async def _tenant(tx: UnitOfWork) -> UUID:
    """The firm this unit of work was opened for, read back from its transaction (the kernel's
    `transaction_context`): never passed in, so it is the tenant row-level security enforces."""
    return (await transaction_context(tx.session)).tenant_id


def canonical(value: object) -> bytes:
    """The snapshot's bytes: sorted keys, no whitespace, UTF-8 (the hash is over these)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_of(
    *,
    layout: str,
    template_version_id: UUID | None,
    variables: Mapping[str, str],
    clause_states: Mapping[str, bool],
    overrides: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    return {
        "layout": layout,
        "layout_version": LAYOUT_VERSION,
        "template_version_id": None if template_version_id is None else str(template_version_id),
        "variables": dict(sorted(variables.items())),
        "clauses": dict(sorted(clause_states.items())),
        "overrides": {k: list(v) for k, v in sorted(overrides.items())},
    }


def declared_values(
    declared: tuple[str, ...], resolved: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Keep only the declared keys; a declared key with no value (or only whitespace) is missing.
    Undeclared keys the provider returns never reach the document."""
    kept: dict[str, str] = {}
    missing: list[str] = []
    for key in declared:
        value = resolved.get(key)
        if value is None or not value.strip():
            missing.append(key)
        else:
            kept[key] = value
    return kept, missing


# --- reads ---------------------------------------------------------------------------------------

Reader = UnitOfWork | AsyncSession


def _session(tx: Reader) -> AsyncSession:
    """Reads run in a consumer's unit of work or, for the routes (P-11-T11), a session."""
    return tx if isinstance(tx, AsyncSession) else tx.session


async def document_row(tx: Reader, document_id: UUID) -> RowMapping | None:
    row = (
        (
            await _session(tx).execute(
                text(
                    "SELECT id, kind, owner_type, owner_id, client_id, engagement_id, "
                    "work_item_id "
                    "FROM generated_documents WHERE id = :id"
                ),
                {"id": document_id},
            )
        )
        .mappings()
        .first()
    )
    return row


async def locked(tx: Reader, document_id: UUID) -> bool:
    found = await _session(tx).scalar(
        text(
            "SELECT 1 FROM generated_document_events "
            "WHERE generated_document_id = :id AND kind = 'locked' LIMIT 1"
        ),
        {"id": document_id},
    )
    return found is not None


async def _latest(tx: Reader, document_id: UUID) -> RowMapping | None:
    return (
        (
            await _session(tx).execute(
                text(
                    "SELECT version_no, mode, content_hash, snapshot_key, snapshot_sha256, "
                    "template_version_id, layout_key, layout_version, engine_version, created_at "
                    "FROM generated_document_versions WHERE generated_document_id = :id "
                    "ORDER BY version_no DESC LIMIT 1"
                ),
                {"id": document_id},
            )
        )
        .mappings()
        .first()
    )


async def latest_version(tx: Reader, document_id: UUID) -> RowMapping | None:
    """The latest version's id and template version (P-11-T11's regenerate)."""
    return (
        (
            await _session(tx).execute(
                text(
                    "SELECT id, version_no, template_version_id FROM generated_document_versions "
                    "WHERE generated_document_id = :id ORDER BY version_no DESC LIMIT 1"
                ),
                {"id": document_id},
            )
        )
        .mappings()
        .first()
    )


async def generated_document(tx: Reader, document_id: UUID) -> GeneratedDocumentView | None:
    """The document's state, computed from its versions, jobs and events (never a stored
    status)."""
    doc = await document_row(tx, document_id)
    if doc is None:
        return None
    latest = await _latest(tx, document_id)
    events = (
        (
            await _session(tx).execute(
                text(
                    "SELECT kind, cause_ref, at FROM generated_document_events "
                    "WHERE generated_document_id = :id ORDER BY at"
                ),
                {"id": document_id},
            )
        )
        .mappings()
        .all()
    )
    locked = any(e["kind"] == "locked" for e in events)
    pending = await _session(tx).scalar(
        text(
            "SELECT 1 FROM render_jobs WHERE generated_document_id = :id "
            "AND status IN ('queued', 'running') LIMIT 1"
        ),
        {"id": document_id},
    )
    since = latest["created_at"] if latest is not None else None
    reasons = tuple(
        str(e["cause_ref"])
        for e in events
        if e["kind"] == "out_of_date" and (since is None or e["at"] > since)
    )
    status: DocumentStatus
    if locked:
        status = "locked"
    elif pending is not None:
        status = "drafting"
    elif latest is not None and latest["mode"] == "final":
        status = "approved"
    else:
        status = "draft"
    return GeneratedDocumentView(
        id=document_id,
        kind=str(doc["kind"]),
        owner_type=str(doc["owner_type"]),
        owner_id=cast(UUID, doc["owner_id"]),
        status=status,
        out_of_date=bool(reasons) and not locked,
        out_of_date_reasons=reasons,
        current_version=None if latest is None else cast(int, latest["version_no"]),
        content_hash=None if latest is None else str(latest["content_hash"]),
    )


# --- writes --------------------------------------------------------------------------------------


async def _document_for(
    tx: UnitOfWork,
    *,
    kind: str,
    owner_type: str,
    owner_id: UUID,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    template_id: UUID | None,
    created_by_kind: str,
) -> UUID:
    """One document per consumer record and kind (0430's unique key): found or created."""
    found = await tx.session.scalar(
        text(
            "SELECT id FROM generated_documents WHERE owner_type = :t AND owner_id = :o "
            "AND kind = :k"
        ),
        {"t": owner_type, "o": owner_id, "k": kind},
    )
    if found is not None:
        return cast(UUID, found)
    created = await tx.session.scalar(
        text(
            "INSERT INTO generated_documents (tenant_id, kind, owner_type, owner_id, client_id, "
            "engagement_id, work_item_id, template_id, created_by_kind) "
            "VALUES (:tenant, :k, :t, :o, :c, :e, :w, :tpl, :by) "
            "RETURNING id"
        ),
        {
            "tenant": await _tenant(tx),
            "k": kind,
            "t": owner_type,
            "o": owner_id,
            "c": client_id,
            "e": engagement_id,
            "w": work_item_id,
            "tpl": template_id,
            "by": created_by_kind,
        },
    )
    return cast(UUID, created)


async def next_version(tx: UnitOfWork, document_id: UUID) -> int:
    current = await tx.session.scalar(
        text(
            "SELECT coalesce(max(version_no), 0) FROM generated_document_versions "
            "WHERE generated_document_id = :id"
        ),
        {"id": document_id},
    )
    return int(cast(int, current)) + 1


async def version_id(tx: UnitOfWork, document_id: UUID, version_no: int) -> UUID:
    """A version's id by its number (N-02-T33: the final an approved letter's envelope names)."""
    found = await tx.session.scalar(
        text(
            "SELECT id FROM generated_document_versions "
            "WHERE generated_document_id = :id AND version_no = :n"
        ),
        {"id": document_id, "n": version_no},
    )
    return cast(UUID, found)


async def insert_version(
    tx: UnitOfWork,
    *,
    document_id: UUID,
    version_no: int,
    mode: Literal["draft", "final"],
    template_version_id: UUID | None,
    layout_key: str,
    snapshot_sha256: str,
    snapshot: Mapping[str, object],
    content_hash: str,
    approval_ref: Mapping[str, str] | None,
    requested_by_kind: str,
    requested_by_user_id: UUID | None,
    requested_by_run_id: UUID | None,
    on_behalf_of_user_id: UUID | None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO generated_document_versions (tenant_id, generated_document_id, "
            "version_no, mode, template_version_id, layout_key, layout_version, snapshot_key, "
            "snapshot_sha256, content_hash, engine_version, approval_ref, requested_by_kind, "
            "requested_by_user_id, requested_by_run_id, on_behalf_of_user_id) VALUES "
            "(:tenant, :doc, :n, :mode, :tv, :layout, :lv, :skey, "
            ":ssha, :ch, :ev, CAST(:approval AS jsonb), :rk, :ru, :rr, :rob)"
        ),
        {
            "tenant": await _tenant(tx),
            "doc": document_id,
            "n": version_no,
            "mode": mode,
            "tv": template_version_id,
            "layout": layout_key,
            "lv": LAYOUT_VERSION,
            "skey": f"generated/{document_id}/{version_no}/snapshot.json",
            "ssha": snapshot_sha256,
            "ch": content_hash,
            "ev": engine_version(),
            "approval": None if approval_ref is None else json.dumps(dict(approval_ref)),
            "rk": requested_by_kind,
            "ru": requested_by_user_id,
            "rr": requested_by_run_id,
            "rob": on_behalf_of_user_id,
        },
    )
    # P-11-T11 (0522): the sealed values beside the version, in the same unit of work.
    await tx.session.execute(
        text(
            "INSERT INTO generated_document_snapshots (tenant_id, version_id, snapshot, "
            "snapshot_sha256) SELECT :tenant, id, CAST(:snap AS jsonb), :ssha "
            "FROM generated_document_versions WHERE generated_document_id = :doc "
            "AND version_no = :n"
        ),
        {
            "tenant": await _tenant(tx),
            "doc": document_id,
            "n": version_no,
            "snap": canonical(dict(snapshot)).decode(),
            "ssha": snapshot_sha256,
        },
    )
    await tx.session.execute(
        text(
            "INSERT INTO render_jobs (tenant_id, generated_document_id, target_version_no, "
            "workflow_id) VALUES (:tenant, :doc, :n, :wf)"
        ),
        {
            "tenant": await _tenant(tx),
            "doc": document_id,
            "n": version_no,
            "wf": f"render-{document_id}-{version_no}",
        },
    )
    tx.emit(
        GeneratedDocumentRenderRequested(generated_document_id=document_id, version_no=version_no)
    )


async def add_event(
    tx: UnitOfWork,
    *,
    document_id: UUID,
    kind: Literal["out_of_date", "locked", "render_failed", "superseded"],
    cause_ref: str,
    changed_keys: list[str] | None,
    actor_kind: str,
    actor_user_id: UUID | None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO generated_document_events (tenant_id, generated_document_id, kind, "
            "cause_ref, changed_keys, actor_kind, actor_user_id) VALUES "
            "(:tenant, :doc, :kind, :cause, :keys, :ak, :au)"
        ),
        {
            "tenant": await _tenant(tx),
            "doc": document_id,
            "kind": kind,
            "cause": cause_ref[:200],
            "keys": changed_keys,
            "ak": actor_kind,
            "au": actor_user_id,
        },
    )


async def create_document(
    tx: UnitOfWork,
    *,
    kind: str,
    owner_type: str,
    owner_id: UUID,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    created_by_kind: str,
) -> UUID:
    return await _document_for(
        tx,
        kind=kind,
        owner_type=owner_type,
        owner_id=owner_id,
        client_id=client_id,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        template_id=None,
        created_by_kind=created_by_kind,
    )


async def declared_keys(tx: UnitOfWork, template_version_id: UUID | None) -> tuple[str, ...]:
    """The template version's declared variable keys (an unknown version declares nothing)."""
    if template_version_id is None:
        return ()
    keys = await report_template_variable_keys(tx.session, template_version_id)
    return keys if keys is not None else ()


async def draft_with_hash(
    tx: UnitOfWork, document_id: UUID, content_hash: str
) -> RowMapping | None:
    """The draft of this document whose content hash an approval names, or None."""
    return (
        (
            await tx.session.execute(
                text(
                    "SELECT id, version_no, template_version_id, layout_key, snapshot_sha256 "
                    "FROM generated_document_versions WHERE generated_document_id = :id "
                    "AND mode = 'draft' AND content_hash = :h ORDER BY version_no DESC LIMIT 1"
                ),
                {"id": document_id, "h": content_hash},
            )
        )
        .mappings()
        .first()
    )


async def snapshot_of_version(session: AsyncSession, version_id: UUID) -> dict[str, object] | None:
    """The sealed snapshot of a version (0522), or None for a version sealed before it."""
    found = await session.scalar(
        text("SELECT snapshot FROM generated_document_snapshots WHERE version_id = :v"),
        {"v": version_id},
    )
    return None if found is None else cast(dict[str, object], found)


def target(document_id: UUID) -> Target:
    return Target(TARGET, document_id)


def ref(**fields: str | int | UUID) -> Ref:
    return Ref(**fields)


def record_rendered(
    tx: UnitOfWork,
    action: str,
    *,
    document_id: UUID,
    version_no: int,
    content_hash: str,
    engagement_id: UUID | None,
    client_id: UUID,
) -> None:
    tx.record(
        action,
        target=Target(TARGET, document_id),
        after=Ref(version_no=version_no, content_hash=content_hash),
        scope=Scope(engagement_id=engagement_id, client_id=client_id),
    )


# --- the out-of-date consumer --------------------------------------------------------------------


def _uuids(payload: Mapping[str, object]) -> Iterator[UUID]:
    for value in payload.values():
        if isinstance(value, str):
            try:
                yield UUID(value)
            except ValueError:
                continue


async def mark_out_of_date_from(event: OutboxEvent, kinds: tuple[str, ...]) -> None:
    """A source event the kinds subscribe to: every document of those kinds whose owner the event
    names (any identifier in its payload) and that is not locked is marked out of date, once per
    event (the relay may redeliver: the event id is the cause)."""
    if not kinds:
        return
    owners = list(dict.fromkeys(_uuids(event.payload)))
    if not owners:
        return
    system = TenantContext(event.tenant_id, "system", "reporting.out_of_date")
    async with tenant_session(system) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT d.id, d.client_id, d.engagement_id FROM generated_documents d "
                        "WHERE d.kind = ANY(:kinds) AND d.owner_id = ANY(:owners) "
                        "AND NOT EXISTS (SELECT 1 FROM generated_document_events e "
                        "WHERE e.generated_document_id = d.id AND (e.kind = 'locked' "
                        "OR (e.kind = 'out_of_date' AND e.cause_ref = :cause)))"
                    ),
                    {"kinds": list(kinds), "owners": owners, "cause": f"event:{event.event_id}"},
                )
            )
            .mappings()
            .all()
        )
    if not rows:  # a redelivery, or nothing of these kinds: nothing to write or audit
        return
    async with uow(system) as tx:
        for row in rows:
            document_id = cast(UUID, row["id"])
            await add_event(
                tx,
                document_id=document_id,
                kind="out_of_date",
                cause_ref=f"event:{event.event_id}",
                changed_keys=[event.event_type],
                actor_kind="system",
                actor_user_id=None,
            )
            tx.record(
                "generated_document.marked_out_of_date",
                target=Target(TARGET, document_id),
                after=Ref(event=event.event_id),
                scope=Scope(
                    engagement_id=cast(UUID | None, row["engagement_id"]),
                    client_id=cast(UUID, row["client_id"]),
                ),
            )
            tx.emit(GeneratedDocumentMarkedOutOfDate(generated_document_id=document_id))
