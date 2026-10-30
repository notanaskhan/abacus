"""T-02-T16 (TASK-2323; T-02 §3.5; DEC-1369) over HTTP against Postgres: "The Feld organizer
created from an imported template has 24 questions in 9 sections and no template text exists in
the repository."

The template is built here from synthetic wording (never committed as firm content), imported as
CSV: a dry run lists 24 added questions and stores nothing; the import stores a draft version a
person publishes; attaching it to the Feld binder makes an organizer of 24 questions in 9
sections, sent by the attach. An inquiry needs an addressee.
"""

from __future__ import annotations

import uuid
from typing import cast

from abacus.kernel.clock import frozen
from abacus.modules.requests.questionnaire_templates import COLUMNS

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board


def _template() -> bytes:
    """24 questions over 9 sections, synthetic wording only."""
    sizes = (4, 3, 3, 3, 2, 3, 2, 2, 2)
    rows = [",".join(COLUMNS)]
    n = 0
    for s, size in enumerate(sizes, start=1):
        for _ in range(size):
            n += 1
            rows.append(f"Section {s},,q{n},yes_no,Synthetic question {n},,,")
    return ("\n".join(rows) + "\n").encode()


async def _binder(b: Board, item: uuid.UUID) -> uuid.UUID:
    engagement = await b.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", item
    )
    return cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name) "
            "VALUES (gen_random_uuid(), $1, $2, $3, '2025 Binder') RETURNING id",
            b.tenant,
            engagement,
            item,
        ),
    )


async def test_ac_the_feld_organizer_has_24_questions_in_9_sections(board: Board) -> None:
    await board.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'questionnaires.v1', 'true', 't02-t16', 'T-02-T16')",
        board.tenant,
    )
    feld = board.returns["Feld Household 1040"]
    binder = await _binder(board, feld)
    samuel = await board.person("Samuel Ito", None)  # partner level: imports and publishes
    engagement = await board.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", feld
    )
    await board.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        board.tenant,
        engagement,
        samuel.user_id,
    )
    call = _as(samuel)
    path = "/v1/questionnaire-templates:import"
    with frozen(DEMO):
        dry = await call(
            "POST",
            path,
            params={"name": "BH Organizer 1040", "dry_run": "true"},
            content=_template(),
        )
        assert dry.status_code == 201, dry.text
        assert (len(cast(list[str], dry.json()["added"])), dry.json()["version"]) == (24, None)
        assert await board.seed.value("SELECT count(*) FROM questionnaire_templates") == 0
        real = await call(
            "POST",
            path,
            params={"name": "BH Organizer 1040", "dry_run": "false"},
            content=_template(),
        )
        assert real.status_code == 201, real.text
        template_id, version = real.json()["template_id"], real.json()["version"]
        published = await call(
            "POST", f"/v1/questionnaire-templates/{template_id}/versions/{version}:publish"
        )
        assert published.status_code == 200, published.text
        assert published.json()["current_version"] == 1
        version_id = await board.seed.value(
            "SELECT id FROM questionnaire_template_versions WHERE template_id = $1",
            uuid.UUID(template_id),
        )
        organizer = await call(
            "POST",
            f"/v1/request-lists/{binder}/questionnaires",
            json={"template_version_id": str(version_id)},
        )
        assert organizer.status_code == 201, organizer.text
        body = cast(Json, organizer.json())
        questions = cast(list[Json], body["questions"])
        assert (body["kind"], body["total"], body["answered"]) == ("organizer", 24, 0)
        assert len({q["section"] for q in questions}) == 9
        assert all(q["sent_at"] is not None for q in questions)
        inquiry = await call(
            "POST",
            "/v1/questionnaires",
            json={"kind": "inquiry", "work_item_id": str(feld), "title": "Inquiries"},
        )
    assert inquiry.status_code == 422, inquiry.text
