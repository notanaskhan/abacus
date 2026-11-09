"""C10's service seam (R-02-T02 stub; R-02 §3.5, §4.3; SPEC-646 AC-17 to AC-20). Contract:
`docs/contracts/deliverables.md`.

A provider publishes inside its own unit of work (A-07's ReleaseWorkflow under the EP's approval
grant, A-06's send-draft; later C-02 and X-01). One deliverable per `(source_module, source_ref)`
and one insert-only version per evidence version; a repeat with the same source version is a
no-op returning the same ids. Publishing is never flagged.

R-02-T09 (TASK-6205; DEC-2805) builds the service behind R-02-T02's signatures:

- `publish_deliverable` writes the deliverable (once per source), an insert-only version per
  evidence version, its audiences and a `published` event; the previous live version gets
  `superseded`. A draft must be a C11 draft-mode render (DRAFT-marked) or it is refused (AC-18).
- `withdraw_deliverable` records `withdrawn` with a reason and a sealed note (Restricted).
- `deliverables_for_work_item` is AUD-24's dock and CLS-08's delivery state per audience contact,
  from `deliverable_receipts` (AC-20); `expected_deliverables` is POR-09's Coming next.
- `portal_deliverables` is POR-09's rail for a client person: bands by work item, Coming next,
  and the read-through rows other modules own (K-1 packages from T-02; envelopes from C7) through
  `register_k1_rows` and `register_envelope_rows`, since those modules import reporting.
- `deliverable_versions_for_work_item` is FIL-01's Deliverables folder provider, registered with
  `evidence.api.register_folder_provider("deliverables", ...)`; Files lists those versions under
  `visible()`, so a walled item stays absent.

The portal routes stay 501 until R-02-T14 turns on `portal.deliverables`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.engagements.api import work_item_titles
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting.deliverable_reads import Audience, first_covering_grant
from abacus.modules.reporting.events import (
    DeliverablePublished,
    DeliverableSuperseded,
    DeliverableWithdrawn,
)

AudienceScope = Literal["client", "client_entity", "engagement", "work_item", "governance_room"]
ActorKind = Literal["human", "system"]
WithdrawReason = Literal["wrong_file", "reissued", "other"]
DeliveryState = Literal["not_opened", "delivered", "viewed", "downloaded"]


class DraftWithoutWatermark(DomainInvalid):
    """A draft version whose P-11 generated document carries no DRAFT watermark (AC-18)."""

    code = "draft_without_watermark"


class DeliverableInvalid(DomainInvalid):
    """A publish missing what C10 needs (a title, pages, an audience, the actor's person)."""

    code = "deliverable_invalid"


class DeliverableWithdrawnAlready(DomainConflict):
    """The version already ended: superseded or withdrawn (one terminal event per version)."""

    code = "deliverable_version_ended"


@dataclass(frozen=True)
class DeliverableAudience:
    scope_kind: AudienceScope
    scope_id: UUID


@dataclass(frozen=True)
class DeliverableSpec:
    """One publish. `kind` is one of `portal.deliverables_contract.DeliverableKind`; the actor is
    a person, or the system on a person's behalf (`on_behalf_of_user_id` is then required)."""

    client_id: UUID
    kind: str
    title: str
    source_module: str
    source_ref: str
    evidence_version_id: UUID
    render_hash: str
    page_count: int
    audiences: Sequence[DeliverableAudience]
    published_by_user_id: UUID
    actor_kind: ActorKind = "human"
    on_behalf_of_user_id: UUID | None = None
    client_entity_id: UUID | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    generated_document_id: UUID | None = None
    is_draft: bool = False
    page_comments: bool = False
    restricted_use: bool = False
    legend_kind: Literal["ar_c_70"] | None = None
    approval_kind: str | None = None
    approval_item_id: UUID | None = None


@dataclass(frozen=True)
class PublishedDeliverable:
    deliverable_id: UUID
    version_id: UUID
    version_no: int
    created: bool


@dataclass(frozen=True)
class AudienceReceipt:
    """Per audience contact: "Delivered", "Viewed Oct 9, 10:22 AM", "Downloaded" (AC-20)."""

    contact_id: UUID
    state: DeliveryState
    first_viewed_at: datetime | None = None
    first_downloaded_at: datetime | None = None
    download_count: int = 0


@dataclass(frozen=True)
class WorkItemDeliverable:
    deliverable_id: UUID
    kind: str
    title: str
    latest_version_no: int
    is_draft: bool
    receipts: Sequence[AudienceReceipt] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExpectedDeliverable:
    """POR-09's Coming next, from C1's client-visible milestones."""

    label: str
    expected_on: date | None = None


# --- publish -------------------------------------------------------------------------------

_DRAFT_RENDER = text(
    """
    SELECT EXISTS (
        SELECT 1 FROM generated_document_files f
          JOIN generated_document_versions gv ON gv.id = f.version_id
         WHERE f.evidence_version_id = :ev
           AND gv.generated_document_id = :doc
           AND gv.mode = 'draft'
    )
    """
)
_UPSERT = text(
    """
    INSERT INTO deliverables (tenant_id, client_id, client_entity_id, engagement_id, work_item_id,
                              kind, title, source_module, source_ref, restricted_use, legend_kind,
                              created_by)
    VALUES (CAST(:tenant AS uuid), :client, :entity, :engagement, :work_item,
            :kind, :title, :source_module, :source_ref, :restricted, :legend, :by)
    ON CONFLICT (tenant_id, source_module, source_ref) DO NOTHING
    RETURNING id
    """
)
_FIND = text(
    "SELECT id, client_id, kind FROM deliverables "
    "WHERE source_module = :source_module AND source_ref = :source_ref FOR UPDATE"
)
_SAME_VERSION = text(
    "SELECT id, version_no FROM deliverable_versions "
    "WHERE deliverable_id = :d AND evidence_version_id = :ev"
)
_LIVE = text(
    """
    SELECT v.id, v.version_no FROM deliverable_versions v
     WHERE v.deliverable_id = :d
       AND NOT EXISTS (SELECT 1 FROM deliverable_events e
                        WHERE e.deliverable_version_id = v.id
                          AND e.kind IN ('superseded', 'withdrawn'))
     ORDER BY v.version_no DESC LIMIT 1
    """
)
_NEXT_NO = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM deliverable_versions WHERE deliverable_id = :d"
)
_INSERT_VERSION = text(
    """
    INSERT INTO deliverable_versions (tenant_id, deliverable_id, version_no, evidence_version_id,
        generated_document_id, render_hash, page_count, is_draft, page_comments, approval_kind,
        approval_item_id, published_by_user_id, actor_kind, on_behalf_of_user_id,
        supersedes_version_id)
    VALUES (CAST(:tenant AS uuid), :d, :no, :ev, :doc, :hash, :pages, :draft,
            :comments, :approval_kind, :approval_item, :by, :actor_kind, :behalf, :supersedes)
    RETURNING id
    """
)
_AUDIENCE = text(
    "INSERT INTO deliverable_audiences (tenant_id, deliverable_id, scope_kind, scope_id) "
    "VALUES (CAST(:tenant AS uuid), :d, :kind, :scope) ON CONFLICT DO NOTHING"
)
_EVENT = text(
    """
    INSERT INTO deliverable_events (tenant_id, deliverable_version_id, kind, reason_code,
                                    note_sealed, actor_kind, actor_user_id, on_behalf_of_user_id)
    VALUES (CAST(:tenant AS uuid), :v, :kind, :reason, :note, :actor_kind,
            :actor, :behalf)
    """
)


def _validated(spec: DeliverableSpec) -> None:
    if not spec.title.strip() or len(spec.title) > 200:
        raise DeliverableInvalid(facts={"field": "title"})
    if spec.page_count <= 0:
        raise DeliverableInvalid(facts={"field": "page_count"})
    if not spec.audiences:
        raise DeliverableInvalid(facts={"field": "audiences"})
    if spec.actor_kind == "system" and spec.on_behalf_of_user_id is None:
        raise DeliverableInvalid(facts={"field": "on_behalf_of_user_id"})
    if spec.page_comments and not spec.is_draft:
        raise DeliverableInvalid(facts={"field": "page_comments"})
    if (spec.approval_kind is None) != (spec.approval_item_id is None):
        raise DeliverableInvalid(facts={"field": "approval_item_id"})
    if spec.work_item_id is not None and spec.engagement_id is None:
        raise DeliverableInvalid(facts={"field": "engagement_id"})
    if spec.restricted_use and any(a.scope_kind == "client" for a in spec.audiences):
        # Restricted use (governance letters, SOC reports): named audiences, never the whole
        # client (AC-18).
        raise DeliverableInvalid(facts={"field": "audiences"})


def _actor(spec: DeliverableSpec) -> dict[str, object]:
    human = spec.actor_kind == "human"
    return {
        "actor_kind": spec.actor_kind,
        "actor": spec.published_by_user_id if human else None,
        "behalf": None if human else spec.on_behalf_of_user_id,
    }


async def publish_deliverable(tx: UnitOfWork, spec: DeliverableSpec) -> PublishedDeliverable:
    """AC-17 to AC-19, inside the provider's own unit of work."""
    _validated(spec)
    session = tx.session
    tenant = (await transaction_context(session)).tenant_id
    if spec.is_draft:
        drawn = spec.generated_document_id is not None and bool(
            await session.scalar(
                _DRAFT_RENDER,
                {"ev": spec.evidence_version_id, "doc": spec.generated_document_id},
            )
        )
        if not drawn:
            raise DraftWithoutWatermark
    created = await session.scalar(
        _UPSERT,
        {
            "tenant": tenant,
            "client": spec.client_id,
            "entity": spec.client_entity_id,
            "engagement": spec.engagement_id,
            "work_item": spec.work_item_id,
            "kind": spec.kind,
            "title": spec.title.strip(),
            "source_module": spec.source_module,
            "source_ref": spec.source_ref,
            "restricted": spec.restricted_use,
            "legend": spec.legend_kind,
            "by": spec.published_by_user_id,
        },
    )
    found = (
        await session.execute(
            _FIND, {"source_module": spec.source_module, "source_ref": spec.source_ref}
        )
    ).one()
    deliverable_id: UUID = found.id
    if found.client_id != spec.client_id or found.kind != spec.kind:
        raise DeliverableInvalid(facts={"field": "source_ref"})  # one source, one deliverable
    same = (
        await session.execute(_SAME_VERSION, {"d": deliverable_id, "ev": spec.evidence_version_id})
    ).first()
    if same is not None:  # the same source version again: a no-op with the same ids
        # A provider's retry may carry nothing else to record; the repeat is audited so its unit
        # of work can commit (S31 end pass).
        tx.record(
            "deliverable.publish_repeated",
            target=Target("deliverable_version", same.id),
            scope=Scope(engagement_id=spec.engagement_id, work_item_id=spec.work_item_id),
        )
        return PublishedDeliverable(deliverable_id, same.id, same.version_no, False)
    live = (await session.execute(_LIVE, {"d": deliverable_id})).first()
    version_no = int(await session.scalar(_NEXT_NO, {"d": deliverable_id}) or 1)
    version_id: UUID = await session.scalar(
        _INSERT_VERSION,
        {
            "tenant": tenant,
            "d": deliverable_id,
            "no": version_no,
            "ev": spec.evidence_version_id,
            "doc": spec.generated_document_id,
            "hash": spec.render_hash,
            "pages": spec.page_count,
            "draft": spec.is_draft,
            "comments": spec.page_comments,
            "approval_kind": spec.approval_kind,
            "approval_item": spec.approval_item_id,
            "by": spec.published_by_user_id,
            "actor_kind": spec.actor_kind,
            "behalf": spec.on_behalf_of_user_id,
            "supersedes": None if live is None else live.id,
        },
    )
    for audience in spec.audiences:
        await session.execute(
            _AUDIENCE,
            {
                "tenant": tenant,
                "d": deliverable_id,
                "kind": audience.scope_kind,
                "scope": audience.scope_id,
            },
        )
    actor = _actor(spec)
    await session.execute(
        _EVENT,
        {"tenant": tenant, "v": version_id, "kind": "published", "reason": None, "note": None}
        | actor,
    )
    scope = Scope(engagement_id=spec.engagement_id, work_item_id=spec.work_item_id)
    if live is not None:
        await session.execute(
            _EVENT,
            {"tenant": tenant, "v": live.id, "kind": "superseded", "reason": None, "note": None}
            | actor,
        )
        tx.record(
            "deliverable.superseded",
            target=Target("deliverable_version", live.id),
            after=Ref(by_version=version_id),
            scope=scope,
        )
        tx.emit(DeliverableSuperseded(deliverable_id=deliverable_id, version_id=live.id))
    tx.record(
        "deliverable.published",
        target=Target("deliverable_version", version_id),
        after=Ref(deliverable=deliverable_id, version_no=version_no),
        scope=scope,
    )
    tx.emit(
        DeliverablePublished(
            deliverable_id=deliverable_id,
            version_id=version_id,
            version_no=version_no,
            is_draft=spec.is_draft,
            has_approval=spec.approval_item_id is not None,
            engagement_id=spec.engagement_id,
            work_item_id=spec.work_item_id,
        )
    )
    return PublishedDeliverable(deliverable_id, version_id, version_no, created is not None)


async def supersede_deliverable(
    tx: UnitOfWork, deliverable_id: UUID, spec: DeliverableSpec
) -> PublishedDeliverable:
    """A newer version of a known deliverable: the spec must name the same source."""
    found = (
        await tx.session.execute(
            _FIND, {"source_module": spec.source_module, "source_ref": spec.source_ref}
        )
    ).first()
    if found is None or found.id != deliverable_id:
        raise NotFound("deliverable")
    return await publish_deliverable(tx, spec)


_ENDED = text(
    """
    SELECT v.id, d.engagement_id, d.work_item_id, d.id AS deliverable_id,
           EXISTS (SELECT 1 FROM deliverable_events e WHERE e.deliverable_version_id = v.id
                     AND e.kind IN ('superseded', 'withdrawn')) AS ended
      FROM deliverable_versions v JOIN deliverables d ON d.id = v.deliverable_id
     WHERE v.id = :v
    """
)


async def withdraw_deliverable(
    tx: UnitOfWork,
    version_id: UUID,
    reason: WithdrawReason,
    actor_user_id: UUID,
    note: str | None = None,
) -> None:
    """OQ-7: the firm withdraws a version (a person's act); the client reads "Replaced by" the
    firm's name and the date. The note is sealed (Restricted) and never in an audit row."""
    found = (await tx.session.execute(_ENDED, {"v": version_id})).first()
    if found is None:
        raise NotFound("deliverable")
    if found.ended:
        raise DeliverableWithdrawnAlready
    tenant_id = (await transaction_context(tx.session)).tenant_id
    sealed = None
    if note is not None and note.strip():
        sealed = await seal(tenant_id, note.strip().encode(), f"deliverable_event:{version_id}")
    try:
        await tx.session.execute(
            _EVENT,
            {
                "tenant": tenant_id,
                "v": version_id,
                "kind": "withdrawn",
                "reason": reason,
                "note": sealed,
                "actor_kind": "human",
                "actor": actor_user_id,
                "behalf": None,
            },
        )
    except IntegrityError as exc:
        # `deliverable_events_one_terminal`: a concurrent supersede or withdrawal won the race.
        raise DeliverableWithdrawnAlready from exc
    tx.record(
        "deliverable.withdrawn",
        target=Target("deliverable_version", version_id),
        # The reason code is on the event row; a reference never carries text (S31 end pass).
        scope=Scope(engagement_id=found.engagement_id, work_item_id=found.work_item_id),
    )
    tx.emit(DeliverableWithdrawn(deliverable_id=found.deliverable_id, version_id=version_id))


# --- reads ---------------------------------------------------------------------------------------

_FOR_WORK_ITEM = text(
    """
    SELECT d.id, d.kind, d.title, v.id AS version_id, v.version_no, v.is_draft,
           v.evidence_version_id
      FROM deliverables d
      JOIN LATERAL (
          SELECT * FROM deliverable_versions x
           WHERE x.deliverable_id = d.id
             AND EXISTS (SELECT 1 FROM deliverable_events p WHERE p.deliverable_version_id = x.id
                           AND p.kind = 'published')
             AND NOT EXISTS (SELECT 1 FROM deliverable_events e
                              WHERE e.deliverable_version_id = x.id AND e.kind = 'withdrawn')
           ORDER BY x.version_no DESC LIMIT 1
      ) v ON true
     WHERE d.work_item_id = :wi
     ORDER BY d.created_at, d.id
    """
)
_RECEIPTS = text(
    "SELECT deliverable_version_id, contact_id, first_viewed_at, first_downloaded_at, "
    "download_count FROM deliverable_receipts WHERE deliverable_version_id = ANY(:ids) "
    "ORDER BY contact_id"
)


def _receipt_state(viewed: datetime | None, downloads: int) -> DeliveryState:
    if downloads > 0:
        return "downloaded"
    return "viewed" if viewed is not None else "delivered"


async def deliverables_for_work_item(
    tenant: TenantContext, work_item_id: UUID
) -> list[WorkItemDeliverable]:
    """AC-20: each deliverable's newest published, not withdrawn version, with the delivery
    state per audience contact. For a caller already authorised on the work item."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_FOR_WORK_ITEM, {"wi": work_item_id})).all()
        ids = [r.version_id for r in rows]
        receipts = (await session.execute(_RECEIPTS, {"ids": ids})).all()
    by_version: dict[UUID, list[AudienceReceipt]] = {}
    for r in receipts:
        by_version.setdefault(r.deliverable_version_id, []).append(
            AudienceReceipt(
                contact_id=r.contact_id,
                state=_receipt_state(r.first_viewed_at, int(r.download_count)),
                first_viewed_at=r.first_viewed_at,
                first_downloaded_at=r.first_downloaded_at,
                download_count=int(r.download_count),
            )
        )
    return [
        WorkItemDeliverable(
            deliverable_id=r.id,
            kind=r.kind,
            title=r.title,
            latest_version_no=r.version_no,
            is_draft=r.is_draft,
            receipts=tuple(by_version.get(r.version_id, ())),
        )
        for r in rows
    ]


async def deliverable_versions_for_work_item(
    tenant: TenantContext, work_item_id: UUID
) -> list[UUID]:
    """FIL-01's Deliverables folder (N-01, `folder_kind = 'deliverables'`): the evidence versions
    of the work item's live deliverable versions. Files lists them under `visible()`."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_FOR_WORK_ITEM, {"wi": work_item_id})).all()
    return [r.evidence_version_id for r in rows]


# C1's client-visible milestones reach Coming next through a slot (engagements owns C1 and
# imports reporting): a provider answers (label, expected_on) per work item.
type ExpectedProvider = Callable[[TenantContext, UUID], Awaitable[Sequence[ExpectedDeliverable]]]
_EXPECTED: list[ExpectedProvider] = []


def register_expected_deliverables(provider: ExpectedProvider) -> None:
    if provider not in _EXPECTED:
        _EXPECTED.append(provider)


async def expected_deliverables(
    tenant: TenantContext, work_item_id: UUID
) -> list[ExpectedDeliverable]:
    """POR-09's Coming next: what C1 says the client will receive, nothing about progress."""
    out: list[ExpectedDeliverable] = []
    for provider in _EXPECTED:
        out.extend(await provider(tenant, work_item_id))
    return sorted(out, key=lambda e: (e.expected_on or date.max, e.label))


# --- the portal rail (POR-09) --------------------------------------------------------------------


@dataclass(frozen=True)
class PortalRow:
    deliverable_id: UUID
    kind: str
    title: str
    status: str
    latest_version: int | None
    page_count: int | None
    released_on: date | None
    restricted_use: bool


@dataclass(frozen=True)
class PortalBand:
    key: str
    label: str
    work_item_id: UUID | None
    rows: tuple[PortalRow, ...]


@dataclass(frozen=True)
class PortalK1:
    package_id: UUID
    title: str
    released_on: date


@dataclass(frozen=True)
class PortalDeliverables:
    bands: tuple[PortalBand, ...]
    coming_next: tuple[ExpectedDeliverable, ...]
    k1s: tuple[PortalK1, ...]


# T-02 owns K-1 delivery (its consent sheet and tracking); C7 owns envelopes ("In Sign"). Both
# import reporting, so their rows reach the rail through these slots.
type K1Rows = Callable[[AuthContext], Awaitable[Sequence[PortalK1]]]
type EnvelopeRows = Callable[[AuthContext, UUID], Awaitable[Sequence[PortalRow]]]
_K1_ROWS: list[K1Rows] = []
_ENVELOPE_ROWS: list[EnvelopeRows] = []


def register_k1_rows(provider: K1Rows) -> None:
    if provider not in _K1_ROWS:
        _K1_ROWS.append(provider)


def register_envelope_rows(provider: EnvelopeRows) -> None:
    if provider not in _ENVELOPE_ROWS:
        _ENVELOPE_ROWS.append(provider)


_PORTAL = text(
    """
    SELECT d.id, d.kind, d.title, d.client_id, d.client_entity_id, d.engagement_id,
           d.work_item_id, d.restricted_use,
           v.version_no, v.page_count, v.is_draft, v.published_at,
           (SELECT max(e.created_at) FROM deliverable_events e
             WHERE e.deliverable_version_id = v.id AND e.kind = 'withdrawn') AS withdrawn_at
      FROM deliverables d
      JOIN LATERAL (
          SELECT * FROM deliverable_versions x
           WHERE x.deliverable_id = d.id
             AND EXISTS (SELECT 1 FROM deliverable_events p WHERE p.deliverable_version_id = x.id
                           AND p.kind = 'published')
           ORDER BY x.version_no DESC LIMIT 1
      ) v ON true
     WHERE d.client_id = ANY(:clients)
     ORDER BY d.work_item_id NULLS LAST, d.created_at, d.id
    """
)
_AUDIENCES = text(
    "SELECT deliverable_id, scope_kind, scope_id FROM deliverable_audiences "
    "WHERE deliverable_id = ANY(:ids)"
)
_STATUS_DRAFT: Final = "for_your_review"
_STATUS_FINAL: Final = "final"
_STATUS_REPLACED: Final = "replaced"


def _status(is_draft: bool, withdrawn: bool) -> str:
    if withdrawn:
        return _STATUS_REPLACED
    return _STATUS_DRAFT if is_draft else _STATUS_FINAL


async def portal_deliverables(ctx: AuthContext, client_ids: Sequence[UUID]) -> PortalDeliverables:
    """POR-09's rail for a client person: the deliverables one of their grants covers (C10's
    reader rule, per role and scope; DEC-93), banded by work item, then Coming next and their
    own released K-1s. A person no grant reaches gets empty bands, never another's rows."""
    if ctx.tenant.actor_kind != "human" or not ctx.client:
        raise NotFound("deliverable")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_PORTAL, {"clients": list(client_ids)})).all()
        ids = [r.id for r in rows]
        audiences = (await session.execute(_AUDIENCES, {"ids": ids})).all()
    by_deliverable: dict[UUID, list[Audience]] = {}
    for a in audiences:
        by_deliverable.setdefault(a.deliverable_id, []).append(
            Audience(str(a.scope_kind), a.scope_id)
        )
    bands: dict[str, list[PortalRow]] = {}
    labels: dict[str, tuple[str, UUID | None]] = {}
    work_items: list[UUID] = []
    for r in rows:
        grant = await first_covering_grant(
            ctx, by_deliverable.get(r.id, []), r.client_id, r.engagement_id, r.client_entity_id
        )
        if grant is None:
            continue
        key = f"work_item:{r.work_item_id}" if r.work_item_id else f"client:{r.client_id}"
        labels.setdefault(key, (r.title, r.work_item_id))
        if r.work_item_id is not None and r.work_item_id not in work_items:
            work_items.append(r.work_item_id)
        bands.setdefault(key, []).append(
            PortalRow(
                deliverable_id=r.id,
                kind=r.kind,
                title=r.title,
                status=_status(r.is_draft, r.withdrawn_at is not None),
                latest_version=r.version_no,
                page_count=r.page_count,
                released_on=None if r.is_draft else r.published_at.date(),
                restricted_use=r.restricted_use,
            )
        )
    # A work item's band reads its name (engagements owns it; S31 end pass).
    names = await work_item_titles(ctx.tenant, work_items)
    for work_item, name in names.items():
        key = f"work_item:{work_item}"
        if key in labels:
            labels[key] = (name, work_item)
    for work_item in work_items:
        key = f"work_item:{work_item}"
        for provider in _ENVELOPE_ROWS:
            bands.setdefault(key, []).extend(await provider(ctx, work_item))
    coming: list[ExpectedDeliverable] = []
    for work_item in work_items:
        coming.extend(await expected_deliverables(ctx.tenant, work_item))
    k1s: list[PortalK1] = []
    for provider in _K1_ROWS:
        k1s.extend(await provider(ctx))
    return PortalDeliverables(
        bands=tuple(
            PortalBand(key, labels[key][0], labels[key][1], tuple(rows_))
            for key, rows_ in bands.items()
        ),
        coming_next=tuple(coming),
        k1s=tuple(k1s),
    )
