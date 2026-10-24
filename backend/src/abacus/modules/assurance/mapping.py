"""Account mapping and the draft statements (SPEC-316; TASK-345; A-03, AUD-20).

Firm level: people with `grouping_set.import` load the firm's taxonomy (CSV) into a draft;
`grouping_set.publish` publishes a draft with no problems. Engagement level: `mapping_set.edit`
starts the trial balance's mapping on a published version and maps accounts; the mapping is a
reviewable (L1 needs every account mapped), and the statements are read with
`trial_balance.read`. The ledger computes everything; this authorises and names.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.ledger.api import (
    MappingView,
    Statements,
    VersionView,
    create_mapping_set,
    edit_mappings,
    engagement_trial_balances,
    grouping_set_versions,
    import_grouping_set,
    mapping_set_authors,
    mapping_set_of,
    mapping_view,
    publish_version,
    published_versions,
    statements_for,
)
from abacus.modules.review.api import Reviewable, ReviewableFacts, record_sign_off

TARGET = "mapping_set"


class Unmapped(DomainConflict):
    """The preparer signs a mapping only when every account is mapped."""

    code = "unmapped_accounts"


async def versions(ctx: AuthContext) -> list[VersionView]:
    await authorise(ctx, "grouping_set.import", Resource.firm(ctx.tenant_id))
    return await grouping_set_versions(ctx.tenant)


async def import_csv(ctx: AuthContext, key: str, name: str, text: str) -> UUID:
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, "grouping_set.import", Resource.firm(ctx.tenant_id))
        return await import_grouping_set(
            tx, tenant_id=ctx.tenant_id, key=key, name=name, text=text, user_id=ctx.user_id
        )


async def publish(ctx: AuthContext, version_id: UUID) -> None:
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, "grouping_set.publish", Resource.firm(ctx.tenant_id))
        await publish_version(
            tx, version_id=version_id, user_id=ctx.user_id, actor_kind=ctx.tenant.actor_kind
        )


async def mapping_for(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID
) -> tuple[MappingView | None, list[VersionView]]:
    """The mapping (None before it starts) and the published versions to start it on."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    found = await mapping_view(ctx.tenant, engagement_id, tb_id)
    return found, (await published_versions(ctx.tenant) if found is None else [])


async def start(ctx: AuthContext, engagement_id: UUID, tb_id: UUID, version_id: UUID) -> None:
    if tb_id not in {t.id for t in await engagement_trial_balances(ctx.tenant, engagement_id)}:
        raise NotFound("trial_balance")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "mapping_set.edit", ref.resource())
        await create_mapping_set(
            tx,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            tb_id=tb_id,
            version_id=version_id,
            user_id=ctx.user_id,
        )


async def edit(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, edits: Sequence[tuple[str, UUID | None]]
) -> None:
    found = await mapping_set_of(ctx.tenant, tb_id)
    if found is None or found.engagement_id != engagement_id:
        raise NotFound("mapping_set")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "mapping_set.edit", ref.resource())
        await edit_mappings(
            tx,
            tenant_id=ctx.tenant_id,
            mapping_set_id=found.id,
            version_id=found.grouping_set_version_id,
            edits=edits,
            user_id=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )


async def sign_mapping(ctx: AuthContext, engagement_id: UUID, tb_id: UUID, level: int) -> None:
    found = await mapping_view(ctx.tenant, engagement_id, tb_id)
    if found is None:
        raise NotFound("mapping_set")
    if found.unmapped:
        raise Unmapped(str(found.unmapped))
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await record_sign_off(
            tx,
            ctx,
            ref.resource(),
            engagement_id,
            TARGET,
            found.mapping_set_id,
            level,
            found.content_hash,
        )


async def statements(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, layer: str
) -> Statements | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    return await statements_for(ctx.tenant, engagement_id, tb_id, layer)


async def mapping_facts(tenant: TenantContext, mapping_set_id: UUID) -> ReviewableFacts | None:
    """P-04-T15: a mapping set's facts for the sign-off rules. Its preparers are its creator and
    everyone who edited a mapping in it (the ledger's own records)."""
    authors = await mapping_set_authors(tenant, mapping_set_id)
    if authors is None:
        return None
    found = await mapping_view(tenant, authors.engagement_id, authors.trial_balance_id)
    if found is None or found.mapping_set_id != mapping_set_id:
        return None
    return ReviewableFacts(
        TARGET,
        mapping_set_id,
        authors.engagement_id,
        found.content_hash,
        found.version.version,
        authors.authors,
    )


async def mapping_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Each mapping set with its content hash, for the matrix and G5."""
    out: list[Reviewable] = []
    for tb in await engagement_trial_balances(tenant, engagement_id):
        found = await mapping_view(tenant, engagement_id, tb.id)
        if found is not None:
            out.append(
                Reviewable(
                    TARGET,
                    found.mapping_set_id,
                    f"MAP {tb.period_end.isoformat()}",
                    f"Account mapping ({found.version.set_name} v{found.version.version})",
                    found.content_hash,
                    True,
                )
            )
    return out
