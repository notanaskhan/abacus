"""A-04-T13: the risk register AUD-05 and AUD-08 read (A-04 §3.4 AC4.1-AC4.7; SPEC-620;
DEC-1951).

0613's `risk_register_rows` on the audit work item (SPEC-300's `risks` keeps its name, DEC-1866)
and their `risk_linkages`. A person creates and edits a risk; every field write goes through
`review.api.record_value` (the field history AUD-08 b's versions read), and the row carries the
new content hash and version. Code computes everything the register shows (ADR-050):

- RMM from the firm's K-02 `rmm_matrix` in effect, stamped with its version (AC4.2);
- the tally from the rows (AC4.1: risks, significant with the proposed count, presumed fraud,
  high RMM, unaddressed, the partner's approval);
- the linkage matrix: live links and suggested ones; a workpaper target not yet registered as an
  audit section renders as planned (AC4.6);
- the coverage check: the trial balance's material areas against the assessed risks (AC4.7).

Management override is never rebuttable: 422 `presumption_not_rebuttable` here and a CHECK in
0613 (AC4.5). Approving is the partner's act on the `significant_risk` card (A-04-T18), never
here; the agent's drafts arrive as suggestions a person adopts through the `risk` applier.

A drafted response (A-04-T24; DEC-2480) is a suggestion on the risk's `response` field, one section
code from `response_targets`. While it waits, the linkage matrix and the drawer read it from the
suggestion, so no agent writes `risk_linkages`; adopting it writes the live link, naming the
suggestion. Model text that is not a registered section is never drawn and never adopted.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import FetchedValue, func, insert, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Text

from abacus.kernel.clock import now, today
from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.agents.api import AdoptedValue, PendingSuggestion, pending_suggestions
from abacus.modules.assurance.events import RiskRegisterApproved
from abacus.modules.assurance.sections import registered_sections
from abacus.modules.engagements.api import assurance_item_id, get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, authorise, names_of
from abacus.modules.ledger.api import engagement_trial_balances, trial_balance_view
from abacus.modules.methodology.api import rmm_matrix_for, version_steps
from abacus.modules.review.api import (
    AppliedDecision,
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    Json,
    content_hash,
    field_timeline,
    raise_decision_card,
    record_value,
    register_decision_kind,
)

TARGET: Final = "risk"  # the field history and the suggestion target (AC4.7)
# The trail's target type: SPEC-300's `risk` already names fieldwork's rows (DEC-1866).
AUDIT_TARGET: Final = "risk_register_row"
Rating = Literal["low", "moderate", "high"]
ControlRating = Literal["low", "moderate", "high", "max"]
FACTORS: Final = ("susceptibility_to_fraud", "change", "complexity", "subjectivity", "uncertainty")
_PLAIN_NOTE: Final = "Entered on the risk register (AUD-08)"
_CODE: Final = re.compile(r"^R([1-9][0-9]{0,2})$")
_AREA: Final = re.compile(r"[a-z0-9]+")
# The fields a person edits (and the agent suggests), in the history's keys.
FIELDS: Final = (
    "assertions",
    "inherent_risk",
    "control_risk",
    "inherent_factors",
    "rationale",
    "significance",
    "fraud",
)
# A drafted response lands as a live link, so it has a suggestion but no field history (A-04-T24).
RESPONSE_FIELD: Final = "response"
RESPONSE_KIND: Final = "workpaper"
ADOPTABLE_FIELDS: Final = (*FIELDS, RESPONSE_FIELD)
_RESPONSE_SCREENS: Final = ("AUD-", "EBP-")


class RiskRow(Base):
    __tablename__ = "risk_register_rows"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    code: Mapped[str]
    level: Mapped[str]
    area_key: Mapped[str]
    area_label: Mapped[str]
    assertions: Mapped[list[str]] = mapped_column(ARRAY(Text))
    inherent_risk: Mapped[str]
    control_risk: Mapped[str]
    rmm: Mapped[str]
    rmm_policy_version_id: Mapped[UUID | None]
    significance: Mapped[str]
    fraud: Mapped[str]
    presumption_kind: Mapped[str]
    inherent_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # Any: JSON
    rationale: Mapped[str | None]
    status: Mapped[str]
    approved_card_id: Mapped[UUID | None]
    content_hash: Mapped[str]
    version_no: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Linkage(Base):
    __tablename__ = "risk_linkages"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    risk_id: Mapped[UUID]
    target_kind: Mapped[str]
    target_ref: Mapped[str]
    state: Mapped[str]
    suggestion_id: Mapped[UUID | None]
    removed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


# --- errors --------------------------------------------------------------------------------------


class PresumptionNotRebuttable(DomainInvalid):
    """Management override of controls is presumed and never rebuttable (AU-C 240; AC4.5)."""

    code = "presumption_not_rebuttable"


class RiskMoved(DomainConflict):
    """The risk changed since the caller read it."""

    code = "version_conflict"


class RiskInvalid(DomainInvalid):
    code = "risk_invalid"


class RmmMatrixMissing(DomainConflict):
    """The firm has no RMM matrix in effect (K-02 `rmm_matrix`)."""

    code = "rmm_matrix_missing"


class AlreadyLinked(DomainConflict):
    code = "already_linked"


class NotLinked(DomainConflict):
    code = "not_linked"


# --- facts ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Edit:
    """A person's edit; None leaves a field as it is."""

    assertions: Sequence[str] | None = None
    inherent_risk: Rating | None = None
    control_risk: ControlRating | None = None
    inherent_factors: Sequence[tuple[str, Rating]] | None = None
    rationale: str | None = None
    significance: Literal["proposed", "not_significant"] | None = None
    fraud: Literal["rebuttal_proposed"] | None = None


@dataclass(frozen=True)
class Tally:
    risks: int
    significant: int
    significant_proposed: int
    fraud: int
    high_rmm: int
    unaddressed: int
    ep_approval: Literal["pending", "approved", "changed"]


@dataclass(frozen=True)
class Register:
    rows: list[RiskRow]
    linked: frozenset[UUID]
    tally: Tally
    register_hash: str
    actions: list[str]


@dataclass(frozen=True)
class VersionFact:
    version_no: int
    at: datetime
    by_name: str


@dataclass(frozen=True)
class SuggestedResponse:
    suggestion_id: UUID
    target_ref: str
    citations: int
    version: int


@dataclass(frozen=True)
class SuggestedRationale:
    suggestion_id: UUID
    text: str
    citations: int
    version: int


@dataclass(frozen=True)
class Drawer:
    risk: RiskRow
    linked: bool
    citation_ids: tuple[UUID, ...]  # the adopted rationale's
    versions: list[VersionFact]
    actions: list[str]
    response_suggestion: SuggestedResponse | None = None
    rationale_suggestion: SuggestedRationale | None = None


@dataclass(frozen=True)
class LinkTarget:
    kind: str
    ref: str
    label: str
    registered: bool


@dataclass(frozen=True)
class LinkageMatrix:
    codes: list[str]
    targets: list[LinkTarget]
    cells: list[tuple[str, str, str]]  # risk code, target ref, state
    # (risk code, target ref) -> the pending suggestion a `suggested` cell draws (A-04-T24)
    suggestions: dict[tuple[str, str], UUID] = field(default_factory=dict[tuple[str, str], UUID])


@dataclass(frozen=True)
class Coverage:
    material_areas: int
    covered: int
    unaddressed_codes: list[str]


# --- pure helpers (code computes; ADR-050) -------------------------------------------------------


def area_key(label: str) -> str:
    """ "Contributions — participant & employer" -> "contributions_participant_employer"."""
    key = "_".join(_AREA.findall(label.casefold()))[:64]
    if not key or not key[0].isalpha():
        raise RiskInvalid(facts={"field": "area_label"})
    return key


def tally(rows: Sequence[RiskRow], linked: frozenset[UUID]) -> Tally:
    """AC4.1: counted from the rows. Significant counts mandatory, proposed and approved (R1 and
    R3 for Northwind: 2, of which 1 proposed); presumed fraud only (R5's proposed rebuttal is not
    a fraud risk count); unaddressed is a risk with no live response."""
    statuses = {r.status for r in rows}
    approval: Literal["pending", "approved", "changed"] = "pending"
    if rows and statuses == {"ep_approved"}:
        approval = "approved"
    elif "revised" in statuses:
        approval = "changed"
    return Tally(
        risks=len(rows),
        significant=sum(
            1 for r in rows if r.significance in ("mandatory", "proposed", "approved")
        ),
        significant_proposed=sum(1 for r in rows if r.significance == "proposed"),
        fraud=sum(1 for r in rows if r.fraud == "presumed"),
        high_rmm=sum(1 for r in rows if r.rmm == "high"),
        unaddressed=sum(1 for r in rows if r.id not in linked),
        ep_approval=approval,
    )


def _row_hash(r: RiskRow) -> str:
    return content_hash(
        cast(
            Json,
            {
                "code": r.code,
                "level": r.level,
                "area_key": r.area_key,
                "assertions": sorted(r.assertions),
                "inherent_risk": r.inherent_risk,
                "control_risk": r.control_risk,
                "rmm": r.rmm,
                "significance": r.significance,
                "fraud": r.fraud,
                "presumption_kind": r.presumption_kind,
                "inherent_factors": sorted(
                    (str(f["factor"]), str(f["rating"])) for f in r.inherent_factors
                ),
                "rationale": r.rationale or "",
            },
        )
    )


def register_hash(rows: Sequence[RiskRow]) -> str:
    """What the partner approves (A-04-T18): the rows' hashes in code order."""
    return content_hash(
        cast(Json, [[r.code, r.content_hash] for r in sorted(rows, key=lambda r: _number(r.code))])
    )


def _number(code: str) -> int:
    found = _CODE.fullmatch(code)
    return int(found.group(1)) if found else 0


def _factors_json(factors: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:  # Any: JSON
    seen: set[str] = set()
    out: list[dict[str, Any]] = []  # Any: JSON
    for factor, rating in factors:
        if factor not in FACTORS or rating not in ("low", "moderate", "high") or factor in seen:
            raise RiskInvalid(facts={"field": "inherent_factors"})
        seen.add(factor)
        out.append({"factor": factor, "rating": rating})
    return sorted(out, key=lambda f: FACTORS.index(str(f["factor"])))


def _text(value: str | None) -> dict[str, object]:
    return {"t": "text", "v": value}


def _field_value(row: RiskRow, key: str) -> dict[str, object]:
    if key == "assertions":
        return _text(",".join(row.assertions))
    if key == "inherent_factors":
        return _text(",".join(f"{f['factor']}:{f['rating']}" for f in row.inherent_factors))
    return _text(cast(str | None, getattr(row, key)))


# --- reads ---------------------------------------------------------------------------------------


async def _work_item(tenant: TenantContext, engagement_id: UUID) -> UUID:
    found = await assurance_item_id(tenant, engagement_id)
    if found is None:
        raise NotFound("risk")
    return found


async def rows_of(tenant: TenantContext, work_item_id: UUID) -> list[RiskRow]:
    """The register's rows (G4's facts read them, A-04-T18)."""
    return await _rows(tenant, work_item_id)


async def _rows(tenant: TenantContext, work_item_id: UUID) -> list[RiskRow]:
    async with tenant_session(tenant) as session:
        rows = list(
            (
                await session.execute(select(RiskRow).where(RiskRow.work_item_id == work_item_id))
            ).scalars()
        )
    return sorted(rows, key=lambda r: _number(r.code))


async def _links(tenant: TenantContext, work_item_id: UUID) -> list[Linkage]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(Linkage)
                    .where(Linkage.work_item_id == work_item_id, Linkage.removed_at.is_(None))
                    .order_by(Linkage.created_at, Linkage.id)
                )
            ).scalars()
        )


async def _actions(ctx: AuthContext, engagement_id: UUID) -> list[str]:
    ref = await get_ref(ctx, engagement_id)
    can = await allowed_actions(
        ctx,
        ref.resource(),
        ("risk.edit", "risk.link", "risk.route_for_approval", "workpaper.draft"),
    )
    return [a for a in ("risk.edit", "risk.link", "risk.route_for_approval") if a in can]


async def linked_refs(tenant: TenantContext, work_item_id: UUID) -> dict[UUID, list[str]]:
    """Each risk's live responses, for the risk mode's cells (A-04-T24)."""
    refs: dict[UUID, list[str]] = {}
    for link in await _links(tenant, work_item_id):
        if link.state == "linked":
            refs.setdefault(link.risk_id, []).append(link.target_ref)
    return refs


async def linked_ids(tenant: TenantContext, work_item_id: UUID) -> list[UUID]:
    """The risks with a live response (the risk mode's coverage facts read them, A-04-T24)."""
    return [link.risk_id for link in await _links(tenant, work_item_id) if link.state == "linked"]


async def register(ctx: AuthContext, engagement_id: UUID) -> Register:
    """`GET …/risks/register` (the route authorised `risk.read` and the flag)."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    rows = await _rows(ctx.tenant, work_item)
    linked = frozenset(
        link.risk_id for link in await _links(ctx.tenant, work_item) if link.state == "linked"
    )
    return Register(
        rows, linked, tally(rows, linked), register_hash(rows), await _actions(ctx, engagement_id)
    )


async def _row(tenant: TenantContext, engagement_id: UUID, risk_id: UUID) -> RiskRow:
    work_item = await _work_item(tenant, engagement_id)
    async with tenant_session(tenant) as session:
        found = await session.get(RiskRow, risk_id)
    if found is None or found.work_item_id != work_item:
        raise NotFound("risk")
    return found


async def drawer(ctx: AuthContext, engagement_id: UUID, risk_id: UUID) -> Drawer:
    """`GET …/risks/{rid}` (AC4.3): the row, its rationale's citations and the versions."""
    row = await _row(ctx.tenant, engagement_id, risk_id)
    links = await _links(ctx.tenant, row.work_item_id)
    history = {key: await field_timeline(ctx.tenant, TARGET, row.id, key) for key in FIELDS}
    rationale = history["rationale"]
    latest = rationale[-1] if rationale else None
    # A version is a moment the row changed: each distinct write time across the fields, in order.
    moments = sorted(
        {
            (v.created_at, v.actor_kind, v.actor_id, v.on_behalf_of_user_id)
            for vs in history.values()
            for v in vs
        }
    )
    people = await names_of(
        sorted(
            {UUID(m[2]) for m in moments if m[1] == "human"}
            | {m[3] for m in moments if m[3] is not None}
        )
    )
    versions: list[VersionFact] = []
    last: datetime | None = None
    for at, kind, actor, behalf in moments:
        if last is not None and (at - last).total_seconds() < 1:
            continue  # one save writes several fields
        last = at
        if kind == "human":
            name = people.get(UUID(actor), "")
        else:
            name = f"{people.get(behalf, '') if behalf else ''} via Agent".strip()
        versions.append(VersionFact(len(versions) + 1, at, name))
    pending = await _pending_of(ctx, engagement_id, RESPONSE_FIELD)
    live = {link.target_ref.upper() for link in links if link.risk_id == row.id}
    response = next(
        (
            SuggestedResponse(p.id, ref, len(p.citation_ids), p.version)
            for p in pending
            if p.target_id == row.id
            and (ref := response_target(p.value)) is not None
            and ref.upper() not in live
        ),
        None,
    )
    # Pending, not the field's history: an adopted value is the person's and waits on nobody. The
    # store reads oldest first; a re-draft is the one to decide (DEC-2481).
    rationales = [
        p for p in await _pending_of(ctx, engagement_id, "rationale") if p.target_id == row.id
    ]
    return Drawer(
        risk=row,
        response_suggestion=response,
        rationale_suggestion=SuggestedRationale(
            rationales[-1].id,
            rationales[-1].value,
            len(rationales[-1].citation_ids),
            rationales[-1].version,
        )
        if rationales
        else None,
        linked=any(link.risk_id == row.id and link.state == "linked" for link in links),
        citation_ids=latest.citation_ids if latest is not None else (),
        versions=versions,
        actions=await _actions(ctx, engagement_id),
    )


# --- writes --------------------------------------------------------------------------------------


async def _rmm(tenant: TenantContext, ir: str, cr: str) -> tuple[str, UUID]:
    try:
        found = await rmm_matrix_for(
            tenant.tenant_id,
            inherent_risk=cast(Rating, ir),
            control_risk=cast(ControlRating, cr),
            as_of=await today(tenant),
        )
    except LookupError:
        raise RmmMatrixMissing from None
    return found.rmm, found.policy.version_id


async def _record(
    tx: UnitOfWork,
    row: RiskRow,
    keys: Sequence[str],
    *,
    note: str,
    adopted: AdoptedValue | None = None,
) -> None:
    for key in keys:
        if adopted is not None and adopted.field_key == key:
            await record_value(
                tx,
                engagement_id=row.engagement_id,
                target_type=TARGET,
                target_id=row.id,
                field_key=key,
                value=adopted.value,
                value_source=adopted.value_source,
                cause=adopted.cause,
                suggestion_id=adopted.suggestion_id,
                checkpoint_id=adopted.checkpoint_id,
                citation_ids=adopted.citation_ids,
                citation_note=adopted.citation_note,
            )
            continue
        await record_value(
            tx,
            engagement_id=row.engagement_id,
            target_type=TARGET,
            target_id=row.id,
            field_key=key,
            value=_field_value(row, key),
            value_source="human",
            cause="edit",
            citation_note=note,
        )


@dataclass(frozen=True)
class NewRisk:
    level: Literal["financial_statement", "assertion"]
    area_label: str
    assertions: Sequence[str]
    inherent_risk: Rating
    control_risk: ControlRating
    presumption_kind: Literal["none", "management_override", "revenue_recognition"]
    inherent_factors: Sequence[tuple[str, Rating]]
    rationale: str | None


async def create(ctx: AuthContext, engagement_id: UUID, new: NewRisk) -> RiskRow:
    """`POST …/risks/register` (the route authorised `risk.edit`): the next code (R1, R2…), RMM
    from the firm's matrix, every field through the history. A presumed fraud risk (management
    override, revenue recognition) reads Presumed; management override is significant by rule
    (`mandatory`, AU-C 240), and the team proposes the others to the partner (AUD-08 a: R3)."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    rmm, matrix = await _rmm(ctx.tenant, new.inherent_risk, new.control_risk)
    presumed = new.presumption_kind != "none"
    override = new.presumption_kind == "management_override"
    try:
        async with uow(ctx.tenant) as tx:
            await lock_ref(tx, engagement_id)
            codes = (
                await tx.session.execute(
                    select(RiskRow.code).where(RiskRow.work_item_id == work_item)
                )
            ).scalars()
            code = f"R{max((_number(c) for c in codes), default=0) + 1}"
            draft = RiskRow(
                code=code,
                level=new.level,
                area_key=area_key(new.area_label),
                area_label=new.area_label.strip(),
                assertions=sorted(set(new.assertions)),
                inherent_risk=new.inherent_risk,
                control_risk=new.control_risk,
                rmm=rmm,
                significance="mandatory" if override else "none",
                fraud="presumed" if presumed else "none",
                presumption_kind=new.presumption_kind,
                inherent_factors=_factors_json(new.inherent_factors),
                rationale=(new.rationale or "").strip() or None,
            )
            risk_id = (
                await tx.session.execute(
                    insert(RiskRow)
                    .values(
                        tenant_id=ctx.tenant_id,
                        engagement_id=engagement_id,
                        work_item_id=work_item,
                        code=draft.code,
                        level=draft.level,
                        area_key=draft.area_key,
                        area_label=draft.area_label,
                        assertions=draft.assertions,
                        inherent_risk=draft.inherent_risk,
                        control_risk=draft.control_risk,
                        rmm=draft.rmm,
                        rmm_policy_version_id=matrix,
                        significance=draft.significance,
                        fraud=draft.fraud,
                        presumption_kind=draft.presumption_kind,
                        inherent_factors=draft.inherent_factors,
                        rationale=draft.rationale,
                        status="draft",
                        content_hash=_row_hash(draft),
                        version_no=1,
                    )
                    .returning(RiskRow.id)
                )
            ).scalar_one()
            stored = await tx.session.get(RiskRow, risk_id)
            if stored is None:
                raise NotFound("risk")
            await _record(tx, stored, FIELDS, note=_PLAIN_NOTE)
            tx.record(
                "risk.created",
                target=Target(AUDIT_TARGET, risk_id),
                after=Ref(version=1, rmm_policy=matrix),
                scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
            )
    except IntegrityError as exc:
        if "risk_register_rows_tenant_id_work_item_id_code_key" in str(exc.orig):
            raise RiskMoved from None
        raise
    return await _row(ctx.tenant, engagement_id, risk_id)


async def _apply(
    tx: UnitOfWork,
    ctx: AuthContext,
    row: RiskRow,
    edit: Edit,
    *,
    expected_version: int | None,
    note: str,
    adopted: AdoptedValue | None = None,
) -> RiskRow:
    """One edit, under the row lock: the presumption rule, RMM by code, the fields' history, the
    row's new hash and version (AC4.2, AC4.5)."""
    locked = (
        await tx.session.execute(select(RiskRow).where(RiskRow.id == row.id).with_for_update())
    ).scalar_one()
    if expected_version is not None and locked.version_no != expected_version:
        raise RiskMoved(facts={"current": locked.version_no})
    if edit.fraud == "rebuttal_proposed":
        if locked.presumption_kind == "management_override":
            raise PresumptionNotRebuttable
        if locked.fraud != "presumed":
            raise RiskInvalid(facts={"field": "fraud"})
    if edit.significance is not None and locked.significance == "mandatory":
        raise RiskInvalid(facts={"field": "significance"})  # a presumption stays significant
    changed: list[str] = []
    if edit.assertions is not None and sorted(set(edit.assertions)) != sorted(locked.assertions):
        locked.assertions = sorted(set(edit.assertions))
        changed.append("assertions")
    if edit.inherent_risk is not None and edit.inherent_risk != locked.inherent_risk:
        locked.inherent_risk = edit.inherent_risk
        changed.append("inherent_risk")
    if edit.control_risk is not None and edit.control_risk != locked.control_risk:
        locked.control_risk = edit.control_risk
        changed.append("control_risk")
    if edit.inherent_factors is not None:
        factors = _factors_json(edit.inherent_factors)
        if factors != locked.inherent_factors:
            locked.inherent_factors = factors
            changed.append("inherent_factors")
    if edit.rationale is not None and (edit.rationale.strip() or None) != locked.rationale:
        locked.rationale = edit.rationale.strip() or None
        changed.append("rationale")
    if edit.significance is not None and edit.significance != locked.significance:
        locked.significance = edit.significance
        changed.append("significance")
    if edit.fraud is not None and edit.fraud != locked.fraud:
        locked.fraud = edit.fraud
        changed.append("fraud")
    if not changed:
        return locked
    if {"inherent_risk", "control_risk"} & set(changed):
        locked.rmm, locked.rmm_policy_version_id = await _rmm(
            ctx.tenant, locked.inherent_risk, locked.control_risk
        )
    if locked.status == "ep_approved":
        locked.status = "revised"  # the partner's approval no longer covers this row (A-04-T18)
    locked.version_no += 1
    locked.content_hash = _row_hash(locked)
    locked.updated_at = await now(ctx.tenant)
    await _record(tx, locked, changed, note=note, adopted=adopted)
    tx.record(
        "risk.updated",
        target=Target(AUDIT_TARGET, locked.id),
        after=Ref(version=locked.version_no, fields=len(changed)),
        scope=Scope(engagement_id=locked.engagement_id, work_item_id=locked.work_item_id),
    )
    if edit.significance == "proposed":
        tx.record("risk.significance_proposed", target=Target(AUDIT_TARGET, locked.id))
    if edit.fraud == "rebuttal_proposed":
        tx.record("risk.rebuttal_proposed", target=Target(AUDIT_TARGET, locked.id))
    return locked


async def edit(
    ctx: AuthContext,
    engagement_id: UUID,
    risk_id: UUID,
    change: Edit,
    *,
    expected_version: int,
    reason: str | None,
) -> RiskRow:
    """`PATCH …/risks/{rid}` (the route authorised `risk.edit`)."""
    row = await _row(ctx.tenant, engagement_id, risk_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        await _apply(
            tx,
            ctx,
            row,
            change,
            expected_version=expected_version,
            note=(reason or "").strip() or _PLAIN_NOTE,
        )
    return await _row(ctx.tenant, engagement_id, risk_id)


def _edit_of(field_key: str, value: dict[str, object]) -> Edit:
    raw = value.get("v")
    text = raw if isinstance(raw, str) else None
    if field_key == "rationale":
        return Edit(rationale=text or "")
    if field_key == "assertions":
        return Edit(assertions=[a for a in (text or "").split(",") if a])
    if field_key == "inherent_factors":
        pairs = [p.split(":", 1) for p in (text or "").split(",") if ":" in p]
        return Edit(inherent_factors=[(f, cast(Rating, r)) for f, r in pairs])
    if field_key in ("inherent_risk", "control_risk", "significance", "fraud") and text:
        return Edit(**{field_key: text})  # pyright: ignore[reportArgumentType] -- checked by the row
    raise RiskInvalid(facts={"field": "field_key"})


async def apply_risk_suggestion(tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue) -> None:
    """The `risk` suggestion applier (AC4.7): a person adopted (or edited and adopted) the agent's
    value for one field; it writes as an edit, in the adopting unit of work. A response writes the
    live link instead (AC4.6): it has no field history, and the row's hash doesn't cover links."""
    if adopted.field_key not in ADOPTABLE_FIELDS:
        raise RiskInvalid(facts={"field": "field_key"})
    found = await tx.session.get(RiskRow, adopted.target_id)
    if found is None:
        raise NotFound("risk")
    ref = await lock_ref(tx, found.engagement_id)
    if adopted.field_key == RESPONSE_FIELD:
        await authorise(ctx, "risk.link", ref.resource())
        target = response_target(str(adopted.value.get("v") or ""))
        if target is None:
            raise RiskInvalid(facts={"field": RESPONSE_FIELD})
        await _write_link(
            tx, ctx, found, RESPONSE_KIND, target, suggestion_id=adopted.suggestion_id
        )
        return
    await authorise(ctx, "risk.edit", ref.resource())
    await _apply(
        tx,
        ctx,
        found,
        _edit_of(adopted.field_key, adopted.value),
        expected_version=None,
        note=adopted.citation_note or "Adopted from the agent's suggestion",
        adopted=adopted,
    )


async def risk_engagement(tenant: TenantContext, risk_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.get(RiskRow, risk_id)
    return None if found is None else found.engagement_id


# --- linkage -------------------------------------------------------------------------------------


def _registered(kind: str, ref: str) -> bool:
    """A program step or procedure target always resolves; a workpaper target is planned until
    its owner registers it as an audit section with a built screen (A-05-T09)."""
    if kind != "workpaper":
        return True
    wanted = ref.upper()
    return any(s.route.upper() == wanted and s.link == "live" for s in registered_sections())


def response_targets() -> list[str]:
    """What a drafted response may name: the registered audit sections' audit and EBP screens."""
    return sorted(
        {s.route for s in registered_sections() if s.route.startswith(_RESPONSE_SCREENS)}
    )


def response_target(value: str) -> str | None:
    """The section a drafted (or edited) response names, or None: free text is never a target."""
    wanted = value.strip().upper()
    return next((r for r in response_targets() if r.upper() == wanted), None)


async def _pending_of(
    ctx: AuthContext, engagement_id: UUID, field_key: str
) -> list[PendingSuggestion]:
    """A suggestion is a proposal: `proposal.read` is its read (`risk.read` alone sees none)."""
    ref = await get_ref(ctx, engagement_id)
    if "proposal.read" not in await allowed_actions(ctx, ref.resource(), ("proposal.read",)):
        return []
    return await pending_suggestions(ctx.tenant, engagement_id, TARGET, field_key)


async def linkage(ctx: AuthContext, engagement_id: UUID) -> LinkageMatrix:
    """`GET …/risks/linkage` (AC4.6): risks against their responses, live and suggested."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    rows = await _rows(ctx.tenant, work_item)
    by_id = {r.id: r for r in rows}
    links = [link for link in await _links(ctx.tenant, work_item) if link.risk_id in by_id]
    live = {(link.risk_id, link.target_ref.upper()) for link in links}
    suggestions: dict[tuple[str, str], UUID] = {}
    suggested: list[tuple[str, str]] = []
    for pending in await _pending_of(ctx, engagement_id, RESPONSE_FIELD):
        ref = response_target(pending.value)
        if (
            ref is None
            or pending.target_id not in by_id
            or (pending.target_id, ref.upper()) in live
        ):
            continue
        key = (by_id[pending.target_id].code, ref)
        if key not in suggestions:
            suggested.append(key)
            suggestions[key] = pending.id
    targets: dict[tuple[str, str], LinkTarget] = {}
    for link in links:
        key = (link.target_kind, link.target_ref)
        if key not in targets:
            targets[key] = LinkTarget(
                link.target_kind,
                link.target_ref,
                link.target_ref,
                _registered(link.target_kind, link.target_ref),
            )
    for _, ref in suggested:
        targets.setdefault(
            (RESPONSE_KIND, ref),
            LinkTarget(RESPONSE_KIND, ref, ref, _registered(RESPONSE_KIND, ref)),
        )
    return LinkageMatrix(
        codes=[r.code for r in rows],
        targets=sorted(targets.values(), key=lambda t: (t.kind, t.ref)),
        cells=[
            *((by_id[link.risk_id].code, link.target_ref, link.state) for link in links),
            *((code, ref, "suggested") for code, ref in suggested),
        ],
        suggestions=suggestions,
    )


async def _write_link(
    tx: UnitOfWork,
    ctx: AuthContext,
    row: RiskRow,
    target_kind: str,
    ref: str,
    *,
    suggestion_id: UUID | None = None,
) -> bool:
    """The live link (under the engagement's lock), naming what it came from; False when a live
    link already stands, which only `link_response` treats as an error."""
    live = (
        await tx.session.execute(
            select(Linkage)
            .where(
                Linkage.risk_id == row.id,
                Linkage.target_kind == target_kind,
                Linkage.target_ref == ref,
                Linkage.removed_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if live is not None and live.state == "linked":
        return False
    if live is not None:
        await tx.session.execute(
            update(Linkage).where(Linkage.id == live.id).values(state="linked")
        )
        link_id = live.id
    else:
        link_id = (
            await tx.session.execute(
                insert(Linkage)
                .values(
                    tenant_id=ctx.tenant_id,
                    engagement_id=row.engagement_id,
                    work_item_id=row.work_item_id,
                    risk_id=row.id,
                    target_kind=target_kind,
                    target_ref=ref,
                    state="linked",
                    suggestion_id=suggestion_id,
                )
                .returning(Linkage.id)
            )
        ).scalar_one()
    tx.record(
        "risk.linked",
        target=Target(AUDIT_TARGET, row.id),
        after=Ref(link=link_id),
        scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
    )
    return True


async def link_response(
    ctx: AuthContext, engagement_id: UUID, risk_id: UUID, *, target_kind: str, target_ref: str
) -> None:
    """`POST …/risks/{rid}/responses` (the route authorised `risk.link`): a live link; a
    suggested link to the same target is accepted into it."""
    row = await _row(ctx.tenant, engagement_id, risk_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        if not await _write_link(tx, ctx, row, target_kind, target_ref.strip()):
            raise AlreadyLinked


async def unlink(
    ctx: AuthContext, engagement_id: UUID, risk_id: UUID, *, target_kind: str, target_ref: str
) -> None:
    """`DELETE …/risks/{rid}/responses`: the link is removed (kept, with `removed_at`)."""
    row = await _row(ctx.tenant, engagement_id, risk_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        found = await tx.session.scalar(
            select(Linkage.id).where(
                Linkage.risk_id == row.id,
                Linkage.target_kind == target_kind,
                Linkage.target_ref == target_ref.strip(),
                Linkage.removed_at.is_(None),
            )
        )
        if found is None:
            raise NotLinked
        await tx.session.execute(
            update(Linkage).where(Linkage.id == found).values(removed_at=func.clock_timestamp())
        )
        tx.record(
            "risk.unlinked",
            target=Target(AUDIT_TARGET, row.id),
            after=Ref(link=found),
            scope=Scope(engagement_id=engagement_id, work_item_id=row.work_item_id),
        )


# --- coverage ------------------------------------------------------------------------------------


async def coverage(
    ctx: AuthContext, engagement_id: UUID, *, performance: Decimal | None
) -> Coverage:
    """`POST …/risks/coverage` (AC4.7), by code: the latest trial balance's audit areas whose
    absolute balance reaches performance materiality (every area with a balance before one is
    decided) against the risks' areas; a risk with no live response is unaddressed."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    rows = await _rows(ctx.tenant, work_item)
    links = await _links(ctx.tenant, work_item)
    linked = {link.risk_id for link in links if link.state == "linked"}
    areas: set[str] = set()
    balances = await engagement_trial_balances(ctx.tenant, engagement_id)
    if balances:
        latest = max(balances, key=lambda b: (b.period_end, b.current_version_no))
        view = await trial_balance_view(ctx.tenant, engagement_id, latest.id)
        totals: dict[str, Decimal] = {}
        for line in view.lines:
            if line.area:
                totals[line.area] = totals.get(line.area, Decimal(0)) + line.eoy
        floor = performance if performance is not None else Decimal("0.01")
        areas = {area_key(a) for a, v in totals.items() if abs(v) >= floor}
    assessed = {r.area_key for r in rows}
    covered = {a for a in areas if any(a == k or k.startswith(f"{a}_") for k in assessed)}
    return Coverage(
        material_areas=len(areas),
        covered=len(covered),
        unaddressed_codes=[r.code for r in rows if r.id not in linked],
    )


# --- presumed fraud risks prepopulated by code (A-04-T23; AC2.1; DEC-2059) -----------------------

PRESUMED_TARGET: Final = "risk_assessment.presumed_fraud_risks"
# AU-C 240: management override is presumed in every audit and never rebuttable; revenue
# recognition is presumed and stays unless a person adopts a rebuttal proposal (AC2.2).
_PRESUMED: Final = (
    NewRisk(
        level="financial_statement",
        area_label="Management override of controls",
        assertions=(),
        inherent_risk="high",
        control_risk="max",
        presumption_kind="management_override",
        inherent_factors=(),
        rationale=None,
    ),
    NewRisk(
        level="assertion",
        area_label="Revenue recognition",
        assertions=("occurrence", "cutoff"),
        inherent_risk="high",
        control_risk="max",
        presumption_kind="revenue_recognition",
        inherent_factors=(),
        rationale=None,
    ),
)


async def presumed_preparer(ctx: AuthContext, engagement_id: UUID, paper: object) -> None:
    """risk_narrative's preparer (the section drafter's slot): the presumed risks, when the
    person starting the draft may edit the register; otherwise nothing (the draft still runs)."""
    del paper
    ref = await get_ref(ctx, engagement_id)
    if "risk.edit" in await allowed_actions(ctx, ref.resource(), ("risk.edit",)):
        await prepopulate_presumed(ctx, engagement_id)


async def prepopulate_presumed(ctx: AuthContext, engagement_id: UUID) -> list[str]:
    """When the engagement's pinned methodology prepopulates the presumed fraud risks (a step
    with the `risk_assessment.presumed_fraud_risks` target, BH-EBP-110 step 9), the register gets
    each presumption it lacks, as the person who started the draft. Code inserts them; the agent
    never does. Returns the codes added."""
    ref = await get_ref(ctx, engagement_id)
    if ref.methodology_version_id is None:
        return []
    steps = await version_steps(ctx.tenant, ref.methodology_version_id)
    if not any(PRESUMED_TARGET in s.prepopulates for s in steps.steps):
        return []
    work_item = await _work_item(ctx.tenant, engagement_id)
    have = {r.presumption_kind for r in await _rows(ctx.tenant, work_item)}
    added: list[str] = []
    for presumed in _PRESUMED:
        if presumed.presumption_kind not in have:
            added.append((await create(ctx, engagement_id, presumed)).code)
    return added


# --- the partner's approval of the register (A-04-T18; AC4.3, AC4.4; DEC-2056) -------------------

APPROVAL_KIND: Final = "significant_risk"
APPROVAL_QUESTION: Final = "risks.register"
APPROVE: Final = "approve"
RETURN: Final = "return"


class NothingPending(DomainConflict):
    """No significance or rebuttal waits for the partner."""

    code = "nothing_pending"


@dataclass(frozen=True)
class ApprovalRequest:
    card_id: UUID
    subject_codes: tuple[str, ...]


def _pending(rows: Sequence[RiskRow]) -> list[RiskRow]:
    return [r for r in rows if r.significance == "proposed" or r.fraud == "rebuttal_proposed"]


def _subject_word(r: RiskRow) -> str:
    return "rebuttal" if r.fraud == "rebuttal_proposed" else "significance"


async def _approval_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The `significant_risk` provider: one card over every pending proposal, its options and
    title by code (AC4.3: "Approve R3 significant and R5's rebuttal")."""
    if subject.work_item_id is None:
        raise RiskInvalid(facts={"field": "work_item_id"})
    rows = await _rows(tenant, subject.work_item_id)
    pending = _pending(rows)
    if not pending:
        raise NothingPending
    outcomes = {r.code: _subject_word(r) for r in pending}
    figures = {
        "register_hash": register_hash(rows),
        **{f"subject.{k}": v for k, v in outcomes.items()},
    }
    listed = ", ".join(
        f"{r.code} {'rebuttal' if _subject_word(r) == 'rebuttal' else 'significant'}"
        for r in pending
    )
    return ComputedCard(
        options=(
            CardOption(APPROVE, f"Approve {listed}", figures),
            CardOption(RETURN, "Return to the team", figures),
        ),
        context=tuple(CardContext(f"risk.{r.code}", r.code, r.area_label) for r in pending),
    )


async def request_approval(ctx: AuthContext, engagement_id: UUID) -> ApprovalRequest:
    """`POST …/risks/approval-requests` (the route authorised `risk.route_for_approval`): one
    `significant_risk` card, reserved to the engagement partner, over every pending proposal;
    409 `nothing_pending`. Remind is C3's `POST /v1/decision-cards/{id}/notify`."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    pending = _pending(await _rows(ctx.tenant, work_item))
    if not pending:
        raise NothingPending
    card_id = await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=APPROVAL_KIND,
        question_key=APPROVAL_QUESTION,
        work_item_id=work_item,
    )
    return ApprovalRequest(card_id, tuple(r.code for r in pending))


async def _apply_approval(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    """The `significant_risk` applier, in the decision's unit of work: Approve sets each subject's
    outcome (significance approved, rebuttal approved) through the field history and marks every
    row EP approved under the card; Return leaves the proposals for the team. The register must be
    as the card saw it (409 `version_conflict` otherwise)."""
    if decided.work_item_id is None:
        raise RiskInvalid(facts={"field": "work_item_id"})
    rows = list(
        (
            await tx.session.execute(
                select(RiskRow)
                .where(RiskRow.work_item_id == decided.work_item_id)
                .order_by(RiskRow.code)
                .with_for_update()
            )
        ).scalars()
    )
    if register_hash(rows) != decided.figures.get("register_hash"):
        raise RiskMoved(facts={"field": "register"})
    scope = Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id)
    if decided.option_key != APPROVE:
        tx.record(
            "risk_register.returned",
            target=Target("work_item", decided.work_item_id),
            after=Ref(decision=decided.decision_id),
            scope=scope,
        )
        return
    outcomes = {
        k.removeprefix("subject."): v
        for k, v in decided.figures.items()
        if k.startswith("subject.")
    }
    for row in rows:
        changed: list[str] = []
        outcome = outcomes.get(row.code)
        if outcome == "significance" and row.significance == "proposed":
            row.significance = "approved"
            changed.append("significance")
        elif outcome == "rebuttal" and row.fraud == "rebuttal_proposed":
            row.fraud = "rebuttal_approved"
            changed.append("fraud")
        if changed:
            await _record(tx, row, changed, note="Approved by the engagement partner")
            row.content_hash = _row_hash(row)
            row.version_no += 1
        row.status = "ep_approved"
        row.approved_card_id = decided.card_id
    approved = register_hash(rows)
    tx.record(
        "risk_register.approved",
        target=Target("work_item", decided.work_item_id),
        after=Ref(decision=decided.decision_id, register_hash=approved),
        scope=scope,
    )
    tx.emit(
        RiskRegisterApproved(
            engagement_id=decided.engagement_id,
            work_item_id=decided.work_item_id,
            decision_id=decided.decision_id,
            register_hash=approved,
        )
    )


def register_approval_kind() -> None:
    register_decision_kind(
        DecisionKind(
            code=APPROVAL_KIND,
            reserved_role="engagement_partner",
            options=_approval_card,
            questions={APPROVAL_QUESTION: "Significant risks and rebuttals"},
            apply=_apply_approval,
        )
    )


AUDIT_KINDS = frozenset({AUDIT_TARGET})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `risk_register_row` rows named by an audit event: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(RiskRow.id, RiskRow.engagement_id).where(RiskRow.id.in_(list(ids)))
        )
        return {found: owned for found, owned in rows}
