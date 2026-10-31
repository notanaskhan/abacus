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

from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Literal, cast, get_args
from uuid import UUID

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
from abacus.modules.reporting.engagement_letters import (
    finalise_engagement_letter,
    lock_engagement_letter,
    render_engagement_letter,
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
ROUTERS = (templates_router, documents_router)

KINDS: frozenset[str] = frozenset(get_args(GeneratedDocumentKind))
LAYOUTS: frozenset[str] = frozenset(get_args(LayoutKey))


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


@dataclass(frozen=True)
class DocumentKind:
    kind: GeneratedDocumentKind
    layout: LayoutKey
    variables_provider: VariablesProvider
    approval_provider: ApprovalProvider
    source_events: tuple[str, ...] = ()
    retention_record_type: str = ""
    formats: tuple[RenderFormat, ...] = field(default=("pdf",))


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
    if request.template_version_id is None and request.kind != "run_trace_export":
        raise RenderRefused("unknown_layout", "no template version")
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
    resolved = await kind.variables_provider(request.owner_ref, request.scope)
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
        kinds = self._events()[event_type]

        async def handle(event: OutboxEvent) -> None:
            from abacus.modules.reporting import documents as docs

            await docs.mark_out_of_date_from(event, kinds)

        return handle

    def __iter__(self) -> Iterator[str]:
        return iter((RENDER_REQUESTED, *(e for e in self._events() if e != RENDER_REQUESTED)))

    def __len__(self) -> int:
        return len(set(self._events()) | {RENDER_REQUESTED})


# P-11-T11 (DEC-1561): a version's render job runs on the relay's delivery of its event.
RENDER_REQUESTED = "generated_document.render_requested"


async def _render_requested(event: OutboxEvent) -> None:
    # Imported here: the job reaches evidence.api, which reporting.api must not import (DEC-1457).
    from abacus.modules.reporting.render_job import on_render_requested

    await on_render_requested(event)


SUBSCRIPTIONS: Mapping[str, Callable[[OutboxEvent], Awaitable[None]]] = _SourceSubscriptions()
# The worker composes WORKFLOWS and ACTIVITIES beside SUBSCRIPTIONS for every module that has one.
# The render job is a relay subscription, not a workflow (DEC-1561).
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# N-02-T32 (DEC-1458): the engagement letter renders through C11 by engagements' port, since
# engagements may not import reporting (ADR-008).
register_letter_renderer(render_engagement_letter)
register_letter_finaliser(finalise_engagement_letter)  # N-02-T33: the approval renders final
register_letter_locker(lock_engagement_letter)  # N-02-T33: a completed envelope locks it
