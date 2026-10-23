"""The portal home read model and preferences (P-08-T13; POR-02; SPEC-320 AC-15 to AC-17).

One scope at a time: the person's full-client grant on it (any other answers 404, INV-4), the
engagements and work items it covers, each authorised for `portal_home.read` on its own target
(`scope_only`), then every registered home source over exactly those. Nothing here carries a firm
status, an amount, materiality or the agent: sources speak client codes.

`first_visit` is the welcome not yet dismissed for the scope (DEC-210): portal sessions arrive with
P-08-T10 and carry no history of earlier visits yet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, portal_work_items
from abacus.modules.identity.api import (
    FULL_ROLES,
    AuthContext,
    Forbidden,
    GrantScope,
    authorise,
    portal_scopes,
    scope_facts,
)
from abacus.modules.portal import home_sources, repository
from abacus.modules.portal.home_sources import (
    Binder,
    Earlier,
    HomeScope,
    HomeTeamMember,
    Todo,
    WorkCard,
)

# The sources P-08 ships register on import; later epics add their own modules (C5 v1.1).
from abacus.modules.portal.home_sources import engagements as _engagements
from abacus.modules.portal.home_sources import requests as _requests

LOADED = (_requests.requests_source, _engagements.engagements_source)


class PortalPreferencesStale(DomainConflict):
    """The preferences changed since they were read (`version` is behind): read the home again."""

    code = "portal_preferences_stale"


@dataclass(frozen=True)
class HomeScopeView:
    kind: str
    id: UUID
    label: str
    role_label: str
    sub: str | None = None


@dataclass(frozen=True)
class HomeView:
    scope: HomeScopeView
    todos: list[Todo]
    work_cards: list[WorkCard]
    binder: Binder | None
    team: list[HomeTeamMember]
    earlier: list[Earlier]
    first_visit: bool
    welcome_dismissed: bool
    all_done: bool


@dataclass(frozen=True)
class PreferencesView:
    scope_id: UUID
    welcome_dismissed: bool
    welcome_dismissed_at: datetime | None
    version: int


async def _grant(ctx: AuthContext, scope_id: UUID | None) -> GrantScope:
    """The person's full-client grant on the scope (or their first one); 404 for any other."""
    held = await portal_scopes(ctx)
    found = [g for g in held.scopes if g.role in FULL_ROLES and scope_id in (None, g.scope_id)]
    if not found:
        raise NotFound("portal_scope")
    # Two roles on one scope: the label names the stronger (an owner before a contributor).
    return min(found, key=lambda g: (g.scope_id != found[0].scope_id, g.role == "contributor"))


async def _covered(ctx: AuthContext, grant: GrantScope) -> HomeScope:
    facts = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
    if facts is None:
        raise NotFound("portal_scope")
    items = await portal_work_items(ctx, grant.scope_kind, grant.scope_id)
    engagements: list[UUID] = []
    for engagement_id in dict.fromkeys(i.engagement_id for i in items):
        resource = replace(
            (await get_ref(ctx, engagement_id)).resource(), work_item_id=facts.work_item_id
        )
        try:
            await authorise(ctx, "portal_home.read", resource)
        except (Forbidden, NotFound):
            continue  # a target this scope's grant does not cover (INV-4)
        engagements.append(engagement_id)
    if not engagements:
        raise NotFound("portal_scope")  # nothing of the scope this person may read
    return HomeScope(
        grant.scope_kind,
        grant.scope_id,
        facts.client_id,
        tuple(engagements),
        tuple(i for i in items if i.engagement_id in engagements),
        await clock.today(ctx.tenant),
    )


async def read_home(ctx: AuthContext, scope_id: UUID | None) -> HomeView:
    grant = await _grant(ctx, scope_id)
    scope = await _covered(ctx, grant)
    todos: list[Todo] = []
    cards: list[WorkCard] = []
    binders: list[Binder] = []
    team: list[HomeTeamMember] = []
    earlier: list[Earlier] = []
    for _, source in home_sources.home_sources():
        part = await source(ctx, scope)
        todos += part.todos
        cards += part.work_cards
        binders += part.binders
        team += [m for m in part.team if m.user_id not in {t.user_id for t in team}]
        earlier += part.earlier
    async with tenant_session(ctx.tenant) as session:
        prefs = await repository.preference(session, ctx.user_id, grant.scope_kind, grant.scope_id)
    dismissed = prefs is not None and prefs["welcome_dismissed_at"] is not None
    binder = max(binders, key=lambda b: b.total - b.done, default=None)
    label = scope.work_items[0].client_name if scope.work_items else ""
    return HomeView(
        scope=HomeScopeView(
            grant.scope_kind, grant.scope_id, label, grant.role.replace("_", " ").capitalize()
        ),
        todos=todos,
        work_cards=cards,
        binder=binder,
        team=team,
        earlier=earlier,
        first_visit=not dismissed,
        welcome_dismissed=dismissed,
        all_done=all(t.count == 0 for t in todos)
        and all(b.done == b.total for b in binders)
        and not cards,
    )


async def set_preferences(
    ctx: AuthContext, scope_id: UUID, welcome_dismissed: bool, version: int
) -> PreferencesView:
    """Per user and scope, at the version read (0: never written); audited."""
    grant = await _grant(ctx, scope_id)
    scope = await _covered(ctx, grant)
    await authorise(
        ctx, "portal_preferences.update", (await get_ref(ctx, scope.engagements[0])).resource()
    )
    async with uow(ctx.tenant) as tx:
        if version == 0:
            row = await repository.insert_preference(
                tx.session,
                ctx.tenant_id,
                ctx.user_id,
                grant.scope_kind,
                scope_id,
                welcome_dismissed,
            )
        else:
            row = await repository.update_preference(
                tx.session, ctx.user_id, grant.scope_kind, scope_id, welcome_dismissed, version
            )
        if row is None:
            current = await repository.preference(
                tx.session, ctx.user_id, grant.scope_kind, scope_id
            )
            raise PortalPreferencesStale(
                facts={"version": int(current["version"]) if current is not None else 0}
            )
        tx.record(
            "portal_preferences.updated",
            target=Target("firm", ctx.tenant_id),
            after=Ref(welcome_dismissed=int(welcome_dismissed), version=int(row["version"])),
        )
    return PreferencesView(
        scope_id,
        row["welcome_dismissed_at"] is not None,
        row["welcome_dismissed_at"],
        row["version"],
    )
