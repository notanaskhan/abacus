"""T-02-T31 (TASK-2624; ADR-078; T-02 §3.5, §3.7) over HTTP against Postgres: independent tests for
T-02-T16 (the questionnaire engine), T-02-T22 (portal questionnaire routes) and the portal's side
of drafts, written from the contract and SPEC, reusing only T-02-T09's world seed.

Row acceptance: "...pass on main and fail on a planted draft leak to the portal."

- A question a person added but has not sent never reaches the client's portal read (the planted
  draft): not in the list, not in the detail, and answering it is refused.
- Autosave is optimistic: two saves at the same version, the second answers 409.
- A hostile answer is stored and returned as the same inert string, never interpreted.
- A template whose wording carries markup or a formula is refused at import (dry run included).
- An inquiry reaches only its addressee.
- A K-1 recipient's details change stores no full TIN, and another recipient's id is not theirs.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.questionnaire_templates import COLUMNS
from abacus.modules.tax import k1_portal
from abacus.modules.tax.k1_portal import DetailsChangeInvalid

from . import test_t02t09_practice_board as t02t09
from . import test_t02t21_k1_release as t02t21
from . import test_t02t26_portal_k1 as t02t26
from .test_t02t09_practice_board import DEMO, Board, Json

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer
_released = t02t26._released  # pyright: ignore[reportPrivateUsage] -- T-02-T26's release world
HOSTILE = '<script>alert(1)</script> =HYPERLINK("http://x") {{ secret }} ‮'


def _csv(rows: list[str]) -> bytes:
    return ("\n".join([",".join(COLUMNS), *rows]) + "\n").encode()


async def _world(b: Board) -> tuple[AuthContext, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Samuel (manager) with the Feld organizer of three questions attached and sent; the Feld
    engagement and the questionnaire id."""
    await b.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'questionnaires.v1', 'true', 't02-t31', 'T-02-T31')",
        b.tenant,
    )
    feld = b.returns["Feld Household 1040"]
    engagement = cast(
        uuid.UUID,
        await b.seed.value("SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", feld),
    )
    binder = cast(
        uuid.UUID,
        await b.seed.value(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name) "
            "VALUES (gen_random_uuid(), $1, $2, $3, '2025 Binder') RETURNING id",
            b.tenant,
            engagement,
            feld,
        ),
    )
    samuel = await b.person("Samuel Ito", None)
    await b.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        b.tenant,
        engagement,
        samuel.user_id,
    )
    call = _as(samuel)
    template = _csv([f"General,,q{n},text,Synthetic question {n},,," for n in (1, 2, 3)])
    with frozen(DEMO):
        made = await call(
            "POST",
            "/v1/questionnaire-templates:import",
            params={"name": "Independent organizer", "dry_run": "false"},
            content=template,
        )
        assert made.status_code == 201, made.text
        tid, version = made.json()["template_id"], made.json()["version"]
        published = await call(
            "POST", f"/v1/questionnaire-templates/{tid}/versions/{version}:publish"
        )
        assert published.status_code == 200, published.text
        version_id = await b.seed.value(
            "SELECT id FROM questionnaire_template_versions WHERE template_id = $1",
            uuid.UUID(tid),
        )
        organizer = await call(
            "POST",
            f"/v1/request-lists/{binder}/questionnaires",
            json={"template_version_id": str(version_id)},
        )
    assert organizer.status_code == 201, organizer.text
    return samuel, feld, engagement, uuid.UUID(cast(str, cast(Json, organizer.json())["id"]))


async def _client(b: Board, engagement: uuid.UUID, name: str) -> AuthContext:
    who = await b.person(name, None)
    await b.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        b.tenant,
        who.user_id,
    )
    await b.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        b.tenant,
        who.user_id,
        engagement,
    )
    return replace(who, client=True, mfa_at=who.mfa_at, portal_second_step=True)


async def test_ac_a_planted_draft_question_never_reaches_the_portal(board: Board) -> None:
    samuel, _feld, engagement, questionnaire = await _world(board)
    with frozen(DEMO):
        planted = await _as(samuel)(
            "POST",
            f"/v1/questionnaires/{questionnaire}/questions",
            json={"section": "General", "type": "text", "client_wording": "Draft, not sent"},
        )
    assert planted.status_code == 201, planted.text
    draft_id = cast(str, cast(Json, planted.json())["id"])
    claire = await _client(board, engagement, "Claire Feld")
    portal = _as(claire)
    listed = await portal("GET", "/v1/portal/questionnaires")
    assert listed.status_code == 200, listed.text
    assert "Draft, not sent" not in listed.text
    detail = await portal("GET", f"/v1/portal/questionnaires/{questionnaire}")
    assert detail.status_code == 200, detail.text
    questions = cast(list[Json], cast(Json, detail.json())["questions"])
    assert draft_id not in {q["id"] for q in questions}
    assert len(questions) == 3
    answered = await portal(
        "PUT",
        f"/v1/portal/questionnaires/{questionnaire}/answers/{draft_id}",
        json={"value": "yes"},
        headers={"If-Match": "1"},
    )
    assert answered.status_code in (404, 409), answered.text


async def test_autosave_is_optimistic_and_a_hostile_answer_stays_inert(board: Board) -> None:
    _samuel, _feld, engagement, questionnaire = await _world(board)
    claire = await _client(board, engagement, "Claire Feld")
    portal = _as(claire)
    detail = cast(Json, (await portal("GET", f"/v1/portal/questionnaires/{questionnaire}")).json())
    question = cast(list[Json], detail["questions"])[0]
    path = f"/v1/portal/questionnaires/{questionnaire}/answers/{question['id']}"
    first = await portal("PUT", path, json={"value": HOSTILE}, headers={"If-Match": "1"})
    assert first.status_code == 200, first.text
    stale = await portal("PUT", path, json={"value": "later"}, headers={"If-Match": "1"})
    assert stale.status_code == 409, stale.text
    read = cast(Json, (await portal("GET", f"/v1/portal/questionnaires/{questionnaire}")).json())
    mine = next(q for q in cast(list[Json], read["questions"]) if q["id"] == question["id"])
    assert cast(Json, mine["answer"])["value"] == HOSTILE  # stored and served verbatim


async def test_a_template_with_markup_or_a_formula_is_refused(board: Board) -> None:
    samuel, _feld, _engagement, _questionnaire = await _world(board)
    call = _as(samuel)
    for wording in ("<b>Income</b>", "=HYPERLINK(1)", "Hello {{ name }}"):
        for dry in ("true", "false"):
            refused = await call(
                "POST",
                "/v1/questionnaire-templates:import",
                params={"name": f"Bad {wording[:3]}", "dry_run": dry},
                content=_csv([f"General,,q1,text,{wording},,,"]),
            )
            assert refused.status_code == 422, (wording, dry, refused.text)


async def test_an_inquiry_reaches_only_its_addressee(board: Board) -> None:
    samuel, feld, engagement, _questionnaire = await _world(board)
    claire = await _client(board, engagement, "Claire Feld")
    jonah = await _client(board, engagement, "Jonah Feld")
    contact = await board.seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
        "SELECT $1, client_id, 'Claire Feld', 'client_person', $2 FROM engagements "
        "WHERE id = $3 RETURNING id",
        board.tenant,
        claire.user_id,
        engagement,
    )
    with frozen(DEMO):
        made = await _as(samuel)(
            "POST",
            "/v1/questionnaires",
            json={
                "kind": "inquiry",
                "work_item_id": str(feld),
                "title": "A question for Claire",
                "addressed_to_contact_id": str(contact),
            },
        )
    assert made.status_code == 201, made.text
    for_claire = (await _as(claire)("GET", "/v1/portal/questionnaires")).text
    for_jonah = (await _as(jonah)("GET", "/v1/portal/questionnaires")).text
    assert "A question for Claire" not in for_jonah
    del for_claire  # sending is a person's later act; only Jonah's absence is the rule here


async def test_a_details_change_keeps_no_full_tin_and_stays_the_recipients(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    finals, (first, _second) = await _released(board)
    mine, theirs = [
        cast(
            uuid.UUID,
            await board.seed.value("SELECT recipient_id FROM k1_packages WHERE id = $1", package),
        )
        for package in finals[:2]
    ]
    address = {"line1": "1 Main St", "city": "Brooklyn", "postal_code": "11201", "country": "US"}
    with pytest.raises(DetailsChangeInvalid):
        await k1_portal.submit_details_change(
            first, mine, "address", None, {**address, "tin": "123456789"}
        )
    with pytest.raises(NotFound):
        await k1_portal.submit_details_change(first, theirs, "address", None, address)
    await k1_portal.submit_details_change(first, mine, "address", None, address)
    stored = cast(
        str,
        await board.seed.value(
            "SELECT string_agg(row_to_json(c)::text, '') FROM recipient_details_changes c "
            "WHERE tenant_id = $1",
            board.tenant,
        ),
    )
    assert "123456789" not in stored
    assert (
        await board.seed.value(
            "SELECT count(*) FROM recipient_details_changes WHERE recipient_id = $1", theirs
        )
        == 0
    )
