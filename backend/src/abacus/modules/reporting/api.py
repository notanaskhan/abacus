"""Public interface of the reporting module; other modules import only this (ADR-008).

C11 v1 (P-11-T03; `docs/contracts/c11-renderer.md`; ADR-320): the routers, and the in-process
renderer API consumers call inside their unit of work. A consumer registers a document kind
(layout, variables provider, approval provider, source events, retention record type), asks for
drafts with `render`, and asks for a final render only with a human approval (`render_final`).
Values are resolved by the kind's provider from the database: a consumer never passes values
from the browser. The shapes are frozen with C11 (S18 Contract Monday). P-11-T08 builds the service
(`documents.py`): `render(tx, …)`, `render_final(tx, …)`, `lock(tx, …)` and
`generated_document(tx, …)` run inside the caller's unit of work, as C11 §2 says, and a kind's
`source_events` mark its documents out of date through `SUBSCRIPTIONS`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, cast, get_args
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.uow import UnitOfWork
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import (
    register_letter_finaliser,
    register_letter_locker,
    register_letter_renderer,
)
from abacus.modules.reporting.consent import Recipients as Recipients
from abacus.modules.reporting.consent import RecipientsUnavailable as RecipientsUnavailable
from abacus.modules.reporting.consent import recipients as _consent_recipients
from abacus.modules.reporting.contract import CONSENT_RECIPIENTS_KEY as CONSENT_RECIPIENTS_KEY
from abacus.modules.reporting.contract import DocBlock as DocBlock
from abacus.modules.reporting.contract import (
    GeneratedDocumentKind,
    LayoutKey,
    RenderFormat,
    RequesterKind,
    documents_router,
    templates_router,
)
from abacus.modules.reporting.contract import TemplateImportIn as TemplateImportIn
from abacus.modules.reporting.deliverable_reads import ReaderVersion as ReaderVersion
from abacus.modules.reporting.deliverable_reads import reader_version as reader_version
from abacus.modules.reporting.deliverables import AudienceReceipt as AudienceReceipt
from abacus.modules.reporting.deliverables import DeliverableAudience as DeliverableAudience
from abacus.modules.reporting.deliverables import DeliverableSpec as DeliverableSpec
from abacus.modules.reporting.deliverables import DraftWithoutWatermark as DraftWithoutWatermark
from abacus.modules.reporting.deliverables import ExpectedDeliverable as ExpectedDeliverable
from abacus.modules.reporting.deliverables import PublishedDeliverable as PublishedDeliverable
from abacus.modules.reporting.deliverables import WorkItemDeliverable as WorkItemDeliverable
from abacus.modules.reporting.deliverables import (
    deliverables_for_work_item as deliverables_for_work_item,
)
from abacus.modules.reporting.deliverables import expected_deliverables as expected_deliverables
from abacus.modules.reporting.deliverables import publish_deliverable as publish_deliverable
from abacus.modules.reporting.deliverables import supersede_deliverable as supersede_deliverable
from abacus.modules.reporting.deliverables import withdraw_deliverable as withdraw_deliverable
from abacus.modules.reporting.engagement_letters import (
    finalise_engagement_letter,
    lock_engagement_letter,
    render_engagement_letter,
)
from abacus.modules.reporting.fs_captions import (
    statement_caption_amounts as statement_caption_amounts,
)
from abacus.modules.reporting.render.core import DocxRenderOutput as DocxRenderOutput

# T-01-T10's consumer API (re-exported).
from abacus.modules.reporting.render.core import RenderInput as RenderInput
from abacus.modules.reporting.render.core import RenderOutput as RenderOutput
from abacus.modules.reporting.render.core import render_docx as render_docx
from abacus.modules.reporting.render.core import render_isolated as render_isolated
from abacus.modules.reporting.render.head import RenderRefused as _RenderingRefused

# P-11-T13: the template import and publication services the routes call, for the scenario loader
# (a firm's content goes in through these, never a migration or constant; AGENTS 16).
from abacus.modules.reporting.templates import import_bundle as _import_bundle
from abacus.modules.reporting.templates import publish as _publish_template

consent_recipients = _consent_recipients
import_template_bundle = _import_bundle
publish_template = _publish_template
RenderingRefused = _RenderingRefused

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.kernel.audit_owners import register_engagement_owners  # noqa: E402
from abacus.modules.reporting import statements as _statements  # noqa: E402
from abacus.modules.reporting.statements_contract import statements_router  # noqa: E402

# A-06-T25 (DEC-2304): the trail places a statement version and a checklist answer.
register_engagement_owners(_statements.AUDIT_KINDS, _statements.audit_owners)

ROUTERS = (templates_router, documents_router, statements_router)  # A-06-T19: statements stub

KINDS: frozenset[str] = frozenset(get_args(GeneratedDocumentKind))
# The layouts a kind may register: a template's six and the composed `financial_statements`.
LAYOUTS: frozenset[str] = frozenset(get_args(LayoutKey)) | {"financial_statements"}


class RenderRefused(ValueError):
    """A render refused with a C11 error code (`missing_variable`, `final_requires_approval`,
    `approval_hash_mismatch`, `document_locked`, …)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class OwnerRef:
    type: str
    id: UUID


@dataclass(frozen=True)
class RenderScope:
    """The consumer record's scope; it drives `visible()` and walls (AC-26)."""

    client_id: UUID
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None


@dataclass(frozen=True)
class ClauseState:
    clause_id: str
    enabled: bool


@dataclass(frozen=True)
class SectionOverride:
    """Plain-text paragraphs a person wrote in the consumer's editor, kept with their author."""

    section_id: str
    paragraphs: tuple[str, ...]
    authored_by_user_id: UUID


@dataclass(frozen=True)
class ApprovalRef:
    """The consumer's human approval of a draft: its kind and id, and the draft's content hash
    it approved (AC-15)."""

    kind: str
    id: UUID
    content_hash: str


@dataclass(frozen=True)
class Requester:
    """Who asks: a person, or the agent for that person (a run), or the system."""

    kind: RequesterKind
    user_id: UUID | None = None
    run_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None


@dataclass(frozen=True)
class RenderRequest:
    kind: GeneratedDocumentKind
    owner_ref: OwnerRef
    scope: RenderScope
    template_version_id: UUID | None
    requested_by: Requester
    mode: Literal["draft", "final"] = "draft"
    formats: tuple[RenderFormat, ...] = ("pdf",)
    clause_states: tuple[ClauseState, ...] = ()
    section_overrides: tuple[SectionOverride, ...] = ()
    approval_ref: ApprovalRef | None = None


@dataclass(frozen=True)
class RenderTicket:
    generated_document_id: UUID
    version_no: int
    status: Literal["drafting"] = "drafting"
    # The draft's content hash (additive, N-02-T32): what a consumer's approval names.
    content_hash: str = ""


# A kind's providers: variables resolved from the database for a scope; an approval resolved to
# the approver's user id and the content hash they approved, or None when it is not a human's.
VariablesProvider = Callable[[OwnerRef, RenderScope], Awaitable[Mapping[str, str]]]
ApprovalProvider = Callable[[ApprovalRef], Awaitable[tuple[UUID, str] | None]]
# N-04-T16 (DEC-2311): the same, for a kind whose values need the transaction's tenant.
TenantVariablesProvider = Callable[
    [TenantContext, OwnerRef, RenderScope], Awaitable[Mapping[str, str]]
]
# A-06-T29 (DEC-2615): a kind whose whole body code composes from its owner's sealed record (the
# financial statements): DocBlocks as plain data, sealed in the snapshot; it takes no template.
BodyProvider = Callable[[TenantContext, OwnerRef, RenderScope], Awaitable[Sequence[object]]]


# A kind's layout: a template's six, or `financial_statements`, which only a composed kind uses
# (DEC-2615; C11's template contract and its OpenAPI are unchanged).
KindLayout = LayoutKey | Literal["financial_statements"]


@dataclass(frozen=True)
class DocumentKind:
    kind: GeneratedDocumentKind
    layout: KindLayout
    variables_provider: VariablesProvider
    approval_provider: ApprovalProvider
    source_events: tuple[str, ...] = ()
    retention_record_type: str = ""
    formats: tuple[RenderFormat, ...] = field(default=("pdf",))
    tenant_variables_provider: TenantVariablesProvider | None = None
    body_provider: BodyProvider | None = None


class UnknownDocumentKind(LookupError):
    """A render for a kind nobody registered: refused, never guessed (ADR-140)."""


_REGISTRY: dict[str, DocumentKind] = {}


def register_document_kind(kind: DocumentKind) -> None:
    """A consumer's registration (N-02 letters and consents, A-07 reports, N-04 responses…).
    One registration per kind; a second for the same kind is a programming error."""
    if kind.kind not in KINDS:
        raise UnknownDocumentKind(kind.kind)
    if kind.layout not in LAYOUTS:
        raise RenderRefused("unknown_layout", kind.layout)
    if kind.kind in _REGISTRY and _REGISTRY[kind.kind] is not kind:
        raise ValueError(f"document kind {kind.kind} is already registered")
    _REGISTRY[kind.kind] = kind


def document_kind(kind: str) -> DocumentKind:
    found = _REGISTRY.get(kind)
    if found is None:
        raise UnknownDocumentKind(kind)
    return found


def _body_kind(kind: str) -> bool:
    """A registered kind whose body code composes (DEC-2615)."""
    registered = _REGISTRY.get(kind)
    return registered is not None and registered.body_provider is not None


_BLOCKS: Final = TypeAdapter(list[DocBlock])


async def _composed_body(
    tx: UnitOfWork, kind: DocumentKind, request_owner: OwnerRef, scope: RenderScope
) -> list[object] | None:
    """A composed kind's body, checked against C11's closed block union before it is sealed."""
    if kind.body_provider is None:
        return None
    body = list(
        await kind.body_provider(await transaction_context(tx.session), request_owner, scope)
    )
    try:
        _BLOCKS.validate_python(body)
    except ValidationError as invalid:
        raise RenderRefused("unknown_layout", "the composed body is not C11 blocks") from invalid
    return body


def check_render_request(request: RenderRequest) -> None:
    """The rules every render request meets before any work (AC-15, AC-16; INV-1):

    - an agent's request is a draft, carrying its run id; never a final render;
    - a final render is a person's, with an approval reference;
    - the template version is named for every kind but a run trace export.
    The approval itself (a human's, on this draft's content hash) is checked against the kind's
    approval provider when the render runs (P-11-T08)."""
    who = request.requested_by
    if who.kind == "agent":
        if request.mode != "draft":
            raise RenderRefused("final_requires_approval", "an agent requests drafts only")
        if who.run_id is None:
            raise RenderRefused("final_requires_approval", "an agent draft names its run")
    if request.mode == "final":
        if who.kind != "human" or who.user_id is None:
            raise RenderRefused("final_requires_approval", "a final render is a person's")
        if request.approval_ref is None:
            raise RenderRefused("final_requires_approval")
    composed = _body_kind(request.kind)
    if request.template_version_id is None and request.kind != "run_trace_export" and not composed:
        raise RenderRefused("unknown_layout", "no template version")
    if composed and request.template_version_id is not None:
        raise RenderRefused("unknown_layout", "a composed kind takes no template version")
    if not request.formats:
        raise RenderRefused("unknown_layout", "no format")


async def render(tx: UnitOfWork, request: RenderRequest) -> RenderTicket:
    """Start a draft render inside the caller's unit of work; answers the ticket at Drafting.

    The kind's provider resolves the values; only the template version's declared keys are kept,
    and a declared key with no value refuses with `missing_variable` (never a blank). An agent's
    request is a draft (C11 §4). The bytes follow from the render job (the RenderWorkflow)."""
    from abacus.modules.reporting import documents as docs

    check_render_request(request)
    if request.mode != "draft":
        raise RenderRefused("final_requires_approval", "a final render goes through render_final")
    kind = document_kind(request.kind)
    resolved = (
        await kind.tenant_variables_provider(
            await transaction_context(tx.session), request.owner_ref, request.scope
        )
        if kind.tenant_variables_provider is not None
        else await kind.variables_provider(request.owner_ref, request.scope)
    )
    declared = await docs.declared_keys(tx, request.template_version_id)
    variables, missing = docs.declared_values(declared, resolved)
    if missing:
        raise RenderRefused("missing_variable", ",".join(missing))
    snapshot = docs.snapshot_of(
        layout=kind.layout,
        template_version_id=request.template_version_id,
        variables=variables,
        clause_states={c.clause_id: c.enabled for c in request.clause_states},
        overrides={o.section_id: o.paragraphs for o in request.section_overrides},
        body=await _composed_body(tx, kind, request.owner_ref, request.scope),
    )
    snapshot_sha = docs.sha256_hex(docs.canonical(snapshot))
    content_hash = docs.sha256_hex(f"{kind.layout}:{snapshot_sha}".encode())
    who = request.requested_by
    document_id = await docs.create_document(
        tx,
        kind=request.kind,
        owner_type=request.owner_ref.type,
        owner_id=request.owner_ref.id,
        client_id=request.scope.client_id,
        engagement_id=request.scope.engagement_id,
        work_item_id=request.scope.work_item_id,
        created_by_kind=who.kind,
    )
    if await docs.locked(tx, document_id):
        raise RenderRefused("document_locked")
    version_no = await docs.next_version(tx, document_id)
    await docs.insert_version(
        tx,
        document_id=document_id,
        version_no=version_no,
        mode="draft",
        template_version_id=request.template_version_id,
        layout_key=kind.layout,
        snapshot_sha256=snapshot_sha,
        snapshot=snapshot,
        content_hash=content_hash,
        approval_ref=None,
        requested_by_kind=who.kind,
        requested_by_user_id=who.user_id,
        requested_by_run_id=who.run_id,
        on_behalf_of_user_id=who.on_behalf_of_user_id,
    )
    docs.record_rendered(
        tx,
        "generated_document.rendered",
        document_id=document_id,
        version_no=version_no,
        content_hash=content_hash,
        engagement_id=request.scope.engagement_id,
        client_id=request.scope.client_id,
    )
    return RenderTicket(
        generated_document_id=document_id, version_no=version_no, content_hash=content_hash
    )


async def render_final(
    tx: UnitOfWork, document_id: UUID, approval_ref: ApprovalRef, requester: Requester
) -> RenderTicket:
    """A final render of the approved draft: only a person's, with an approval the kind's provider
    confirms as a human's, on the content hash of one of this document's drafts (C11 §4)."""
    from abacus.modules.reporting import documents as docs

    if requester.kind != "human" or requester.user_id is None:
        raise RenderRefused("final_requires_approval", "a final render is a person's")
    doc = await docs.document_row(tx, document_id)
    if doc is None:
        raise RenderRefused("not_found")
    if await docs.locked(tx, document_id):
        raise RenderRefused("document_locked")
    draft = await docs.draft_with_hash(tx, document_id, approval_ref.content_hash)
    if draft is None:
        raise RenderRefused("approval_hash_mismatch")
    kind = document_kind(str(doc["kind"]))
    approved = await kind.approval_provider(approval_ref)
    if approved is None:
        raise RenderRefused("final_requires_approval", "the approval is not a person's")
    if approved[1] != approval_ref.content_hash:
        raise RenderRefused("approval_hash_mismatch")
    sealed = await docs.snapshot_of_version(tx.session, cast(UUID, draft["id"]))
    if sealed is None:
        raise RenderRefused("approval_hash_mismatch", "the draft has no sealed snapshot")
    version_no = await docs.next_version(tx, document_id)
    await docs.insert_version(
        tx,
        document_id=document_id,
        version_no=version_no,
        mode="final",
        template_version_id=cast(UUID | None, draft["template_version_id"]),
        layout_key=str(draft["layout_key"]),
        snapshot_sha256=str(draft["snapshot_sha256"]),
        snapshot=sealed,
        content_hash=approval_ref.content_hash,
        approval_ref={
            "kind": approval_ref.kind,
            "id": str(approval_ref.id),
            "content_hash": approval_ref.content_hash,
            "approver_user_id": str(approved[0]),
        },
        requested_by_kind="human",
        requested_by_user_id=requester.user_id,
        requested_by_run_id=None,
        on_behalf_of_user_id=None,
    )
    docs.record_rendered(
        tx,
        "generated_document.finalised",
        document_id=document_id,
        version_no=version_no,
        content_hash=approval_ref.content_hash,
        engagement_id=cast(UUID | None, doc["engagement_id"]),
        client_id=cast(UUID, doc["client_id"]),
    )
    return RenderTicket(
        generated_document_id=document_id,
        version_no=version_no,
        content_hash=approval_ref.content_hash,
    )


async def regenerate(tx: UnitOfWork, document_id: UUID, requester: Requester) -> RenderTicket:
    """A person's new draft of the document (P-11-T11; AC-18): the latest version's sealed
    snapshot, with each declared value the kind's provider answers now in place of the sealed
    one (a provider that answers only inside its consumer's call keeps the sealed values), its
    clause states and overrides; refused when locked (`document_locked`)."""
    from abacus.modules.reporting import documents as docs

    if requester.kind != "human" or requester.user_id is None:
        raise RenderRefused("final_requires_approval", "regenerate is a person's")
    doc = await docs.document_row(tx, document_id)
    if doc is None:
        raise RenderRefused("not_found")
    if await docs.locked(tx, document_id):
        raise RenderRefused("document_locked")
    latest = await docs.latest_version(tx, document_id)
    if latest is None:
        raise RenderRefused("missing_variable", "no version to regenerate")
    sealed = await docs.snapshot_of_version(tx.session, cast(UUID, latest["id"]))
    if sealed is None:
        raise RenderRefused("missing_variable", "the version has no sealed snapshot")
    kind = document_kind(str(doc["kind"]))
    scope = RenderScope(
        client_id=cast(UUID, doc["client_id"]),
        engagement_id=cast(UUID | None, doc["engagement_id"]),
        work_item_id=cast(UUID | None, doc["work_item_id"]),
    )
    template_version_id = cast(UUID | None, latest["template_version_id"])
    raw = sealed.get("variables")
    values = (
        {str(k): str(v) for k, v in cast(Mapping[object, object], raw).items()}
        if isinstance(raw, Mapping)
        else {}
    )
    resolved = await kind.variables_provider(
        OwnerRef(str(doc["owner_type"]), doc["owner_id"]), scope
    )
    declared = await docs.declared_keys(tx, template_version_id)
    merged = {**values, **{k: v for k, v in resolved.items() if v.strip()}}
    variables, missing = docs.declared_values(declared, merged)
    if missing:
        raise RenderRefused("missing_variable", ",".join(missing))
    clauses = sealed.get("clauses")
    overrides = sealed.get("overrides")
    snapshot = docs.snapshot_of(
        layout=kind.layout,
        template_version_id=template_version_id,
        variables=variables,
        clause_states={
            str(k): bool(v) for k, v in cast(Mapping[object, object], clauses or {}).items()
        },
        overrides={
            str(k): tuple(str(p) for p in cast(list[object], v))
            for k, v in cast(Mapping[object, object], overrides or {}).items()
        },
        body=await _composed_body(
            tx, kind, OwnerRef(str(doc["owner_type"]), cast(UUID, doc["owner_id"])), scope
        ),
    )
    snapshot_sha = docs.sha256_hex(docs.canonical(snapshot))
    content_hash = docs.sha256_hex(f"{kind.layout}:{snapshot_sha}".encode())
    version_no = await docs.next_version(tx, document_id)
    await docs.insert_version(
        tx,
        document_id=document_id,
        version_no=version_no,
        mode="draft",
        template_version_id=template_version_id,
        layout_key=kind.layout,
        snapshot_sha256=snapshot_sha,
        snapshot=snapshot,
        content_hash=content_hash,
        approval_ref=None,
        requested_by_kind="human",
        requested_by_user_id=requester.user_id,
        requested_by_run_id=None,
        on_behalf_of_user_id=None,
    )
    docs.record_rendered(
        tx,
        "generated_document.regenerated",
        document_id=document_id,
        version_no=version_no,
        content_hash=content_hash,
        engagement_id=scope.engagement_id,
        client_id=scope.client_id,
    )
    return RenderTicket(
        generated_document_id=document_id, version_no=version_no, content_hash=content_hash
    )


async def lock(tx: UnitOfWork, document_id: UUID, cause_ref: str) -> None:
    """The consumer's lock (envelope completed, report released): no render after it (AC-19)."""
    from abacus.modules.reporting import documents as docs

    doc = await docs.document_row(tx, document_id)
    if doc is None:
        raise RenderRefused("not_found")
    if await docs.locked(tx, document_id):
        return
    await docs.add_event(
        tx,
        document_id=document_id,
        kind="locked",
        cause_ref=cause_ref,
        changed_keys=None,
        actor_kind="system",
        actor_user_id=None,
    )
    tx.record(
        "generated_document.locked",
        target=docs.target(document_id),
        after=docs.ref(cause=docs.sha256_hex(cause_ref.encode())),
    )


async def generated_document(tx: UnitOfWork, document_id: UUID) -> object:
    """The document's computed state (status, Out of date overlay, current version)."""
    from abacus.modules.reporting import documents as docs

    return await docs.generated_document(tx, document_id)


class _SourceSubscriptions(Mapping[str, Callable[[OutboxEvent], Awaitable[None]]]):
    """`SUBSCRIPTIONS`, read when the worker composes them (after every consumer registered): each
    registered kind's source events mark its documents out of date (P-11 §4.4)."""

    def _events(self) -> dict[str, tuple[str, ...]]:
        out: dict[str, list[str]] = {}
        for registered in _REGISTRY.values():
            for event_type in registered.source_events:
                out.setdefault(event_type, []).append(registered.kind)
        return {k: tuple(v) for k, v in out.items()}

    def __getitem__(self, event_type: str) -> Callable[[OutboxEvent], Awaitable[None]]:
        if event_type == RENDER_REQUESTED:
            return _render_requested
        if event_type == DRAFT_REQUESTED:
            return _draft_requested
        if event_type == TIE_OUT_REQUESTED:
            return _tie_out_requested
        kinds = self._events()[event_type]

        async def handle(event: OutboxEvent) -> None:
            from abacus.modules.reporting import documents as docs

            await docs.mark_out_of_date_from(event, kinds)

        return handle

    def __iter__(self) -> Iterator[str]:
        own = (RENDER_REQUESTED, DRAFT_REQUESTED, TIE_OUT_REQUESTED)
        return iter((*own, *(e for e in self._events() if e not in own)))

    def __len__(self) -> int:
        return len(set(self._events()) | {RENDER_REQUESTED, DRAFT_REQUESTED, TIE_OUT_REQUESTED})


# P-11-T11 (DEC-1561): a version's render job runs on the relay's delivery of its event.
RENDER_REQUESTED = "generated_document.render_requested"
DRAFT_REQUESTED = "statement.draft_requested"
TIE_OUT_REQUESTED = "statement.tie_out_requested"


async def _render_requested(event: OutboxEvent) -> None:
    # Imported here: the job reaches evidence.api, which reporting.api must not import (DEC-1457).
    from abacus.modules.reporting.render_job import on_render_requested

    await on_render_requested(event)


async def _draft_requested(event: OutboxEvent) -> None:
    # Imported here: the jobs reach agents.api and `kernel.dispatch` (A-06-T25).
    from abacus.modules.reporting.statements_jobs import on_draft_requested

    await on_draft_requested(event)


async def _tie_out_requested(event: OutboxEvent) -> None:
    from abacus.modules.reporting.statements_jobs import on_tie_out_requested

    await on_tie_out_requested(event)


SUBSCRIPTIONS: Mapping[str, Callable[[OutboxEvent], Awaitable[None]]] = _SourceSubscriptions()
# The worker composes WORKFLOWS and ACTIVITIES beside SUBSCRIPTIONS for every module that has one.
from abacus.modules.reporting.statements_jobs import (  # noqa: E402 -- A-06-T25
    draft_activity,
    draft_failed_activity,
    tie_out_activity,
)
from abacus.modules.reporting.statements_workflows import (  # noqa: E402
    DRAFT_ACTIVITY as DRAFT_ACTIVITY,
)
from abacus.modules.reporting.statements_workflows import (  # noqa: E402
    DRAFT_FAILED_ACTIVITY as DRAFT_FAILED_ACTIVITY,
)
from abacus.modules.reporting.statements_workflows import (  # noqa: E402
    TIE_OUT_ACTIVITY as TIE_OUT_ACTIVITY,
)
from abacus.modules.reporting.statements_workflows import (  # noqa: E402
    FsDraftWorkflow,
    TieOutWorkflow,
)

# The render job is a relay subscription, not a workflow (DEC-1561).
WORKFLOWS: dict[type, str] = {FsDraftWorkflow: "interactive", TieOutWorkflow: "background"}
ACTIVITIES: tuple[object, ...] = (draft_activity, draft_failed_activity, tie_out_activity)

# N-02-T32 (DEC-1458): the engagement letter renders through C11 by engagements' port, since
# engagements may not import reporting (ADR-008).
register_letter_renderer(render_engagement_letter)
register_letter_finaliser(finalise_engagement_letter)  # N-02-T33: the approval renders final
register_letter_locker(lock_engagement_letter)  # N-02-T33: a completed envelope locks it

# A-06-T15 (DEC-2215): a reviewable on C3's matrix and G5.
from abacus.modules.reporting.review_targets import (  # noqa: E402
    FS_TARGET,
    fs_facts,
    fs_reviewables,
)
from abacus.modules.review.api import (  # noqa: E402
    register_reviewable as _register_reviewable,
)
from abacus.modules.review.api import (  # noqa: E402
    register_reviewable_facts as _register_reviewable_facts,
)

_register_reviewable(FS_TARGET, fs_reviewables)
_register_reviewable_facts(FS_TARGET, fs_facts)


def template_blocks(
    *,
    layout_key: str,
    body: Sequence[object],
    clauses: Sequence[object],
    values: Mapping[str, str],
) -> list[tuple[str, str | None, str]]:
    """N-04-T12 (DEC-2240): a published template's standard text for the given values, as
    (block id, clause id, text) per top-level block: what a consumer drafts from and regenerates
    against. Templates are database content; nothing here holds wording."""
    from abacus.modules.reporting.compose import block_texts, standard

    return block_texts(standard(layout_key=layout_key, body=body, clauses=clauses, values=values))


async def latest_document_version(
    tenant: TenantContext, document_id: UUID
) -> tuple[UUID, str] | None:
    """N-04-T16: a generated document's newest version: its id and content hash (C7's source)."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, content_hash FROM generated_document_versions "
                    "WHERE generated_document_id = :d ORDER BY version_no DESC LIMIT 1"
                ),
                {"d": document_id},
            )
        ).first()
    return None if row is None else (row.id, row.content_hash)


async def document_is_final(tenant: TenantContext, document_id: UUID) -> bool:
    """N-04-T16: a person's final render of this document exists."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT 1 FROM generated_document_versions "
                "WHERE generated_document_id = :d AND mode = 'final' LIMIT 1"
            ),
            {"d": document_id},
        )
    return found is not None


# A-06-T25, T28: the run record's port, the workflows' inputs, and the slice's path.
# A-06-T29 (DEC-2615): the financial statements as a composed C11 kind, registered at import so
# the render job (the worker) knows its layout and record type; send-draft calls the render.
from abacus.modules.reporting.fs_render import ensure_kind as _ensure_fs_kind  # noqa: E402
from abacus.modules.reporting.fs_render import (  # noqa: E402
    render_statement_draft as render_statement_draft,
)

# A-06-T16 seam (TASK-3395): the agent's suggested checklist answers; assurance wires them, since
# reporting may not import agents (BOUND-002).
from abacus.modules.reporting.statements import (  # noqa: E402
    SUGGESTION_TARGET as CHECKLIST_SUGGESTION_TARGET,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for assurance's seam (A-06-T16)
)
from abacus.modules.reporting.statements import (  # noqa: E402
    RunRecordPort as RunRecordPort,
)
from abacus.modules.reporting.statements import (  # noqa: E402
    answer_item as answer_statements_item,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the scenario loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    apply_suggested_answer as apply_suggested_answer,
)
from abacus.modules.reporting.statements import (  # noqa: E402
    checklist_options as statements_checklist_options,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the scenario loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    document_engagement as statement_document_engagement,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for assurance's seam (A-06-T16)
)
from abacus.modules.reporting.statements import (  # noqa: E402
    draft as draft_statements,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    pick_checklist as pick_statements_checklist,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the scenario loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    record_management_approval as record_management_approval,
)
from abacus.modules.reporting.statements import (  # noqa: E402
    record_suggested_answer as record_suggested_answer,
)
from abacus.modules.reporting.statements import (  # noqa: E402
    register_run_record as register_run_record,
)
from abacus.modules.reporting.statements import (  # noqa: E402
    review_items as review_statements_items,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the scenario loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    run_tie_out as run_statement_tie_out,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- for the loader
)
from abacus.modules.reporting.statements import (  # noqa: E402
    suggested_answer as suggested_answer,
)
from abacus.modules.reporting.statements_workflow_types import (  # noqa: E402
    FsDraftInput as FsDraftInput,
)
from abacus.modules.reporting.statements_workflow_types import (  # noqa: E402
    TieOutInput as TieOutInput,
)

_ensure_fs_kind()
