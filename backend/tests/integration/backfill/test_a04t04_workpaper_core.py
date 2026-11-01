"""A-04-T04 (TASK-2711; A-04 §3.1 AC1.3, AC1.6, AC1.7; DEC-1762): the workpaper core service.

"An L2 sign-off goes stale after a cell edit, two exports of one version are byte-identical, and a
citation to Exceptions!D2 verifies through C4." Also: a stale `expected_version` answers 409
`version_conflict`, overriding an agent value without a reason answers 422 `reason_required`, an
earlier version is projected as it stood, and the export is audited.

Boundary: `create_app()` over HTTP on the migrated test database; the paper is seeded as A-04's
drafter will leave it (an internal-control paper with an Exceptions sheet); the citation goes
through `evidence.api.record_citations`, C4's one writer.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

from .tb_support import Books, Json, books

FLAG: Final = "workpapers.core"
D2: Final = "14850.00"


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T04') ON CONFLICT DO NOTHING",
        found.tenant_id,
        FLAG,
    )
    forget_flags()
    return found


async def _paper(world: Books) -> uuid.UUID:
    """Northwind's IC paper: an Exceptions sheet with D2 (a person's) and E2 (an agent's)."""
    paper = uuid.uuid4()
    seed = world.seed
    await seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "audit_area, created_by, kind) VALUES ($1, $2, $3, $4, 'IC', 'Internal Control', "
        "'Controls', $5, 'internal_control')",
        paper,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
        world.senior.user_id,
    )
    await seed.run(
        "INSERT INTO workpaper_sections (tenant_id, workpaper_id, sheet_key, title, position, "
        "band_kind) VALUES ($1, $2, 'exceptions', 'Exceptions', 0, 'sheet')",
        world.tenant_id,
        paper,
    )
    for cell, value, source, state, suggestion in (
        ("D2", D2, "human", "human", None),
        ("E2", "Deficiency", "agent", "suggested", uuid.uuid4()),
    ):
        await seed.run(
            "INSERT INTO workpaper_cells (tenant_id, workpaper_id, sheet_key, cell_key, raw, "
            "value_source, set_by, value, value_state, suggestion_id) VALUES ($1, $2, "
            "'exceptions', $3, $4, $5, $6, jsonb_build_object('t', $7::text, 'v', $4::text), "
            "$8, $9)",
            world.tenant_id,
            paper,
            cell,
            value,
            source,
            world.senior.user_id,
            "decimal" if cell == "D2" else "text",
            state,
            suggestion,
        )
    return paper


def _wp(world: Books, paper: uuid.UUID, rest: str = "") -> str:
    return f"/v1/engagements/{world.site.engagement_id}/workpapers/{paper}{rest}"


async def _record(world: Books, paper: uuid.UUID, query: str = "") -> Json:
    response = await world.call("GET", _wp(world, paper, f"/record{query}"), world.manager)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def _edit(
    world: Books, paper: uuid.UUID, version: int, cells: list[Json]
) -> tuple[int, Json]:
    response = await world.net.http.patch(
        _wp(world, paper, "/cells"),
        json={"expected_version": version, "cells": cells},
        headers={**world.net.headers(world.manager), "Idempotency-Key": str(uuid.uuid4())},
    )
    return response.status_code, cast(Json, response.json())


def _rung(record: Json, level: str) -> Json:
    [found] = [r for r in cast(list[Json], record["sign_offs"]) if r["level"] == level]
    return found


async def test_ac_an_l2_sign_off_goes_stale_after_a_cell_edit(world: Books) -> None:
    paper = await _paper(world)
    for who, step in ((world.senior, "prepare"), (world.manager, "review")):
        signed = await world.call("POST", _wp(world, paper, f"/sign-offs/{step}"), who)
        assert signed.status_code == 201, signed.text
    before = await _record(world, paper)
    assert _rung(before, "L2")["stale"] is False and _rung(before, "L2")["initials"] == "PO"
    status, after = await _edit(
        world,
        paper,
        cast(int, before["current_version_no"]),
        [
            {
                "sheet_key": "exceptions",
                "cell_key": "D2",
                "value": {"t": "decimal", "v": "14900.00"},
            }
        ],
    )
    assert status == 200, after
    assert after["version_no"] == after["current_version_no"] == before["current_version_no"] + 1  # pyright: ignore[reportOperatorIssue] -- ints
    assert _rung(after, "L2")["stale"] is True and _rung(after, "L1")["stale"] is True
    [d2] = [c for c in cast(list[Json], after["cells"]) if c["cell_key"] == "D2"]
    assert d2["value"] == {"t": "decimal", "v": "14900.00"} and d2["value_state"] == "human"
    # The earlier version is projected as it stood, read-only but exportable.
    earlier = await _record(world, paper, f"?version={before['current_version_no']}")
    [old] = [c for c in cast(list[Json], earlier["cells"]) if c["cell_key"] == "D2"]
    assert old["value"]["v"] == D2  # pyright: ignore[reportIndexIssue] -- a TypedValue
    assert earlier["allowed_actions"] == ["workpaper.export"]
    versions = await world.call("GET", _wp(world, paper, "/versions"), world.manager)
    assert versions.status_code == 200
    newest = cast(list[Json], versions.json())[0]
    assert (newest["cause"], newest["produced_by_kind"]) == ("edit", "human")


async def test_ac_a_stale_version_is_409_and_an_agent_override_needs_a_reason(
    world: Books,
) -> None:
    paper = await _paper(world)
    record = await _record(world, paper)
    current = cast(int, record["current_version_no"])
    status, body = await _edit(
        world,
        paper,
        current + 1,
        [{"sheet_key": "exceptions", "cell_key": "D2", "value": {"t": "decimal", "v": "1.00"}}],
    )
    assert (status, body["detail"]) == (409, "version_conflict")
    status, body = await _edit(
        world,
        paper,
        current,
        [
            {
                "sheet_key": "exceptions",
                "cell_key": "E2",
                "value": {"t": "text", "v": "No exception"},
            }
        ],
    )
    assert (status, body["detail"]) == (422, "reason_required")
    status, body = await _edit(
        world,
        paper,
        current,
        [
            {
                "sheet_key": "exceptions",
                "cell_key": "E2",
                "value": {"t": "text", "v": "No exception"},
                "reason": "Walkthrough on Sep 9 found the control operated",
            }
        ],
    )
    assert status == 200, body
    [e2] = [c for c in cast(list[Json], body["cells"]) if c["cell_key"] == "E2"]
    assert (e2["value_state"], e2["value_source"]) == ("edited", "human")


async def test_ac_two_exports_of_one_version_are_byte_identical_and_audited(world: Books) -> None:
    paper = await _paper(world)
    first = await world.call("GET", _wp(world, paper, "/export.xlsx"), world.manager)
    second = await world.call("GET", _wp(world, paper, "/export.xlsx"), world.manager)
    assert first.status_code == second.status_code == 200, first.text
    assert first.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert first.content == second.content and first.content[:2] == b"PK"
    exported = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'workpaper.exported'",
        world.tenant_id,
    )
    assert exported == 2


async def test_ac_a_citation_to_exceptions_d2_verifies_through_c4(world: Books) -> None:
    paper = await _paper(world)
    actor = await world.human(world.manager)

    async def cite(value: str, engagement: uuid.UUID) -> tuple[bool, str | None, str | None]:
        async with uow(actor.tenant) as tx:
            [row] = await record_citations(
                tx,
                actor=actor,
                anchor=CitationAnchor(
                    type="workpaper", id=paper, ref="D2", engagement_id=engagement
                ),
                claims=[
                    CitationClaim(
                        "workpaper_cell",
                        {
                            "sheet_id": str(paper),
                            "sheet_key": "exceptions",
                            "row_key": "2",
                            "column_key": "D",
                        },
                        value=value,
                    )
                ],
            )
        return row.verified, row.verification_reason, row.match_id

    verified, reason, match = await cite("14,850.00", world.site.engagement_id)
    assert (verified, reason) == (True, None)
    assert match == f"wp:{paper}!exceptions.2.D"
    assert (await cite("14,851.00", world.site.engagement_id))[:2] == (False, "value_mismatch")
    # Another engagement's anchor never learns the cell (no oracle across engagements).
    assert (await cite("14,850.00", uuid.uuid4()))[:2] == (False, "source_not_visible")


async def test_the_flag_off_hides_the_routes(world: Books) -> None:
    paper = await _paper(world)
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        world.tenant_id,
        FLAG,
    )
    forget_flags()
    response = await world.call("GET", _wp(world, paper, "/record"), world.manager)
    assert response.status_code == 404
