"""T-03-T05 (TASK-3335; DEC-2326): the organizer template lifecycle and the editor's wall.

Row acceptance: "only the template owner can publish v7 with fresh MFA". US-2.2 and US-2.3: one
draft at a time, a published version is frozen, a binder takes the version published for its tax
year and a binder already started keeps its own.
"""

from __future__ import annotations

import uuid
from typing import cast

from abacus.kernel.clock import frozen
from abacus.modules.requests.api import questionnaire_from_template
from abacus.modules.requests.questionnaire_templates import COLUMNS

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board

T = "/v1/questionnaire-templates"


def _file() -> bytes:
    rows = [",".join(COLUMNS)]
    rows += [f"Income,,q{n},yes_no,Synthetic question {n},,," for n in range(1, 4)]
    return ("\n".join(rows) + "\n").encode()


async def _flags(b: Board) -> None:
    for flag in ("questionnaires.editor",):
        await b.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 't03-t05', 'T-03-T05')",
            b.tenant,
            flag,
        )


async def _published_template(b: Board, owner: uuid.UUID) -> tuple[str, Json]:
    """An imported, published v1 with an owner and a key, as T-03-T15 loads one."""
    call = _as(await b.person("Samuel Ito", None))
    made = await call(
        "POST",
        f"{T}:import",
        params={"name": "1040 organizer", "dry_run": "false"},
        content=_file(),
    )
    assert made.status_code == 201, made.text
    template_id = made.json()["template_id"]
    await b.seed.run(
        "UPDATE questionnaire_templates SET key = 'organizer_1040', form_family = '1040', "
        "owner_id = $1 WHERE id = $2",
        owner,
        uuid.UUID(template_id),
    )
    return template_id, cast(Json, made.json())


async def test_us22_a_draft_copies_the_current_version_and_only_the_owner_publishes(
    board: Board,
) -> None:
    await _flags(board)
    with frozen(DEMO):
        samuel = await board.person("Samuel Ito", None)
        other = await board.person("Kevin Osei", None)
        template_id, _ = await _published_template(board, samuel.user_id)
        owner = _as(samuel)
        first = await owner(
            "POST", f"{T}/{template_id}/versions/1:publish", json={"applies_to_tax_year": 2025}
        )
        assert first.status_code == 200, first.text

        draft = await owner(
            "POST",
            f"{T}/{template_id}/versions",
            json={"change_summary": "Add a question"},
            headers={"Idempotency-Key": "t05-1"},
        )
        assert draft.status_code == 201, draft.text
        assert (draft.json()["version"], draft.json()["status"]) == (2, "draft")
        again = await owner(
            "POST",
            f"{T}/{template_id}/versions",
            json={},
            headers={"Idempotency-Key": "t05-2"},
        )
        assert (again.status_code, again.json()["detail"]) == (409, "draft_exists")

        questionnaire = draft.json()["questionnaire_id"]
        editor = await owner("GET", f"/v1/questionnaires/{questionnaire}/editor")
        assert editor.status_code == 200, editor.text
        body = cast(Json, editor.json())
        assert body["owner_kind"] == "template_version"
        assert len(cast(list[Json], body["questions"])) == 3
        assert body["banner"] == (
            "Editing template 1040 organizer v2 — changes apply to TY2025 binders"
        )
        assert "questionnaire_template.publish" in cast(list[str], body["allowed_actions"])

        kept = cast(list[Json], body["questions"])
        saved = await owner(
            "PUT",
            f"/v1/questionnaires/{questionnaire}",
            headers={"If-Match": str(body["row_version"])},
            json={
                "sections": [
                    {"key": s["key"], "title": s["title"]}
                    for s in cast(list[Json], body["sections"])
                ],
                "questions": [
                    {
                        "key": q["key"],
                        "section_key": q["section_key"],
                        "type": q["type"],
                        "client_wording": q["client_wording"],
                    }
                    for q in kept[:2]
                ],
            },
        )
        assert saved.status_code == 200, saved.text
        diff = await owner("GET", f"{T}/{template_id}/versions/2/diff")
        assert diff.status_code == 200, diff.text
        assert (diff.json()["against"], diff.json()["changes"][0]["kind"]) == (1, "removed")

        no_year = await owner("POST", f"{T}/{template_id}/versions/2:publish", json={})
        assert (no_year.status_code, no_year.json()["detail"]) == (422, "tax_year_required")
        by_other = await _as(other)(
            "POST", f"{T}/{template_id}/versions/2:publish", json={"applies_to_tax_year": 2026}
        )
        assert by_other.status_code == 403, by_other.text

        published = await owner(
            "POST", f"{T}/{template_id}/versions/2:publish", json={"applies_to_tax_year": 2026}
        )
        assert published.status_code == 200, published.text
        (row,) = await board.seed.rows(
            "SELECT status, applies_to_tax_year, published_actor_kind "
            "FROM questionnaire_template_versions WHERE template_id = $1 AND version = 2",
            uuid.UUID(template_id),
        )
        assert tuple(row) == ("published", 2026, "human")
        assert (
            await board.seed.value(
                "SELECT count(*) FROM outbox "
                "WHERE event_type = 'questionnaire_template.published' AND tenant_id = $1",
                board.tenant,
            )
            == 2
        )
        frozen_save = await owner(
            "PUT",
            f"/v1/questionnaires/{questionnaire}",
            headers={"If-Match": str(cast(Json, saved.json()["questionnaire"])["row_version"])},
            json={"sections": [], "questions": []},
        )
        assert (frozen_save.status_code, frozen_save.json()["detail"]) == (
            409,
            "version_published",
        )
        gone = await owner("DELETE", f"{T}/{template_id}/versions/2")
        assert (gone.status_code, gone.json()["detail"]) == (409, "version_published")


async def test_a_discarded_draft_leaves_the_lists_and_frees_the_next_draft(board: Board) -> None:
    await _flags(board)
    with frozen(DEMO):
        samuel = await board.person("Samuel Ito", None)
        template_id, _ = await _published_template(board, samuel.user_id)
        owner = _as(samuel)
        await owner(
            "POST", f"{T}/{template_id}/versions/1:publish", json={"applies_to_tax_year": 2025}
        )
        await owner(
            "POST", f"{T}/{template_id}/versions", json={}, headers={"Idempotency-Key": "d1"}
        )
        dropped = await owner("DELETE", f"{T}/{template_id}/versions/2")
        assert (dropped.status_code, dropped.json()["status"]) == (200, "discarded")
        shown = await owner("GET", f"{T}/{template_id}")
        assert [v["version"] for v in cast(list[Json], shown.json()["versions"])] == [1]
        listed = await owner("GET", T)
        assert cast(list[Json], listed.json())[0]["draft_version"] is None
        next_one = await owner(
            "POST", f"{T}/{template_id}/versions", json={}, headers={"Idempotency-Key": "d2"}
        )
        assert (next_one.status_code, next_one.json()["version"]) == (201, 3)


async def test_only_a_partner_owns_a_template(board: Board) -> None:
    await _flags(board)
    with frozen(DEMO):
        samuel = await board.person("Samuel Ito", None)
        kevin = await board.person("Kevin Osei", None)
        await board.seed.run(
            "UPDATE memberships SET level = 'staff' WHERE user_id = $1", kevin.user_id
        )
        template_id, _ = await _published_template(board, samuel.user_id)
        refused = await _as(samuel)(
            "PUT", f"{T}/{template_id}/owner", json={"owner_id": str(kevin.user_id)}
        )
    assert refused.status_code == 403 or refused.json()["detail"] == "owner_not_partner"


async def test_us23_a_binder_takes_its_years_version_and_keeps_it(board: Board) -> None:
    await _flags(board)
    feld = board.returns["Feld Household 1040"]
    engagement = await board.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", feld
    )
    binder = await board.seed.value(
        "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name) "
        "VALUES (gen_random_uuid(), $1, $2, $3, '2025 Binder') RETURNING id",
        board.tenant,
        engagement,
        feld,
    )
    with frozen(DEMO):
        samuel = await board.person("Samuel Ito", None)
        await board.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'manager')",
            board.tenant,
            engagement,
            samuel.user_id,
        )
        template_id, _ = await _published_template(board, samuel.user_id)
        owner = _as(samuel)
        await owner(
            "POST", f"{T}/{template_id}/versions/1:publish", json={"applies_to_tax_year": 2025}
        )
        made = await questionnaire_from_template(samuel, "organizer_1040", 2025, binder)
        (row,) = await board.seed.rows(
            "SELECT q.source_template_version_id, v.version FROM questionnaires q "
            "JOIN questionnaire_template_versions v ON v.id = q.source_template_version_id "
            "WHERE q.id = $1",
            made,
        )
        assert row["version"] == 1
        await owner(
            "POST", f"{T}/{template_id}/versions", json={}, headers={"Idempotency-Key": "b1"}
        )
        await owner(
            "POST", f"{T}/{template_id}/versions/2:publish", json={"applies_to_tax_year": 2026}
        )
        badge = await owner("GET", f"/v1/binders/{binder}/questionnaire")
        assert badge.status_code == 200, badge.text
        assert cast(Json, badge.json()["template"])["version"] == 1


async def test_the_wall_holds_a_binders_answers_from_the_firm_level_gate(board: Board) -> None:
    await _flags(board)
    feld = board.returns["Feld Household 1040"]
    engagement = await board.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", feld
    )
    binder = await board.seed.value(
        "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name) "
        "VALUES (gen_random_uuid(), $1, $2, $3, '2025 Binder') RETURNING id",
        board.tenant,
        engagement,
        feld,
    )
    with frozen(DEMO):
        samuel = await board.person("Samuel Ito", None)
        await board.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'manager')",
            board.tenant,
            engagement,
            samuel.user_id,
        )
        template_id, _ = await _published_template(board, samuel.user_id)
        owner = _as(samuel)
        await owner(
            "POST", f"{T}/{template_id}/versions/1:publish", json={"applies_to_tax_year": 2025}
        )
        made = await questionnaire_from_template(samuel, "organizer_1040", 2025, binder)
        await board.seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "SELECT $1, $2, client_id, $2 FROM engagements WHERE id = $3",
            board.tenant,
            samuel.user_id,
            engagement,
        )
        walled = await owner("GET", f"/v1/questionnaires/{made}/editor")
    assert walled.status_code in {403, 404}, walled.text
