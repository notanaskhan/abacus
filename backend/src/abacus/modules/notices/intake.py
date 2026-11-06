"""Notice intakes (N-04-T07; N-04 §3 F1; NOT-01 b, c, d; DEC-2218).

An intake is a notice file on its way in: from an evidence version or an inbox item already
stored. Code reads it when C4 v1.1's form extraction covers the firm (`evidence.form_extraction`
on: `extracting` until `evidence_text.ready`), otherwise a person enters it (`manual_entry`).
Field values are insert-only (`notice_field_values`): a correction or a confirmation is a new
human row that supersedes the one read. A value below 0.90 confidence is `low_confidence` and
blocks Create notice until a person confirms or corrects it (409 `low_confidence_unconfirmed`);
nothing is guessed.

**Create notice** (Grace's click): the client's `notice_response` engagement (QN-1; 409
`no_notice_engagement` when the client has none yet), a `notice` work item, the notice's v1
columns from the adopted values, its first status event (Received, "New"), and the intake
`created`. The work item is created through engagements' own unit of work, then the notice and
the intake in this one (DEC-2218). Discard records its reason. Every write is audited.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel._flags import EVIDENCE_FORM_EXTRACTION
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_variant
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import create_work_item
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices.events import NoticeCreated

LOW_CONFIDENCE: Final = Decimal("0.90")
_READY: Final = frozenset({"ready", "manual_entry", "failed"})
FIELD_KINDS: Final[dict[str, str]] = {
    "notice.code": "code",
    "notice.tax_year": "int",
    "notice.form": "text",
    "notice.date": "date",
    "notice.respond_by": "date",
    "notice.amount_tax": "money",
    "notice.amount_interest": "money",
    "notice.amount_penalty": "money",
    "notice.amount_total": "money",
    "notice.interest_to": "date",
    "notice.response_page": "int",
    "taxpayer.name": "text",
    "taxpayer.tin": "tin",
    "agency.name": "text",
}


class NotReady(DomainConflict):
    code = "not_ready"


class LowConfidenceUnconfirmed(DomainConflict):
    """A value read below 0.90 confidence waits for a person's confirmation or correction."""

    code = "low_confidence_unconfirmed"


class DuplicateUnresolved(DomainConflict):
    code = "duplicate_unresolved"


class NoNoticeEngagement(DomainConflict):
    """The client has no `notice_response` engagement yet (QN-1: created through ENG-01)."""

    code = "no_notice_engagement"


class IntakeMoved(DomainConflict):
    code = "version_conflict"


@dataclass(frozen=True)
class FieldValue:
    key: str
    value_text: str | None
    last4: str | None
    confidence: Decimal | None
    low_confidence: bool
    origin: str
    confirmed: bool
    citation_id: UUID | None


@dataclass(frozen=True)
class Intake:
    id: UUID
    status: str
    source: str
    evidence_version_id: UUID | None
    extraction_mode: str | None
    client_id: UUID | None
    match: Mapping[str, object]
    authorization: Mapping[str, object]
    duplicate_of: UUID | None
    assignee_user_id: UUID | None
    notify_user_ids: tuple[UUID, ...]
    created_work_item_id: UUID | None
    row_version: int
    fields: tuple[FieldValue, ...]

    @property
    def unconfirmed(self) -> list[str]:
        return [f.key for f in self.fields if f.low_confidence and not f.confirmed]


_INTAKE = text(
    "SELECT id, status, source, evidence_version_id, extraction_mode, client_id, match, "
    "authorization_facts, duplicate_of_work_item_id, assignee_user_id, notify_user_ids, "
    "created_work_item_id, row_version FROM notice_intakes WHERE id = :id"
)
_FIELDS = text(
    "SELECT DISTINCT ON (field_key) field_key, value_text, last4, confidence, low_confidence, "
    "origin, confirmed_by, citation_id FROM notice_field_values WHERE owner_type = 'intake' "
    "AND owner_id = :id ORDER BY field_key, created_at DESC"
)


async def intake(ctx: AuthContext, intake_id: UUID) -> Intake:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_INTAKE, {"id": intake_id})).mappings().one_or_none()
        if row is None:
            raise NotFound("notice_intake")
        values = (await session.execute(_FIELDS, {"id": intake_id})).mappings().all()
    fields = tuple(
        FieldValue(
            key=cast(str, v["field_key"]),
            value_text=cast(str | None, v["value_text"]),
            last4=cast(str | None, v["last4"]),
            confidence=cast(Decimal | None, v["confidence"]),
            low_confidence=bool(v["low_confidence"]),
            origin=cast(str, v["origin"]),
            confirmed=v["confirmed_by"] is not None or v["origin"] == "human",
            citation_id=cast(UUID | None, v["citation_id"]),
        )
        for v in values
    )
    return Intake(
        id=cast(UUID, row["id"]),
        status=cast(str, row["status"]),
        source=cast(str, row["source"]),
        evidence_version_id=cast(UUID | None, row["evidence_version_id"]),
        extraction_mode=cast(str | None, row["extraction_mode"]),
        client_id=cast(UUID | None, row["client_id"]),
        match=cast(Mapping[str, object], row["match"] or {}),
        authorization=cast(Mapping[str, object], row["authorization_facts"] or {}),
        duplicate_of=cast(UUID | None, row["duplicate_of_work_item_id"]),
        assignee_user_id=cast(UUID | None, row["assignee_user_id"]),
        notify_user_ids=tuple(cast(Sequence[UUID], row["notify_user_ids"] or ())),
        created_work_item_id=cast(UUID | None, row["created_work_item_id"]),
        row_version=int(cast(int, row["row_version"])),
        fields=fields,
    )


async def create(
    ctx: AuthContext,
    *,
    source: str,
    evidence_version_id: UUID | None,
    inbox_item_id: UUID | None,
) -> Intake:
    """An intake from a stored file: code reads it when the firm's extraction covers notices,
    otherwise a person enters it."""
    reads = await flag_variant(ctx.tenant, EVIDENCE_FORM_EXTRACTION) != "off"
    status, mode = ("extracting", "code_map") if reads else ("manual_entry", "manual")
    async with uow(ctx.tenant) as tx:
        new_id = await tx.session.scalar(
            text(
                "INSERT INTO notice_intakes (tenant_id, source, inbox_item_id, "
                "evidence_version_id, status, extraction_mode, created_by) VALUES (:t, :s, "
                ":inbox, :ev, :status, :mode, :by) RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "s": source,
                "inbox": inbox_item_id,
                "ev": evidence_version_id,
                "status": status,
                "mode": mode,
                "by": ctx.user_id,
            },
        )
        tx.record("notice_intake.created", target=Target("notice_intake", cast(UUID, new_id)))
    return await intake(ctx, cast(UUID, new_id))


async def revise(
    ctx: AuthContext,
    intake_id: UUID,
    expected_version: int,
    *,
    fields: Sequence[tuple[str, str | None, bool]],
    client_id: UUID | None,
    assignee_user_id: UUID | None,
    notify_user_ids: Sequence[UUID] | None,
) -> Intake:
    """Corrections (`value_text`) and confirmations (`confirm`), each a new human value row."""
    current = await intake(ctx, intake_id)
    if current.row_version != expected_version:
        raise IntakeMoved
    if current.status in ("created", "discarded"):
        raise NotReady(facts={"status": current.status})
    by_key = {f.key: f for f in current.fields}
    async with uow(ctx.tenant) as tx:
        for key, value, confirm in fields:
            if key not in FIELD_KINDS or FIELD_KINDS[key] == "tin":
                continue  # a TIN is corrected by picking the client entity, never typed
            was = by_key.get(key)
            await tx.session.execute(
                text(
                    "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, field_key, "
                    "value_type, value_text, confidence, low_confidence, origin, "
                    "recorded_actor_kind, recorded_by, confirmed_by) VALUES (:t, 'intake', :id, "
                    ":k, :vt, :v, :conf, false, 'human', 'human', :by, :by)"
                ),
                {
                    "t": ctx.tenant_id,
                    "id": intake_id,
                    "k": key,
                    "vt": FIELD_KINDS[key],
                    "v": value if value is not None else (was.value_text if was else None),
                    "conf": was.confidence if (confirm and was) else None,
                    "by": ctx.user_id,
                },
            )
        moved = await tx.session.scalar(
            text(
                "UPDATE notice_intakes SET client_id = coalesce(:client, client_id), "
                "assignee_user_id = coalesce(:assignee, assignee_user_id), "
                "notify_user_ids = coalesce(:notify, notify_user_ids), "
                "row_version = row_version + 1 WHERE id = :id AND row_version = :v RETURNING id"
            ),
            {
                "client": client_id,
                "assignee": assignee_user_id,
                "notify": None if notify_user_ids is None else list(notify_user_ids),
                "id": intake_id,
                "v": expected_version,
            },
        )
        if moved is None:
            raise IntakeMoved
        tx.record(
            "notice_intake.updated",
            target=Target("notice_intake", intake_id),
            after=Ref(version=expected_version + 1),
        )
    return await intake(ctx, intake_id)


def _date(value: str | None) -> date | None:
    try:
        return None if value is None else date.fromisoformat(value)
    except ValueError:
        return None


def _money(value: str | None) -> Decimal | None:
    try:
        return None if value is None else Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def notice_code_of(printed: str) -> str:
    """The stored code from what a notice prints: "Notice of tax due" reads NOTICE-OF-TAX-DUE. The
    column takes only capitals, digits and dashes (0089), and a state notice prints words."""
    slug = re.sub(r"[^A-Z0-9-]+", "-", printed.upper()).strip("-")[:20].rstrip("-")
    return slug if len(slug) >= 2 else "NOTICE"


async def notice_engagement_for(ctx: AuthContext, client_entity_id: UUID) -> UUID | None:
    """QN-1: the client entity's `notice_response` engagement, if it has one."""
    from abacus.modules.engagements.api import notice_engagement

    return await notice_engagement(ctx.tenant, client_entity_id)


async def create_notice(
    ctx: AuthContext,
    intake_id: UUID,
    *,
    client_entity_id: UUID,
    assignee_id: UUID,
    engagement_id: UUID | None,
    related_return_id: UUID | None,
    create_anyway: bool,
) -> tuple[UUID, UUID]:
    """Create notice: the work item, the notice's columns, Received, and the intake created."""
    current = await intake(ctx, intake_id)
    if current.status not in _READY:
        raise NotReady(facts={"status": current.status})
    if current.unconfirmed:
        raise LowConfidenceUnconfirmed(facts={"field": current.unconfirmed[0]})
    if current.duplicate_of is not None and not create_anyway:
        raise DuplicateUnresolved
    engagement = engagement_id or await notice_engagement_for(ctx, client_entity_id)
    if engagement is None:
        raise NoNoticeEngagement
    values = {f.key: f for f in current.fields}
    code = (values["notice.code"].value_text if "notice.code" in values else None) or "NOTICE"
    year = values.get("notice.tax_year")
    respond_by = (
        _date(values["notice.respond_by"].value_text) if "notice.respond_by" in values else None
    )
    work_item = await create_work_item(
        ctx,
        engagement,
        "notice",
        name=f"{code} · TY{year.value_text}" if year and year.value_text else code,
        client_entity_id=client_entity_id,
        due_on=respond_by,
        details={
            "notice_code": notice_code_of(code),
            "received_on": (await clock.today(ctx.tenant)).isoformat(),
        },
    )

    def text_of(key: str) -> str | None:
        found = values.get(key)
        return found.value_text if found else None

    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE notices SET client_entity_id = :entity, tax_year = :year, "
                "form = :form, notice_date = :nd, respond_by = :rb, respond_by_source = :rbs, "
                "amount_tax = :tax, amount_interest = :interest, amount_penalty = :penalty, "
                "amount_total = :total, interest_to = :it, taxpayer_tin_last4 = :last4, "
                "agency_name = :agency, related_return_id = :ret, assignee_user_id = :assignee, "
                "source_intake_id = :intake, source_evidence_version_id = :ev, "
                "row_version = row_version + 1 "
                "WHERE work_item_id = :w"
            ),
            {
                "entity": client_entity_id,
                "year": int(text_of("notice.tax_year") or 0) or None,
                "form": text_of("notice.form"),
                "nd": _date(text_of("notice.date")),
                "rb": respond_by,
                "rbs": None if respond_by is None else "extracted",
                "tax": _money(text_of("notice.amount_tax")),
                "interest": _money(text_of("notice.amount_interest")),
                "penalty": _money(text_of("notice.amount_penalty")),
                "total": _money(text_of("notice.amount_total")),
                "it": _date(text_of("notice.interest_to")),
                "last4": values["taxpayer.tin"].last4 if "taxpayer.tin" in values else None,
                "agency": text_of("agency.name"),
                "ret": related_return_id,
                "assignee": assignee_id,
                "intake": intake_id,
                "ev": current.evidence_version_id,
                "w": work_item,
            },
        )
        await tx.session.execute(
            text(
                "INSERT INTO notice_status_events (tenant_id, work_item_id, from_status, "
                "to_status, actor_kind, actor_user_id) VALUES (:t, :w, NULL, 'received', "
                "'human', :by)"
            ),
            {"t": ctx.tenant_id, "w": work_item, "by": ctx.user_id},
        )
        moved = await tx.session.scalar(
            text(
                "UPDATE notice_intakes SET status = 'created', created_work_item_id = :w, "
                "row_version = row_version + 1 WHERE id = :id AND status = :was RETURNING id"
            ),
            {"w": work_item, "id": intake_id, "was": current.status},
        )
        if moved is None:
            raise IntakeMoved
        tx.emit(NoticeCreated(work_item_id=work_item))
        tx.record(
            "notice.created",
            target=Target("notice", work_item),
            after=Ref(intake=intake_id),
        )
    return work_item, engagement


async def discard(ctx: AuthContext, intake_id: UUID, reason_code: str) -> Intake:
    current = await intake(ctx, intake_id)
    if current.status in ("created", "discarded"):
        raise NotReady(facts={"status": current.status})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE notice_intakes SET status = 'discarded', discarded_reason_code = :r, "
                "row_version = row_version + 1 WHERE id = :id"
            ),
            {"r": reason_code, "id": intake_id},
        )
        tx.record("notice_intake.discarded", target=Target("notice_intake", intake_id))
    return await intake(ctx, intake_id)
