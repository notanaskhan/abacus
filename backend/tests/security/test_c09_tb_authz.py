"""A-02 security review (TASK-1185, TASK-1186; SPEC-333 AC-9, AC-26, AC-30): the C9 stubs and
`connection.read`, through the real `authorise`, `get_ref` and walls on the migrated test
database. Nothing is mocked.

- Each C9 v1 stub route answers a walled caller exactly as it answers an engagement that never
  existed: 404 with the same body (INV-3, DEC-43). The control, an engagement the caller works on
  with `ledger.tb_workpaper` on, answers 501, so the 404s are not the flag's.
- `connection.read` is authorised on an engagement. On a client-level resource it is refused to
  a senior who sits on another engagement of the firm: a firm-wide read must not draw that
  person's roles from every engagement for a `scope_only` action (INV-4).
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise

from .support import Env, Person, Seeder

TBS: Final = "/v1/engagements/{e}/trial-balances/{tb}"
# (method, path under the trial balance, JSON body) for each C9 v1 stub (DEC-314). The view by
# layer and the leadsheet by area are live since A-02-T10: their walls, independence and flag
# are proved on a real trial balance in `test_a02t10_tb_read_model.py`; the issue link since
# A-02-T17, in `test_a02t17_tie_service.py` (a walled member's 404 is the missing engagement's).
STUBS: Final = (("GET", "/export.xlsx", None),)
IDS: Final = ["export"]


async def _flag_on(seed: Seeder, tenant_id: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'ledger.tb_workpaper', 'true', 'test-seed', 'A-02 security review')",
        tenant_id,
    )


async def _call(
    env: Env, who: Person, method: str, path: str, body: object, engagement_id: uuid.UUID
) -> tuple[int, str]:
    url = (TBS + path).format(e=engagement_id, tb=uuid.uuid4(), check=uuid.uuid4())
    headers = env.net.headers(who)
    if method == "POST":
        headers["Idempotency-Key"] = f"a02-{uuid.uuid4().hex}"
    response = await env.net.http.request(method, url, json=body, headers=headers)
    return response.status_code, response.text


@pytest.mark.parametrize(("method", "path", "body"), STUBS, ids=IDS)
async def test_ac26_a_walled_caller_and_a_missing_engagement_get_the_same_404(
    env: Env, method: str, path: str, body: object
) -> None:
    await _flag_on(env.net.seed, env.tenant_id)
    manager = await env.walled("manager")  # on both engagements, walled from client A
    walled = await _call(env, manager, method, path, body, env.a.engagement_id)
    missing = await _call(env, manager, method, path, body, uuid.uuid4())
    assert walled[0] == 404
    assert walled == missing
    assert str(env.a.engagement_id) not in walled[1] and env.a.marker not in walled[1]
    # The control: the same caller on an engagement they work on reaches the stub.
    control = await _call(env, manager, method, path, body, env.b.engagement_id)
    assert control[0] == 501, control[1]


async def _context(seed: Seeder, who: Person) -> AuthContext:
    membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            who.tenant_id,
            who.user_id,
        ),
    )
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        membership,
        None,
        None,
    )


async def test_ac30_connection_read_on_a_client_is_refused_to_a_senior_of_another_engagement(
    env: Env,
) -> None:
    seed = env.net.seed
    senior = await seed.person(env.tenant_id)
    await seed.member(env.b, senior, "senior")  # client B's engagement only
    ctx = await _context(seed, senior)
    with pytest.raises(Forbidden):
        await authorise(ctx, "connection.read", Resource.client(env.tenant_id, env.a.client_id))
    # Not vacuous: on the engagement the senior sits on, the read is allowed.
    await authorise(
        ctx,
        "connection.read",
        Resource.engagement(
            env.tenant_id, env.b.engagement_id, archived=False, client_id=env.b.client_id
        ),
    )
