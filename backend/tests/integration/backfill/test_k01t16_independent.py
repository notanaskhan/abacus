"""K-01-T16 (TASK-2516; ADR-078; K-01 §3.4, §3.5): independent AC tests for K-01-T12 and T14,
written from the epic's acceptance criteria and the matrix, not from the implementing sessions'
tests.

- Published-version immutability: no step route changes a published version, and its rows read
  the same after a draft is made, edited, discarded and made again.
- `step_key` stability (AC4.4, AC5.7): a step's key is the same in every version and draft, an
  edit keeps it, a manual step gets a fresh one, and a key absent from a version does not resolve.
- QM-only mandatory changes (AC5.3, INV-1): the agent and the system are denied by the matrix, a
  manager without `methodology.approve` is refused, the QM owner without a fresh second factor is
  refused, and with one her change is audited under her name.
- The `methodology_step` verifier (AC4.5, INV-2): accepted only for a step in the cited version
  with a quote equal after NFKC folding; anything else is rejected and not verified.
- Export determinism (AC4.6): byte-identical per version, a different version differs, and every
  export writes `methodology_version.exported`.

Not covered here: the "Where step 4 is cited" list of AC4.7 (INV-3). No route lists a step's
citations on main yet (C4 has no by-source query); TASK-2516 records it as open for K-01-T15.
"""

from __future__ import annotations

import contextlib
import re
import uuid
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.agents.methodology_citations import verify_methodology_step
from abacus.modules.evidence.api import CitationAnchor, CitationClaim, CitationVerdict
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

from .support import Json, Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- the shared synthetic fixture builders
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
    _workbook,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's BH EBP workbook
)

pytestmark = pytest.mark.asyncio
TEMPLATE = "BH Audit Methodology"


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


async def _world(net: Net) -> tuple[uuid.UUID, Person, Person, uuid.UUID, uuid.UUID]:
    tenant = await net.seed.firm()
    manager = await net.seed.person(tenant, "firm_admin")  # methodology.manage, not .approve
    owner = await net.seed.person(tenant, "practice_leader")  # the QM owner
    await _flags(net, tenant, "methodology.programs")
    v2 = await _import(net, manager, TEMPLATE, _workbook())
    v3 = await _import(net, manager, TEMPLATE, _workbook(changed=4))
    return tenant, manager, owner, v2, v3


async def _draft(net: Net, who: Person, published: uuid.UUID) -> uuid.UUID:
    made = await net.call("POST", f"/v1/methodology/versions/{published}/drafts", who)
    assert made.status_code == 201, made.text
    return uuid.UUID(cast(str, made.json()["version_id"]))


# --- published-version immutability -----------------------------------------------------------


async def test_no_step_route_changes_a_published_version(net: Net) -> None:
    _tenant, manager, owner, _v2, v3 = await _world(net)
    program_id, before = await _steps(net, manager, v3)
    four = next(s for s in before if s["number"] == 4)
    one = next(s for s in before if s["number"] == 1)
    attempts: tuple[tuple[str, str, Person, Json | None], ...] = (
        ("PATCH", f"/v1/methodology/versions/{v3}/steps/{four['id']}", manager, {"text": "x"}),
        ("DELETE", f"/v1/methodology/versions/{v3}/steps/{four['id']}", manager, None),
        (
            "POST",
            f"/v1/methodology/versions/{v3}/programs/{program_id}/steps",
            manager,
            {"text": "Added to a published version", "level": "testing"},
        ),
        (
            "POST",
            f"/v1/methodology/versions/{v3}/steps/{one['id']}/mandatory",
            owner,
            {"mandatory": False},
        ),
    )
    for method, path, who, body in attempts:
        response = await _send(
            net, method, path, who, body=body, if_match=cast(int, four["row_version"])
        )
        assert response.status_code in (403, 404, 409), (method, path, response.text)
    _pid, after = await _steps(net, manager, v3)
    assert after == before


async def test_the_published_version_reads_the_same_through_a_draft_lifecycle(net: Net) -> None:
    _tenant, manager, _owner, _v2, v3 = await _world(net)
    _pid, before = await _steps(net, manager, v3)
    draft = await _draft(net, manager, v3)
    _dpid, steps = await _steps(net, manager, draft)
    eleven = next(s for s in steps if s["number"] == 11)
    edited = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{eleven['id']}",
        manager,
        body={"text": "Tailored in the draft only"},
        if_match=cast(int, eleven["row_version"]),
    )
    assert edited.status_code == 200, edited.text
    _pid, after = await _steps(net, manager, v3)
    assert after == before
    assert next(s for s in after if s["number"] == 11)["text"] == "Step 11 of program 1"


# --- step_key stability (AC4.4, AC5.7) --------------------------------------------------------


async def test_ac4_4_a_key_is_the_same_in_every_version_and_draft(net: Net) -> None:
    _tenant, manager, _owner, v2, v3 = await _world(net)
    _p2, two = await _steps(net, manager, v2)
    _p3, three = await _steps(net, manager, v3)
    assert [s["step_key"] for s in two] == [s["step_key"] for s in three]
    assert two[3]["text"] != three[3]["text"]  # step 4 changed, its key did not
    draft = await _draft(net, manager, v3)
    _pd, drafted = await _steps(net, manager, draft)
    assert [s["step_key"] for s in drafted] == [s["step_key"] for s in three]
    four = next(s for s in drafted if s["number"] == 4)
    edited = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{four['id']}",
        manager,
        body={"text": "Step 4, edited"},
        if_match=cast(int, four["row_version"]),
    )
    assert cast(Json, edited.json())["step_key"] == four["step_key"]


async def test_ac5_1_a_manual_step_gets_a_fresh_key_unlike_any_other(net: Net) -> None:
    _tenant, manager, _owner, _v2, v3 = await _world(net)
    draft = await _draft(net, manager, v3)
    program_id, steps = await _steps(net, manager, draft)
    added = await net.call(
        "POST",
        f"/v1/methodology/versions/{draft}/programs/{program_id}/steps",
        manager,
        body={"text": "A manual step", "level": "testing"},
    )
    assert added.status_code == 201, added.text
    key = cast(str, added.json()["step_key"])
    assert key not in {s["step_key"] for s in steps}
    assert re.fullmatch(r"bh-ebp-110-m[0-9a-f]{12}", key), key


async def test_ac4_4_a_key_absent_from_the_version_does_not_resolve(net: Net) -> None:
    _tenant, manager, _owner, v2, v3 = await _world(net)
    draft = await _draft(net, manager, v3)
    program_id, _ = await _steps(net, manager, draft)
    added = await net.call(
        "POST",
        f"/v1/methodology/versions/{draft}/programs/{program_id}/steps",
        manager,
        body={"text": "Only in the draft", "level": "testing"},
    )
    key = cast(str, added.json()["step_key"])
    headers = net.headers(manager)
    for version, status in ((draft, 200), (v3, 404), (v2, 404)):
        found = await net.http.get(
            "/v1/methodology/steps/resolve",
            params={"key": key, "version": str(version)},
            headers=headers,
        )
        assert found.status_code == status, (version, found.text)


async def test_ac5_7_a_discarded_draft_keeps_its_number_and_the_keys_hold(net: Net) -> None:
    tenant, manager, _owner, _v2, v3 = await _world(net)
    first = await _draft(net, manager, v3)
    await _flags(net, tenant, "methodology.lifecycle")
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{first}/state", manager)).json()
    )
    gone = await net.call(
        "POST",
        f"/v1/methodology/versions/{first}/discard",
        manager,
        body={"row_version": state["row_version"]},
    )
    assert gone.status_code == 200, gone.text
    second = await _draft(net, manager, v3)
    numbers = await net.seed.rows(
        "SELECT id, version FROM methodology_versions WHERE id = ANY($1::uuid[])", [first, second]
    )
    by_id = {r["id"]: r["version"] for r in numbers}
    assert by_id[second] == by_id[first] + 1
    _p3, three = await _steps(net, manager, v3)
    _ps, again = await _steps(net, manager, second)
    assert [s["step_key"] for s in again] == [s["step_key"] for s in three]


# --- QM-only mandatory changes (AC5.3, INV-1) -------------------------------------------------


def test_inv1_the_agent_and_the_system_never_change_what_is_mandatory() -> None:
    for action in ("methodology.approve", "methodology.manage"):
        rule = RULES[action]
        assert rule.decisions.get("agent", "deny") == "deny", action
        assert rule.decisions.get("system", "deny") == "deny", action
    assert RULES["methodology.approve"].mfa_recent


async def test_ac5_3_only_the_qm_owner_with_a_fresh_factor_unlocks_a_step(net: Net) -> None:
    tenant, manager, owner, _v2, v3 = await _world(net)
    draft = await _draft(net, manager, v3)
    _pid, steps = await _steps(net, manager, draft)
    one = next(s for s in steps if s["number"] == 1)
    assert one["mandatory"] is True
    path = f"/v1/methodology/versions/{draft}/steps/{one['id']}/mandatory"
    body: Json = {"mandatory": False}
    refused = await _send(net, "POST", path, manager, body=body, if_match=1)
    assert refused.status_code == 403, refused.text
    stale_factor = await _send(net, "POST", path, owner, body=body, if_match=1, mfa=False)
    assert stale_factor.status_code in (401, 403), stale_factor.text
    _pid, unchanged = await _steps(net, manager, draft)
    assert next(s for s in unchanged if s["number"] == 1)["mandatory"] is True
    done = await _send(net, "POST", path, owner, body=body, if_match=1)
    assert done.status_code == 200, done.text
    rows = await net.seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'methodology_step.mandatory_changed'",
        tenant,
    )
    assert [str(r["actor_id"]) for r in rows] == [str(owner.user_id)]
    edit = await _send(
        net,
        "PATCH",
        f"/v1/methodology/versions/{draft}/steps/{one['id']}",
        manager,
        body={"text": "Now optional, now editable"},
        if_match=cast(int, cast(Json, done.json())["row_version"]),
    )
    assert edit.status_code == 200, edit.text


# --- the verifier (AC4.5, INV-2) --------------------------------------------------------------


class _ReadOnly(Exception):
    """Rolls back a unit of work that only read."""


async def _verify(
    ctx: AuthContext, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    found: list[CitationVerdict] = []
    with contextlib.suppress(_ReadOnly):
        async with uow(ctx.tenant) as tx:
            found.append(await verify_methodology_step(tx, ctx, claim, anchor))
            raise _ReadOnly
    return found[0]


async def _ctx(net: Net, tenant: uuid.UUID, who: Person) -> AuthContext:
    membership = cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
        ),
    )
    return AuthContext(
        TenantContext(tenant, "human", str(who.user_id)),
        who.user_id,
        membership,
        "firm_admin",
        datetime.now(UTC),
    )


async def test_ac4_5_the_verifier_accepts_only_a_step_in_the_cited_version(net: Net) -> None:
    tenant, manager, _owner, v2, v3 = await _world(net)
    ctx = await _ctx(net, tenant, manager)
    anchor = CitationAnchor("workpaper", uuid.uuid4())

    def claim(version: uuid.UUID, key: str, quote: str | None) -> CitationClaim:
        return CitationClaim(
            "methodology_step", {"template_version_id": str(version), "step_key": key}, quote=quote
        )

    accepted = await _verify(
        ctx, claim(v3, "bh-ebp-110-4", "Step 4 of program 1 (revised)"), anchor
    )
    assert accepted.verified, accepted.reason
    # NFKC: full-width digits and a compatibility space fold to the step's text.
    wide = "Step\u00a0\uff14 of program \uff11"
    folded = await _verify(ctx, claim(v3, "bh-ebp-110-4", wide), anchor)
    assert folded.verified, folded.reason
    # The v3 wording is not the v2 step's: the same key at v2 rejects it.
    other = await _verify(ctx, claim(v2, "bh-ebp-110-4", "(revised)"), anchor)
    assert not other.verified
    unknown = await _verify(ctx, claim(v3, "bh-ebp-110-99", None), anchor)
    assert not unknown.verified and unknown.reason == "source_not_found"
    wrong = await _verify(ctx, claim(v3, "bh-ebp-110-4", "words the step never had"), anchor)
    assert not wrong.verified and wrong.match_id is None


# --- export determinism (AC4.6) ---------------------------------------------------------------


async def test_ac4_6_exports_are_deterministic_per_version_and_audited(net: Net) -> None:
    tenant, manager, _owner, v2, v3 = await _world(net)
    headers = net.headers(manager)
    three = [
        await net.http.get(f"/v1/methodology/versions/{v3}/export.xlsx", headers=headers)
        for _ in range(2)
    ]
    two = await net.http.get(f"/v1/methodology/versions/{v2}/export.xlsx", headers=headers)
    assert [r.status_code for r in (*three, two)] == [200, 200, 200]
    assert three[0].content == three[1].content
    assert two.content != three[0].content
    exported = await net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'methodology_version.exported'",
        tenant,
    )
    assert exported == 3
