"""The tax profile's data access (T-01-T43; migration 0550): authorizations, elections, staged
files, transcripts, their lines and comparisons. Statements only; the service decides."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

Row = RowMapping
Values = Mapping[str, object]

_AUTHORIZATIONS = text(
    "SELECT id, form, state_form_code, designees, tax_matters, tax_years, received_on, "
    "expires_on, status FROM tax_authorizations WHERE client_entity_id = :entity "
    "ORDER BY form, created_at, id"
)
_AUTHORIZATION = text(
    "SELECT id, client_entity_id, form, status, tax_years FROM tax_authorizations WHERE id = :id"
)
_INSERT_AUTHORIZATION = text(
    "INSERT INTO tax_authorizations (id, tenant_id, client_entity_id, form, state_form_code, "
    "designees, tax_matters, forms_covered, tax_years, received_on, expires_on, status, "
    "evidence_version_id, created_by) VALUES (:id, :tenant, :entity, :form, :state_form_code, "
    "CAST(:designees AS jsonb), :tax_matters, :forms_covered, :tax_years, :received_on, "
    ":expires_on, :status, :evidence_version_id, :created_by)"
)
_ELECTIONS = text(
    "SELECT kind, jurisdiction, tax_year, amount, status_code, row_version FROM tax_elections "
    "WHERE client_entity_id = :entity ORDER BY tax_year DESC, kind, jurisdiction NULLS FIRST"
)
_ELECTION = text(
    "SELECT id, row_version FROM tax_elections WHERE client_entity_id = :entity AND kind = :kind "
    "AND coalesce(jurisdiction, '') = coalesce(CAST(:jurisdiction AS text), '') "
    "AND tax_year = :tax_year FOR UPDATE"
)
_INSERT_ELECTION = text(
    "INSERT INTO tax_elections (tenant_id, client_entity_id, kind, jurisdiction, tax_year, "
    "amount, status_code, updated_by) VALUES (:tenant, :entity, :kind, :jurisdiction, "
    ":tax_year, :amount, :status_code, :user) RETURNING row_version"
)
_UPDATE_ELECTION = text(
    "UPDATE tax_elections SET amount = :amount, status_code = :status_code, "
    "updated_by = :user, row_version = row_version + 1 WHERE id = :id AND row_version = :seen "
    "RETURNING row_version"
)
_INSERT_FILE = text(
    "INSERT INTO tax_profile_files (id, tenant_id, client_entity_id, uploaded_by, file_name, "
    "media_type, size_bytes, sha256, storage_key, storage_version_id) VALUES (:id, :tenant, "
    ":entity, :user, :name, :media, :size, :sha, :key, :version)"
)
_OWN_FILE = text(
    "SELECT id, file_name, media_type, size_bytes, sha256, storage_key, storage_version_id "
    "FROM tax_profile_files WHERE id = :id AND uploaded_by = :user AND client_entity_id = :entity "
    "AND consumed_by IS NULL FOR UPDATE"
)
_CONSUME_FILE = text("UPDATE tax_profile_files SET consumed_by = :by WHERE id = :id")
_INSERT_TRANSCRIPT = text(
    "INSERT INTO transcripts (id, tenant_id, client_entity_id, kind, tax_year, pulled_at, "
    "pulled_by, authorization_id, evidence_version_id, file_id, parse_status, problems, "
    "account_balance) VALUES (:id, :tenant, :entity, :kind, :tax_year, :pulled_at, :user, "
    ":authorization_id, :evidence_version_id, :file_id, :parse_status, "
    "CAST(:problems AS jsonb), :account_balance)"
)
_INSERT_LINE = text(
    "INSERT INTO transcript_lines (tenant_id, transcript_id, line_no, form, payer_name, amount, "
    "tc_code, tc_date) VALUES (:tenant, :transcript_id, :line_no, :form, :payer_name, :amount, "
    ":tc_code, :tc_date)"
)
_TRANSCRIPTS = text(
    "SELECT t.id, t.kind, t.tax_year, t.pulled_at, t.pulled_by, t.parse_status, "
    "t.account_balance, a.form AS authorization_form FROM transcripts t "
    "JOIN tax_authorizations a ON a.id = t.authorization_id "
    "WHERE t.client_entity_id = :entity ORDER BY t.tax_year, t.pulled_at, t.kind DESC, t.id"
)
_TRANSCRIPT = text(
    "SELECT t.id, t.client_entity_id, t.kind, t.tax_year, t.pulled_at, t.pulled_by, "
    "t.parse_status, t.account_balance, a.form AS authorization_form FROM transcripts t "
    "JOIN tax_authorizations a ON a.id = t.authorization_id WHERE t.id = :id"
)
_ENTITY_OF = text("SELECT client_entity_id FROM transcripts WHERE id = :id")
_LINES = text(
    "SELECT transcript_id, line_no, form, payer_name, amount, tc_code, tc_date "
    "FROM transcript_lines WHERE transcript_id = ANY(:ids) ORDER BY transcript_id, line_no"
)
_LATEST = text(
    "SELECT DISTINCT ON (transcript_id) id, transcript_id, return_id, checkpoint_id, result, "
    "difference_total, lines, agreeing, engine_version, computed_at FROM transcript_comparisons "
    "WHERE transcript_id = ANY(:ids) ORDER BY transcript_id, computed_at DESC, id DESC"
)
_INSERT_COMPARISON = text(
    "INSERT INTO transcript_comparisons (id, tenant_id, transcript_id, return_id, "
    "checkpoint_id, result, difference_total, lines, agreeing, engine_version, computed_by) "
    "VALUES (:id, :tenant, :transcript_id, :return_id, :checkpoint_id, :result, "
    ":difference_total, CAST(:lines AS jsonb), CAST(:agreeing AS jsonb), :engine_version, "
    ":user) RETURNING computed_at"
)
_RETURN = text(
    "SELECT work_item_id, client_entity_id, tax_year, form FROM tax_returns "
    "WHERE work_item_id = :id"
)


async def authorizations(session: AsyncSession, entity_id: UUID) -> Sequence[Row]:
    return (await session.execute(_AUTHORIZATIONS, {"entity": entity_id})).mappings().all()


async def authorization(session: AsyncSession, authorization_id: UUID) -> Row | None:
    return (await session.execute(_AUTHORIZATION, {"id": authorization_id})).mappings().first()


async def insert_authorization(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_AUTHORIZATION, dict(values))


async def elections(session: AsyncSession, entity_id: UUID) -> Sequence[Row]:
    return (await session.execute(_ELECTIONS, {"entity": entity_id})).mappings().all()


async def election_for_update(session: AsyncSession, values: Values) -> Row | None:
    return (await session.execute(_ELECTION, dict(values))).mappings().first()


async def insert_election(session: AsyncSession, values: Values) -> int:
    return int((await session.execute(_INSERT_ELECTION, dict(values))).scalar_one())


async def update_election(session: AsyncSession, values: Values) -> int | None:
    """The new version, or None when `seen` was not the row's (a stale write)."""
    found = (await session.execute(_UPDATE_ELECTION, dict(values))).scalar_one_or_none()
    return None if found is None else int(found)


async def insert_file(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_FILE, dict(values))


async def own_file_for_update(session: AsyncSession, values: Values) -> Row | None:
    return (await session.execute(_OWN_FILE, dict(values))).mappings().first()


async def consume_file(session: AsyncSession, file_id: UUID, by: UUID) -> None:
    await session.execute(_CONSUME_FILE, {"id": file_id, "by": by})


async def insert_transcript(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_TRANSCRIPT, dict(values))


async def insert_lines(session: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
    if rows:
        await session.execute(_INSERT_LINE, [dict(r) for r in rows])


async def transcripts(session: AsyncSession, entity_id: UUID) -> Sequence[Row]:
    return (await session.execute(_TRANSCRIPTS, {"entity": entity_id})).mappings().all()


async def transcript(session: AsyncSession, transcript_id: UUID) -> Row | None:
    return (await session.execute(_TRANSCRIPT, {"id": transcript_id})).mappings().first()


async def entity_of_transcript(session: AsyncSession, transcript_id: UUID) -> UUID | None:
    found = (await session.execute(_ENTITY_OF, {"id": transcript_id})).scalar_one_or_none()
    return None if found is None else UUID(str(found))


async def lines(session: AsyncSession, transcript_ids: Sequence[UUID]) -> Sequence[Row]:
    if not transcript_ids:
        return []
    return (await session.execute(_LINES, {"ids": list(transcript_ids)})).mappings().all()


async def latest_comparisons(
    session: AsyncSession, transcript_ids: Sequence[UUID]
) -> Sequence[Row]:
    if not transcript_ids:
        return []
    return (await session.execute(_LATEST, {"ids": list(transcript_ids)})).mappings().all()


async def insert_comparison(session: AsyncSession, values: Values) -> object:
    return (await session.execute(_INSERT_COMPARISON, dict(values))).scalar_one()


async def tax_return(session: AsyncSession, return_id: UUID) -> Row | None:
    return (await session.execute(_RETURN, {"id": return_id})).mappings().first()
