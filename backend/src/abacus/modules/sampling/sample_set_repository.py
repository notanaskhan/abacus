"""The sample sets' data access (A-03-T10; migration 0520): sample sets, their versions, strata and
items, and the population rows a draw reads. Statements only; `sample_sets` and `draw` decide."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Values = Mapping[str, object]
Row = dict[str, Any]  # Any: a row's columns are of mixed types

# A version's number is the set's next (the table's trigger checks it); two draws on one set are
# serialised by a transaction advisory lock on the set (versions are inserted, never locked).
_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_INSERT_SET = text(
    "INSERT INTO sample_sets (id, tenant_id, engagement_id, work_item_id, title, purpose, "
    "program_step_key, created_by) VALUES (:id, :tenant_id, :engagement_id, :work_item_id, "
    ":title, :purpose, :program_step_key, :created_by)"
)
_SET = text(
    "SELECT id, engagement_id, work_item_id, title, purpose, program_step_key, created_by, "
    "created_at FROM sample_sets WHERE id = :id"
)
_SETS_OF_WORK_ITEM = text(
    "SELECT id, engagement_id, work_item_id, title, purpose, program_step_key, created_by, "
    "created_at FROM sample_sets WHERE work_item_id = :work_item_id ORDER BY created_at, id"
)
_SETS_OF_ENGAGEMENT = text("SELECT id FROM sample_sets WHERE engagement_id = :engagement_id")
_VERSIONS = text(
    "SELECT id, sample_set_id, version_no, population_id, method, parameters, "
    "size_policy_version_id, computed_size, statistical_crosscheck_size, override_size, "
    "override_rationale, final_size, seed, seed_source, sampler_version, inputs_hash, "
    "items_hash, content_hash, status, failure_code, approved_by, approved_at, "
    "approved_actor_kind, superseded_by, created_by, created_at, row_version FROM "
    "sample_set_versions WHERE sample_set_id = ANY(:ids) ORDER BY sample_set_id, version_no"
)
_VERSION = text(
    "SELECT id, sample_set_id, version_no, population_id, method, parameters, "
    "size_policy_version_id, computed_size, statistical_crosscheck_size, override_size, "
    "override_rationale, final_size, seed, seed_source, sampler_version, inputs_hash, "
    "items_hash, content_hash, status, failure_code, approved_by, approved_at, "
    "approved_actor_kind, superseded_by, created_by, created_at, row_version FROM "
    "sample_set_versions WHERE sample_set_id = :sample_set_id AND version_no = :version_no"
)
_VERSION_BY_ID = text(
    "SELECT id, sample_set_id, version_no, population_id, method, parameters, "
    "size_policy_version_id, computed_size, statistical_crosscheck_size, override_size, "
    "override_rationale, final_size, seed, seed_source, sampler_version, inputs_hash, "
    "items_hash, content_hash, status, failure_code, approved_by, approved_at, "
    "approved_actor_kind, superseded_by, created_by, created_at, row_version FROM "
    "sample_set_versions WHERE id = :id"
)
_NEXT_VERSION = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM sample_set_versions "
    "WHERE sample_set_id = :sample_set_id"
)
_INSERT_VERSION = text(
    "INSERT INTO sample_set_versions (id, tenant_id, sample_set_id, version_no, population_id, "
    "method, parameters, size_policy_version_id, computed_size, statistical_crosscheck_size, "
    "override_size, override_rationale, final_size, seed, seed_source, sampler_version, "
    "inputs_hash, created_by) VALUES (:id, :tenant_id, :sample_set_id, :version_no, "
    ":population_id, :method, CAST(:parameters AS jsonb), :size_policy_version_id, "
    ":computed_size, :statistical_crosscheck_size, :override_size, :override_rationale, "
    ":final_size, :seed, :seed_source, :sampler_version, :inputs_hash, :created_by)"
)
_MARK_DRAFT = text(
    "UPDATE sample_set_versions SET status = 'draft', items_hash = :items_hash, "
    "content_hash = :content_hash, row_version = row_version + 1 "
    "WHERE id = :id AND status = 'drawing'"
)
_MARK_FAILED = text(
    "UPDATE sample_set_versions SET status = 'failed', failure_code = :failure_code, "
    "row_version = row_version + 1 WHERE id = :id AND status = 'drawing'"
)
_APPROVE = text(
    "UPDATE sample_set_versions SET status = 'approved', approved_by = :approved_by, "
    "approved_at = :approved_at, approved_actor_kind = 'human', row_version = row_version + 1 "
    "WHERE id = :id AND status = 'draft' AND row_version = :row_version"
)
_SUPERSEDE = text(
    "UPDATE sample_set_versions SET status = 'superseded', superseded_by = :superseded_by, "
    "row_version = row_version + 1 WHERE sample_set_id = :sample_set_id "
    "AND status = 'approved' AND id <> :superseded_by RETURNING id, version_no"
)
_INSERT_STRATUM = text(
    "INSERT INTO sample_strata (tenant_id, sample_set_version_id, position, min_amount, "
    "max_amount, population_count, population_amount, test_rule, random_count, selected_count) "
    "VALUES (:tenant_id, :sample_set_version_id, :position, :min_amount, :max_amount, "
    ":population_count, :population_amount, :test_rule, :random_count, :selected_count)"
)
_STRATA = text(
    "SELECT position, min_amount, max_amount, population_count, population_amount, test_rule, "
    "random_count, selected_count FROM sample_strata WHERE sample_set_version_id = :id "
    "ORDER BY position"
)
_INSERT_ITEM = text(
    "INSERT INTO sample_items (tenant_id, sample_set_version_id, position, "
    "population_record_ordinal, record_key, stratum_position, selection_reason, display) VALUES "
    "(:tenant_id, :sample_set_version_id, :position, :population_record_ordinal, :record_key, "
    ":stratum_position, :selection_reason, CAST(:display AS jsonb))"
)
_ITEMS = text(
    "SELECT i.position, i.population_record_ordinal, i.record_key, i.stratum_position, "
    "i.selection_reason, i.display, r.amount FROM sample_items i "
    "JOIN sample_set_versions v ON v.tenant_id = i.tenant_id AND v.id = i.sample_set_version_id "
    "JOIN sample_population_records r ON r.tenant_id = i.tenant_id "
    "AND r.population_id = v.population_id AND r.ordinal = i.population_record_ordinal "
    "WHERE i.sample_set_version_id = :id ORDER BY i.position"
)
_ITEM_COUNTS = text(
    "SELECT sample_set_version_id, count(*) AS n FROM sample_items "
    "WHERE sample_set_version_id = ANY(:ids) GROUP BY sample_set_version_id"
)
_RECORDS = text(
    "SELECT ordinal, record_key, amount, display FROM sample_population_records "
    "WHERE population_id = :id ORDER BY ordinal"
)
_TIE_RESULTS = text(
    "SELECT population_id, result, difference FROM completeness_ties "
    "WHERE population_id = ANY(:ids) ORDER BY population_id, position"
)
_POPULATIONS = text(
    "SELECT id, engagement_id, work_item_id, record_count, amount_total, sha256, created_at "
    "FROM sample_populations WHERE id = ANY(:ids)"
)


async def lock_set(session: AsyncSession, sample_set_id: UUID) -> None:
    await session.execute(_LOCK, {"key": f"sample_set:{sample_set_id}"})


async def insert_set(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_SET, dict(values))


async def sample_set(session: AsyncSession, sample_set_id: UUID) -> Row | None:
    found = (await session.execute(_SET, {"id": sample_set_id})).mappings().first()
    return None if found is None else dict(found)


async def sets_of_work_item(session: AsyncSession, work_item_id: UUID) -> list[Row]:
    rows = await session.execute(_SETS_OF_WORK_ITEM, {"work_item_id": work_item_id})
    return [dict(r) for r in rows.mappings()]


async def sets_of_engagement(session: AsyncSession, engagement_id: UUID) -> list[UUID]:
    rows = await session.execute(_SETS_OF_ENGAGEMENT, {"engagement_id": engagement_id})
    return [r[0] for r in rows]


async def versions(session: AsyncSession, sample_set_ids: Sequence[UUID]) -> list[Row]:
    if not sample_set_ids:
        return []
    rows = await session.execute(_VERSIONS, {"ids": list(sample_set_ids)})
    return [dict(r) for r in rows.mappings()]


async def version(session: AsyncSession, sample_set_id: UUID, version_no: int) -> Row | None:
    found = (
        (
            await session.execute(
                _VERSION, {"sample_set_id": sample_set_id, "version_no": version_no}
            )
        )
        .mappings()
        .first()
    )
    return None if found is None else dict(found)


async def version_by_id(session: AsyncSession, version_id: UUID) -> Row | None:
    found = (await session.execute(_VERSION_BY_ID, {"id": version_id})).mappings().first()
    return None if found is None else dict(found)


async def next_version_no(session: AsyncSession, sample_set_id: UUID) -> int:
    found = (await session.execute(_NEXT_VERSION, {"sample_set_id": sample_set_id})).scalar_one()
    return int(found)


async def insert_version(session: AsyncSession, values: Values) -> None:
    await session.execute(_INSERT_VERSION, dict(values))


async def mark_draft(session: AsyncSession, values: Values) -> bool:
    return (await session.execute(_MARK_DRAFT, dict(values))).rowcount == 1


async def mark_failed(session: AsyncSession, version_id: UUID, failure_code: str) -> bool:
    found = await session.execute(_MARK_FAILED, {"id": version_id, "failure_code": failure_code})
    return found.rowcount == 1


async def approve(session: AsyncSession, values: Values) -> bool:
    return (await session.execute(_APPROVE, dict(values))).rowcount == 1


async def supersede_approved(
    session: AsyncSession, sample_set_id: UUID, by: UUID
) -> list[tuple[UUID, int]]:
    found = await session.execute(
        _SUPERSEDE, {"sample_set_id": sample_set_id, "superseded_by": by}
    )
    return [(r[0], r[1]) for r in found]


async def insert_strata(session: AsyncSession, rows: Sequence[Values]) -> None:
    if rows:
        await session.execute(_INSERT_STRATUM, [dict(r) for r in rows])


async def strata(session: AsyncSession, version_id: UUID) -> list[Row]:
    return [dict(r) for r in (await session.execute(_STRATA, {"id": version_id})).mappings()]


async def insert_items(session: AsyncSession, rows: Sequence[Values]) -> None:
    if rows:
        await session.execute(_INSERT_ITEM, [dict(r) for r in rows])


async def items(session: AsyncSession, version_id: UUID) -> list[Row]:
    return [dict(r) for r in (await session.execute(_ITEMS, {"id": version_id})).mappings()]


async def item_counts(session: AsyncSession, version_ids: Sequence[UUID]) -> dict[UUID, int]:
    if not version_ids:
        return {}
    rows = await session.execute(_ITEM_COUNTS, {"ids": list(version_ids)})
    return {r[0]: int(r[1]) for r in rows}


async def records(session: AsyncSession, population_id: UUID) -> list[Row]:
    return [dict(r) for r in (await session.execute(_RECORDS, {"id": population_id})).mappings()]


async def tie_results(session: AsyncSession, population_ids: Sequence[UUID]) -> list[Row]:
    if not population_ids:
        return []
    rows = await session.execute(_TIE_RESULTS, {"ids": list(population_ids)})
    return [dict(r) for r in rows.mappings()]


async def populations(session: AsyncSession, population_ids: Sequence[UUID]) -> list[Row]:
    if not population_ids:
        return []
    rows = await session.execute(_POPULATIONS, {"ids": list(population_ids)})
    return [dict(r) for r in rows.mappings()]
