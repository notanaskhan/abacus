"""A-06-T11's remaining clauses (TASK-5302; A-06 §4.3; DEC-2421).

Boundary: `create_app()` over HTTP on the migrated test database. A finding and its issue commit
or fail as one; a consultation is raised by the partner or manager and concluded only by the
person consulted. (The projected conversion this PR first carried landed on main by DEC-2360.)
"""

from __future__ import annotations

import contextlib
import uuid
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.modules.assurance import findings

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    # A-06-T37 (DEC-2714): the `assurance_completion` entitlement replaces the retired flag.
    await found.seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "VALUES ($1, 'assurance_completion', '2000-01-01', 'test-seed') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    return found


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def _wi(world: Books, rest: str) -> str:
    return f"/v1/work-items/{world.work_item_id}{rest}"


async def _workpaper(world: Books) -> uuid.UUID:
    workpaper = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "created_by) VALUES ($1, $2, $3, $4, 'EBP-150', 'Findings', $5)",
        workpaper,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
        world.senior.user_id,
    )
    return workpaper


def _finding_body(workpaper: uuid.UUID) -> dict[str, object]:
    return {
        "workpaper_id": str(workpaper),
        "title": "Employer match missed on bonus pay",
        "kind": "control_deficiency",
    }


async def _finding(world: Books) -> str:
    made = await world.call(
        "POST",
        _wi(world, "/findings"),
        world.senior,
        _finding_body(await _workpaper(world)),
        headers=_keyed(),
    )
    assert made.status_code == 201, made.text
    return cast(str, cast(Json, cast(Json, made.json())["finding"])["id"])


async def test_a_finding_and_its_issue_fail_as_one(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Boom(RuntimeError):
        pass

    def fails(*_a: object) -> None:
        raise Boom

    workpaper = await _workpaper(world)
    monkeypatch.setattr(findings, "Target", fails)
    with contextlib.suppress(Boom):
        await world.call(
            "POST",
            _wi(world, "/findings"),
            world.senior,
            _finding_body(workpaper),
            headers=_keyed(),
        )
    count = "SELECT count(*) FROM {} WHERE tenant_id = $1 AND work_item_id = $2"
    for table in ("audit_findings", "issues"):
        left = await world.seed.value(count.format(table), world.tenant_id, world.work_item_id)
        assert left == 0, table


def _sample_set(engagement_id: object, status: str = "approved") -> object:
    return SimpleNamespace(
        engagement_id=engagement_id,
        status=status,
        version_no=1,
        parameters=SimpleNamespace(final_size=25),
        population=SimpleNamespace(record_count=412, record_unit="census records"),
    )


async def test_a_consultation_is_concluded_only_by_the_person_consulted(world: Books) -> None:
    raised = await world.call(
        "POST",
        _wi(world, "/consultations"),
        world.manager,
        {
            "question": "Is the late deposit a prohibited transaction?",
            "consulted_with_user_id": str(world.reviewer.user_id),
        },
        headers=_keyed(),
    )
    assert raised.status_code == 201, raised.text
    made = cast(Json, raised.json())
    assert (made["ref"], made["status"], made["conclusion"]) == ("C-01", "open", None)
    assert made["allowed_actions"] == []
    conclude = f"/v1/consultations/{made['id']}/conclude"
    body = {"conclusion": "Yes; report it on Schedule G."}

    other = await world.call("POST", conclude, world.partner, body, headers=_keyed())
    assert other.status_code == 403, other.text
    assert cast(Json, other.json())["detail"] == "not_the_consulted_person"

    # The person consulted reads the ones naming them, and may conclude them.
    listed = await world.call("GET", _wi(world, "/consultations"), world.reviewer)
    assert listed.status_code == 200, listed.text
    rows = cast(list[Json], cast(Json, listed.json())["items"])
    assert [r["question"] for r in rows] == ["Is the late deposit a prohibited transaction?"]
    assert rows[0]["allowed_actions"] == ["consultation.conclude"]

    done = await world.call("POST", conclude, world.reviewer, body, headers=_keyed())
    assert done.status_code == 200, done.text
    concluded = cast(Json, done.json())
    assert (concluded["status"], concluded["conclusion"]) == (
        "concluded",
        "Yes; report it on Schedule G.",
    )
    assert concluded["concluded_at"] is not None

    again = await world.call("POST", conclude, world.reviewer, body, headers=_keyed())
    assert again.status_code == 409, again.text
    assert cast(Json, again.json())["detail"] == "consultation_concluded"

    # The sealed question is not stored in the clear.
    sealed = await world.seed.value(
        "SELECT question_sealed FROM consultations WHERE id = $1",
        uuid.UUID(cast(str, made["id"])),
    )
    assert b"prohibited" not in cast(bytes, sealed)


async def test_who_may_raise_and_read_a_consultation(world: Books) -> None:
    body = {
        "question": "Which standard governs?",
        "consulted_with_user_id": str(world.reviewer.user_id),
    }
    staff = await world.call(
        "POST", _wi(world, "/consultations"), world.staff, body, headers=_keyed()
    )
    assert staff.status_code == 403, staff.text
    senior = await world.call(
        "POST", _wi(world, "/consultations"), world.senior, body, headers=_keyed()
    )
    assert senior.status_code == 403, senior.text

    made = await world.call(
        "POST", _wi(world, "/consultations"), world.partner, body, headers=_keyed()
    )
    assert made.status_code == 201, made.text
    # A senior holds the read, but sees only the ones naming them.
    seen = await world.call("GET", _wi(world, "/consultations"), world.senior)
    assert seen.status_code == 200, seen.text
    assert cast(Json, seen.json())["items"] == []
    everyone = await world.call("GET", _wi(world, "/consultations"), world.manager)
    assert [r["ref"] for r in cast(list[Json], cast(Json, everyone.json())["items"])] == ["C-01"]

    self_consult = await world.call(
        "POST",
        _wi(world, "/consultations"),
        world.partner,
        {"question": "Mine?", "consulted_with_user_id": str(world.partner.user_id)},
        headers=_keyed(),
    )
    assert self_consult.status_code == 422, self_consult.text
    stranger = await world.call(
        "POST",
        _wi(world, "/consultations"),
        world.partner,
        {"question": "Yours?", "consulted_with_user_id": str(uuid.uuid4())},
        headers=_keyed(),
    )
    assert stranger.status_code == 422, stranger.text
