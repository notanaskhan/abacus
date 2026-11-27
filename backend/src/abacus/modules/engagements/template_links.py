"""The engagement's template link (K-03-T19; TASK-9013; K-03 F5; SHL-22; KNW-07; DEC-6019).

`engagement_template_links` names the template version an engagement follows (1011 backfilled
one per pinned engagement, state `current`). Behind `templates_v2.enabled`:

- **Pinning** (`pin_methodology`): the first pin writes the legacy column (kept as the current
  methodology version) and the link to the methodology version's published template wrapper.
  A second pin, on an engagement already linked or pinned, answers 409
  `template_update_required`: the version moves only through `template.apply_update`
  (K-03-T33's `TemplateUpdateWorkflow`). With the flag off the SPEC-008 path is unchanged
  (409 `methodology_already_applied`).
- **Reading** (`pinned_version`): the methodology version an engagement follows is its link's
  version's methodology version when the flag is on and a link exists, else the legacy column
  (roll-forward reads it: a prior engagement updated to FS v6 rolls forward on FS v6).
- A methodology version published after 1011 has no template wrapper until K-03's publish path
  creates one; pinning it writes the legacy column only, and the reads fall back to it.
"""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import TEMPLATES_V2_ENABLED
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.methodology.api import template_wrapper_of, wrapped_methodology_version

ACTOR: Final = "engagements:template_link"


class TemplateUpdateRequired(DomainConflict):
    """The engagement already follows a template version: move it with Update to vN."""

    code = "template_update_required"


_LINK: Final = text(
    "SELECT id, template_version_id FROM engagement_template_links WHERE engagement_id = :e"
)
_INSERT: Final = text(
    "INSERT INTO engagement_template_links (id, tenant_id, engagement_id, template_id, "
    "template_version_id) VALUES (:id, :t, :e, :template, :version)"
)


async def links_on(tenant_id: UUID) -> bool:
    return await flag_enabled(TenantContext(tenant_id, "system", ACTOR), TEMPLATES_V2_ENABLED)


async def before_pin(
    tx: UnitOfWork, tenant_id: UUID, engagement_id: UUID, legacy: UUID | None
) -> None:
    """Flag on: refuse a second pin (409 `template_update_required`)."""
    if not await links_on(tenant_id):
        return
    found = (await tx.session.execute(_LINK, {"e": engagement_id})).first()
    if found is not None or legacy is not None:
        raise TemplateUpdateRequired(facts={"engagement": str(engagement_id)})


async def link_pin(
    tx: UnitOfWork, tenant_id: UUID, engagement_id: UUID, methodology_version_id: UUID
) -> UUID | None:
    """Flag on: link the engagement to the version's template wrapper (None when it has none)."""
    if not await links_on(tenant_id):
        return None
    wrapper = await template_wrapper_of(tx.session, methodology_version_id)
    if wrapper is None:
        return None
    template_id, version_id = wrapper
    link = uuid4()
    await tx.session.execute(
        _INSERT,
        {"id": link, "t": tenant_id, "e": engagement_id, "template": template_id,
         "version": version_id},
    )  # fmt: skip
    tx.record(
        "engagement.template_linked",
        target=Target("engagement", engagement_id),
        after=Ref(template_version=version_id, methodology_version=methodology_version_id),
    )
    return link


async def pinned_version(
    tenant: TenantContext, engagement_id: UUID, legacy: UUID | None
) -> UUID | None:
    """The methodology version the engagement follows (its link's, else the legacy column)."""
    if not await links_on(tenant.tenant_id):
        return legacy
    async with tenant_session(tenant) as session:
        return await _linked(session, engagement_id) or legacy


async def _linked(session: AsyncSession, engagement_id: UUID) -> UUID | None:
    found = (await session.execute(_LINK, {"e": engagement_id})).first()
    if found is None:
        return None
    return await wrapped_methodology_version(session, found.template_version_id)


async def linked_template_version(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The template version the engagement's link names (K-03-T20: its sheets' definitions)."""
    async with tenant_session(tenant) as session:
        found = (await session.execute(_LINK, {"e": engagement_id})).first()
    return None if found is None else cast(UUID, found.template_version_id)


__all__ = [
    "TemplateUpdateRequired",
    "before_pin",
    "link_pin",
    "linked_template_version",
    "links_on",
    "pinned_version",
]
