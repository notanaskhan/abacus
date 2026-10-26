"""C16 v1.1: portal settings and the read-only preview, stubbed (R-01-T16; SPEC-345; R-01 §4.3,
Story 8.1, 8.2). Contract: `docs/contracts/portal-settings.md`.

For ADM-10 (R-01-T28) and the settings' readers (P-08's branding service, R-01-T24's follow-up
policy, R-02 and A-07 for the published client experience). The portal module owns no business
truth: publish (R-01-T26) applies the brand through P-08's `set_branding` / `set_logo`, the
client-experience row and the follow-up policy (communications) in one unit of work.

- `GET /v1/firm/portal-settings` (`portal_settings.read`) and `GET …/preview`
  (`portal.preview`) are never flag-gated: 501 until R-01-T26.
- Draft save and discard, publish and logo (`portal_settings.manage`, fresh MFA) are behind
  `portal.settings_editor`: 404 off, 501 on.

The preview is P-08's POR-02 projection built in preview mode: read-only, no session, no
impersonation. `portal.preview` grants no client content (DEC-379, `communications.api.
viewer_scoped`): the contact must be visible to the viewer (404 otherwise, DEC-20), every
projected item is kept only if the viewer could read it themselves (`engagement.read` and the
item's read action under `visible()`), dropped items leave no count, and with nothing left the
preview is the sample client from the firm's published settings. The stub checks the flag first;
the implementing task authorises first.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import PORTAL_SETTINGS_EDITOR
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.communications.api import FollowUpPolicyFields, NextSendOut
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.portal.contract import PortalHomeOut

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
SettingsAllowedAction = Literal["edit", "publish", "preview"]
PreviewDevice = Literal["desktop", "phone"]


class PortalSettingsPersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("internal")]


class PortalBrandFields(BaseModel):
    """Brand slots, not theming: the accent is fixed (ADR-155) and the host is read-only until
    custom portal domains ship (DEC-59)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    portal_name: Annotated[str, Field(min_length=1, max_length=80), classified("public")]
    sender_display_name: Annotated[str, Field(min_length=1, max_length=80), classified("public")]
    secured_footer: Annotated[bool, classified("public")] = False  # "Secured by …", off (DEC-59)


class PortalBrandOut(PortalBrandFields):
    accent: Annotated[Literal["espresso"], classified("public")] = "espresso"
    portal_host: Annotated[str, classified("public")]  # brightwaterhale.<neutral-portal-domain>
    logo_url: Annotated[str | None, classified("public")] = None


class ClientExperienceFields(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Off until N-01's route is live (R-01-T33).
    allow_upload_something_else: Annotated[bool, classified("internal")] = False
    phone_capture: Annotated[bool, classified("internal")] = True
    show_team_card: Annotated[bool, classified("internal")] = True
    show_progress_per_item: Annotated[bool, classified("internal")] = True
    # The service checks this is an active member of the firm (else 422); never a client contact.
    support_contact_user_id: Annotated[UUID | None, classified("internal")] = None


class PortalSettingsVersionOut(BaseModel):
    """A published version: insert-only (`portal_settings_versions`)."""

    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    brand: Annotated[PortalBrandOut, classified("public")]
    client_experience: Annotated[ClientExperienceFields, classified("internal")]
    follow_up_policy: Annotated[FollowUpPolicyFields, classified("internal")]
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    published_at: Annotated[datetime, classified("internal")]
    published_by: Annotated[PortalSettingsPersonOut, classified("internal")]


class PortalSettingsDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: Annotated[int, Field(ge=0), classified("internal")]
    base_version: Annotated[int | None, classified("internal")]
    brand: Annotated[PortalBrandFields, classified("public")]
    client_experience: Annotated[ClientExperienceFields, classified("internal")]
    follow_up_policy: Annotated[FollowUpPolicyFields, classified("internal")]
    has_new_logo: Annotated[bool, classified("internal")] = False
    saved_at: Annotated[datetime, classified("internal")]
    saved_by: Annotated[PortalSettingsPersonOut, classified("internal")]


class PortalSettingsOut(BaseModel):
    """ADM-10 a: published values, the draft, and the next reminder for the preview contact."""

    model_config = ConfigDict(frozen=True)

    published: Annotated[PortalSettingsVersionOut | None, classified("internal")] = None
    draft: Annotated[PortalSettingsDraftOut | None, classified("internal")] = None
    next_reminder: Annotated[NextSendOut | None, classified("internal")] = None
    allowed_actions: Annotated[list[SettingsAllowedAction], classified("internal")] = []


class PortalSettingsDraftIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    brand: Annotated[PortalBrandFields, classified("public")]
    client_experience: Annotated[ClientExperienceFields, classified("internal")]
    follow_up_policy: Annotated[FollowUpPolicyFields, classified("internal")]
    expected_version: Annotated[int, Field(ge=0), classified("internal")]


class PortalLogoOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    logo_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    expected_version: Annotated[int, Field(ge=0), classified("internal")]


class PortalPreviewOut(BaseModel):
    """POR-02 as one client would see it, read-only. No session, no mutation route, no
    `allowed_actions`: `read_only` is always true."""

    model_config = ConfigDict(frozen=True)

    read_only: Annotated[Literal[True], classified("internal")] = True
    device: Annotated[PreviewDevice, classified("internal")]
    contact_id: Annotated[UUID | None, classified("internal")]  # None: the sample client
    sample: Annotated[bool, classified("internal")]
    source: Annotated[Literal["draft", "published"], classified("internal")]
    brand: Annotated[PortalBrandOut, classified("public")]
    home: Annotated[PortalHomeOut, classified("confidential")]


async def _stub(ctx: AuthContext, flag: Flag | None = None) -> NoReturn:
    if flag is not None and not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


settings_router = AbacusRouter(prefix="/v1/firm/portal-settings", tags=["portal settings"])


@settings_router.get(
    "", action="portal_settings.read", response_model=PortalSettingsOut, errors=(501,)
)
async def get_portal_settings_route(ctx: Ctx) -> PortalSettingsOut:
    """ADM-10 a (R-01-T26)."""
    await _stub(ctx)


@settings_router.put(
    "/draft",
    action="portal_settings.manage",
    response_model=PortalSettingsDraftOut,
    errors=(409, 501),
)
async def save_portal_settings_draft_route(
    body: PortalSettingsDraftIn, ctx: Ctx
) -> PortalSettingsDraftOut:
    """ADM-10 b (R-01-T26): 409 `stale_version` on an old `expected_version`. Audited
    `portal_settings.draft_saved`."""
    await _stub(ctx, PORTAL_SETTINGS_EDITOR)


@settings_router.delete(
    "/draft",
    action="portal_settings.manage",
    response_model=PortalSettingsOut,
    errors=(501,),
)
async def discard_portal_settings_draft_route(ctx: Ctx) -> PortalSettingsOut:
    """Discard the draft (R-01-T26)."""
    await _stub(ctx, PORTAL_SETTINGS_EDITOR)


@settings_router.post(
    "/publish",
    action="portal_settings.manage",
    response_model=PortalSettingsVersionOut,
    status_code=201,
    errors=(409, 501),
)
async def publish_portal_settings_route(
    ctx: Ctx, idempotency_key: IdempotencyKey
) -> PortalSettingsVersionOut:
    """ADM-10 f (R-01-T26): one unit of work, an insert-only version; "Portal settings published
    · clients see changes on next visit". Audited `portal_settings.published`; outbox
    `portal_settings.published {version}`."""
    await _stub(ctx, PORTAL_SETTINGS_EDITOR)


@settings_router.post(
    "/logo",
    action="portal_settings.manage",
    response_model=PortalLogoOut,
    errors=(413, 415, 501),
)
async def upload_portal_logo_route(
    request: Request,
    ctx: Ctx,
    content_type: Annotated[str, Header(alias="Content-Type", max_length=100)],
) -> PortalLogoOut:
    """The draft's logo as the raw body, re-encoded server side by P-08's `set_logo`
    (R-01-T26); 413 too large, 415 a type P-08 does not accept."""
    await _stub(ctx, PORTAL_SETTINGS_EDITOR)


@settings_router.get(
    "/preview", action="portal.preview", response_model=PortalPreviewOut, errors=(501,)
)
async def preview_portal_route(
    ctx: Ctx,
    as_contact: Annotated[UUID | None, Query(alias="as")] = None,
    device: PreviewDevice = "desktop",
    source: Literal["draft", "published"] = "draft",
) -> PortalPreviewOut:
    """ADM-10 a, c, g (R-01-T26): 404 for a contact outside `visible()`; only items the viewer
    may read themselves, else the sample client (DEC-379); audited `portal.preview_viewed` with
    the contact id or `sample`."""
    await _stub(ctx)
