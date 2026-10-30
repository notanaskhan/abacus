"""Public interface of the reporting module; other modules import only this (ADR-008).

C11 v1 (P-11-T03; `docs/contracts/c11-renderer.md`; ADR-320): the routers, and the in-process
renderer API consumers call inside their unit of work. A consumer registers a document kind
(layout, variables provider, approval provider, source events, retention record type), asks for
drafts with `render`, and asks for a final render only with a human approval (`render_final`).
Values are resolved by the kind's provider from the database: a consumer never passes values
from the browser. The shapes are frozen with C11 (S18 Contract Monday); `render`, `render_final`,
`lock` and `generated_document` raise `NotImplementedError` until P-11-T08.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, NoReturn, get_args
from uuid import UUID

from abacus.modules.reporting.consent import Recipients, RecipientsUnavailable
from abacus.modules.reporting.consent import recipients as consent_recipients
from abacus.modules.reporting.contract import CONSENT_RECIPIENTS_KEY
from abacus.modules.reporting.contract import (
    GeneratedDocumentKind,
    LayoutKey,
    RenderFormat,
    RequesterKind,
    documents_router,
    templates_router,
)

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.reporting.render.core import (  # noqa: E402 -- T-01-T10's consumer API
    RenderInput,
    RenderOutput,
    render_isolated,
)
from abacus.modules.reporting.render.head import RenderRefused as RenderingRefused  # noqa: E402

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


def _unbuilt() -> NoReturn:
    raise NotImplementedError("C11: P-11-T08 builds the RenderWorkflow and the service")


async def render(request: RenderRequest) -> RenderTicket:
    """Start a draft render (the caller's unit of work); answers the ticket at Drafting."""
    check_render_request(request)
    _unbuilt()


async def render_final(
    document_id: UUID, approval_ref: ApprovalRef, requester: Requester
) -> RenderTicket:
    """A final render of the approved draft: only a person's, with a matching approval."""
    if requester.kind != "human" or requester.user_id is None:
        raise RenderRefused("final_requires_approval", "a final render is a person's")
    _unbuilt()


async def lock(document_id: UUID, cause_ref: str) -> None:
    """The consumer's lock (envelope completed, report released): no render after it (AC-19)."""
    _unbuilt()
