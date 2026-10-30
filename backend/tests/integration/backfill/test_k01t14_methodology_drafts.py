"""K-01-T14 (TASK-2315; K-01 §3.5 AC5.1 to AC5.4, AC5.7; DEC-1361): "Hannah's draft adds step 17
and edits step 11, her mandatory change returns 403, Margaret's succeeds with fresh MFA, and the
published version is unchanged."

Hannah holds `methodology.manage` (a firm admin) without `methodology.approve`; Margaret is the QM
owner (a practice leader). The workbook is K-01-T05's: program BH-EBP-110 has 16 steps, step 1
mandatory, each step linked to the request of its number. Rows are read back as the superuser.
"""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from .support import Json, Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
    _workbook,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's BH EBP workbook
)

pytestmark = pytest.mark.asyncio


async def _send(
    net: Net,
    method: str,
    path: str,
    who: Person,
    *,
    body: Json | None = None,
    if_match: int | None = None,
    mfa: bool = True,
) -> httpx.Response:
    headers = net.headers(who, mfa=mfa)
    if if_match is not None:
        headers["If-Match"] = str(if_match)
    return await net.http.request(method, path, json=body, headers=headers)


async def _steps(net: Net, who: Person, version: uuid.UUID) -> tuple[str, list[Json]]:
    programs = cast(
        list[Json],
        (await net.call("GET", f"/v1/methodology/versions/{version}/programs", who)).json(),
    )
    first = next(p for p in programs if p["code"] == "BH-EBP-110")
    steps = cast(
        list[Json],
        (await net.call("GET", f"/v1/methodology/programs/{first['id']}/steps", who)).json(),
    )
    return cast(str, first["id"]), steps


async def test_ac5_hannah_drafts_margaret_locks_and_the_published_version_stays(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, "methodology.programs")
    published = await _import(net, hannah, "BH EBP", _workbook(programs=True))
    _pid, before = await _steps(net, hannah, published)

    # AC5.1: Draft vN+1 from the published version, with its lineage; one open draft at a time.
    made = await net.call("POST", f"/v1/methodology/versions/{published}/drafts", hannah)
    assert made.status_code == 201, made.text
    draft_out = cast(Json, made.json())
    assert draft_out["status"] == "draft"
    draft = uuid.UUID(cast(str, draft_out["version_id"]))
    again = await net.call("POST", f"/v1/methodology/versions/{published}/drafts", hannah)
    assert (again.status_code, again.json()["detail"]) == (409, "draft_exists")
    origin = await seed.rows(
        "SELECT drafted_from_version_id, origin FROM methodology_versions WHERE id = $1", draft
    )
    assert (origin[0]["drafted_from_version_id"], origin[0]["origin"]) == (published, "draft")

    program_id, steps = await _steps(net, hannah, draft)
    assert [s["step_key"] for s in steps] == [s["step_key"] for s in before]
    by_number = {cast(int, s["number"]): s for s in steps}

    # AC5.2: edit step 11; its key and source stay, the edit names Hannah.
    eleven = by_number[11]
    edited = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{eleven['id']}",
        hannah,
        body={"text": "Step 11, tailored wording"},
        if_match=cast(int, eleven["row_version"]),
    )
    assert edited.status_code == 200, edited.text
    out = cast(Json, edited.json())
    assert (out["text"], out["step_key"], out["origin"]) == (
        "Step 11, tailored wording",
        eleven["step_key"],
        eleven["origin"],
    )
    who = await seed.value("SELECT edited_by FROM program_steps WHERE id = $1", out["id"])
    assert who == hannah.user_id
    # AC5.4: a second write at the old row version is stale.
    stale = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{eleven['id']}",
        hannah,
        body={"text": "Lost update"},
        if_match=cast(int, eleven["row_version"]),
    )
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_version")

    # + Step: row 17, a manual step with a fresh key.
    added = await net.call(
        "POST",
        f"/v1/methodology/versions/{draft}/programs/{program_id}/steps",
        hannah,
        body={"text": "Confirm the plan's late remittances", "level": "testing"},
    )
    assert added.status_code == 201, added.text
    seventeen = cast(Json, added.json())
    assert (seventeen["number"], seventeen["origin"], seventeen["mandatory"]) == (
        17,
        "manual",
        False,
    )

    # AC5.3: the mandatory step is locked for Hannah, both as an edit and as a lock change.
    one = by_number[1]
    assert one["mandatory"] is True
    locked = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{one['id']}",
        hannah,
        body={"text": "Weakened"},
        if_match=cast(int, one["row_version"]),
    )
    assert (locked.status_code, locked.json()["detail"]) == (409, "mandatory_locked")
    unlock: Json = {"mandatory": False}
    path = f"/v1/methodology/versions/{draft}/steps/{one['id']}/mandatory"
    refused = await _send(net, "POST", path, hannah, body=unlock, if_match=1)
    assert refused.status_code == 403, refused.text
    no_mfa = await _send(net, "POST", path, margaret, body=unlock, if_match=1, mfa=False)
    assert no_mfa.status_code in (401, 403), no_mfa.text
    done = await _send(net, "POST", path, margaret, body=unlock, if_match=1)
    assert done.status_code == 200, done.text
    assert cast(Json, done.json())["mandatory"] is False

    # Remove the added step; a step a request links to stays.
    removed = await _send(
        net,
        "DELETE",
        f"/v1/methodology/versions/{draft}/steps/{seventeen['id']}",
        hannah,
        if_match=cast(int, seventeen["row_version"]),
    )
    assert removed.status_code == 200, removed.text
    linked = by_number[5]
    kept = await _send(
        net,
        "DELETE",
        f"/v1/methodology/versions/{draft}/steps/{linked['id']}",
        hannah,
        if_match=cast(int, linked["row_version"]),
    )
    assert (kept.status_code, kept.json()["detail"]) == (409, "step_has_requests")

    # The published version is unchanged.
    _pid, after = await _steps(net, hannah, published)
    assert after == before
    audited = {
        r["action"]
        for r in await seed.rows("SELECT action FROM audit_events WHERE tenant_id = $1", tenant)
    }
    assert {
        "methodology_version.draft_created",
        "methodology_step.edited",
        "methodology_step.added",
        "methodology_step.removed",
        "methodology_step.mandatory_changed",
        "methodology_step.mandatory_refused",
    } <= audited

    # AC5.7: a discarded draft keeps its number; the next draft takes the one after.
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{draft}/state", hannah)).json()
    )
    gone = await net.call(
        "POST",
        f"/v1/methodology/versions/{draft}/discard",
        hannah,
        body={"row_version": state["row_version"]},
    )
    assert gone.status_code == 200 and gone.json()["status"] == "discarded", gone.text
    nxt = await net.call("POST", f"/v1/methodology/versions/{published}/drafts", hannah)
    assert nxt.status_code == 201, nxt.text
    numbers = [
        r["version"]
        for r in await seed.rows(
            "SELECT version FROM methodology_versions WHERE template_id = "
            "(SELECT template_id FROM methodology_versions WHERE id = $1) ORDER BY version",
            published,
        )
    ]
    assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2]
