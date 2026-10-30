"""C21 part B, the service: firm standards and threshold policies (K-02-T08; K-02 §3 F3, §4.2 to
§4.5; KNW-04; `docs/contracts/rules-tables.md`).

Two table pairs follow the glossary (`firm_standards` and `threshold_policies`, each with its
versions, 0401); one service serves both, chosen by kind. The lifecycle:

- **Create** (`firm_standard.create`, fresh MFA by the matrix): a parent with no version yet; its
  owner must be a partner member (422 `owner_not_partner`); a key is one standard per firm
  across both tables (409 `standard_key_taken`).
- **Assign owner** (`firm_standard.assign_owner`): another partner member.
- **New version…** (`firm_standard.draft`, `owner_of_target`): a draft copied from the version in
  effect (or the latest published one before its date); one draft per standard (409
  `draft_exists`); nothing published yet is 409 `no_current_version` (content arrives by import,
  K-02-T11).
- **Edit** at the `row_version` read (409 `stale_version`), a draft only (409 `not_draft`), the
  payload valid for the standard's kind (422 `payload_invalid`; an AJE version keeps its
  "review required" and "always held" rows).
- **Discard**: the draft becomes `discarded` (kept, never deleted; hidden from every list).
- **Publish** (`firm_standard.publish`, `owner_of_target`, fresh MFA by the matrix): a person
  only (INV-1: an agent, the system or support is refused and audited
  `decision.refused_non_human`; the database refuses any other actor too), effective on or after
  today in business time (422 `effective_from_backdated`) and after every published version's
  date (422 `effective_from_not_after_current`). The prior version stays current until then;
  "Superseded" is computed at read time, never stored.

The owner check is the matrix's `owner_of_target` on the standard's owner; a partner who is not
the owner gets 403 `not_standard_owner`. Drafts are partners' only: anyone else never sees one
(404, and no draft row in a list). Every write is one unit of work with its audit event; publish
emits `firm_standard.published` or `threshold_policy.published` (identifiers only).

Registrations: KNW-01's `firm_standards` catalog category (cards, change log), the C15 search
projection (metadata only: the name and kind, never a value), and the examples slot
(`register_standard_examples`), whose providers return rows already filtered by `visible()`: a
walled client's row is absent and no hidden count is shown (DEC-43).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final, cast, get_args
from uuid import UUID, uuid4

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    allowed_actions,
    authorise,
    member_facts,
    names_of,
    partner_members,
)
from abacus.modules.methodology.events import FirmStandardPublished, ThresholdPolicyPublished
from abacus.modules.methodology.models import (
    FirmStandard,
    FirmStandardVersion,
    ThresholdPolicy,
    ThresholdPolicyVersion,
)
from abacus.modules.methodology.standards_contract import (
    AjeThresholdsPayload,
    ExampleRow,
    ExamplesProvider,
    FirmStandardKind,
    PolicyRef,
    StandardChangedCellOut,
    StandardCreateIn,
    StandardDetailOut,
    StandardDraftPatchIn,
    StandardExampleRowOut,
    StandardExamplesOut,
    StandardKind,
    StandardOut,
    StandardPayload,
    StandardPersonOut,
    StandardPublishIn,
    StandardVersionDiffOut,
    StandardVersionOut,
    StandardVersionSummaryOut,
)

READ: Final = "firm_standard.read"
CREATE: Final = "firm_standard.create"
ASSIGN: Final = "firm_standard.assign_owner"
DRAFT: Final = "firm_standard.draft"
IMPORT: Final = "firm_standard.import"
PUBLISH: Final = "firm_standard.publish"
_CANDIDATES: Final = (READ, DRAFT, IMPORT, PUBLISH, ASSIGN)

_FIRM_KINDS: Final = frozenset(get_args(FirmStandardKind))
_PAYLOAD: Final = TypeAdapter[StandardPayload](StandardPayload)

Parent = FirmStandard | ThresholdPolicy
Version = FirmStandardVersion | ThresholdPolicyVersion


@dataclass(frozen=True)
class _Family:
    """One table pair, its audit subjects and its outbox event."""

    parent: type[FirmStandard] | type[ThresholdPolicy]
    version: type[FirmStandardVersion] | type[ThresholdPolicyVersion]
    subject: str
    version_subject: str
    created: str
    owner_changed: str
    drafted: str
    edited: str
    discarded: str
    published: str
    event: type[FirmStandardPublished] | type[ThresholdPolicyPublished]


# The action literals are spelled out so the activity catalogue's static check sees each one.
_FIRM: Final = _Family(
    FirmStandard,
    FirmStandardVersion,
    "firm_standard",
    "firm_standard_version",
    "firm_standard.created",
    "firm_standard.owner_changed",
    "firm_standard_version.drafted",
    "firm_standard_version.edited",
    "firm_standard_version.discarded",
    "firm_standard_version.published",
    FirmStandardPublished,
)
_THRESHOLD: Final = _Family(
    ThresholdPolicy,
    ThresholdPolicyVersion,
    "threshold_policy",
    "threshold_policy_version",
    "threshold_policy.created",
    "threshold_policy.owner_changed",
    "threshold_policy_version.drafted",
    "threshold_policy_version.edited",
    "threshold_policy_version.discarded",
    "threshold_policy_version.published",
    ThresholdPolicyPublished,
)


def _family(kind: str) -> _Family:
    return _FIRM if kind in _FIRM_KINDS else _THRESHOLD


# --- errors --------------------------------------------------------------------------------------


class OwnerNotPartner(DomainInvalid):
    """The owner of a standard must be a partner member of the firm."""

    code = "owner_not_partner"


class StandardKeyTaken(DomainConflict):
    """The firm already has a standard with this key."""

    code = "standard_key_taken"


class DraftExists(DomainConflict):
    """The standard already has a draft: edit it, publish it or discard it first."""

    code = "draft_exists"


class NoCurrentVersion(DomainConflict):
    """Nothing is published to draft from: import the first version (K-02-T11)."""

    code = "no_current_version"


class NotDraft(DomainConflict):
    """Only a draft changes: this version is published or discarded."""

    code = "not_draft"


class StaleVersion(DomainConflict):
    """The draft changed since you read it: reload."""

    code = "stale_version"


class PayloadInvalid(DomainInvalid):
    """The payload is not valid for the standard's kind (`facts.kind`, `facts.problems`)."""

    code = "payload_invalid"


class EffectiveFromBackdated(DomainInvalid):
    """A version takes effect today or later (business time)."""

    code = "effective_from_backdated"


class EffectiveFromNotAfterCurrent(DomainInvalid):
    """A version takes effect after every published version's date."""

    code = "effective_from_not_after_current"


class NotStandardOwner(DomainForbidden):
    """Only the standard's owner drafts and publishes it."""

    code = "not_standard_owner"


# --- reading -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Loaded:
    family: _Family
    parent: Parent
    versions: list[Version]  # newest first, discarded included


def payload_hash(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def in_effect(versions: Sequence[Version], on: date) -> Version | None:
    """The published version in effect on `on`: the latest `effective_from` on or before it,
    ties to the highest version."""
    published = [
        v
        for v in versions
        if v.status == "published" and v.effective_from is not None and v.effective_from <= on
    ]
    return max(published, key=lambda v: (v.effective_from, v.version), default=None)


def status_of(version: Version, current: Version | None) -> str:
    """The C2 code: a published version older than the one in effect is `superseded`."""
    if version.status != "published" or current is None or version.id == current.id:
        return version.status
    mine = (version.effective_from or date.min, version.version)
    older = mine < (current.effective_from or date.min, current.version)
    return "superseded" if older else "published"


async def _find(session: AsyncSession, standard_id: UUID, *, lock: bool = False) -> _Loaded:
    for family in (_FIRM, _THRESHOLD):
        stmt = select(family.parent).where(family.parent.id == standard_id)
        if lock:
            stmt = stmt.with_for_update()
        parent = (await session.execute(stmt)).scalar_one_or_none()
        if parent is not None:
            return _Loaded(family, parent, await _versions(session, family, standard_id))
    raise NotFound("firm_standard")


async def _versions(session: AsyncSession, family: _Family, parent_id: UUID) -> list[Version]:
    rows = (
        await session.execute(
            select(family.version)
            .where(family.version.parent_id == parent_id)
            .order_by(family.version.version.desc())
        )
    ).scalars()
    return list(rows)


async def _all(session: AsyncSession, kind: StandardKind | None) -> list[_Loaded]:
    loaded: list[_Loaded] = []
    families = (_family(kind),) if kind is not None else (_FIRM, _THRESHOLD)
    for family in families:
        stmt = select(family.parent).order_by(family.parent.name, family.parent.key)
        if kind is not None:
            stmt = stmt.where(family.parent.kind == kind)
        for parent in (await session.execute(stmt)).scalars():
            loaded.append(_Loaded(family, parent, await _versions(session, family, parent.id)))
    return loaded


async def _is_partner(ctx: AuthContext) -> bool:
    """Drafts are partners' only (US-3.4): a partner-level staff member of this firm."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        return False
    member = await member_facts(ctx.tenant, ctx.user_id)
    return member is not None and not member.client and member.level == "partner"


def _resource(ctx: AuthContext, parent: Parent) -> Resource:
    return replace(Resource.firm(ctx.tenant_id), target=TargetFacts(owner_user_id=parent.owner_id))


def _tax_year(version: Version) -> int | None:
    payload = version.payload
    if payload.get("kind") == "review_checklist":
        applies = cast(Mapping[str, object], payload.get("applies_to") or {})
        year = applies.get("tax_year")
        return year if isinstance(year, int) else None
    return None


def _entries(version: Version | None) -> int | None:
    """How many entries a version holds (a checklist's checks, a policy's rows or tiers)."""
    if version is None:
        return None
    for field in ("items", "rows", "tiers", "applies_to"):
        value = version.payload.get(field)
        if isinstance(value, list):
            return len(cast(list[object], value))
    return None


@dataclass(frozen=True)
class _Names:
    names: Mapping[UUID, str]

    def of(self, user_id: UUID) -> StandardPersonOut:
        return StandardPersonOut(user_id=user_id, name=self.names.get(user_id, ""))

    def person(self, user_id: UUID | None) -> StandardPersonOut | None:
        return None if user_id is None else self.of(user_id)


async def _names(loaded: Sequence[_Loaded]) -> _Names:
    ids: set[UUID] = set()
    for item in loaded:
        ids.add(item.parent.owner_id)
        for v in item.versions:
            ids.add(v.drafted_by)
            if v.published_by is not None:
                ids.add(v.published_by)
    return _Names(await names_of(sorted(ids)) if ids else {})


def _summary(
    version: Version, current: Version | None, names: _Names
) -> StandardVersionSummaryOut:
    return StandardVersionSummaryOut(
        id=version.id,
        version=version.version,
        status=status_of(version, current),  # type: ignore[arg-type] -- a C2 code
        effective_from=version.effective_from,
        published_at=version.published_at,
        published_by=names.person(version.published_by),
        current=current is not None and version.id == current.id,
        tax_year=_tax_year(version),
    )


def _shown(item: _Loaded, on: date) -> Version | None:
    """The version a header shows: the one in effect, else the latest published one."""
    current = in_effect(item.versions, on)
    if current is not None:
        return current
    return next((v for v in item.versions if v.status == "published"), None)


async def _standard_out(
    ctx: AuthContext, item: _Loaded, on: date, names: _Names, partner: bool
) -> StandardOut:
    current = in_effect(item.versions, on)
    shown = _shown(item, on)
    draft = next((v for v in item.versions if v.status == "draft"), None)
    actions = await allowed_actions(ctx, _resource(ctx, item.parent), _CANDIDATES)
    owner = item.parent.owner_id == ctx.user_id
    listed = [a for a in _CANDIDATES if a in actions and (a != IMPORT or owner)]
    return StandardOut(
        id=item.parent.id,
        kind=item.parent.kind,  # type: ignore[arg-type] -- the table's CHECK
        key=item.parent.key,
        name=item.parent.name,
        owner=names.of(item.parent.owner_id),
        current_version=None if shown is None else _summary(shown, current, names),
        draft_version=_summary(draft, current, names) if draft is not None and partner else None,
        usage_count=None,  # no usage counter is registered for standards yet (never invented)
        entries=_entries(shown),
        allowed_actions=listed,
    )


def _version_out(version: Version, current: Version | None, names: _Names) -> StandardVersionOut:
    return StandardVersionOut(
        id=version.id,
        standard_id=version.parent_id,
        version=version.version,
        status=status_of(version, current),  # type: ignore[arg-type] -- a C2 code
        effective_from=version.effective_from,
        payload_schema_version=version.payload_schema_version,
        payload_hash=version.payload_hash,
        change_summary=version.change_summary,
        drafted_from_version_id=version.drafted_from_version_id,
        drafted_by=names.of(version.drafted_by),
        published_by=names.person(version.published_by),
        published_at=version.published_at,
        row_version=version.row_version,
        payload=_PAYLOAD.validate_python(version.payload),
    )


def _visible_versions(item: _Loaded, partner: bool) -> list[Version]:
    """Discarded versions are hidden from everyone; a draft from anyone but a partner."""
    return [
        v for v in item.versions if v.status != "discarded" and (v.status != "draft" or partner)
    ]


async def list_standards(ctx: AuthContext, kind: StandardKind | None) -> list[StandardOut]:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    on = await today(ctx.tenant)
    partner = await _is_partner(ctx)
    async with tenant_session(ctx.tenant) as session:
        loaded = await _all(session, kind)
    names = await _names(loaded)
    return [await _standard_out(ctx, item, on, names, partner) for item in loaded]


async def standard_detail(
    ctx: AuthContext, standard_id: UUID, version: int | None
) -> StandardDetailOut:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    on = await today(ctx.tenant)
    partner = await _is_partner(ctx)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    names = await _names([item])
    current = in_effect(item.versions, on)
    visible = _visible_versions(item, partner)
    if version is None:
        chosen = _shown(item, on)
    else:
        chosen = next((v for v in visible if v.version == version), None)
        if chosen is None:
            raise NotFound("firm_standard_version")
    return StandardDetailOut(
        standard=await _standard_out(ctx, item, on, names, partner),
        version=None if chosen is None else _version_out(chosen, current, names),
        timeline=[_summary(v, current, names) for v in visible],
    )


async def version_detail(
    ctx: AuthContext, standard_id: UUID, version_id: UUID
) -> StandardVersionOut:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    on = await today(ctx.tenant)
    partner = await _is_partner(ctx)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    found = next((v for v in _visible_versions(item, partner) if v.id == version_id), None)
    if found is None:
        raise NotFound("firm_standard_version")
    return _version_out(found, in_effect(item.versions, on), await _names([item]))


# --- the diff (KNW-04 i) -------------------------------------------------------------------------


def _leaves(value: object, path: str = "") -> dict[str, str]:
    """Each scalar in a payload, by JSON pointer; lists of keyed items by their key."""
    if isinstance(value, Mapping):
        out: dict[str, str] = {}
        for k, v in cast(Mapping[str, object], value).items():
            out |= _leaves(v, f"{path}/{k}")
        return out
    if isinstance(value, list):
        out = {}
        for i, v in enumerate(cast(list[object], value)):
            out |= _leaves(v, f"{path}/{i}")
        return out
    return {path: "" if value is None else str(value)}


def diff_cells(
    before: Mapping[str, object], after: Mapping[str, object]
) -> list[StandardChangedCellOut]:
    """The changed values, in the after-payload's order, then values only the before had."""
    old, new = _leaves(before), _leaves(after)
    cells = [
        StandardChangedCellOut(path=p, before=old.get(p), after=v)
        for p, v in new.items()
        if old.get(p) != v and p != "/kind"
    ]
    cells += [
        StandardChangedCellOut(path=p, before=v, after=None)
        for p, v in old.items()
        if p not in new
    ]
    return cells


async def version_diff(
    ctx: AuthContext, standard_id: UUID, version_id: UUID, against: UUID | None
) -> StandardVersionDiffOut:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    partner = await _is_partner(ctx)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    visible = {v.id: v for v in _visible_versions(item, partner)}
    version = visible.get(version_id)
    if version is None:
        raise NotFound("firm_standard_version")
    base_id = against or version.drafted_from_version_id
    if base_id is None:
        base_id = next(
            (
                v.id
                for v in item.versions
                if v.status == "published" and v.version < version.version
            ),
            None,
        )
    base = visible.get(base_id) if base_id is not None else None
    if base is None:
        raise NotFound("firm_standard_version")
    return StandardVersionDiffOut(
        version_id=version.id,
        against_version_id=base.id,
        cells=diff_cells(base.payload, version.payload),
    )


# --- writes --------------------------------------------------------------------------------------


async def _refused(ctx: AuthContext, subject: str, object_id: UUID) -> None:
    """Keep the refusal in its own unit of work (the raise that follows rolls nothing back). A
    non-human's attempt is recorded by the system for the person it ran for."""
    tenant = (
        ctx.tenant
        if ctx.tenant.actor_kind == "human"
        else TenantContext(
            ctx.tenant_id,
            "system",
            f"standards:refusal:{object_id}",
            on_behalf_of_user_id=ctx.tenant.on_behalf_of_user_id or ctx.user_id,
        )
    )
    async with uow(tenant) as tx:
        tx.record("decision.refused_non_human", target=Target(subject, object_id))


async def _human(ctx: AuthContext, action: str, standard_id: UUID) -> None:
    """INV-1: a client principal is 404; an agent, the system or support is refused and
    audited."""
    if ctx.client:
        raise NotFound("firm_standard")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        await _refused(ctx, "firm_standard", standard_id)
        raise Forbidden(action, "role")


async def _owner_guard(ctx: AuthContext, action: str, item: _Loaded) -> None:
    """The matrix's `owner_of_target`; a partner who is not the owner is told so."""
    try:
        await authorise(ctx, action, _resource(ctx, item.parent))
    except Forbidden:
        if item.parent.owner_id != ctx.user_id and await _is_partner(ctx):
            raise NotStandardOwner(facts={"standard_id": str(item.parent.id)}) from None
        raise


async def _check_owner(ctx: AuthContext, owner_id: UUID) -> None:
    if owner_id not in await partner_members(ctx.tenant_id):
        raise OwnerNotPartner(facts={"owner_id": str(owner_id)})


def validate_payload(kind: str, payload: Mapping[str, object]) -> dict[str, object]:
    """The payload as stored: valid for `kind`. An AJE version keeps its "review required" and
    "always held" rows (K-02 §4.3)."""
    if payload.get("kind") != kind:
        raise PayloadInvalid(facts={"kind": kind, "problems": 1})
    try:
        parsed = _PAYLOAD.validate_python(payload)
    except ValidationError as error:
        raise PayloadInvalid(facts={"kind": kind, "problems": error.error_count()}) from None
    if isinstance(parsed, AjeThresholdsPayload):
        rules = {row.rule for row in parsed.rows}
        if not {"review_required", "always_held"} <= rules:
            raise PayloadInvalid(facts={"kind": kind, "problems": 1})
    return cast(dict[str, object], parsed.model_dump(mode="json"))


async def create_standard(ctx: AuthContext, body: StandardCreateIn) -> StandardOut:
    if ctx.client:
        raise NotFound("firm_standard")
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    await _check_owner(ctx, body.owner_id)
    family = _family(body.kind)
    standard_id = uuid4()
    async with uow(ctx.tenant) as tx:
        for other in (_FIRM, _THRESHOLD):
            taken = await tx.session.execute(
                select(other.parent.id).where(other.parent.key == body.key)
            )
            if taken.scalar_one_or_none() is not None:
                raise StandardKeyTaken(facts={"key": body.key})
        tx.session.add(
            family.parent(
                id=standard_id,
                tenant_id=ctx.tenant_id,
                kind=body.kind,
                key=body.key,
                name=body.name,
                owner_id=body.owner_id,
                applies_to={},
                created_by=ctx.user_id,
            )
        )
        tx.record(
            family.created,
            target=Target(family.subject, standard_id),
            after=Ref(owner=body.owner_id),
        )
    return await _one(ctx, standard_id)


async def _one(ctx: AuthContext, standard_id: UUID) -> StandardOut:
    on = await today(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    return await _standard_out(ctx, item, on, await _names([item]), await _is_partner(ctx))


async def assign_owner(ctx: AuthContext, standard_id: UUID, owner_id: UUID) -> StandardOut:
    if ctx.client:
        raise NotFound("firm_standard")
    await authorise(ctx, ASSIGN, Resource.firm(ctx.tenant_id))
    await _check_owner(ctx, owner_id)
    async with uow(ctx.tenant) as tx:
        item = await _find(tx.session, standard_id, lock=True)
        before = item.parent.owner_id
        if before != owner_id:
            await tx.session.execute(
                update(item.family.parent)
                .where(item.family.parent.id == standard_id)
                .values(owner_id=owner_id, row_version=item.parent.row_version + 1)
            )
            tx.record(
                item.family.owner_changed,
                target=Target(item.family.subject, standard_id),
                before=Ref(owner=before),
                after=Ref(owner=owner_id),
            )
    return await _one(ctx, standard_id)


async def _locked_draft(
    tx_session: AsyncSession, item: _Loaded, version_id: UUID, if_match: int
) -> Version:
    version = (
        await tx_session.execute(
            select(item.family.version)
            .where(
                item.family.version.id == version_id,
                item.family.version.parent_id == item.parent.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if version is None or version.status == "discarded":
        raise NotFound("firm_standard_version")
    if version.status != "draft":
        raise NotDraft(facts={"version_id": str(version_id)})
    if version.row_version != if_match:
        raise StaleVersion(facts={"version_id": str(version_id)})
    return version


async def _version_view(
    ctx: AuthContext, standard_id: UUID, version_id: UUID
) -> StandardVersionOut:
    on = await today(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    found = next(v for v in item.versions if v.id == version_id)
    return _version_out(found, in_effect(item.versions, on), await _names([item]))


async def draft_version(ctx: AuthContext, standard_id: UUID) -> StandardVersionOut:
    await _human(ctx, DRAFT, standard_id)
    on = await today(ctx.tenant)
    version_id = uuid4()
    async with uow(ctx.tenant) as tx:
        item = await _find(tx.session, standard_id, lock=True)
        await _owner_guard(ctx, DRAFT, item)
        if any(v.status == "draft" for v in item.versions):
            raise DraftExists(facts={"standard_id": str(standard_id)})
        source = _shown(item, on)
        if source is None:
            raise NoCurrentVersion(facts={"standard_id": str(standard_id)})
        number = max(v.version for v in item.versions) + 1
        tx.session.add(
            item.family.version(
                id=version_id,
                tenant_id=ctx.tenant_id,
                parent_id=standard_id,
                version=number,
                payload=source.payload,
                payload_hash=source.payload_hash,
                change_summary=None,
                drafted_from_version_id=source.id,
                drafted_by=ctx.user_id,
            )
        )
        tx.record(
            item.family.drafted,
            target=Target(item.family.version_subject, version_id),
            after=Ref(standard=standard_id, version=number, drafted_from=source.id),
        )
    return await _version_view(ctx, standard_id, version_id)


async def edit_draft(
    ctx: AuthContext,
    standard_id: UUID,
    version_id: UUID,
    body: StandardDraftPatchIn,
    if_match: int,
) -> StandardVersionOut:
    await _human(ctx, DRAFT, standard_id)
    async with uow(ctx.tenant) as tx:
        item = await _find(tx.session, standard_id, lock=True)
        await _owner_guard(ctx, DRAFT, item)
        version = await _locked_draft(tx.session, item, version_id, if_match)
        payload = validate_payload(item.parent.kind, body.payload.model_dump(mode="json"))
        digest = payload_hash(payload)
        await tx.session.execute(
            update(item.family.version)
            .where(item.family.version.id == version_id)
            .values(
                payload=payload,
                payload_hash=digest,
                change_summary=body.change_summary,
                row_version=version.row_version + 1,
            )
        )
        tx.record(
            item.family.edited,
            target=Target(item.family.version_subject, version_id),
            # Audit refs take the bare SHA-256 (64 hex), not the stored "sha256:" form.
            before=Ref(payload=version.payload_hash.removeprefix("sha256:")),
            after=Ref(payload=digest.removeprefix("sha256:")),
        )
    return await _version_view(ctx, standard_id, version_id)


async def discard_draft(
    ctx: AuthContext, standard_id: UUID, version_id: UUID, if_match: int
) -> StandardVersionSummaryOut:
    await _human(ctx, DRAFT, standard_id)
    async with uow(ctx.tenant) as tx:
        item = await _find(tx.session, standard_id, lock=True)
        await _owner_guard(ctx, DRAFT, item)
        version = await _locked_draft(tx.session, item, version_id, if_match)
        await tx.session.execute(
            update(item.family.version)
            .where(item.family.version.id == version_id)
            .values(status="discarded", row_version=version.row_version + 1)
        )
        tx.record(
            item.family.discarded,
            target=Target(item.family.version_subject, version_id),
            after=Ref(standard=standard_id, version=version.version),
        )
    on = await today(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    found = next(v for v in item.versions if v.id == version_id)
    return _summary(found, in_effect(item.versions, on), await _names([item]))


def _day(on: date) -> int:
    """A date as an audit ref (integers only): 2026-10-01 is 20261001."""
    return on.year * 10000 + on.month * 100 + on.day


async def publish_version(
    ctx: AuthContext,
    standard_id: UUID,
    version_id: UUID,
    body: StandardPublishIn,
    if_match: int,
) -> StandardVersionOut:
    await _human(ctx, PUBLISH, standard_id)
    on = await today(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        item = await _find(tx.session, standard_id, lock=True)
        await _owner_guard(ctx, PUBLISH, item)
        version = await _locked_draft(tx.session, item, version_id, if_match)
        if body.effective_from < on:
            raise EffectiveFromBackdated(facts={"field": "effective_from"})
        published = [
            v.effective_from
            for v in item.versions
            if v.status == "published" and v.effective_from is not None
        ]
        if published and body.effective_from <= max(published):
            raise EffectiveFromNotAfterCurrent(facts={"field": "effective_from"})
        validate_payload(item.parent.kind, version.payload)
        await tx.session.execute(
            update(item.family.version)
            .where(item.family.version.id == version_id)
            .values(
                status="published",
                effective_from=body.effective_from,
                change_summary=body.change_summary,
                published_by=ctx.user_id,
                published_actor_kind="human",
                published_at=func.abacus_now(),
                row_version=version.row_version + 1,
            )
        )
        tx.record(
            item.family.published,
            target=Target(item.family.version_subject, version_id),
            after=Ref(
                standard=standard_id,
                version=version.version,
                effective_from=_day(body.effective_from),
            ),
        )
        event: DomainEvent = item.family.event(
            standard_id=standard_id,
            version_id=version_id,
            version=version.version,
            by_user=ctx.user_id,
        )
        tx.emit(event)
    return await _version_view(ctx, standard_id, version_id)


# --- examples (KNW-04 a, e to h) -----------------------------------------------------------------

_EXAMPLES: dict[str, ExamplesProvider] = {}


def register_standard_examples(kind: StandardKind, provider: ExamplesProvider) -> None:
    """A consumer's examples for a kind (C-01 for AJE thresholds, A-04 for materiality), once.
    The provider filters by `visible()`: a walled client's row is absent, with no count."""
    known = _EXAMPLES.get(kind)
    if known is not None and known is not provider:
        raise ValueError(f"standard kind {kind!r} already has an examples provider")
    _EXAMPLES[kind] = provider


def _example_out(row: ExampleRow) -> StandardExampleRowOut:
    return StandardExampleRowOut(
        client_id=row.client_id,
        client_name=row.client_name,
        label=row.label,
        amount_usd=row.amount_usd,
        outcome=row.outcome,
        detail=row.detail,
        route=row.route,
    )


async def examples(ctx: AuthContext, standard_id: UUID, period: str | None) -> StandardExamplesOut:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        item = await _find(session, standard_id)
    provider = _EXAMPLES.get(item.parent.kind)
    if provider is None:
        return StandardExamplesOut(
            standard_id=standard_id, period=period, provider_registered=False, rows=[]
        )
    rows = await provider(ctx, period)
    return StandardExamplesOut(
        standard_id=standard_id,
        period=period,
        provider_registered=True,
        rows=[_example_out(r) for r in rows],
    )


# --- the C21 part B module API -------------------------------------------------------------------


async def current_version(tenant_id: UUID, standard_key: str, as_of: date) -> PolicyRef:
    """The version of a standard in effect on `as_of` (its latest published `effective_from` on
    or before it). None published by then, or no such standard: `LookupError`."""
    tenant = TenantContext(tenant_id, "system", "standards:current_version")
    async with tenant_session(tenant) as session:
        for family in (_FIRM, _THRESHOLD):
            parent = (
                await session.execute(
                    select(family.parent).where(family.parent.key == standard_key)
                )
            ).scalar_one_or_none()
            if parent is not None:
                found = in_effect(await _versions(session, family, parent.id), as_of)
                if found is None:
                    break
                return PolicyRef(
                    standard_key=parent.key,
                    version_id=found.id,
                    version=found.version,
                    name=parent.name,
                )
    raise LookupError(standard_key)


async def current_version_of_kind(
    tenant_id: UUID, kind: StandardKind, as_of: date
) -> PolicyRef | None:
    """T-02-T10: the version in effect on `as_of` of the firm's standard of `kind` (the
    return-approval policy, BH-TAX-02, is one per firm); the first by key when there are more.
    None when nothing of the kind is in effect."""
    tenant = TenantContext(tenant_id, "system", "standards:current_version_of_kind")
    family = _family(kind)
    async with tenant_session(tenant) as session:
        parents = (
            await session.execute(
                select(family.parent).where(family.parent.kind == kind).order_by(family.parent.key)
            )
        ).scalars()
        for parent in parents:
            found = in_effect(await _versions(session, family, parent.id), as_of)
            if found is not None:
                return PolicyRef(
                    standard_key=parent.key,
                    version_id=found.id,
                    version=found.version,
                    name=parent.name,
                )
    return None


# --- KNW-01 and C15 registrations ----------------------------------------------------------------


@dataclass(frozen=True)
class StandardCard:
    """What KNW-01's `firm_standards` category needs of one standard."""

    id: UUID
    title: str
    status: str
    version: int | None
    effective_from: date | None
    owner_user_id: UUID
    updated_at: datetime


async def standard_cards(ctx: AuthContext) -> list[StandardCard]:
    """One card per standard with a published version, in effect or not yet (drafts are the
    owner's business on KNW-04, not catalog cards)."""
    on = await today(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        loaded = await _all(session, None)
    cards: list[StandardCard] = []
    for item in loaded:
        shown = _shown(item, on)
        if shown is None:
            continue
        cards.append(
            StandardCard(
                id=item.parent.id,
                title=item.parent.name,
                status="published",
                version=shown.version,
                effective_from=shown.effective_from,
                owner_user_id=item.parent.owner_id,
                updated_at=shown.published_at or item.parent.created_at,
            )
        )
    return cards


@dataclass(frozen=True)
class StandardChange:
    version_id: UUID
    standard_id: UUID
    title: str
    version: int
    at: datetime
    by_user: UUID


async def standard_changes(ctx: AuthContext) -> list[StandardChange]:
    """Every published version, newest first: KNW-01's change log."""
    async with tenant_session(ctx.tenant) as session:
        loaded = await _all(session, None)
    changes = [
        StandardChange(
            version_id=v.id,
            standard_id=item.parent.id,
            title=item.parent.name,
            version=v.version,
            at=v.published_at,
            by_user=v.published_by,
        )
        for item in loaded
        for v in item.versions
        if v.status == "published" and v.published_at is not None and v.published_by is not None
    ]
    return sorted(changes, key=lambda c: c.at, reverse=True)


async def search_metadata(tenant: TenantContext, standard_id: UUID) -> tuple[str, str] | None:
    """C15 metadata only: the name and kind, never a value."""
    async with tenant_session(tenant) as session:
        try:
            item = await _find(session, standard_id)
        except NotFound:
            return None
    return item.parent.name, item.parent.kind


__all__ = [
    "DraftExists",
    "EffectiveFromBackdated",
    "EffectiveFromNotAfterCurrent",
    "NoCurrentVersion",
    "NotDraft",
    "NotStandardOwner",
    "OwnerNotPartner",
    "PayloadInvalid",
    "StaleVersion",
    "StandardKeyTaken",
    "assign_owner",
    "create_standard",
    "current_version",
    "current_version_of_kind",
    "diff_cells",
    "discard_draft",
    "draft_version",
    "edit_draft",
    "examples",
    "in_effect",
    "list_standards",
    "publish_version",
    "register_standard_examples",
    "standard_cards",
    "standard_changes",
    "standard_detail",
    "status_of",
    "validate_payload",
    "version_detail",
    "version_diff",
]
