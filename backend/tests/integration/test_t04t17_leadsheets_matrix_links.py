"""TASK-7330 (T-04-T17 rest): the leadsheet, matrix and prior-year reads on Postgres. Lines of the
form only (another form, an inactive worksheet or a field without a line is left out), in sheet,
section and field order; each K-1 activity's worksheet by `k1_worksheet_id` first; the prior-year
K-1 of the same issuer on the same client's same form, and nothing for another issuer or year.
The rows go in as the superuser with foreign-key triggers off (the queries read the tables
alone); the service's arithmetic is `tests/unit/tax/test_t04t17_leadsheets_matrix_links.py`."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import Iterator
from typing import Any

import asyncpg
import pytest

from abacus.modules.tax import leadsheets as ls
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

TENANT, ENGAGEMENT, PY_ENGAGEMENT, CLIENT = (uuid.uuid4() for _ in range(4))
RETURN, PY_RETURN = uuid.uuid4(), uuid.uuid4()
HASH = "0" * 64


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _positional(query: object, order: list[str]) -> str:
    sql = str(query)
    for n, name in enumerate(order, start=1):
        sql = re.sub(rf":{name}\b", f"${n}", sql)
    return sql


async def _seed(conn: asyncpg.Connection) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}

    async def tax_return(work_item: uuid.UUID, engagement: uuid.UUID, year: int) -> None:
        await conn.execute(
            "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
            "form, tax_year) VALUES ($1, $2, $3, $4, '1040', $5)",
            TENANT,
            work_item,
            engagement,
            CLIENT,
            year,
        )

    async def sheet(
        key: str, ret: uuid.UUID, engagement: uuid.UUID, form: str, order: int, active: bool = True
    ) -> uuid.UUID:
        found: uuid.UUID = await conn.fetchval(
            "INSERT INTO return_worksheets (tenant_id, engagement_id, tax_return_id, key, "
            "form_code, title, jurisdiction, default_tsj, origin, sort_order, active, "
            "content_hash) VALUES ($1, $2, $3, $4, $5, $4, 'US', 'J', 'agent', $6, $7, $8) "
            "RETURNING id",
            TENANT,
            engagement,
            ret,
            key,
            form,
            order,
            active,
            HASH,
        )
        ids[key] = found
        return found

    async def section(
        worksheet: uuid.UUID,
        ret: uuid.UUID,
        engagement: uuid.UUID,
        key: str,
        name: str,
        order: int,
    ) -> uuid.UUID:
        return await conn.fetchval(
            "INSERT INTO return_worksheet_sections (tenant_id, engagement_id, tax_return_id, "
            "worksheet_id, key, name, sort_order, content_hash) VALUES "
            "($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
            TENANT,
            engagement,
            ret,
            worksheet,
            key,
            name,
            order,
            HASH,
        )

    async def fld(
        worksheet: uuid.UUID,
        sec: uuid.UUID,
        ret: uuid.UUID,
        engagement: uuid.UUID,
        key: str,
        line: str | None,
        value: str | None,
        order: int,
        value_type: str = "amount",
    ) -> None:
        await conn.execute(
            "INSERT INTO return_fields (tenant_id, engagement_id, tax_return_id, worksheet_id, "
            "section_id, field_key, line_ref, label, tsj, value_type, derivation, current_value, "
            "sort_order) VALUES ($1, $2, $3, $4, $5, $6, $7, $6, 'J', $8, 'input', "
            "CAST($9 AS jsonb), $10)",
            TENANT,
            engagement,
            ret,
            worksheet,
            sec,
            key,
            line,
            value_type,
            None if value is None else json.dumps({"t": "decimal", "v": value}),
            order,
        )

    async def activity(
        ret: uuid.UUID, engagement: uuid.UUID, issuer: str, worksheet: uuid.UUID | None
    ) -> uuid.UUID:
        return await conn.fetchval(
            "INSERT INTO k1_activities (tenant_id, engagement_id, tax_return_id, issuer_name, "
            "issuer_form, recipient_tsj, k1_worksheet_id, content_hash) VALUES "
            "($1, $2, $3, $4, '1065', 'T', $5, $6) RETURNING id",
            TENANT,
            engagement,
            ret,
            issuer,
            worksheet,
            HASH,
        )

    await tax_return(RETURN, ENGAGEMENT, 2025)
    await tax_return(PY_RETURN, PY_ENGAGEMENT, 2024)
    income = await sheet("income", RETURN, ENGAGEMENT, "1040", 1)
    dividends = await section(income, RETURN, ENGAGEMENT, "dividends", "Dividends", 2)
    interest = await section(income, RETURN, ENGAGEMENT, "interest", "Interest", 1)
    await fld(income, dividends, RETURN, ENGAGEMENT, "div.halvard.1a", "3b", "14280", 1)
    await fld(income, interest, RETURN, ENGAGEMENT, "int.ridgeline.5", "2b", "4600", 2)
    await fld(income, interest, RETURN, ENGAGEMENT, "int.halvard.1", "2b", "2310", 1)
    await fld(income, interest, RETURN, ENGAGEMENT, "int.note", None, None, 3)
    await fld(income, interest, RETURN, ENGAGEMENT, "int.text", "2a", None, 4, "text")
    old = await sheet("old", RETURN, ENGAGEMENT, "1040", 2, active=False)
    old_s = await section(old, RETURN, ENGAGEMENT, "x", "X", 1)
    await fld(old, old_s, RETURN, ENGAGEMENT, "old.1", "1a", "1", 1)
    ny = await sheet("it201", RETURN, ENGAGEMENT, "it201", 3)
    ny_s = await section(ny, RETURN, ENGAGEMENT, "x", "X", 1)
    await fld(ny, ny_s, RETURN, ENGAGEMENT, "it201.20", "20", "1550", 1)

    k1 = await sheet("k1-ridgeline", RETURN, ENGAGEMENT, "k1", 4)
    k1_s = await section(k1, RETURN, ENGAGEMENT, "boxes", "Boxes", 1)
    await fld(k1, k1_s, RETURN, ENGAGEMENT, "box2", "2", "307900", 1)
    await fld(k1, k1_s, RETURN, ENGAGEMENT, "box5", "5", "4600", 2)
    ids["ridgeline"] = await activity(RETURN, ENGAGEMENT, "Ridgeline Property Partners, LP", k1)
    ids["bare"] = await activity(RETURN, ENGAGEMENT, "Another LP", None)

    py_k1 = await sheet("py-k1-ridgeline", PY_RETURN, PY_ENGAGEMENT, "k1", 1)
    py_s = await section(py_k1, PY_RETURN, PY_ENGAGEMENT, "boxes", "Boxes", 1)
    await fld(py_k1, py_s, PY_RETURN, PY_ENGAGEMENT, "box2", "2", "281600", 1)
    await activity(PY_RETURN, PY_ENGAGEMENT, "Ridgeline Property Partners, LP", py_k1)
    await activity(PY_RETURN, PY_ENGAGEMENT, "Someone Else LP", None)
    return ids


def test_the_reads_on_postgres(db: sc.Database) -> None:
    async def go() -> tuple[dict[str, uuid.UUID], dict[str, list[Any]]]:  # Any: asyncpg rows
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute("SET session_replication_role = replica")
            ids = await _seed(conn)
            out: dict[str, list[Any]] = {  # Any: asyncpg rows
                "lead": await conn.fetch(
                    _positional(ls.LEADSHEET_FIELDS, ["r", "form"]),
                    RETURN,
                    "1040",
                ),
                "activities": await conn.fetch(
                    _positional(ls.ACTIVITIES, ["r"]),
                    RETURN,
                ),
                "prior": await conn.fetch(
                    _positional(ls.PRIOR_SHEET, ["a"]),
                    ids["ridgeline"],
                ),
                "prior_bare": await conn.fetch(
                    _positional(ls.PRIOR_SHEET, ["a"]),
                    ids["bare"],
                ),
                "k1": await conn.fetch(
                    _positional(ls.SHEET_AMOUNTS, ["w"]),
                    ids["k1-ridgeline"],
                ),
                "linked": await conn.fetch(
                    _positional(ls.LINKED_FIELDS, ["r"]),
                    RETURN,
                ),
                "year": [
                    await conn.fetchval(
                        _positional(ls.RETURN_YEAR, ["r"]),
                        RETURN,
                    )
                ],
            }
            return ids, out
        finally:
            await conn.close()

    ids, out = asyncio.run(go())
    assert [(r["section_key"], r["field_key"], r["line_ref"]) for r in out["lead"]] == [
        ("interest", "int.halvard.1", "2b"),
        ("interest", "int.ridgeline.5", "2b"),
        ("dividends", "div.halvard.1a", "3b"),
    ]
    activities = {r["id"]: r["worksheet_id"] for r in out["activities"]}
    assert activities == {ids["ridgeline"]: ids["k1-ridgeline"], ids["bare"]: None}
    assert [(r["engagement_id"], r["worksheet_id"]) for r in out["prior"]] == [
        (PY_ENGAGEMENT, ids["py-k1-ridgeline"])
    ]
    assert out["prior_bare"] == []  # last year has no K-1 from this issuer
    assert [r["field_key"] for r in out["k1"]] == ["box2", "box5"]
    assert out["year"] == [2025]
    # The mismatch check and the links read every active field with its value, in sheet order.
    linked = [(r["field_key"], r["line_ref"]) for r in out["linked"]]
    assert ("old.1", "1a") not in linked  # inactive worksheet
    assert linked[:5] == [  # field order within the sheet, then key (sections do not order)
        ("div.halvard.1a", "3b"),
        ("int.halvard.1", "2b"),
        ("int.ridgeline.5", "2b"),
        ("int.note", None),
        ("int.text", "2a"),
    ]
    values = {r["field_key"]: r["current_value"] for r in out["linked"]}
    assert json.loads(values["div.halvard.1a"]) == {"t": "decimal", "v": "14280"}
