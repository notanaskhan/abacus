"""The acceptance tables (migration 0163, P-07-T35) and the G1 decision they answer.

`g1_decision` is G1's one source (DEC-372): the engagement's acceptance record's decision, or
none while it has none. SPEC-025's `engagement_acceptance` fallback dropped with P-07-T59
(migration 0321; DEC-906).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import Column, FetchedValue, MetaData, Table, select
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Boolean, Date, DateTime, Integer, SmallInteger, Text

_meta = MetaData()


def _id() -> Column[UUID]:
    return Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue())


def _uuid(name: str) -> Column[UUID]:
    return Column(name, PgUUID(as_uuid=True))


def _at(name: str) -> Column[datetime]:
    return Column(name, DateTime(timezone=True), server_default=FetchedValue())


templates = Table(
    "acceptance_questionnaire_templates",
    _meta,
    _id(),
    _uuid("tenant_id"),
    Column("name", Text),
    Column("family", Text),
    _uuid("created_by"),
    _at("created_at"),
)
template_versions = Table(
    "acceptance_questionnaire_template_versions",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("template_id"),
    Column("version_no", Integer),
    Column("sections", JSONB),
    _uuid("created_by"),
    _at("created_at"),
)
records = Table(
    "acceptance_records",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("engagement_id"),
    _uuid("client_id"),
    Column("kind", Text),
    _uuid("template_version_id"),
    _uuid("prepared_by"),
    Column("status", Text, server_default=FetchedValue()),
    Column("risk_rating", Text),
    Column("sent_to_partner_at", DateTime(timezone=True)),
    _uuid("sent_to_partner_by"),
    _uuid("prescreen_run_id"),
    _uuid("prior_record_id"),
    Column("version", Integer, server_default=FetchedValue()),
    _at("created_at"),
    _at("updated_at"),
    Column("high_risk_seen", Boolean, server_default=FetchedValue()),  # 0165: sticky
)
answers = Table(
    "acceptance_answers",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    Column("section_code", Text),
    Column("answers_sealed", BYTEA),
    Column("state", Text),
    Column("version", Integer, server_default=FetchedValue()),
    _uuid("updated_by"),
    _at("updated_at"),
)
manual_checks = Table(
    "acceptance_manual_checks",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    Column("section_code", Text),
    _uuid("requested_of"),
    _uuid("requested_by"),
    _at("requested_at"),
    _uuid("completed_by"),
    _at("completed_at"),
    Column("note_sealed", BYTEA),
)
flags = Table(
    "acceptance_flags",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    Column("severity", Text),
    Column("title_sealed", BYTEA),
    Column("body_sealed", BYTEA),
    Column("source_refs", JSONB),
    _uuid("authored_by"),
    Column("authored_kind", Text, server_default=FetchedValue()),
    _at("authored_at"),
    _uuid("condition_id"),
)
decisions = Table(
    "acceptance_decisions",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    Column("option", Text),
    Column("rationale_sealed", BYTEA),
    _uuid("decided_by"),
    _at("decided_at"),
    Column("mfa_verified_at", DateTime(timezone=True)),
    Column("actor_kind", Text, server_default=FetchedValue()),
)
condition_rows = Table(
    "acceptance_conditions",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    _uuid("decision_id"),
    Column("position", SmallInteger),
    Column("text_sealed", BYTEA),
    _uuid("assignee_user_id"),
    Column("due_on", Date),
    _at("created_at"),
)
condition_events = Table(
    "acceptance_condition_events",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("condition_id"),
    Column("kind", Text, server_default=FetchedValue()),
    Column("note_sealed", BYTEA),
    _uuid("actor_id"),
    Column("actor_kind", Text, server_default=FetchedValue()),
    _at("at"),
)
reviews = Table(
    "risk_partner_reviews",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("record_id"),
    Column("event", Text),
    _uuid("partner_id"),
    _uuid("actor_id"),
    Column("actor_kind", Text, server_default=FetchedValue()),
    _at("at"),
)

LOCKED: Final = frozenset({"decided", "declined"})


@dataclass(frozen=True)
class G1Decision:
    """The acceptance decision G1 reads: accepted or not, when, and by whom (when known)."""

    accepted: bool
    decided_at: datetime
    decided_by: UUID | None


async def g1_decision(session: AsyncSession, engagement_id: UUID) -> G1Decision | None:
    """The engagement's acceptance decision, or None while it has none (DEC-372)."""
    found = (
        await session.execute(
            select(records.c.id, records.c.status).where(records.c.engagement_id == engagement_id)
        )
    ).one_or_none()
    if found is not None:
        # DEC-375 (M1): a decision counts only on a record the database moved to decided or
        # declined (the guard trigger needs the matching decision row), never a row alone.
        if found.status not in LOCKED:
            return None
        record = found.id
        row = (
            await session.execute(
                select(decisions.c.option, decisions.c.decided_at, decisions.c.decided_by).where(
                    decisions.c.record_id == record
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return G1Decision(row.option != "decline", row.decided_at, row.decided_by)
    return None
