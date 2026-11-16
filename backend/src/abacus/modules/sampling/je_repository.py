"""JE testing's tables (A-08-T12; migration 0895): `je_tests`, `je_test_criteria`,
`je_posting_user_roles`, `je_score_runs` and `je_scores`. Tenant-scoped sessions only; ids come
from the database (`RETURNING id`), never the application role."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Result, text
from sqlalchemy.ext.asyncio import AsyncSession

Row = dict[str, Any]  # Any: database rows of mixed column types
Values = Mapping[str, object]
SCORE_BATCH: Final = 5000
_PLAIN: Final = text("SELECT * FROM je_tests WHERE id = :i")
_SCORES_PAGE: Final = text(
    "SELECT * FROM je_scores WHERE run_id = :r "
    "AND (CAST(:bit AS integer) IS NULL OR (criteria_mask & CAST(:bit AS integer)) <> 0) "
    "AND (CAST(:refs AS text[]) IS NULL "
    "OR (entry_ref = ANY(CAST(:refs AS text[]))) = CAST(:in_refs AS boolean)) "
    "AND (CAST(:as AS integer) IS NULL OR score < CAST(:as AS integer) "
    "OR (score = CAST(:as AS integer) AND entry_ref > CAST(:ar AS text))) "
    "ORDER BY score DESC, entry_ref LIMIT :limit"
)
_LOCKED: Final = text("SELECT * FROM je_tests WHERE id = :i FOR UPDATE")


def _rows(result: Result[Any]) -> list[Row]:  # Any: rows of mixed column types
    return [dict(r) for r in result.mappings()]


async def insert_test(session: AsyncSession, values: Values) -> UUID:
    found = await session.scalar(
        text(
            "INSERT INTO je_tests (tenant_id, engagement_id, work_item_id, gl_snapshot_id, "
            "period_start, period_end, post_close_through, created_by) VALUES (:tenant_id, "
            ":engagement_id, :work_item_id, :gl_snapshot_id, :period_start, :period_end, "
            ":post_close_through, :created_by) ON CONFLICT (work_item_id, gl_snapshot_id) "
            "DO NOTHING RETURNING id"
        ),
        dict(values),
    )
    return cast(UUID, found) if found is not None else await _existing(session, values)


async def _existing(session: AsyncSession, values: Values) -> UUID:
    found = await session.scalar(
        text("SELECT id FROM je_tests WHERE work_item_id = :w AND gl_snapshot_id = :g"),
        {"w": values["work_item_id"], "g": values["gl_snapshot_id"]},
    )
    return cast(UUID, found)


async def test(session: AsyncSession, je_test_id: UUID, *, lock: bool = False) -> Row | None:
    rows = _rows(await session.execute(_LOCKED if lock else _PLAIN, {"i": je_test_id}))
    return rows[0] if rows else None


async def set_policy(session: AsyncSession, je_test_id: UUID, policy_version_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE je_tests SET policy_version_id = :p, row_version = row_version + 1 "
            "WHERE id = :i"
        ),
        {"i": je_test_id, "p": policy_version_id},
    )


async def set_status(
    session: AsyncSession,
    je_test_id: UUID,
    status: str,
    *,
    expect: Sequence[str],
    failure_code: str | None = None,
    score_version: int | None = None,
) -> bool:
    result = await session.execute(
        text(
            "UPDATE je_tests SET status = :s, failure_code = :f, "
            "score_version = coalesce(:v, score_version), row_version = row_version + 1 "
            "WHERE id = :i AND status = ANY(:expect) RETURNING id"
        ),
        {
            "i": je_test_id,
            "s": status,
            "f": failure_code,
            "v": score_version,
            "expect": list(expect),
        },
    )
    return result.first() is not None


async def set_sample_set(session: AsyncSession, je_test_id: UUID, sample_set_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE je_tests SET sample_set_id = :s, row_version = row_version + 1 WHERE id = :i"
        ),
        {"i": je_test_id, "s": sample_set_id},
    )


# --- criteria ------------------------------------------------------------------------------------


async def next_configured_version(session: AsyncSession, je_test_id: UUID) -> int:
    found = await session.scalar(
        text(
            "SELECT coalesce(max(configured_version), 0) + 1 FROM je_test_criteria "
            "WHERE je_test_id = :i"
        ),
        {"i": je_test_id},
    )
    return int(cast(int, found))


async def insert_criteria(session: AsyncSession, rows: Sequence[Values]) -> None:
    if rows:
        await session.execute(
            text(
                "INSERT INTO je_test_criteria (tenant_id, je_test_id, configured_version, "
                "position, key, weight, params, set_by) VALUES (:tenant_id, :je_test_id, "
                ":configured_version, :position, :key, :weight, CAST(:params AS jsonb), :set_by)"
            ),
            [{**r, "params": json.dumps(r["params"])} for r in rows],
        )


async def criteria(session: AsyncSession, je_test_id: UUID) -> list[Row]:
    """The latest configured criteria, in position order (empty before any configuration)."""
    return _rows(
        await session.execute(
            text(
                "SELECT * FROM je_test_criteria WHERE je_test_id = :i AND configured_version = "
                "(SELECT max(configured_version) FROM je_test_criteria WHERE je_test_id = :i) "
                "ORDER BY position"
            ),
            {"i": je_test_id},
        )
    )


# --- posting user roles --------------------------------------------------------------------------


async def insert_roles(session: AsyncSession, rows: Sequence[Values]) -> None:
    if rows:
        await session.execute(
            text(
                "INSERT INTO je_posting_user_roles (tenant_id, je_test_id, posting_user_sha256, "
                "posting_user_sealed, role_class, citation_id, set_by) VALUES (:tenant_id, "
                ":je_test_id, :posting_user_sha256, :posting_user_sealed, :role_class, "
                ":citation_id, :set_by)"
            ),
            list(rows),
        )


async def roles(session: AsyncSession, je_test_id: UUID) -> dict[bytes, str]:
    """posting user SHA-256 -> its latest role class."""
    result = await session.execute(
        text(
            "SELECT DISTINCT ON (posting_user_sha256) posting_user_sha256, role_class "
            "FROM je_posting_user_roles WHERE je_test_id = :i "
            "ORDER BY posting_user_sha256, created_at DESC, id DESC"
        ),
        {"i": je_test_id},
    )
    return {bytes(r[0]): str(r[1]) for r in result}


async def role_count(session: AsyncSession, je_test_id: UUID) -> int:
    found = await session.scalar(
        text(
            "SELECT count(DISTINCT posting_user_sha256) FROM je_posting_user_roles "
            "WHERE je_test_id = :i"
        ),
        {"i": je_test_id},
    )
    return int(cast(int, found or 0))


# --- score runs ----------------------------------------------------------------------------------


async def insert_run(session: AsyncSession, values: Values) -> UUID:
    found = await session.scalar(
        text(
            "INSERT INTO je_score_runs (tenant_id, je_test_id, score_version, engine_version, "
            "inputs_hash, entries_count, unique_flagged, hits) VALUES (:tenant_id, :je_test_id, "
            ":score_version, :engine_version, :inputs_hash, :entries_count, :unique_flagged, "
            "CAST(:hits AS jsonb)) ON CONFLICT (je_test_id, score_version) DO NOTHING RETURNING id"
        ),
        {**values, "hits": json.dumps(values["hits"])},
    )
    return cast(UUID, found) if found is not None else UUID(int=0)


async def insert_scores(session: AsyncSession, rows: Sequence[Values]) -> None:
    statement = text(
        "INSERT INTO je_scores (tenant_id, run_id, entry_ref, score, reason_codes, criteria_mask, "
        "posted_on, amount, account_last4, description) VALUES (:tenant_id, :run_id, :entry_ref, "
        ":score, :reason_codes, :criteria_mask, :posted_on, :amount, :account_last4, :description)"
    )
    for start in range(0, len(rows), SCORE_BATCH):
        await session.execute(statement, list(rows[start : start + SCORE_BATCH]))


async def run_of(session: AsyncSession, je_test_id: UUID, score_version: int) -> Row | None:
    rows = _rows(
        await session.execute(
            text("SELECT * FROM je_score_runs WHERE je_test_id = :i AND score_version = :v"),
            {"i": je_test_id, "v": score_version},
        )
    )
    return rows[0] if rows else None


async def run_by_id(session: AsyncSession, run_id: UUID) -> Row | None:
    rows = _rows(
        await session.execute(text("SELECT * FROM je_score_runs WHERE id = :i"), {"i": run_id})
    )
    return rows[0] if rows else None


async def all_scores(session: AsyncSession, run_id: UUID) -> list[tuple[str, int, object]]:
    """(entry_ref, score, amount) for every entry of a run, by reference."""
    result = await session.execute(
        text(
            "SELECT entry_ref, score, amount FROM je_scores WHERE run_id = :r ORDER BY entry_ref"
        ),
        {"r": run_id},
    )
    return [(str(r[0]), int(r[1]), r[2]) for r in result]


async def scores_page(
    session: AsyncSession,
    run_id: UUID,
    *,
    mask_bit: int | None,
    refs: Sequence[str] | None,
    in_refs: bool = True,
    after: tuple[int, str] | None,
    limit: int,
) -> list[Row]:
    """A page of scores, score high first then reference (keyset after `(score, ref)`); each
    filter is a bound parameter that is NULL when unset."""
    params: dict[str, object] = {
        "r": run_id,
        "limit": limit,
        "bit": None if mask_bit is None else 1 << mask_bit,
        "refs": None if refs is None else list(refs),
        "in_refs": in_refs,
        "as": None if after is None else after[0],
        "ar": None if after is None else after[1],
    }
    return _rows(await session.execute(_SCORES_PAGE, params))
