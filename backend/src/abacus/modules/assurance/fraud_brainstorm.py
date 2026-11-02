"""A-04-T19: AUD-05's narrative extras (A-04 §3.2 AC2.3-AC2.5; SPEC-620; DEC-2055).

0613's `fraud_brainstorm_sessions` (one per audit work item), `fraud_minutes_approvals`
(insert-only) and `fraud_inquiries`, with 0651's row version:

- **The session** (AUD-05 b): when, how, who led and who attended, and who was excluded with a
  reason. The engagement's EQR is never an attendee (AU-C 220: the EQR stays objective); naming
  them answers 422 `eqr_must_be_excluded`.
- **The minutes**: a person writes them (`minutes_source = human`), or a person adopts the agent's
  suggestion through C3's suggestion adopt, which calls this module's `fraud_minutes` applier
  (`adopted_suggestion`). Either way the minutes wait for the engagement partner and any earlier
  approval no longer holds: the status returns to Awaiting approval at the new hash.
- **The approval** is the engagement partner's own act, five layers deep: the matrix
  (`fraud_minutes.approve`, the EP only), `require_live_human` here, 0613's CHECK and guard (a
  person, in their own session), FRAUD-MINUTES-001 (only this module writes an approval) and the
  `fraud_minutes.approved` audit event. A stale hash answers 409 `minutes_changed`.
- **Inquiries**: a management inquiry is a C5 questionnaire **draft** addressed to the contact; a
  person sends it from the questionnaire, never here (AC2.5). A governance-body inquiry is
  recorded with its body's reference. Requested or Answered is derived from `answered_at`.
- Attention flags (AC2.3) are workpapers' own (`workpapers/flags.py`).

HOME-02 reads the gate kind `fraud_minutes_approval` (met when no session waits for the partner),
and the partners are told by `fraud_minutes_awaiting_approval` (C16).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.agents.api import AdoptedValue
from abacus.modules.assurance.events import FraudMinutesAwaitingApproval
from abacus.modules.engagements.api import assurance_item_id, get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    engagement_partners,
    engagement_role_of,
    names_of,
)
from abacus.modules.organisations.api import contact_facts
from abacus.modules.requests.api import create_questionnaire
from abacus.modules.requests.api import questionnaire as questionnaire_view

AUDIT_TARGET: Final = "fraud_brainstorm_session"
INQUIRY_TARGET: Final = "fraud_inquiry"
AUDIT_KINDS: Final = frozenset({AUDIT_TARGET, INQUIRY_TARGET})
GATE_KIND: Final = "fraud_minutes_approval"
SUGGESTION_TARGET: Final = "fraud_minutes"
APPROVE: Final = "fraud_minutes.approve"
EDIT: Final = "fraud_session.edit"
Medium = Literal["in_person", "video", "hybrid"]
ExclusionReason = Literal["eqr", "independence", "other"]
MinutesStatus = Literal["draft", "awaiting_approval", "approved"]
_ACTIONS: Final = (EDIT, APPROVE, "fraud_inquiry.request")
MAX_MINUTES: Final = 20_000  # 0613's CHECK


class SessionMoved(DomainConflict):
    """The session changed since the caller read it."""

    code = "version_conflict"


class MinutesChanged(DomainConflict):
    """The minutes changed since the partner read them: approve the current hash."""

    code = "minutes_changed"


class NothingToApprove(DomainConflict):
    code = "minutes_not_awaiting_approval"


class EqrMustBeExcluded(DomainInvalid):
    """The engagement's EQR is never an attendee of the fraud brainstorm (AU-C 220)."""

    code = "eqr_must_be_excluded"


class SessionInvalid(DomainInvalid):
    code = "fraud_session_invalid"


class AdoptThroughSuggestion(DomainInvalid):
    """A suggestion is adopted through C3's `POST /v1/suggestions/{id}/adopt`, which calls the
    `fraud_minutes` applier, so the adoption is the person's recorded act (ADR-161)."""

    code = "adopt_through_suggestion"


@dataclass(frozen=True)
class Attendee:
    user_id: UUID
    name: str
    initials: str


@dataclass(frozen=True)
class Exclusion:
    user_id: UUID
    name: str
    reason: ExclusionReason


@dataclass(frozen=True)
class Discussion:
    step_key: str
    summary: str


@dataclass(frozen=True)
class Session:
    id: UUID
    held_at: datetime | None
    medium: Medium | None
    led_by: Attendee | None
    attendees: tuple[Attendee, ...]
    excluded: tuple[Exclusion, ...]
    discussion: tuple[Discussion, ...]
    minutes_text: str | None
    minutes_hash: str | None
    minutes_status: MinutesStatus
    minutes_source: Literal["human", "adopted_suggestion"] | None
    approved_by_name: str | None
    approved_at: datetime | None
    row_version: int
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class SessionEdit:
    expected_version: int
    held_at: datetime | None
    medium: Medium | None
    led_by_user_id: UUID | None
    attendee_user_ids: tuple[UUID, ...]
    excluded: tuple[tuple[UUID, ExclusionReason], ...]


@dataclass(frozen=True)
class Inquiry:
    id: UUID
    respondent_name: str
    questionnaire_id: UUID | None
    sent: bool
    status: Literal["requested", "answered"]
    answered_at: datetime | None


def minutes_hash(minutes: str) -> str:
    """The hash the partner approves: SHA-256 of the minutes' UTF-8 text."""
    return hashlib.sha256(minutes.encode("utf-8")).hexdigest()


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part)[:3].upper()


def _live_human(ctx: AuthContext) -> None:
    """`require_live_human` (INV-1): a person's own act, never an agent, the platform, a client
    principal or a break-glass support session."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(APPROVE, "role")


async def _work_item(tenant: TenantContext, engagement_id: UUID) -> UUID:
    found = await assurance_item_id(tenant, engagement_id)
    if found is None:
        raise NotFound("fraud_session")
    return found


_SELECT = (
    "SELECT id, held_at, medium, led_by_user_id, attendees, excluded, discussion, minutes_text, "
    "minutes_hash, minutes_status, minutes_source, row_version FROM fraud_brainstorm_sessions "
    "WHERE work_item_id = :w"
)
_SELECT_LOCKED = (
    "SELECT id, held_at, medium, led_by_user_id, attendees, excluded, discussion, minutes_text, "
    "minutes_hash, minutes_status, minutes_source, row_version FROM fraud_brainstorm_sessions "
    "WHERE work_item_id = :w FOR UPDATE"
)


async def _row(tenant: TenantContext, work_item_id: UUID) -> RowMapping | None:
    async with tenant_session(tenant) as session:
        return (await session.execute(text(_SELECT), {"w": work_item_id})).mappings().first()


async def _approval(
    tenant: TenantContext, session_id: UUID, digest: str | None
) -> tuple[UUID, datetime] | None:
    if digest is None:
        return None
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text(
                    "SELECT approved_by_user_id, created_at FROM fraud_minutes_approvals "
                    "WHERE session_id = :s AND minutes_hash = :h"
                ),
                {"s": session_id, "h": digest},
            )
        ).first()
    return None if found is None else (found[0], found[1])


async def _people(ids: Sequence[UUID]) -> dict[UUID, str]:
    return await names_of(list(dict.fromkeys(ids))) if ids else {}


def _person(user_id: UUID, names: dict[UUID, str]) -> Attendee:
    name = names.get(user_id, "")
    return Attendee(user_id, name, _initials(name))


async def _actions(ctx: AuthContext, engagement_id: UUID) -> tuple[str, ...]:
    ref = await get_ref(ctx, engagement_id)
    can = await allowed_actions(ctx, ref.resource(), _ACTIONS)
    return tuple(a for a in _ACTIONS if a in can)


async def session_view(ctx: AuthContext, engagement_id: UUID) -> Session:
    """`GET …/fraud-brainstorm` (the route authorised `fraud_session.read`). Before anything is
    recorded the session reads empty at version 0, so the first save sends 0."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    row = await _row(ctx.tenant, work_item)
    actions = await _actions(ctx, engagement_id)
    if row is None:
        return Session(
            work_item, None, None, None, (), (), (), None, None, "draft", None, None, None, 0,
            actions,
        )  # fmt: skip
    attendees = [UUID(str(u)) for u in cast(list[object], row["attendees"])]
    excluded = cast(list[dict[str, str]], row["excluded"])
    approval = await _approval(ctx.tenant, row["id"], row["minutes_hash"])
    lead = cast("UUID | None", row["led_by_user_id"])
    names = await _people(
        [
            *attendees,
            *(UUID(e["user_id"]) for e in excluded),
            *([lead] if lead else []),
            *([approval[0]] if approval else []),
        ]
    )
    return Session(
        id=row["id"],
        held_at=row["held_at"],
        medium=row["medium"],
        led_by=None if lead is None else _person(lead, names),
        attendees=tuple(_person(u, names) for u in attendees),
        excluded=tuple(
            Exclusion(
                UUID(e["user_id"]),
                names.get(UUID(e["user_id"]), ""),
                cast(ExclusionReason, e["reason"]),
            )
            for e in excluded
        ),
        discussion=tuple(
            Discussion(d["step_key"], d["summary"])
            for d in cast(list[dict[str, str]], row["discussion"])
        ),
        minutes_text=row["minutes_text"],
        minutes_hash=row["minutes_hash"],
        minutes_status=row["minutes_status"],
        minutes_source=row["minutes_source"],
        approved_by_name=None if approval is None else names.get(approval[0]),
        approved_at=None if approval is None else approval[1],
        row_version=row["row_version"],
        allowed_actions=actions,
    )


async def _eqr_free(ctx: AuthContext, engagement_id: UUID, attendees: Sequence[UUID]) -> None:
    for user in attendees:
        if await engagement_role_of(ctx.tenant, engagement_id, user) == "eqr_reviewer":
            raise EqrMustBeExcluded(facts={"user_id": str(user)})


async def _locked(tx: UnitOfWork, work_item_id: UUID) -> RowMapping | None:
    return (await tx.session.execute(text(_SELECT_LOCKED), {"w": work_item_id})).mappings().first()


async def record_session(ctx: AuthContext, engagement_id: UUID, edit: SessionEdit) -> Session:
    """`PUT …/fraud-brainstorm` (the route authorised `fraud_session.edit`): the session's facts;
    audited `fraud_session.recorded`. The minutes are untouched."""
    attendees = tuple(dict.fromkeys(edit.attendee_user_ids))
    excluded_ids = {u for u, _ in edit.excluded}
    if excluded_ids & set(attendees):
        raise SessionInvalid(facts={"field": "excluded"})
    await _eqr_free(ctx, engagement_id, attendees)
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        current = await _locked(tx, work_item)
        version = 0 if current is None else int(current["row_version"])
        if version != edit.expected_version:
            raise SessionMoved(facts={"current": version})
        values = {
            "w": work_item,
            "held": edit.held_at,
            "medium": edit.medium,
            "lead": edit.led_by_user_id,
            "att": [str(u) for u in attendees],
            "exc": [{"user_id": str(u), "reason": r} for u, r in edit.excluded],
        }
        if current is None:
            session_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO fraud_brainstorm_sessions (tenant_id, engagement_id, "
                        "work_item_id, held_at, medium, led_by_user_id, attendees, excluded) "
                        "VALUES (:t, :e, :w, :held, :medium, :lead, CAST(:att AS jsonb), "
                        "CAST(:exc AS jsonb)) RETURNING id"
                    ),
                    {**_json(values), "t": ctx.tenant_id, "e": engagement_id},
                )
            ).scalar_one()
        else:
            session_id = current["id"]
            await tx.session.execute(
                text(
                    "UPDATE fraud_brainstorm_sessions SET held_at = :held, medium = :medium, "
                    "led_by_user_id = :lead, attendees = CAST(:att AS jsonb), "
                    "excluded = CAST(:exc AS jsonb), row_version = row_version + 1, "
                    "updated_at = clock_timestamp() WHERE id = :id"
                ),
                {**_json(values), "id": session_id},
            )
        tx.record(
            "fraud_session.recorded",
            target=Target(AUDIT_TARGET, session_id),
            after=Ref(version=version + 1),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await session_view(ctx, engagement_id)


def _json(values: Mapping[str, object]) -> dict[str, object]:
    return {k: json.dumps(v) if k in ("att", "exc", "disc") else v for k, v in values.items()}


async def _write_minutes(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    work_item: UUID,
    minutes: str,
    *,
    source: Literal["human", "adopted_suggestion"],
    expected_version: int | None,
) -> None:
    body = minutes.strip()
    if not body or len(body) > MAX_MINUTES:
        raise SessionInvalid(facts={"field": "text"})
    current = await _locked(tx, work_item)
    if current is None:
        raise SessionInvalid(facts={"field": "session"})  # record the session first
    if expected_version is not None and int(current["row_version"]) != expected_version:
        raise SessionMoved(facts={"current": int(current["row_version"])})
    digest = minutes_hash(body)
    await tx.session.execute(
        text(
            "UPDATE fraud_brainstorm_sessions SET minutes_text = :m, minutes_hash = :h, "
            "minutes_status = 'awaiting_approval', minutes_source = :src, "
            "row_version = row_version + 1, updated_at = clock_timestamp() WHERE id = :id"
        ),
        {"m": body, "h": digest, "src": source, "id": current["id"]},
    )
    tx.record(
        "fraud_minutes.written",
        target=Target(AUDIT_TARGET, current["id"]),
        after=Ref(version=int(current["row_version"]) + 1),
        scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
    )
    partners = await engagement_partners(ctx.tenant_id, engagement_id)
    tx.emit(
        FraudMinutesAwaitingApproval(
            session_id=current["id"],
            engagement_id=engagement_id,
            by_user=ctx.user_id,
            recipient_user_ids=[p for p in partners if p != ctx.user_id],
        )
    )


async def record_minutes(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    expected_version: int,
    minutes: str | None,
    adopt_suggestion_id: UUID | None,
) -> Session:
    """`PUT …/fraud-brainstorm/minutes` (the route authorised `fraud_session.edit`): minutes a
    person wrote. Any earlier approval no longer holds (it was of another hash)."""
    if adopt_suggestion_id is not None:
        raise AdoptThroughSuggestion(facts={"suggestion_id": str(adopt_suggestion_id)})
    if minutes is None:
        raise SessionInvalid(facts={"field": "text"})
    if ctx.tenant.actor_kind != "human":
        raise Forbidden(EDIT, "role")  # the agent suggests minutes; it never writes them
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        await _write_minutes(
            tx, ctx, engagement_id, work_item, minutes, source="human",
            expected_version=expected_version,
        )  # fmt: skip
    return await session_view(ctx, engagement_id)


async def apply_minutes_suggestion(
    tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue
) -> None:
    """The `fraud_minutes` suggestion applier: a person adopted (or edited and adopted) the
    agent's minutes; they are written as the person's, awaiting the partner."""
    if adopted.field_key != "minutes" or adopted.engagement_id is None:
        raise SessionInvalid(facts={"field": "field_key"})
    ref = await lock_ref(tx, adopted.engagement_id)
    await authorise(ctx, EDIT, ref.resource())
    value = adopted.value.get("v")
    if not isinstance(value, str):
        raise SessionInvalid(facts={"field": "value"})
    await _write_minutes(
        tx, ctx, adopted.engagement_id, adopted.target_id, value,
        source="adopted_suggestion" if adopted.cause == "suggestion_adopted" else "human",
        expected_version=None,
    )  # fmt: skip


async def approve_minutes(ctx: AuthContext, engagement_id: UUID, digest: str) -> Session:
    """`POST …/fraud-brainstorm/minutes/approve` (the route authorised `fraud_minutes.approve`,
    the EP only): the partner's approval of the minutes at `digest`. FRAUD-MINUTES-001: the only
    writer of `fraud_minutes_approvals`."""
    _live_human(ctx)
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        current = await _locked(tx, work_item)
        if current is None or current["minutes_status"] != "awaiting_approval":
            raise NothingToApprove
        if current["minutes_hash"] != digest:
            raise MinutesChanged(facts={"current": cast(str, current["minutes_hash"])})
        await tx.session.execute(
            text(
                "INSERT INTO fraud_minutes_approvals (tenant_id, engagement_id, work_item_id, "
                "session_id, minutes_hash, approved_by_user_id, actor_kind) "
                "VALUES (:t, :e, :w, :s, :h, :by, 'human')"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": work_item,
                "s": current["id"],
                "h": digest,
                "by": ctx.user_id,
            },
        )
        await tx.session.execute(
            text(
                "UPDATE fraud_brainstorm_sessions SET minutes_status = 'approved', "
                "row_version = row_version + 1, updated_at = clock_timestamp() WHERE id = :id"
            ),
            {"id": current["id"]},
        )
        tx.record(
            "fraud_minutes.approved",
            target=Target(AUDIT_TARGET, current["id"]),
            after=Ref(minutes_hash=digest),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await session_view(ctx, engagement_id)


async def minutes_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`fraud_minutes_approval` (C13, HOME-02): met when no session on the engagement waits for
    the partner's approval."""
    async with tenant_session(tenant) as session:
        waiting = (
            await session.execute(
                text(
                    "SELECT 1 FROM fraud_brainstorm_sessions WHERE engagement_id = :e "
                    "AND minutes_status = 'awaiting_approval' LIMIT 1"
                ),
                {"e": engagement_id},
            )
        ).first()
    return waiting is None


# --- inquiries (AC2.5) --------------------------------------------------------------------------


async def inquiries(ctx: AuthContext, engagement_id: UUID) -> list[Inquiry]:
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, respondent_contact_id, governance_body_ref, "
                        "questionnaire_id, answered_at FROM fraud_inquiries "
                        "WHERE work_item_id = :w ORDER BY created_at"
                    ),
                    {"w": work_item},
                )
            )
            .mappings()
            .all()
        )
        contacts = await contact_facts(
            session, [r["respondent_contact_id"] for r in rows if r["respondent_contact_id"]]
        )
    out: list[Inquiry] = []
    for r in rows:
        sent = False
        if r["questionnaire_id"] is not None:
            view = await questionnaire_view(ctx, r["questionnaire_id"])
            sent = view.status != "draft"
        out.append(
            Inquiry(
                id=r["id"],
                respondent_name=(
                    contacts[r["respondent_contact_id"]].display_name
                    if r["respondent_contact_id"] in contacts
                    else r["governance_body_ref"] or ""
                ),
                questionnaire_id=r["questionnaire_id"],
                sent=sent,
                status="answered" if r["answered_at"] is not None else "requested",
                answered_at=r["answered_at"],
            )
        )
    return out


async def request_inquiry(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    respondent_contact_id: UUID | None,
    governance_body_ref: str | None,
    title: str,
) -> Inquiry:
    """`POST …/fraud-inquiries` (the route authorised `fraud_inquiry.request`): a management
    inquiry is a C5 questionnaire **draft** to the contact (Dana sees it only after a person
    sends it); a governance-body inquiry is recorded with its reference."""
    if (respondent_contact_id is None) == (governance_body_ref is None):
        raise SessionInvalid(facts={"field": "respondent"})
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("fraud_inquiry.request", "role")
    work_item = await _work_item(ctx.tenant, engagement_id)
    questionnaire_id: UUID | None = None
    if respondent_contact_id is not None:
        created = await create_questionnaire(
            ctx,
            kind="inquiry",
            work_item_id=work_item,
            title=title,
            addressed_to_contact_id=respondent_contact_id,
            due_on=None,
            engagement_id=engagement_id,
        )
        questionnaire_id = created.id
    async with uow(ctx.tenant) as tx:
        inquiry_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO fraud_inquiries (tenant_id, engagement_id, work_item_id, "
                    "respondent_contact_id, governance_body_ref, questionnaire_id) "
                    "VALUES (:t, :e, :w, :c, :g, :q) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item,
                    "c": respondent_contact_id,
                    "g": governance_body_ref,
                    "q": questionnaire_id,
                },
            )
        ).scalar_one()
        tx.record(
            "fraud_inquiry.requested",
            target=Target(INQUIRY_TARGET, inquiry_id),
            after=Ref(),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    found = next(i for i in await inquiries(ctx, engagement_id) if i.id == inquiry_id)
    return found


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `fraud_brainstorm_session` and `fraud_inquiry` rows an audit event names: id -> the
    owning engagement."""
    sql = (
        "SELECT id, engagement_id FROM fraud_brainstorm_sessions WHERE id = ANY(:ids)"
        if kind == AUDIT_TARGET
        else "SELECT id, engagement_id FROM fraud_inquiries WHERE id = ANY(:ids)"
    )
    async with tenant_session(tenant) as session:
        rows = await session.execute(text(sql), {"ids": list(ids)})
        return {found: owned for found, owned in rows}


__all__ = (
    "AUDIT_KINDS",
    "GATE_KIND",
    "SUGGESTION_TARGET",
    "apply_minutes_suggestion",
    "approve_minutes",
    "audit_owners",
    "inquiries",
    "minutes_gate",
    "minutes_hash",
    "record_minutes",
    "record_session",
    "request_inquiry",
    "session_view",
)
