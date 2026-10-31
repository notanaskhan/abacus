"""The sampling populations' data access (A-03-T07; migration 0520): populations, their records
and their completeness ties. Statements only; `populations` decides."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Values = Mapping[str, object]
Row = dict[str, Any]  # Any: a row's columns are of mixed types

# The population and its ties are insert-only (no UPDATE grant), so a row lock is unavailable: a
# tie's next position is serialised by a transaction advisory lock on the population (DEC-1656).
_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_INSERT_POPULATION = text(
    "INSERT INTO sample_populations (id, tenant_id, engagement_id, work_item_id, source_kind, "
    "evidence_version_id, gl_snapshot_id, query, column_map, record_count, record_unit, "
    "amount_total, sha256, sampling_unit, deviation_definition, pulled_at, created_by) VALUES "
    "(:id, :tenant_id, :engagement_id, :work_item_id, :source_kind, :evidence_version_id, "
    ":gl_snapshot_id, CAST(:query AS jsonb), CAST(:column_map AS jsonb), :record_count, "
    ":record_unit, :amount_total, :sha256, :sampling_unit, :deviation_definition, :pulled_at, "
    ":created_by)"
)
_INSERT_RECORD = text(
    "INSERT INTO sample_population_records (tenant_id, population_id, ordinal, record_key, "
    "amount, display) VALUES (:tenant_id, :population_id, :ordinal, :record_key, :amount, "
    "CAST(:display AS jsonb))"
)
_POPULATION = text(
    "SELECT id, engagement_id, work_item_id, source_kind, evidence_version_id, gl_snapshot_id, "
    "query, column_map, record_count, record_unit, amount_total, sha256, sampling_unit, "
    "deviation_definition, pulled_at, created_by, created_at FROM sample_populations "
    "WHERE id = :id"
)
_TIES = text(
    "SELECT id, position, label, left_amount, comparisons, difference, result, explanation, "
    "engine_version, inputs_hash FROM completeness_ties WHERE population_id = :id "
    "ORDER BY position"
)
_NEXT_POSITION = text(
    "SELECT coalesce(max(position), 0) + 1 FROM completeness_ties WHERE population_id = :id"
)
_INSERT_TIE = text(
    "INSERT INTO completeness_ties (id, tenant_id, population_id, position, label, left_amount, "
    "comparisons, difference, result, explanation, engine_version, inputs_hash, created_by) "
    "VALUES (:id, :tenant_id, :population_id, :position, :label, :left_amount, "
    "CAST(:comparisons AS jsonb), :difference, :result, :explanation, :engine_version, "
    ":inputs_hash, :created_by)"
)


async def lock_population(session: AsyncSession, population_id: UUID) -> None:
    await session.execute(_LOCK, {"key": f"sample_population:{population_id}"})


async def insert_population(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_POPULATION, dict(values))


async def insert_records(session: AsyncSession, rows: Sequence[Values]) -> None:
    if rows:
        await session.execute(_INSERT_RECORD, [dict(r) for r in rows])


async def population(session: AsyncSession, population_id: UUID) -> Row | None:
    found = (await session.execute(_POPULATION, {"id": population_id})).mappings().first()
    return None if found is None else dict(found)


async def ties(session: AsyncSession, population_id: UUID) -> list[Row]:
    return [dict(r) for r in (await session.execute(_TIES, {"id": population_id})).mappings()]


async def next_position(session: AsyncSession, population_id: UUID) -> int:
    found = (await session.execute(_NEXT_POSITION, {"id": population_id})).scalar_one()
    return int(found)


async def insert_tie(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_TIE, dict(values))
