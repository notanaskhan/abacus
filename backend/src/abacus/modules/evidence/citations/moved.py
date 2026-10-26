"""Moved and broken citations, and a person's relink (P-03-T12; SPEC-322 F6 AC6.1-AC6.3; ADR-166
§6; DEC-321). PROTECTED.

A citation is never updated: its state is computed from `citation_events` (`display.state_of`).

- **Moved** (`on_version_created`, an outbox consumer of `evidence_version.created`): a new
  version of an evidence item supersedes the item's earlier versions, so every citation to one of
  them gets a `moved` event naming the successor (`cause_ref = evidence_version:<id>`) and a
  `citation.moved` outbox event, within one relay cycle. A version the client withdrew is as if it
  never arrived (ADR-162 §4): a withdrawn new version moves nothing, and citations to a withdrawn
  earlier version are not moved (they are broken).
- **Broken** (`on_version_withdrawn`, on `evidence_version.withdrawn`): every citation to the
  withdrawn version gets a `broken` event (`withdrawn:<id>`). Readers already leave those citations
  out (`live_citation_source`); the event is for P-04's staleness rules. A `moved` event naming a
  successor that was withdrawn later no longer counts (`display.state_of`): the cited version is
  the newest again.
- **Owners** of other sources (methodology, workpapers) call `mark_sources_superseded(tx, ...)`
  in their own unit of work.
- Idempotent on the event: a redelivery, or two relays at once, write each event once
  (`citation_events_once_per_cause`, 0152) and emit only for rows they wrote. A citation already
  relinked is retired and never moves again (its successor row does).
- **Relink** (`relink`, `POST /v1/citations/{id}/relink`): `citation.relink` authorised on the
  citing host (its engagement and work item), by a person in a request they are making
  themself (`serving_request()`; the matrix denies agents and the system; a DB CHECK refuses a
  `relinked` event not by a person). The old quote is read from the old, immutable layer (the run
  hashing to `quote_sha256`), found on the newest live successor's PII-scanned pages only, and
  verified there by the kind's verifier as the person; a new verified row (`supersedes_id`, the
  same anchor and `n`) and a `relinked` event on the old row are written with a
  `citation.relinked` audit event. Not moved: 409 `not_moved`; the text gone: 422
  `relink_unverified` and nothing is written.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.citations.display import RELINK, state_of
from abacus.modules.evidence.citations.matching import quote_span, reread_span, union
from abacus.modules.evidence.citations.registry import Anchor, CitationClaim
from abacus.modules.evidence.citations.service import verify_claim
from abacus.modules.evidence.events import CitationBroken, CitationMoved
from abacus.modules.evidence.models import Citation, CitationEvent, EvidenceVersion
from abacus.modules.evidence.projection import projection_of
from abacus.modules.evidence.repository import (
    citations_on,
    earlier_versions,
    events_of,
    get_citation,
    get_version,
    insert_citation,
    insert_citation_events,
    is_withdrawn,
    lock_citation,
    newest_live_successor,
    pages_of,
)
from abacus.modules.evidence.withdrawals import withdrawn_among
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, serving_request

VERSION_SOURCE: Final = "evidence_version"
_log = get_logger(__name__)


class NotMoved(DomainConflict):
    """Only a moved citation is relinked, onto a successor that is still there."""

    code = "not_moved"


class RelinkUnverified(DomainInvalid):
    """The cited text is not on the successor: the popover offers "Open source" instead."""

    code = "relink_unverified"


class _Unchanged(Exception):
    """Every event was already written: leave the unit of work without a commit."""


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.citations_moved")


def moved_cause(successor_id: UUID) -> str:
    return f"{VERSION_SOURCE}:{successor_id}"


def broken_cause(version_id: UUID) -> str:
    return f"withdrawn:{version_id}"


async def _not_retired(session: AsyncSession, rows: Sequence[Citation]) -> list[Citation]:
    """The rows not yet relinked (a relinked row is retired: its successor row moves instead)."""
    events = await events_of(session, [r.id for r in rows])
    relinked = {e.citation_id for e in events if e.kind == "relinked"}
    return [r for r in rows if r.id not in relinked]


async def _write(
    tx: UnitOfWork, tenant_id: UUID, rows: Sequence[Citation], kind: str, cause: str
) -> int:
    """`kind` events for `rows` with `cause`, each once; audit and outbox for the new ones."""
    added = set(
        await insert_citation_events(
            tx.session,
            [
                {
                    "tenant_id": tenant_id,
                    "citation_id": r.id,
                    "kind": kind,
                    "cause_ref": cause,
                    "actor_kind": "system",
                }
                for r in rows
            ],
        )
    )
    for row in rows:
        if row.id not in added:
            continue
        tx.record(
            f"citation.{kind}",
            target=Target("citation", row.id),
            after=Ref(source=row.source_id),
            scope=Scope(row.engagement_id, row.work_item_id),
        )
        event = CitationMoved if kind == "moved" else CitationBroken
        tx.emit(event(citation_id=row.id, engagement_id=row.engagement_id, cause_ref=cause))
    return len(added)


async def _detect(tenant_id: UUID, kind: str, cause: str, source_ids: Sequence[UUID]) -> int:
    tenant = _system(tenant_id)
    try:
        async with uow(tenant) as tx:
            rows = await _not_retired(
                tx.session, await citations_on(tx.session, VERSION_SOURCE, source_ids)
            )
            written = await _write(tx, tenant_id, rows, kind, cause) if rows else 0
            if not written:
                raise _Unchanged
            return written
    except _Unchanged:
        return 0


async def on_version_created(event: OutboxEvent) -> None:
    """AC6.1: the new version's earlier, live siblings' citations move to it."""
    version_id = UUID(str(event.payload["evidence_version_id"]))
    async with tenant_session(_system(event.tenant_id)) as session:
        version = await get_version(session, version_id)  # None once withdrawn
        if version is None:
            return
        earlier = await earlier_versions(session, version.evidence_item_id, version.version_no)
    if not earlier:
        return
    gone = await withdrawn_among(_system(event.tenant_id), earlier)
    live = [v for v in earlier if v not in gone]
    if live:
        await _detect(event.tenant_id, "moved", moved_cause(version_id), live)


async def on_version_withdrawn(event: OutboxEvent) -> None:
    """AC6.1: a withdrawn version's citations are broken."""
    version_id = UUID(str(event.payload["evidence_version_id"]))
    await _detect(event.tenant_id, "broken", broken_cause(version_id), [version_id])


async def mark_sources_superseded(
    tx: UnitOfWork, *, source_type: str, source_id: UUID, old: str, new: str
) -> int:
    """For owners of versioned sources (methodology, workpapers; AC6.1): citations to version
    `old` of the source move to `new`, in the owner's unit of work. Returns the rows moved."""
    context = await transaction_context(tx.session)
    rows = await _not_retired(
        tx.session, await citations_on(tx.session, source_type, [source_id], source_version=old)
    )
    if not rows:
        return 0
    cause = f"{source_type}:{new}"[:120]
    return await _write(tx, context.tenant_id, rows, "moved", cause)


# --- Relink (AC6.2, AC6.3) ---------------------------------------------------------------------


def _live_human(ctx: AuthContext) -> None:
    """INV-1: only a person, in a request they are making themself, never a support session."""
    if (
        not isinstance(ctx, AuthContext)  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        or ctx.tenant.actor_kind != "human"
        or ctx.is_support
        or not serving_request()
    ):
        raise Forbidden(RELINK, "role")


def _box(raw: object) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, list) or len(raw) != 4:  # pyright: ignore[reportUnknownArgumentType] -- JSON
        return None
    try:
        a, b, c, d = (float(v) for v in raw)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType] -- JSON
    except (TypeError, ValueError):
        return None
    return (a, b, c, d)


async def _old_text(session: AsyncSession, tenant_id: UUID, row: Citation) -> str | None:
    """The quote as the old, immutable layer holds it: the run hashing to `quote_sha256`."""
    box, page_no = _box(row.locator.get("bbox")), row.locator.get("page")
    if row.quote_sha256 is None or box is None or not isinstance(page_no, int):
        return None
    pages = await pages_of(
        session, evidence_version_id=row.source_id, extractor_version=WORDS_VERSION
    )
    page = next((p for p in pages if p.page_no == page_no and p.has_text_layer), None)
    if page is None:
        return None
    try:
        layer = await read_page_layer(tenant_id, page)
    except Exception:  # a shredded or unreadable layer object: storage raises several kinds
        return None
    # P-03-T15: a quote verified since masking hashes the masked words; an older one the clear
    # words, which are then masked. Either way the claim carries only masked text (DEC-369).
    projection = await projection_of(session, evidence_version_id=row.source_id)
    masked = projection.words(layer.words, page_no)
    if masked is not None:
        found = reread_span(masked, box, row.quote_sha256)
        if found:
            return " ".join(w.text for w in found)
    run = reread_span(layer.words, box, row.quote_sha256)
    if not run:
        return None
    shown = projection.words(run, page_no)
    return " ".join(w.text for w in (shown if shown is not None else run))


async def _claim(
    session: AsyncSession, tenant_id: UUID, row: Citation, successor: EvidenceVersion
) -> CitationClaim | None:
    """The same claim on the successor, or None when what was cited can't be found there."""
    if row.kind == "sheet_cell":
        locator = {k: v for k, v in row.locator.items() if k != "evidence_version_id"}
        locator["evidence_version_id"] = str(successor.id)
        return CitationClaim("sheet_cell", locator, value=row.value_text)
    if row.kind != "document_text":
        return None
    quote = await _old_text(session, tenant_id, row)
    wanted = quote or row.value_text
    if wanted is None:
        return None
    pages = await pages_of(
        session, evidence_version_id=successor.id, extractor_version=WORDS_VERSION
    )
    # A successor page no PII scan covers is never searched (fail closed, `projection`).
    projection = await projection_of(session, evidence_version_id=successor.id)
    cited_page = row.locator.get("page")
    for page in sorted(pages, key=lambda p: (p.page_no != cited_page, p.page_no)):
        if not page.has_text_layer or not projection.readable(page.page_no):
            continue
        try:
            layer = await read_page_layer(tenant_id, page)
        except Exception:  # an unreadable layer object: the next page may still hold it
            _log.info("citation.relink_page_unreadable", page=page.page_no)
            continue
        words = projection.words(layer.words, page.page_no) or []
        span = quote_span(words, wanted)  # on the masked words, as the verifier reads them
        if span:
            return CitationClaim(
                "document_text",
                {
                    "evidence_version_id": str(successor.id),
                    "page": page.page_no,
                    "bbox": [round(v, 2) for v in union(span)],
                },
                quote=quote,
                value=row.value_text,
            )
    return None


async def relink(ctx: AuthContext, citation_id: UUID) -> UUID:
    """AC6.2: re-verify a moved citation on its successor as this person; the new row's id."""
    _live_human(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = await get_citation(session, citation_id)
        withdrawn = (
            row is not None
            and row.source_type == VERSION_SOURCE
            and await is_withdrawn(session, row.source_id)
        )
    # SPEC-036 AC-5: a shadow run's citation is not there to relink.
    if row is None or row.engagement_id is None or withdrawn or row.shadow:
        raise NotFound("citation")
    engagement = await get_ref(ctx, row.engagement_id)
    # On the citing host: its engagement and, where it has one, its work item (walls, the
    # archived rule, independence and work-item conditions all apply there).
    host = engagement.resource()
    if row.work_item_id is not None:
        host = replace(host, work_item_id=row.work_item_id)
    await authorise(ctx, RELINK, host)
    async with uow(ctx.tenant) as tx:
        await lock_citation(tx.session, row.id)
        events = await events_of(tx.session, [row.id])
        gone = await withdrawn_among(ctx.tenant, _successors(events))
        state, _ = state_of(events, ignore=frozenset(moved_cause(v) for v in gone))
        if state != "moved" or row.source_type != VERSION_SOURCE:
            raise NotMoved
        cited = await get_version(tx.session, row.source_id)
        successor = (
            await newest_live_successor(tx.session, cited.evidence_item_id, cited.version_no)
            if cited is not None
            else None
        )
        if successor is None:
            raise NotMoved
        claim = await _claim(tx.session, ctx.tenant_id, row, successor)
        anchor = Anchor(
            row.cited_from_type,
            row.cited_from_id,
            row.cited_from_ref,
            row.cited_from_locator,
            row.engagement_id,
            row.work_item_id,
            row.client_id,
        )
        verdict = await verify_claim(tx, ctx, claim, anchor) if claim is not None else None
        if verdict is None or not verdict.verified:
            raise RelinkUnverified
        new_id = await insert_citation(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": row.engagement_id,
                "work_item_id": row.work_item_id,
                "client_id": row.client_id,
                "cited_from_type": row.cited_from_type,
                "cited_from_id": row.cited_from_id,
                "cited_from_ref": row.cited_from_ref,
                "cited_from_locator": row.cited_from_locator,
                "n": row.n,
                "kind": row.kind,
                "source_type": verdict.source_type,
                "source_id": verdict.source_id,
                "source_version": verdict.source_version,
                "locator": verdict.locator,
                "match_id": verdict.match_id,
                "quote_sha256": verdict.quote_sha256,
                "value_text": verdict.value_text,
                "verified": True,
                "verification_reason": None,
                "verifier_version": row.verifier_version,
                "supersedes_id": row.id,
                "shadow": row.shadow,  # a shadow run's citation stays hidden once moved
                "created_by_kind": "human",
                "created_by_user_id": ctx.user_id,
            },
        )
        await insert_citation_events(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "citation_id": row.id,
                    "kind": "relinked",
                    "cause_ref": moved_cause(successor.id),
                    "successor_citation_id": new_id,
                    "actor_kind": "human",
                    "actor_user_id": ctx.user_id,
                }
            ],
        )
        tx.record(
            "citation.relinked",
            target=Target("citation", new_id),
            after=Ref(supersedes_id=row.id, source=successor.id),
            scope=Scope(row.engagement_id, row.work_item_id),
        )
    return new_id


def _successors(events: Sequence[CitationEvent]) -> list[UUID]:
    """The versions the events' `moved` causes name."""
    found: list[UUID] = []
    for event in events:
        cause = event.cause_ref
        if event.kind == "moved" and cause is not None:
            kind, _, raw = cause.partition(":")
            if kind == VERSION_SOURCE:
                try:
                    found.append(UUID(raw))
                except ValueError:
                    continue
    return found


__all__ = [
    "NotMoved",
    "RelinkUnverified",
    "broken_cause",
    "mark_sources_superseded",
    "moved_cause",
    "on_version_created",
    "on_version_withdrawn",
    "relink",
]
