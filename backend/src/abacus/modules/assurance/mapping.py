"""Account mapping and the draft statements (SPEC-316; TASK-345; A-03, AUD-20).

Firm level: people with `grouping_set.import` load the firm's taxonomy (CSV) into a draft;
`grouping_set.publish` publishes a draft with no problems. Engagement level: `mapping_set.edit`
starts the trial balance's mapping on a published version and maps accounts; the mapping is a
reviewable (L1 needs every account mapped), and the statements are read with
`trial_balance.read`. The ledger computes everything; this authorises and names.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Annotated, ClassVar, Final
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.kernel.classification import classified
from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import get_ref, lock_ref, prior_engagement_of
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.ledger.api import (
    GroupingView,
    MappingView,
    Statements,
    VersionView,
    create_mapping_set,
    edit_mappings,
    engagement_trial_balances,
    grouping_catalogue,
    grouping_set_versions,
    grouping_version_id,
    import_grouping_set,
    import_parsed_grouping_set,
    mapping_set_authors,
    mapping_set_of,
    mapping_view,
    parse_grouping_set,
    parse_grouping_workbook,
    prior_keys,
    publish_version,
    published_versions,
    recently_used,
    statements_for,
)
from abacus.modules.review.api import Reviewable, ReviewableFacts, record_sign_off, stale_of

TARGET = "mapping_set"


async def _prior(tenant: TenantContext, engagement_id: UUID) -> dict[str, str]:
    """A-03-T08: the prior year's mapping as normalised code to FS-line key, from the engagement
    this one rolled forward from (its first mapped trial balance). Only line keys cross over,
    never figures, and only into the mapping of an engagement the caller was authorised on."""
    prior = await prior_engagement_of(tenant, engagement_id)
    if prior is None:
        return {}
    for tb in await engagement_trial_balances(tenant, prior):
        found = await mapping_view(tenant, prior, tb.id)
        if found is not None:
            return prior_keys(found)
    return {}


async def prior_keys_for(tenant: TenantContext, engagement_id: UUID) -> dict[str, str]:
    """The prior engagement's confirmed keys (A-03-T08: the mapped trial balance reads the same
    prior as the view, so their content hashes agree)."""
    return await _prior(tenant, engagement_id)


async def mapping_with_prior(
    tenant: TenantContext, engagement_id: UUID, tb_id: UUID
) -> MappingView | None:
    return await mapping_view(tenant, engagement_id, tb_id, await _prior(tenant, engagement_id))


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


async def publish(ctx: AuthContext, version_id: UUID, effective_from: date | None = None) -> None:
    """A person publishes with fresh MFA (the matrix) and an effective date; v0's callers send
    none and the firm's business date is used (A-03-T06, DEC-1556)."""
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, "grouping_set.publish", Resource.firm(ctx.tenant_id))
        await publish_version(
            tx,
            version_id=version_id,
            user_id=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
            effective_from=effective_from or await today(ctx.tenant),
        )


async def import_file(
    ctx: AuthContext, key: str, name: str, content: bytes, media_type: str
) -> UUID:
    """C9 v2 import (A-03-T06): an XLSX workbook (three sheets) or a CSV, as a raw body, into a
    draft with its problems by sheet, row and code."""
    if media_type.startswith(XLSX):
        parsed = parse_grouping_workbook(content)
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise GroupingFileInvalid("encoding") from error
        parsed = parse_grouping_set(text)
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, "grouping_set.import", Resource.firm(ctx.tenant_id))
        return await import_parsed_grouping_set(
            tx, tenant_id=ctx.tenant_id, key=key, name=name, parsed=parsed, user_id=ctx.user_id
        )


class GroupingFileInvalid(DomainInvalid):
    code = "import_invalid"


XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def catalogue(ctx: AuthContext) -> list[VersionView]:
    """Every firm role reads the catalogue (`grouping_set.read`; the taxonomy is firm content)."""
    await authorise(ctx, "grouping_set.read", Resource.firm(ctx.tenant_id))
    return await grouping_set_versions(ctx.tenant)


async def picker(
    ctx: AuthContext, set_id: UUID, version_no: int
) -> tuple[UUID, list[GroupingView], list[UUID]]:
    """A version's groupings and the person's own Recently used FS lines (INV-3)."""
    await authorise(ctx, "grouping_set.read", Resource.firm(ctx.tenant_id))
    version_id = await grouping_version_id(ctx.tenant, set_id, version_no)
    if version_id is None:
        raise NotFound("grouping_set_version")
    views = await grouping_catalogue(ctx.tenant, version_id)
    return version_id, views, await recently_used(ctx.tenant, version_id, ctx.user_id)


async def mapping_for(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID
) -> tuple[MappingView | None, list[VersionView]]:
    """The mapping (None before it starts) and the published versions to start it on."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    found = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
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
    found = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
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
        if level == 1:  # A-03-T08: the preparer's sign-off confirms the mapping
            tx.record(
                "mapping_set.confirmed",
                target=Target("mapping_set", found.mapping_set_id),
                after=Ref(accounts=len(found.accounts)),
            )


async def statements(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, layer: str
) -> Statements | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    prior = await _prior(ctx.tenant, engagement_id)
    return await statements_for(ctx.tenant, engagement_id, tb_id, layer, prior)


async def mapping_facts(tenant: TenantContext, mapping_set_id: UUID) -> ReviewableFacts | None:
    """P-04-T15: a mapping set's facts for the sign-off rules. Its preparers are its creator and
    everyone who edited a mapping in it (the ledger's own records)."""
    authors = await mapping_set_authors(tenant, mapping_set_id)
    if authors is None:
        return None
    found = await mapping_with_prior(tenant, authors.engagement_id, authors.trial_balance_id)
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
        found = await mapping_with_prior(tenant, engagement_id, tb.id)
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


# --- A-03-T14: a new trial balance version leaves a signed mapping stale ----------------------

_STALE_NAMESPACE: Final = uuid.UUID("0f6a7c1e-3d52-4b8f-9e0a-5c4d2b1a8e73")


class MappingSetWentStale(DomainEvent):
    """A newer trial balance version changed a signed mapping's content (A-03 Story 4): review's
    detector tells each signer (`sign_off.went_stale`); A-10 later marks overrides stale."""

    event_type: ClassVar[str] = "mapping_set.went_stale"

    mapping_set_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    trial_balance_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]


def went_stale_id(mapping_set_id: UUID, version_no: int) -> UUID:
    """Once per trial balance version: a replayed adoption announces nothing new."""
    return uuid.uuid5(_STALE_NAMESPACE, f"{mapping_set_id}:{version_no}")


async def on_tb_version(event: OutboxEvent) -> bool:
    """`trial_balance.version_created` (A-02): when a later version leaves the mapping's newest
    sign-offs on other content, emit `mapping_set.went_stale` once. Version 1, a trial balance
    with no mapping and an unsigned mapping change nothing. Human edits survive by account code
    (`mapping_set_edits`), and new accounts read unmapped, by construction of the view."""
    tb_raw, eng_raw, version = (
        event.payload.get("trial_balance_id"),
        event.payload.get("engagement_id"),
        event.payload.get("version_no"),
    )
    if tb_raw is None or eng_raw is None or not isinstance(version, int) or version < 2:
        return False
    tenant = TenantContext(event.tenant_id, "system", "assurance.mapping_stale")
    tb_id, engagement_id = UUID(str(tb_raw)), UUID(str(eng_raw))
    found = await mapping_set_of(tenant, tb_id)
    if found is None:
        return False
    view = await mapping_with_prior(tenant, engagement_id, tb_id)
    if view is None or not await stale_of(tenant, TARGET, {found.id: view.content_hash}):
        return False
    try:
        async with uow(tenant) as tx:
            tx.record(
                "mapping_set.went_stale",
                target=Target("mapping_set", found.id),
                after=Ref(version_no=version, unmapped=view.unmapped),
                scope=Scope(engagement_id=engagement_id),
            )
            tx.emit(
                MappingSetWentStale(
                    event_id=went_stale_id(found.id, version),
                    mapping_set_id=found.id,
                    engagement_id=engagement_id,
                    trial_balance_id=tb_id,
                    version_no=version,
                )
            )
    except IntegrityError:
        return False  # already announced for this version (a replay)
    return True


async def _on_tb_version(event: OutboxEvent) -> None:
    await on_tb_version(event)


SUBSCRIPTIONS = {"trial_balance.version_created": _on_tb_version}
