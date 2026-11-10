"""P-05-T09 (SPEC-650 AC-1, AC-15): a working paper's cells and rows carry threads, and an internal
thread converts to an open AUD-17 review note in the same unit of work.

Exceptions!A3 on AUD-09's paper opens a thread whose label names the place; "Convert to review
note…" raises a note on the paper pinned to the cell and records `converted` on the thread.
"""

from __future__ import annotations

import uuid

import pytest

from .p05_support import Collab, collab
from .support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def w(net: Net) -> Collab:
    world = await collab(net)
    await world.flag(True)
    return world


async def _paper(w: Collab) -> uuid.UUID:
    seed = w.net.seed
    client_id = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", w.site.engagement_id
    )
    # One assurance work item per engagement (`work_items_one_assurance`): reuse it when a paper
    # was seeded before.
    work_item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        w.site.engagement_id,
    ) or await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'assurance', 'Northwind PY2025', "
        "'2025-01-01', '2025-12-31', $4) RETURNING id",
        w.tenant_id,
        w.site.engagement_id,
        client_id,
        w.grace.user_id,
    )
    paper = uuid.uuid4()
    await seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "created_by) VALUES ($1, $2, $3, $4, 'AUD-09', 'Attribute testing', $5)",
        paper,
        w.tenant_id,
        w.site.engagement_id,
        work_item,
        w.grace.user_id,
    )
    return paper


def _anchor(paper: uuid.UUID, **locator: object) -> dict[str, object]:
    return {"anchor_kind": "workpaper", "anchor_id": str(paper), "locator": locator}


async def test_ac1_exceptions_a3_opens_a_thread_on_the_cell(w: Collab) -> None:
    paper = await _paper(w)
    opened = await w.call(
        "POST",
        "/v1/comment-threads",
        w.margaret,
        {"anchor": _anchor(paper, sheet="Exceptions", cell="A3"), "body": "Exception 3 open."},
    )
    assert opened.status_code == 201, opened.text
    assert "Exceptions!A3" in str(opened.json())


async def test_a_locator_outside_the_paper_is_refused(w: Collab) -> None:
    paper = await _paper(w)
    for locator in ({"sheet": "Exceptions", "cell": "A0"}, {"sheet": "Exceptions", "row": 0}):
        response = await w.call(
            "POST",
            "/v1/comment-threads",
            w.margaret,
            {"anchor": _anchor(paper, **locator), "body": "x"},
        )
        assert response.status_code in (404, 422), response.text


async def test_ac15_convert_to_review_note_in_one_unit_of_work(w: Collab) -> None:
    paper = await _paper(w)
    opened = await w.call(
        "POST",
        "/v1/comment-threads",
        w.hannah,
        {"anchor": _anchor(paper, sheet="Exceptions", row=6), "body": "Tie row 6 to AJE-1."},
    )
    assert opened.status_code == 201, opened.text
    thread_id = opened.json()["thread"]["id"] if "thread" in opened.json() else opened.json()["id"]
    converted = await w.call(
        "POST", f"/v1/comment-threads/{thread_id}/convert-to-review-note", w.hannah
    )
    assert converted.status_code == 201, converted.text
    note_id = converted.json()["review_note_id"]
    note = await w.net.seed.rows(
        "SELECT status, target_type, target_id, anchor_ref FROM reviewable_notes WHERE id = $1",
        uuid.UUID(note_id),
    )
    assert note and note[0]["status"] == "open"
    assert note[0]["target_type"] == "workpaper" and note[0]["target_id"] == paper
    actions = [a for a, _ in await w.audit_actions(thread_id)]
    assert "comment_thread.converted" in actions
    staff = await w.call(
        "POST", f"/v1/comment-threads/{thread_id}/convert-to-review-note", w.marcus
    )
    assert staff.status_code in (403, 404)
