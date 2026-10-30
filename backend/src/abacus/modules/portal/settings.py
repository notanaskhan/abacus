"""ADM-10's portal settings and the read-only preview, live (R-01-T26; `portal-settings.md`;
SPEC-345; DEC-653).

- **One draft per firm** (`portal_settings_drafts`): the brand slots, client-experience toggles
  and follow-up policy, saved at `expected_version` (an older one is 409 `stale_version`); a new
  logo waits in it, checked now by P-08's re-encoder (422 `logo_unreadable`) and applied on
  publish. The support contact must be an active staff member of the firm (422).
- **Publish** (fresh MFA by the matrix; `Idempotency-Key` at the route): one unit of work applies
  the brand through P-08's `set_branding` (and `set_logo` for a new logo), writes the follow-up
  policy through communications, inserts the next `portal_settings_versions` row with its content
  hash, and clears the draft. Audited `portal_settings.published`; outbox
  `portal_settings.published {version}`.
- **Preview** (`portal.preview`): POR-02 as a contact would see it, read-only, only when the
  viewer may read every engagement the contact's home covers (`engagement.read`; walls and
  independence through `authorise`); a contact outside `visible()` (a walled client) is 404, and
  a contact whose home the viewer cannot wholly read, or no contact, previews the sample client
  (DEC-379: nothing is shown that the viewer could not read, and nothing says what was left out).
  Audited `portal.preview_viewed` with the contact id or `sample`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel._flags import PORTAL_INTAKE_UPLOAD
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.communications.api import (
    FollowUpPolicy,
    write_follow_up_policy,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    hidden_clients,
    member_context,
    names_of,
)
from abacus.modules.organisations.api import contact_facts
from abacus.modules.portal import home as portal_home
from abacus.modules.portal.branding import BrandingSlots, reencode_logo, set_branding, set_logo
from abacus.modules.portal.contract import PortalHomeOut, PortalHomeScopeOut
from abacus.modules.portal.events import PortalSettingsPublished

READ: Final = "portal_settings.read"
MANAGE: Final = "portal_settings.manage"
PREVIEW: Final = "portal.preview"
SUBJECT: Final = "portal_settings"
Json = dict[str, object]


class SettingsStale(DomainConflict):
    """Someone saved or published since you read: reload."""

    code = "stale_version"


class SupportContactInvalid(DomainInvalid):
    """The support contact must be an active staff member of the firm."""

    code = "support_contact_invalid"


class NothingToPublish(DomainConflict):
    """There is no draft to publish."""

    code = "no_draft"


@dataclass(frozen=True)
class Draft:
    expected_version: int
    base_version: int | None
    brand: Json
    client_experience: Json
    follow_up_policy: Json
    has_new_logo: bool
    saved_at: datetime
    saved_by: UUID


@dataclass(frozen=True)
class Version:
    version: int
    brand: Json
    client_experience: Json
    follow_up_policy: Json
    content_sha256: str
    published_at: datetime
    published_by: UUID


@dataclass(frozen=True)
class Settings:
    published: Version | None
    draft: Draft | None
    names: dict[UUID, str] = field(default_factory=dict[UUID, str])


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def content_hash(brand: Json, experience: Json, policy: Json, logo: str | None) -> str:
    body = json.dumps(
        {
            "brand": brand,
            "client_experience": experience,
            "follow_up_policy": policy,
            "logo": logo,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(body).hexdigest()


def _draft(r: RowMapping) -> Draft:
    return Draft(
        cast(int, r["expected_version"]),
        cast(int | None, r["base_version"]),
        cast(Json, r["brand"]),
        cast(Json, r["client_experience"]),
        cast(Json, r["follow_up_policy"]),
        r["has_logo"] is True,
        cast(datetime, r["saved_at"]),
        cast(UUID, r["saved_by"]),
    )


def _version(r: RowMapping) -> Version:
    return Version(
        cast(int, r["version"]),
        cast(Json, r["brand"]),
        cast(Json, r["client_experience"]),
        cast(Json, r["follow_up_policy"]),
        cast(str, r["content_sha256"]),
        cast(datetime, r["published_at"]),
        cast(UUID, r["published_by"]),
    )


_DRAFT = text(
    "SELECT expected_version, base_version, brand, client_experience, follow_up_policy, "
    "logo IS NOT NULL AS has_logo, saved_at, saved_by FROM portal_settings_drafts"
)
_UPDATE = text(
    "UPDATE portal_settings_drafts SET expected_version = expected_version + 1, "
    "brand = CAST(:brand AS jsonb), client_experience = CAST(:experience AS jsonb), "
    "follow_up_policy = CAST(:policy AS jsonb), saved_at = clock_timestamp(), saved_by = :by"
)
_UPDATE_WITH_LOGO = text(
    "UPDATE portal_settings_drafts SET expected_version = expected_version + 1, "
    "brand = CAST(:brand AS jsonb), client_experience = CAST(:experience AS jsonb), "
    "follow_up_policy = CAST(:policy AS jsonb), saved_at = clock_timestamp(), saved_by = :by, "
    "logo = :logo"
)
_LATEST = text(
    "SELECT version, brand, client_experience, follow_up_policy, content_sha256, published_at, "
    "published_by FROM portal_settings_versions ORDER BY version DESC LIMIT 1"
)


async def upload_something_else(tenant: TenantContext) -> bool:
    """R-01-T33: the published client experience's "Upload something else" (off until a person
    publishes it on), for the portal's binder read and the intake route's refusal."""
    async with tenant_session(tenant) as session:
        found = (await session.execute(_LATEST)).mappings().one_or_none()
    if found is None:
        return False
    experience = cast(dict[str, object], found["client_experience"] or {})
    return experience.get("allow_upload_something_else") is True


async def upload_something_else_offered(tenant: TenantContext) -> bool:
    """POR-03 offers the button only when the toggle is published on and N-01's portal intake
    is live (`portal.intake_upload`)."""
    return await flag_enabled(tenant, PORTAL_INTAKE_UPLOAD) and await upload_something_else(tenant)


async def read_settings(ctx: AuthContext) -> Settings:
    _human(ctx, READ)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        draft = (await session.execute(_DRAFT)).mappings().one_or_none()
        latest = (await session.execute(_LATEST)).mappings().one_or_none()
    found = Settings(_version(latest) if latest else None, _draft(draft) if draft else None)
    people = [
        p
        for p in (
            found.draft and found.draft.saved_by,
            found.published and found.published.published_by,
        )
        if p
    ]
    return Settings(found.published, found.draft, await names_of(people) if people else {})


async def _support_contact(ctx: AuthContext, experience: Json) -> None:
    person = experience.get("support_contact_user_id")
    if person is None:
        return
    member = await member_context(ctx.tenant_id, UUID(str(person)))
    if member is None or member.client:
        raise SupportContactInvalid(facts={"field": "support_contact_user_id"})


async def save_draft(
    ctx: AuthContext, brand: Json, experience: Json, policy: Json, expected_version: int
) -> Draft:
    """ADM-10 b. The first save is at 0; each later one at the draft's `expected_version`."""
    _human(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    await _support_contact(ctx, experience)
    async with uow(ctx.tenant) as tx:
        await _upsert(tx, ctx, brand, experience, policy, expected_version)
        row = (await tx.session.execute(_DRAFT)).mappings().one()
        tx.record(
            "portal_settings.draft_saved",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(version=cast(int, row["expected_version"])),
        )
    return _draft(row)


async def _upsert(
    tx: UnitOfWork,
    ctx: AuthContext,
    brand: Json,
    experience: Json,
    policy: Json,
    expected_version: int,
    logo: bytes | None = None,
) -> None:
    held = await tx.session.scalar(
        text("SELECT expected_version FROM portal_settings_drafts FOR UPDATE")
    )
    values: Json = {
        "brand": json.dumps(brand),
        "experience": json.dumps(experience),
        "policy": json.dumps(policy),
        "by": ctx.user_id,
    }
    if held is None:
        if expected_version != 0:
            raise SettingsStale(facts={"version": 0})
        base = await tx.session.scalar(text("SELECT max(version) FROM portal_settings_versions"))
        await tx.session.execute(
            text(
                "INSERT INTO portal_settings_drafts (tenant_id, expected_version, base_version, "
                "brand, client_experience, follow_up_policy, logo, saved_by) VALUES (:tenant, 1, "
                ":base, CAST(:brand AS jsonb), CAST(:experience AS jsonb), "
                "CAST(:policy AS jsonb), :logo, :by)"
            ),
            {**values, "tenant": ctx.tenant_id, "base": base, "logo": logo},
        )
        return
    if int(held) != expected_version:
        raise SettingsStale(facts={"version": int(held)})
    await tx.session.execute(
        _UPDATE_WITH_LOGO if logo is not None else _UPDATE, {**values, "logo": logo}
    )


async def discard_draft(ctx: AuthContext) -> None:
    _human(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        gone = await tx.session.scalar(
            text("DELETE FROM portal_settings_drafts RETURNING expected_version")
        )
        if gone is not None:
            tx.record("portal_settings.draft_discarded", target=Target(SUBJECT, ctx.tenant_id))


async def upload_logo(ctx: AuthContext, content: bytes) -> tuple[str, int]:
    """The draft's new logo, checked by P-08's re-encoder now (applied on publish); a firm with no
    draft gets one from its published settings."""
    _human(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _png, sha = await reencode_logo(content)
    current = await read_settings(ctx)
    async with uow(ctx.tenant) as tx:
        if current.draft is not None:
            d = current.draft
            await _upsert(
                tx,
                ctx,
                d.brand,
                d.client_experience,
                d.follow_up_policy,
                d.expected_version,
                content,
            )
        else:
            p = current.published
            await _upsert(
                tx,
                ctx,
                p.brand if p else {},
                p.client_experience if p else {},
                p.follow_up_policy if p else {},
                0,
                content,
            )
        version = int(
            await tx.session.scalar(text("SELECT expected_version FROM portal_settings_drafts"))
            or 0
        )
        tx.record(
            "portal_settings.draft_saved",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(version=version, logo=1),
        )
    return sha.hex(), version


def _policy(fields: Json) -> FollowUpPolicy:
    hh, mm = str(fields.get("send_local_time", "09:00")).split(":")
    return FollowUpPolicy(
        cadence_days=int(cast(int, fields.get("cadence_days", 7))),
        max_reminders=int(cast(int, fields.get("max_reminders", 4))),
        send_local_time=time(int(hh), int(mm)),
        weekdays_only=bool(fields.get("weekdays_only", True)),
        stop_on_binder_done=bool(fields.get("stop_on_binder_done", True)),
        notify_preparer_after_max=bool(fields.get("notify_preparer_after_max", True)),
        cc_assigned_preparer=bool(fields.get("cc_assigned_preparer", False)),
        mode=cast(
            Literal["draft_for_person", "send_on_schedule"], fields.get("mode", "draft_for_person")
        ),
    )


async def publish(ctx: AuthContext) -> Version:
    """ADM-10 f: the draft applied in one unit of work; the next insert-only version."""
    _human(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT brand, client_experience, follow_up_policy, logo "
                        "FROM portal_settings_drafts FOR UPDATE"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NothingToPublish(facts={"tenant": "draft"})
        brand = cast(Json, row["brand"])
        experience = cast(Json, row["client_experience"])
        policy = cast(Json, row["follow_up_policy"])
        logo = cast(bytes | None, row["logo"])
        support = experience.get("support_contact_user_id")
        support_name = (
            (await names_of([UUID(str(support))])).get(UUID(str(support))) if support else None
        )
        current = (
            (
                await tx.session.execute(
                    text(
                        "SELECT address_line, help_url, privacy_url, maintenance_banner "
                        "FROM portal_branding"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        await set_branding(
            tx,
            ctx.tenant_id,
            BrandingSlots(
                display_name=str(brand.get("sender_display_name", "")),
                portal_name=cast(str | None, brand.get("portal_name")),
                address_line=cast(str | None, current["address_line"]) if current else None,
                help_url=cast(str | None, current["help_url"]) if current else None,
                privacy_url=cast(str | None, current["privacy_url"]) if current else None,
                support_contact_name=support_name,
                secured_footer=bool(brand.get("secured_footer", False)),
                maintenance_banner=(
                    cast(str | None, current["maintenance_banner"]) if current else None
                ),
            ),
            ctx.user_id,
        )
        logo_sha = None
        if logo is not None:
            await set_logo(tx, ctx.tenant_id, logo, ctx.user_id)
            _png, digest = await reencode_logo(logo)
            logo_sha = digest.hex()
        await write_follow_up_policy(tx, ctx, _policy(policy), None)
        number = int(
            await tx.session.scalar(
                text("SELECT coalesce(max(version), 0) + 1 FROM portal_settings_versions")
            )
            or 1
        )
        digest_all = content_hash(brand, experience, policy, logo_sha)
        published = (
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO portal_settings_versions (tenant_id, version, brand, "
                        "client_experience, follow_up_policy, content_sha256, logo_sha256, "
                        "published_by) VALUES (:tenant, :version, CAST(:brand AS jsonb), "
                        "CAST(:experience AS jsonb), CAST(:policy AS jsonb), :sha, :logo, :by) "
                        "RETURNING version, brand, client_experience, follow_up_policy, "
                        "content_sha256, published_at, published_by"
                    ),
                    {
                        "tenant": ctx.tenant_id,
                        "version": number,
                        "brand": json.dumps(brand),
                        "experience": json.dumps(experience),
                        "policy": json.dumps(policy),
                        "sha": digest_all,
                        "logo": logo_sha,
                        "by": ctx.user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        await tx.session.execute(text("DELETE FROM portal_settings_drafts"))
        tx.record(
            "portal_settings.published",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(version=number, content_sha256=digest_all),
        )
        tx.emit(PortalSettingsPublished(version=number))
    return _version(published)


LOGO_LIMIT: Final = 2 * 1024 * 1024  # the draft column's bound; P-08's re-encoder bounds it again


class LogoTooLarge(DomainInvalid):
    """A logo larger than 2 MB."""

    code = "logo_unreadable"


async def authorised_writer(ctx: AuthContext) -> None:
    """The routes' first step for a write: a person, `portal_settings.manage` at the firm."""
    _human(ctx, MANAGE)
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))


async def people(user_ids: list[UUID]) -> dict[UUID, str]:
    return await names_of(user_ids) if user_ids else {}


async def portal_host(ctx: AuthContext) -> str:
    """The firm's neutral portal host: read-only here, and empty until P-08 exposes a reader of
    `portal_domains` to the app (the table is the definer functions' alone; DEC-653)."""
    return ""


def sample_home() -> PortalHomeOut:
    """The sample client (DEC-379): POR-02's shape with no firm's data in it."""
    return PortalHomeOut(
        scope=PortalHomeScopeOut(
            kind="client", id=UUID(int=0), label="Sample client", role_label="Owner"
        ),
        first_visit=False,
        welcome_dismissed=True,
        all_done=True,
    )


# --- preview -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Preview:
    contact_id: UUID | None
    sample: bool
    home: portal_home.HomeView | None  # None: the sample client


async def _contact(ctx: AuthContext, contact_id: UUID) -> tuple[UUID, UUID | None]:
    async with tenant_session(ctx.tenant) as session:
        facts = (await contact_facts(session, [contact_id])).get(contact_id)
    if facts is None:
        raise NotFound("contact")
    if await hidden_clients(ctx.tenant, ctx.user_id, [facts.client_id]):
        raise NotFound("contact")  # a walled client reads as unknown (DEC-43)
    return facts.client_id, facts.user_id


async def preview(ctx: AuthContext, contact_id: UUID | None) -> Preview:
    _human(ctx, PREVIEW)
    await authorise(ctx, PREVIEW, Resource.firm(ctx.tenant_id))
    shown: Preview = Preview(None, True, None)
    if contact_id is not None:
        _client, user = await _contact(ctx, contact_id)
        person = await member_context(ctx.tenant_id, user) if user is not None else None
        if person is not None and person.client:
            try:
                grant = await portal_home._grant(person, None)  # pyright: ignore[reportPrivateUsage] -- the contact's own scope, read as the portal reads it
                scope = await portal_home._covered(person, grant)  # pyright: ignore[reportPrivateUsage] -- likewise
            except (NotFound, Forbidden):
                scope = None
            if scope is not None and await _viewer_reads_all(ctx, scope.engagements):
                shown = Preview(contact_id, False, await portal_home.read_home(person, None))
    async with uow(ctx.tenant) as tx:
        tx.record(
            "portal.preview_viewed",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(contact=shown.contact_id) if shown.contact_id else Ref(sample=1),
        )
    return shown


async def _viewer_reads_all(ctx: AuthContext, engagements: tuple[UUID, ...]) -> bool:
    """DEC-379: the preview never shows what the viewer could not read themselves."""
    for engagement_id in engagements:
        resource = (await get_ref(ctx, engagement_id)).resource()
        if "engagement.read" not in await allowed_actions(ctx, resource, ["engagement.read"]):
            return False
    return bool(engagements)


__all__ = [
    "Draft",
    "Preview",
    "Settings",
    "Version",
    "content_hash",
    "discard_draft",
    "preview",
    "publish",
    "read_settings",
    "save_draft",
    "upload_logo",
]
