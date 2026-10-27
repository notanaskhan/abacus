"""K-01-T06: a methodology version's lifecycle (DEC-651). "Margaret approves EBP v3 effective
Jan 1, 2026 and v2 reads superseded Dec 31, 2025, while the agent principal and Hannah Leclerc
get 403 and the refusal is audited."

The workbooks are K-01-T05's (`_workbook`); v2 imports with the lifecycle off (published, as
before), v3 with it on (needs review). Rows are read back as the superuser.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.methodology.lifecycle import approve_version

from .support import Json, Net
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
    _workbook,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's BH EBP workbook
)

pytestmark = pytest.mark.asyncio
V3_FROM = date(2026, 1, 1)


async def test_ac_margaret_approves_v3_and_v2_is_superseded_the_day_before(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    hannah = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET level = 'manager' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        hannah.user_id,
    )
    await _flags(net, tenant, "methodology.programs")
    v2 = await _import(net, admin, "BH EBP", _workbook(programs=True))
    await seed.run(
        "UPDATE methodology_version_states SET effective_from = '2025-01-01' "
        "WHERE version_id = $1",
        v2,
    )
    await _flags(net, tenant, "methodology.lifecycle")
    v3 = await _import(net, admin, "BH EBP", _workbook(programs=True, changed=3))

    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", margaret)).json()
    )
    assert state["status"] == "needs_review"
    assert all(i["ok"] for i in cast(list[Json], state["checklist"]))
    body: Json = {
        "effective_from": V3_FROM.isoformat(),
        "checklist_hash": state["checklist_hash"],
        "row_version": state["row_version"],
    }

    # Hannah (a manager) holds no `methodology.approve`: 403, and the refusal is kept.
    refused = await net.call("POST", f"/v1/methodology/versions/{v3}/approve", hannah, body=body)
    assert refused.status_code == 403, refused.text
    # The agent principal: refused at the service, and audited as a non-human's attempt.
    agent = AuthContext(
        TenantContext(tenant, cast(ActorKind, "agent"), f"run:{uuid.uuid4()}"),
        margaret.user_id,
        uuid.uuid4(),
        "practice_leader",
        datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(Forbidden):
        await approve_version(
            agent,
            v3,
            effective_from=V3_FROM,
            checklist_hash=cast(str, state["checklist_hash"]),
            row_version=cast(int, state["row_version"]),
        )
    audited = {
        r["action"]
        for r in await seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
            tenant,
            str(v3),
        )
    }
    assert {"methodology_version.approve_refused", "decision.refused_non_human"} <= audited

    approved = await net.call(
        "POST", f"/v1/methodology/versions/{v3}/approve", margaret, body=body
    )
    assert approved.status_code == 200, approved.text
    out = cast(Json, approved.json())
    assert (out["status"], out["effective_from"], out["approval_basis"]) == (
        "published",
        "2026-01-01",
        "approved",
    )
    assert out["approved_by_user_id"] == str(margaret.user_id)
    old = await seed.rows(
        "SELECT status, effective_to, default_for_new_engagements FROM "
        "methodology_version_states WHERE version_id = $1",
        v2,
    )
    assert (old[0]["status"], old[0]["effective_to"]) == ("superseded", date(2025, 12, 31))
    assert old[0]["default_for_new_engagements"] is False
    assert out["default_for_new_engagements"] is True

    # A second approval of the same version: it is no longer in review.
    again = await net.call("POST", f"/v1/methodology/versions/{v3}/approve", margaret, body=body)
    assert again.status_code == 409 and again.json()["detail"] in (
        "stale_version",
        "version_frozen",
    )


async def test_a_changed_checklist_is_refused(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, "methodology.programs", "methodology.lifecycle")
    v3 = await _import(net, admin, "BH EBP", _workbook(programs=True))
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", margaret)).json()
    )
    body: Json = {
        "effective_from": V3_FROM.isoformat(),
        "checklist_hash": "sha256:" + "0" * 64,
        "row_version": state["row_version"],
    }
    refused = await net.call("POST", f"/v1/methodology/versions/{v3}/approve", margaret, body=body)
    assert (refused.status_code, refused.json()["detail"]) == (409, "checklist_changed")
