"""Field value history (P-04-T35; ADR-160 clauses 5 and 10; SHL-09; DEC-1050).

Every cell and field a module owns keeps its versions in `field_value_versions`, written only by
`review.api.record_value` (FIELD-001). This module is SHL-09's tray over those rows:

- **Provenance** (`field.read`): the versions newest first, each with its actor ("Accrued Agent",
  "Kevin Osei", "Samuel Ito via Agent", "Imported Return"), its citation note or references, and
  `unsupported` computed: an agent value whose citations are not all supported now (C4,
  the field-citations slot over C4; INV-2). The ticks with `stale` computed (their hash is not
  the field's current hash), and the flags (review notes anchored on the field).
- **Edit** (`field.edit`, a person with a preparer function): the owner writes its record in the
  same unit of work (`FieldOwner.apply_edit`), then a `human` version with the required citation
  note; where the owner checkpoints, a person's `human_edit` checkpoint too (SHL-16). A stale
  `seen_seq` is 409 `field_changed` and writes nothing.
- **Add reference** (`field.add_reference`): a document page cited through C4 against the field's
  current value; a verified citation makes a new version (cause `relink`) with the same value and
  the citation added. An unverified one is 422 `uncited_change` and writes nothing.
- **Tick** (`field.sign_off`): `review.sign_offs.tick_field`.

The owner target's engagement authorises everything (404 for walls and other firms); an owner
nobody registered is 422 `unregistered_kind`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, ServiceUnavailable
from abacus.kernel.uow import UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    names_of,
)
from abacus.modules.review import checkpoints
from abacus.modules.review.field_values import (
    field_hash,
    field_target_id,
    record_value,
    typed_value,
)
from abacus.modules.review.models import FieldValueVersion, SignOff
from abacus.modules.review.notes import FieldFlag, field_flags
from abacus.modules.review.repository import field_ticks_of, field_versions_of
from abacus.modules.review.sealing import open_text, record_text_reads
from abacus.modules.review.sign_offs import (
    FieldNow,
    UncitedChange,
    hash_out,
    initials_of,
    live_human,
    tick_field,
)
from abacus.modules.review.slots import (
    DocumentCitation,
    FieldOwner,
    ReviewableFacts,
    field_citations,
    field_owner,
    reviewable_facts,
)

READ: Final = "field.read"
EDIT: Final = "field.edit"
ADD_REFERENCE: Final = "field.add_reference"
SIGN_OFF: Final = "field.sign_off"
_WRITES: Final = (EDIT, ADD_REFERENCE, SIGN_OFF)
NOTE_SUBJECT: Final = "field_value_version"
_AGENT_NAME: Final = "Accrued Agent"
_IMPORT_NAME: Final = "Imported Return"
_SYSTEM_NAME: Final = "Accrued"
_FORMER: Final = "Former member"
ReferenceKind = Literal["document", "engine_import", "workpaper", "prior_return"]


class FieldChanged(DomainConflict):
    """The field has a newer version than the one the person saw: nothing is written."""

    code = "field_changed"


@dataclass(frozen=True)
class FieldReference:
    id: UUID
    kind: ReferenceKind
    label: str
    detail: str | None
    citation_id: UUID | None
    document_id: UUID | None
    page: int | None


@dataclass(frozen=True)
class FieldVersion:
    seq: int
    value: dict[str, object]
    value_kind: str
    value_source: str
    cause: str
    actor_kind: str
    actor_user_id: UUID | None
    actor_name: str
    recorded_at: datetime
    citation: str | None
    citation_ids: list[UUID]
    references: list[FieldReference]
    unsupported: bool
    suggestion_id: UUID | None
    checkpoint_id: UUID | None
    issue_id: UUID | None


@dataclass(frozen=True)
class FieldTick:
    sign_off_id: UUID
    level: int
    signer_user_id: UUID
    signer_name: str
    initials: str
    signed_at: datetime
    content_hash: str
    stale: bool


@dataclass(frozen=True)
class Provenance:
    target_type: str
    target_id: UUID
    field_key: str
    label: str
    current_seq: int
    content_hash: str
    versions: list[FieldVersion]
    ticks: list[FieldTick]
    flags: list[FieldFlag]
    allowed_actions: list[str]


# --- Scope -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Scope:
    owner: FieldOwner
    facts: ReviewableFacts
    resource: Resource


async def _scope(ctx: AuthContext, target_type: str, target_id: UUID, action: str) -> _Scope:
    """The field's owner, the target's facts, and its engagement (with the work item, for the
    preparer-function condition on `field.edit`) authorising `action`."""
    owner = field_owner(target_type)
    facts = await reviewable_facts(ctx.tenant, target_type, target_id)
    resource = await engagement_resource_of(ctx.tenant, facts.engagement_id)
    resource = replace(resource, work_item_id=facts.work_item_id)
    await authorise(ctx, action, resource)
    return _Scope(owner, facts, resource)


def _person(ctx: AuthContext, action: str) -> None:
    """A field write is a person's (INV-1): never an agent, system, client or support principal."""
    if not live_human(ctx):
        raise Forbidden(action, "role")


# --- Current value -----------------------------------------------------------------------------


def unsupported_of(row: FieldValueVersion, supported: frozenset[UUID]) -> bool:
    """INV-2: an agent value with no verified citation (or one no longer valid) is Unsupported.
    A person's edit is cited by its required note; imports, formulas and TB links by their
    source."""
    if row.value_source != "agent_suggested":
        return False
    return not row.citation_ids or not set(row.citation_ids) <= supported


async def _latest_in(
    tx: UnitOfWork, target_type: str, target_id: UUID, field_key: str
) -> FieldValueVersion | None:
    """The field's newest version, under the per-field lock `record_value` takes (re-entrant in
    the transaction), so nothing writes between the check and the write."""
    await tx.session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"fvv:{target_type}:{target_id}:{field_key}"},
    )
    rows = await field_versions_of(tx.session, target_type, target_id, field_key)
    return rows[0] if rows else None


def _hash_of(
    target_type: str, target_id: UUID, field_key: str, row: FieldValueVersion | None
) -> str:
    if row is None:
        return field_hash(target_type, target_id, field_key, None, "exact")
    return field_hash(target_type, target_id, field_key, row.value, row.value_kind)


def _check_seen(row: FieldValueVersion | None, seen_seq: int) -> None:
    """A field with no history yet is edited as `seen_seq` 1 (the wire's floor)."""
    current = row.seq if row is not None else 0
    if max(current, 1) != seen_seq:
        raise FieldChanged(facts={"seq": current})


# --- Provenance --------------------------------------------------------------------------------


def _actor_name(row: FieldValueVersion, names: Mapping[UUID, str]) -> tuple[UUID | None, str]:
    """Who wrote the version, as the tray says it. A person who adopted an agent value reads
    "<person> via Agent" (DEC-19: one agent, attributed to the person)."""
    if row.actor_kind == "agent":
        return None, _AGENT_NAME
    if row.actor_kind == "system":
        return None, _IMPORT_NAME if row.value_source == "engine_import" else _SYSTEM_NAME
    try:
        user = UUID(row.actor_id)
    except ValueError:
        return None, _FORMER
    name = names.get(user, _FORMER)
    if row.value_source == "agent_suggested":
        return user, f"{name} via Agent"
    return user, name


async def _references(
    ctx: AuthContext, citation_ids: Sequence[UUID]
) -> dict[UUID, FieldReference]:
    """Each citation as a reference row, through the C4 read the citations slot provides (it
    authorises the reader and logs a re-read quote). One the reader may not see is left out."""
    described = await field_citations().describe(ctx, list(dict.fromkeys(citation_ids)))
    return {
        cid: FieldReference(
            id=cid,
            kind=cast(ReferenceKind, c.kind),
            label=c.label,
            detail=c.detail,
            citation_id=cid,
            document_id=c.document_id,
            page=c.page,
        )
        for cid, c in described.items()
    }


async def _notes(tenant: TenantContext, rows: Sequence[FieldValueVersion]) -> dict[int, str]:
    out: dict[int, str] = {}
    for r in rows:
        if r.citation_note_sealed is not None:
            out[r.seq] = await open_text(
                tenant,
                r.citation_note_sealed,
                NOTE_SUBJECT,
                r.target_type,
                r.target_id,
                r.field_key,
                r.seq,
            )
    return out


def _tick(row: SignOff, names: Mapping[UUID, str], current_hash: str) -> FieldTick:
    name = names.get(row.signed_by, _FORMER)
    return FieldTick(
        sign_off_id=row.id,
        level=row.level,
        signer_user_id=row.signed_by,
        signer_name=name,
        initials=row.initials or initials_of(name) or "",
        signed_at=row.created_at,
        content_hash=hash_out(row.content_hash),
        stale=row.content_hash != current_hash,
    )


async def provenance(
    ctx: AuthContext, target_type: str, target_id: UUID, field_key: str
) -> Provenance:
    """`GET /v1/fields/{type}/{id}/{key}/provenance` (SHL-09 a to f)."""
    scope = await _scope(ctx, target_type, target_id, READ)
    engagement_id = scope.facts.engagement_id
    field_id = field_target_id(target_type, target_id, field_key)
    async with tenant_session(ctx.tenant) as session:
        rows = list(await field_versions_of(session, target_type, target_id, field_key))
        ticks = list(await field_ticks_of(session, field_id))
    every_citation = [c for r in rows for c in r.citation_ids]
    supported = await field_citations().supported(ctx.tenant, engagement_id, every_citation)
    people = {UUID(r.actor_id) for r in rows if r.actor_kind == "human" and _is_uuid(r.actor_id)}
    names = await names_of(list(people | {t.signed_by for t in ticks}))
    noted = [r for r in rows if r.citation_note_sealed is not None]
    if noted:
        ref = await get_ref(ctx, engagement_id)
        await record_text_reads(
            ctx.tenant,
            NOTE_SUBJECT,
            [r.id for r in noted],
            engagement_id=engagement_id,
            client_id=ref.client_id,
            work_item_id=scope.facts.work_item_id,
        )
    notes = await _notes(ctx.tenant, noted)
    references = await _references(ctx, every_citation)
    versions: list[FieldVersion] = []
    for r in rows:
        user, name = _actor_name(r, names)
        versions.append(
            FieldVersion(
                seq=r.seq,
                value=dict(r.value),
                value_kind=r.value_kind,
                value_source=r.value_source,
                cause=r.cause,
                actor_kind=r.actor_kind,
                actor_user_id=user,
                actor_name=name,
                recorded_at=r.created_at,
                citation=notes.get(r.seq),
                citation_ids=list(r.citation_ids),
                references=[references[c] for c in r.citation_ids if c in references],
                unsupported=unsupported_of(r, supported),
                suggestion_id=r.suggestion_id,
                checkpoint_id=r.checkpoint_id,
                issue_id=r.issue_id,
            )
        )
    current = rows[0] if rows else None
    current_hash = _hash_of(target_type, target_id, field_key, current)
    held = await allowed_actions(ctx, scope.resource, _WRITES)
    if versions and versions[0].unsupported:
        held = [a for a in held if a != SIGN_OFF]  # "Add a reference before signing off"
    label_of = scope.owner.label_of
    return Provenance(
        target_type=target_type,
        target_id=target_id,
        field_key=field_key,
        label=label_of(field_key) if label_of is not None else field_key,
        current_seq=current.seq if current is not None else 0,
        content_hash=hash_out(current_hash),
        versions=versions,
        ticks=[_tick(t, names, current_hash) for t in ticks],
        flags=await field_flags(ctx, engagement_id, target_type, target_id, field_key),
        allowed_actions=sorted(held),
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


# --- Writes ------------------------------------------------------------------------------------


async def edit(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    field_key: str,
    *,
    value: Mapping[str, object],
    value_kind: Literal["exact", "estimate"],
    citation_note: str,
    seen_seq: int,
) -> Provenance:
    """`PUT …/value` (SHL-09 c): a person's edit with its citation note (INV-5)."""
    _person(ctx, EDIT)
    scope = await _scope(ctx, target_type, target_id, EDIT)
    apply_edit = scope.owner.apply_edit
    if apply_edit is None:
        raise ServiceUnavailable
    checked = typed_value(value)
    async with uow(ctx.tenant) as tx:
        latest = await _latest_in(tx, target_type, target_id, field_key)
        _check_seen(latest, seen_seq)
        after_hash = await apply_edit(tx, ctx, target_id, field_key, checked)
        await record_value(
            tx,
            engagement_id=scope.facts.engagement_id,
            target_type=target_type,
            target_id=target_id,
            field_key=field_key,
            value=checked,
            value_source="human",
            cause="edit",
            value_kind=value_kind,
            citation_note=citation_note,
        )
        if scope.owner.checkpoints:
            await checkpoints.record_human_edit(
                tx,
                ctx,
                scope.facts,
                checkpoints.ProposedChange(
                    field_key=field_key,
                    old=dict(latest.value) if latest is not None else None,
                    new=checked,
                    cause="human_edit",
                ),
                content_hash=after_hash or scope.facts.content_hash,
            )
    return await provenance(ctx, target_type, target_id, field_key)


async def add_reference(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    field_key: str,
    *,
    document_id: UUID,
    page: int | None,
    seen_seq: int,
) -> Provenance:
    """`POST …/references` ("Add reference"): a document page that shows the field's current
    value, verified through C4; a new version carries it."""
    _person(ctx, ADD_REFERENCE)
    scope = await _scope(ctx, target_type, target_id, ADD_REFERENCE)
    ref = await get_ref(ctx, scope.facts.engagement_id)
    async with uow(ctx.tenant) as tx:
        latest = await _latest_in(tx, target_type, target_id, field_key)
        _check_seen(latest, seen_seq)
        if latest is None or latest.value.get("v") is None:
            raise UncitedChange(facts={"count": 1})  # nothing on a page can show an empty value
        citation_id, verified = await field_citations().cite_document(
            tx,
            ctx,
            DocumentCitation(
                engagement_id=scope.facts.engagement_id,
                work_item_id=scope.facts.work_item_id,
                client_id=ref.client_id,
                field_id=field_target_id(target_type, target_id, field_key),
                field_key=field_key,
                document_id=document_id,
                page=page,
                value=str(latest.value["v"]),
            ),
        )
        if not verified:
            raise UncitedChange(facts={"count": 1})
        note = (
            await open_text(
                ctx.tenant,
                latest.citation_note_sealed,
                NOTE_SUBJECT,
                target_type,
                target_id,
                field_key,
                latest.seq,
            )
            if latest.citation_note_sealed is not None
            else None
        )
        await record_value(
            tx,
            engagement_id=scope.facts.engagement_id,
            target_type=target_type,
            target_id=target_id,
            field_key=field_key,
            value=latest.value,
            value_source=cast(
                Literal["agent_suggested", "human", "formula", "tb_linked", "engine_import"],
                latest.value_source,
            ),
            cause="relink",
            value_kind=cast(Literal["exact", "estimate"], latest.value_kind),
            on_behalf_of_user_id=latest.on_behalf_of_user_id,
            suggestion_id=latest.suggestion_id,
            checkpoint_id=latest.checkpoint_id,
            citation_ids=[*latest.citation_ids, citation_id],
            citation_note=note,
            issue_id=latest.issue_id,
        )
    return await provenance(ctx, target_type, target_id, field_key)


async def tick(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    field_key: str,
    *,
    level: int,
    seen_hash: str,
) -> Provenance:
    """`POST …/ticks` ("Sign off field"): a `field_tick` sign-off on the current value."""
    field_owner(target_type)  # an unregistered owner is 422 before anything else
    facts = await reviewable_facts(ctx.tenant, target_type, target_id)

    async def current(tx: UnitOfWork) -> FieldNow | None:
        latest = await _latest_in(tx, target_type, target_id, field_key)
        if latest is None:
            return None
        supported = await field_citations().supported(
            ctx.tenant, facts.engagement_id, list(latest.citation_ids)
        )
        return FieldNow(
            field_id=field_target_id(target_type, target_id, field_key),
            content_hash=_hash_of(target_type, target_id, field_key, latest),
            unsupported=unsupported_of(latest, supported),
        )

    await tick_field(ctx, target_type, target_id, field_key, level, seen_hash, current)
    return await provenance(ctx, target_type, target_id, field_key)
