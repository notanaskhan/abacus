"""The Support panel contract stubs, firm side (G-04-T03; SPEC-680 AC-44 to AC-56; DEC-5203).
Contract: `docs/contracts/support.md`. Screen: SHL-05 (the O2 Support drawer).

Every route has one matrix action and answers, in order: a client principal 404 (the portal never
mounts SHL-05, INV-4); the action on the firm; 404 while `support.panel_v2` is off for the firm;
then 501 naming the task that implements it (G-04-T10). A firm user reads and writes only their
own conversation (OWN, in the service). Message bodies are `confidential`: never logged, audited
or put in a notification (DEC-60, DEC-61), and no model reads or writes them (AC-49). Support-
session v2 fields on the firm's own routes are SPEC-681 (G-04-T05), not stubs here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import SUPPORT_PANEL_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
ComponentState = Literal["operational", "needs_attention", "outage", "maintenance"]
BlockKind = Literal["heading", "paragraph", "list", "note", "screen_link"]


# --- conversation (AC-44 to AC-48) ---------------------------------------------------------------


class AvailabilityOut(BaseModel):
    """Computed from support hours content (AC-45): online with the 7-day median first response
    when at least 5 samples exist, else offline with the next opening."""

    model_config = ConfigDict(frozen=True)

    online: Annotated[bool, Internal]
    replies_in_minutes: Annotated[int | None, Field(ge=0), Internal]
    next_open_at: Annotated[datetime | None, Internal]
    reply_email: Annotated[str | None, Confidential]  # the owner's address, offline notice only


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    author_kind: Annotated[Literal["firm_user", "staff"], Internal]
    author_display_name: Annotated[str, Internal]  # "Ines at Accrued Support"
    body: Annotated[str, Confidential]  # plain text, rendered without HTML or auto-links
    related_article_slug: Annotated[str | None, Internal]
    created_at: Annotated[datetime, Internal]


class SessionCardOut(BaseModel):
    """A support-session request linked to this conversation (SHL-05 a, c; SPEC-681 AC-18)."""

    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID, Internal]
    scope_label: Annotated[str, Confidential]  # resolved in the firm's context, never to staff
    duration_minutes: Annotated[int, Field(ge=1, le=120), Internal]
    status: Annotated[
        Literal["requested", "active", "declined", "revoked", "ended", "expired"], Internal
    ]
    decided_by_display_name: Annotated[str | None, Internal]
    expires_at: Annotated[datetime | None, Internal]
    can_decide: Annotated[bool, Internal]  # firm_admin or security_admin


class ConversationOut(BaseModel):
    """GET /v1/support/conversation: the caller's one thread (OWN)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID | None, Internal]  # None until the first message
    availability: AvailabilityOut
    messages: Annotated[list[SupportMessageOut], Internal]
    session_cards: Annotated[list[SessionCardOut], Internal]
    suggestions: Annotated[list[str], Internal]  # the empty thread's two cards (SHL-05 f)


class SupportMessageIn(BaseModel):
    """POST /v1/support/conversation/messages (AC-46): 1 to 4,000 characters, 30 per 10 minutes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


# --- help articles (AC-50 to AC-52) --------------------------------------------------------------


class HelpBlockOut(BaseModel):
    """One structured block (schema v1); never HTML from content."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[BlockKind, Internal]
    text: Annotated[str | None, Internal] = None
    items: Annotated[list[str], Internal] = []
    screen_id: Annotated[str | None, Internal] = None


class HelpArticleSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: Annotated[str, Internal]
    title: Annotated[str, Internal]
    summary: Annotated[str, Internal]
    group_key: Annotated[str, Internal]
    read_minutes: Annotated[int, Field(ge=1), Internal]


class HelpGroupOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]  # `suggested` first when a context is given
    label: Annotated[str, Internal]
    articles: Annotated[list[HelpArticleSummaryOut], Internal]


class HelpArticlesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    groups: Annotated[list[HelpGroupOut], Internal]
    query: Annotated[str | None, Internal]


class HelpArticleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: Annotated[str, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    title: Annotated[str, Internal]
    read_minutes: Annotated[int, Field(ge=1), Internal]
    blocks: Annotated[list[HelpBlockOut], Internal]
    published_at: Annotated[datetime, Internal]


# --- status (AC-53 to AC-56) ---------------------------------------------------------------------


class StatusComponentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    kind: Annotated[Literal["core", "integration"], Internal]
    state: Annotated[ComponentState, Internal]
    note: Annotated[str | None, Field(max_length=280), Internal]  # the incident's public note


class FirmStatusOut(BaseModel):
    """GET /v1/status: core components plus this firm's installed integrations, the worst of open
    global incidents and the firm's own W-01 health, and the firm's data region."""

    model_config = ConfigDict(frozen=True)

    components: Annotated[list[StatusComponentOut], Internal]
    region_label: Annotated[str, Internal]  # "US"
    history_url: Annotated[str, Internal]


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1", tags=["support"])
_TASK = "G-04-T10"


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("support")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SUPPORT_PANEL_V2):
        raise NotFound(SUPPORT_PANEL_V2.name)


@router.get(
    "/support/conversation", action="support.chat", response_model=ConversationOut, errors=(501,)
)
async def support_conversation(ctx: Ctx) -> ConversationOut:
    await _gate(ctx, "support.chat")
    raise NotImplementedYet(_TASK)


@router.post(
    "/support/conversation/messages",
    action="support.chat",
    response_model=SupportMessageOut,
    status_code=201,
    errors=(429, 501),
)
async def support_send_message(
    body: SupportMessageIn, ctx: Ctx, _key: IdempotencyKey
) -> SupportMessageOut:
    await _gate(ctx, "support.chat")
    raise NotImplementedYet(_TASK)


@router.get("/help/articles", action="help.read", response_model=HelpArticlesOut, errors=(501,))
async def help_articles(
    ctx: Ctx,
    context: Annotated[str | None, Query(pattern=r"^[A-Z]{2,4}-[0-9]{2}$")] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> HelpArticlesOut:
    await _gate(ctx, "help.read")
    raise NotImplementedYet(_TASK)


@router.get(
    "/help/articles/{slug}", action="help.read", response_model=HelpArticleOut, errors=(501,)
)
async def help_article(slug: str, ctx: Ctx) -> HelpArticleOut:
    await _gate(ctx, "help.read")
    raise NotImplementedYet(_TASK)


@router.get("/status", action="status.read", response_model=FirmStatusOut, errors=(501,))
async def firm_status(ctx: Ctx) -> FirmStatusOut:
    await _gate(ctx, "status.read")
    raise NotImplementedYet(_TASK)
