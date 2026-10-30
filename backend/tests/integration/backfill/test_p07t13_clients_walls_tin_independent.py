# ac-test-author: ayushkbhatia
"""P-07-T13: independent acceptance tests (ADR-078) for P-07-T07 to T10 (the TIN and relationship
migration, the clients index, the client record and overview, the TIN seal, mask and reveal).

Written from the plan and the contract, not from the code: SPEC-321 Story 2 (AC-6 to AC-9);
P-07 Stories 1.1 to 1.3 and 8.1; `docs/contracts/clients.md` §2 to §7; SPEC-002 AC-4 and AC-18
(walls bind every role; offshore refuses only `not_offshore` actions); DEC-43 (404 semantics, no
count, admins included), DEC-141, DEC-153 and DEC-223 (the reveal is held through an open
engagement of the entity's client; a firm role alone never reveals; an SSN or ITIN on a firm that
is not synthetic is 422 until C19), and the contract's §6 rows from DEC-227 (stale MFA answers
`mfa_step_up_required`; 20 reveals per rolling hour). The row: "walls answer 404 with no count
(INV-3), Grace metadata-only, TIN never in payloads, logs or outbox, reveal rules, SSN guard,
relationship isolation, attribution (INV-5), tenant isolation on new tables".

HTTP through `create_app()` against the migrated Postgres, with fake-identity tokens. Seeding runs
as the superuser, fresh firm per test. The TIN is sealed through `organisations.api.seal_tin` (the
contract's only writer; intake, its first route, is P-07-T42) and relationships through
`organisations.api.add_relationship`. Expected values are typed from the contract. Where the code
does not meet the plan, the test is a strict xfail naming the escaped defect (never weakened).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

import httpx
import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import uow
from abacus.modules.identity.api import (
    RULES,
    AgentContext,
    AuthContext,
    Forbidden,
    authorise,
    engagement_resource,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)
from abacus.modules.organisations import slots
from abacus.modules.organisations import tin as tin_module
from abacus.modules.organisations.api import (
    NewRelationship,
    OverviewItem,
    OverviewSection,
    SectionRows,
    TinKindNotAllowed,
    add_relationship,
    seal_tin,
)

from .support import Net, Person, Role, Seeder, Site

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FLAG = "clients.v2"
NOT_FOUND = {"detail": "not found"}
# The seed holds no real TIN (blueprint §9); the contract's own example EIN.
EIN = "00-0000287"
EIN_DIGITS = "000000287"
EIN_LAST4 = "0287"
# Fake SSN and ITIN shapes (9xx area; the repository is public).
SSN = "900-00-2208"
ITIN = "900-70-2209"
TinKind = Literal["ssn", "ein", "itin"]


# ================================================================================================
# Seeding
# ================================================================================================


@dataclass(frozen=True)
class World:
    net: Net
    seed: Seeder
    tenant: uuid.UUID
    admin: Person  # Grace Holloway: firm admin, metadata only (ADR-024)
    partner: Person  # Daniel Reyes: engagement partner on both clients' engagements
    ashford: Site  # the client a wall will hide
    ridgeline: Site

    async def person(
        self, *, firm_role: str | None = None, level: str | None = None, offshore: bool = False
    ) -> Person:
        who = await self.seed.person(self.tenant, firm_role)
        if level is not None or offshore:
            await self.seed.run(
                "UPDATE memberships SET level = coalesce($3, level), offshore = $4 "
                "WHERE tenant_id = $1 AND user_id = $2",
                self.tenant,
                who.user_id,
                level,
                offshore,
            )
        return who

    def auth(self, who: Person, *, firm_role: str | None = "firm_admin") -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant, "human", str(who.user_id)),
            who.user_id,
            uuid.uuid4(),
            cast(None, firm_role),
            datetime.now(UTC) - timedelta(minutes=1),
        )

    async def seal(self, site: Site, raw: str = EIN, kind: str = "ein") -> None:
        """The firm admin seals a TIN on the site's entity (`client.update`)."""
        ctx = self.auth(self.admin)
        async with uow(ctx.tenant) as tx:
            await seal_tin(tx, ctx, site.entity_id, raw, cast(TinKind, kind))

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        *,
        body: Json | None = None,
        mfa: bool = True,
        tenant: uuid.UUID | None = None,
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, mfa=mfa, tenant=tenant)

    async def wall(self, who: Person, site: Site) -> None:
        await self.net.wall(self.admin, who, site)

    async def audit(self, action: str) -> list[Json]:
        rows = await self.seed.rows(
            "SELECT to_jsonb(a) AS r FROM audit_events a WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [cast(Json, json.loads(cast(str, r["r"]))) for r in rows]

    async def everything_written(self) -> str:
        """The firm's audit trail and outbox, as text."""
        audit = await self.seed.rows(
            "SELECT to_jsonb(a)::text AS t FROM audit_events a WHERE tenant_id = $1", self.tenant
        )
        outbox = await self.seed.rows(
            "SELECT event_type || ' ' || payload::text AS t FROM outbox WHERE tenant_id = $1",
            self.tenant,
        )
        return "\n".join(str(r["t"]) for r in [*audit, *outbox])


async def _world(net: Net, *, flag: bool = True) -> World:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T13')",
            tenant,
            FLAG,
        )
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    ridgeline = await seed.site(tenant, admin.user_id, "Ridgeline")
    for site in (ashford, ridgeline):
        await seed.run(
            "UPDATE clients SET kind = 'business' WHERE tenant_id = $1 AND id = $2",
            tenant,
            site.client_id,
        )
    partner = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        partner.user_id,
    )
    for site in (ashford, ridgeline):
        await seed.member(site, partner, "engagement_partner")
    return World(net, seed, tenant, admin, partner, ashford, ridgeline)


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _ids(page: Json) -> list[str]:
    return [str(cast(Json, row)["id"]) for row in cast(list[object], page["items"])]


def _keys(value: object, prefix: str = "") -> Iterator[str]:
    """Every key path in a JSON value (list positions collapsed)."""
    if isinstance(value, dict):
        for key, inner in cast(Json, value).items():
            yield f"{prefix}{key}"
            yield from _keys(inner, f"{prefix}{key}.")
    elif isinstance(value, list):
        for inner in cast(list[object], value):
            yield from _keys(inner, prefix)


def _reveal(entity: uuid.UUID) -> str:
    return f"/v1/client-entities/{entity}/tin/reveal"


async def _list(w: World, who: Person, query: str = "") -> Json:
    return _json(await w.call("GET", f"/v1/clients?limit=200&facets=true{query}", who))


# ================================================================================================
# INV-3: walls answer 404 with no count (AC-6, AC-7; Story 1.2; DEC-43)
# ================================================================================================


@pytest.mark.parametrize("reader", ["partner", "firm_admin"])
async def test_ac6_a_walled_reader_gets_the_same_shape_without_the_client(
    net: Net, reader: str
) -> None:
    """DEC-43: walls bind admins too; nothing says a client is hidden, and `total` excludes it."""
    w = await _world(net)
    who = (
        await w.person(level="partner")
        if reader == "partner"
        else await w.person(firm_role="firm_admin")
    )
    before = await _list(w, who)
    assert str(w.ashford.client_id) in _ids(before)
    await w.wall(who, w.ashford)
    after = await _list(w, who)
    assert set(after) == set(before)
    assert set(_keys(after)) <= set(_keys(before))
    assert str(w.ashford.client_id) not in _ids(after)
    assert after["total"] == cast(int, before["total"]) - 1
    assert sum(cast(dict[str, int], after["counts"]).values()) == (
        sum(cast(dict[str, int], before["counts"]).values()) - 1
    )
    raw = json.dumps(after)
    assert w.ashford.marker not in raw
    assert not [k for k in _keys(after) if "hidden" in k or "wall" in k]
    # The same keys as a firm that never had Ashford (the unwalled colleague's view minus one).
    assert _ids(after) == [i for i in _ids(before) if i != str(w.ashford.client_id)]


async def test_ac7_a_walled_client_answers_404_on_every_route_like_an_unknown_one(
    net: Net,
) -> None:
    """Daniel is Ashford's engagement partner and a partner: without the wall each route answers;
    with it, each answers exactly as for a client that does not exist (SPEC-002 AC-4)."""
    w = await _world(net)
    await w.seal(w.ashford)
    record = _json(await w.call("GET", f"/v1/clients/{w.ashford.client_id}", w.partner))
    seen_version = record["version"]
    await w.wall(w.partner, w.ashford)
    unknown = uuid.uuid4()
    for client in (w.ashford.client_id, unknown):
        for path in (
            f"/v1/clients/{client}",
            f"/v1/clients/{client}/overview",
            f"/v1/clients/{client}/relationships",
        ):
            response = await w.call("GET", path, w.partner)
            assert (response.status_code, response.json()) == (404, NOT_FOUND), path
        response = await w.call(
            "PATCH",
            f"/v1/clients/{client}",
            w.partner,
            body={"seen_version": seen_version, "descriptor": "Probe"},
        )
        assert (response.status_code, response.json()) == (404, NOT_FOUND)
    for entity in (w.ashford.entity_id, uuid.uuid4()):
        response = await w.call(
            "POST", _reveal(entity), w.partner, body={"reason": "prepare_return"}
        )
        assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert await w.audit("tin.revealed") == []
    assert await w.audit("client.updated") == []


async def test_ac7_a_new_wall_applies_at_the_next_request(net: Net) -> None:
    """Story 1.2: walls are evaluated at query time."""
    w = await _world(net)
    reader = await w.person(level="partner")
    path = f"/v1/clients/{w.ashford.client_id}"
    assert (await w.call("GET", path, reader)).status_code == 200
    await w.wall(reader, w.ashford)
    assert (await w.call("GET", path, reader)).status_code == 404
    assert str(w.ashford.client_id) not in _ids(await _list(w, reader))


async def test_ac6_searching_for_a_walled_client_reads_like_no_match(net: Net) -> None:
    w = await _world(net)
    reader = await w.person(level="partner")
    found = await _list(w, reader, f"&q={w.ashford.marker}")
    assert _ids(found) == [str(w.ashford.client_id)]
    await w.wall(reader, w.ashford)
    walled = await _list(w, reader, f"&q={w.ashford.marker}")
    nothing = await _list(w, reader, f"&q=zz{uuid.uuid4().hex}")
    assert walled["items"] == [] and walled["total"] == 0
    assert set(walled) == set(nothing)
    assert walled["counts"] == nothing["counts"]
    assert w.ashford.marker not in json.dumps(walled)


async def test_ac7_relationship_edges_into_a_walled_client_are_omitted(net: Net) -> None:
    """AC-7: an edge to a walled client is not shown, named or counted (R-3)."""
    w = await _world(net)
    ctx = w.auth(w.admin)
    for source, target, kind in (
        (w.ridgeline, w.ashford, "owner_of"),
        (w.ashford, w.ridgeline, "upper_tier_of"),
    ):
        await add_relationship(
            ctx,
            NewRelationship(
                from_entity_id=source.entity_id,
                to_entity_id=target.entity_id,
                kind=kind,
                effective_from=date(2025, 1, 1),
                percent="25",
            ),
        )
    reader = await w.person(level="partner")
    rels = f"/v1/clients/{w.ridgeline.client_id}/relationships"
    record = f"/v1/clients/{w.ridgeline.client_id}"
    open_page = _json(await w.call("GET", rels, reader))
    assert len(cast(list[object], open_page["items"])) == 2
    assert (
        cast(Json, _json(await w.call("GET", record, reader))["tab_counts"])["relationships"] == 2
    )
    await w.wall(reader, w.ashford)
    walled_page = _json(await w.call("GET", rels, reader))
    assert walled_page["items"] == []
    walled_record = _json(await w.call("GET", record, reader))
    assert cast(Json, walled_record["tab_counts"])["relationships"] == 0
    overview = _json(await w.call("GET", f"{record}/overview", reader))
    for body in (walled_page, walled_record, overview):
        raw = json.dumps(body)
        assert w.ashford.marker not in raw
        assert str(w.ashford.client_id) not in raw
        assert str(w.ashford.entity_id) not in raw


# ================================================================================================
# ADR-024: Grace (firm admin) is metadata only (Story 1.1)
# ================================================================================================


async def _probe_rows(_ctx: AuthContext, _client: uuid.UUID) -> SectionRows:
    return SectionRows([OverviewItem(key="probe", text="probe-row")], 1)


async def test_ac_story1_1_grace_reads_the_record_and_only_metadata_sections(
    net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A section whose owner's read action needs content is omitted for Grace, not disabled."""
    w = await _world(net)
    meta = OverviewSection("p07t13_meta", "details", "client.read", 900, _probe_rows)
    content = OverviewSection("p07t13_content", "details", "evidence.read", 901, _probe_rows)
    for section in (meta, content):
        monkeypatch.setitem(
            slots._SECTIONS,  # pyright: ignore[reportPrivateUsage] -- registered for this test only
            section.code,
            section,
        )
    record = _json(await w.call("GET", f"/v1/clients/{w.ridgeline.client_id}", w.admin))
    assert {"entities", "tab_counts", "version", "allowed_actions"} <= set(record)
    overview = _json(await w.call("GET", f"/v1/clients/{w.ridgeline.client_id}/overview", w.admin))
    sections = cast(list[Json], overview["sections"])
    codes = {str(s["code"]) for s in sections}
    assert "p07t13_meta" in codes
    assert "p07t13_content" not in codes
    # Every section Grace receives is read with a metadata action.
    assert {str(s["read_action"]) for s in sections} <= {
        "client.read",
        "engagement.read_metadata",
    }


# ================================================================================================
# TIN: masked everywhere but the reveal (AC-9; Story 1.3; DEC-141, DEC-223)
# ================================================================================================


def _no_tin(raw: str) -> None:
    assert EIN not in raw and EIN_DIGITS not in raw


async def test_ac9_a_tin_reaches_every_read_only_masked(net: Net) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    client = w.ridgeline.client_id
    for who in (w.admin, w.partner):
        page = await _list(w, who)
        _no_tin(json.dumps(page))
        # The list row carries no TIN-named or Restricted field (contract §3).
        assert not [k for k in _keys(page["items"]) if "tin" in k.split(".")[-1]]
        record = _json(await w.call("GET", f"/v1/clients/{client}", who))
        _no_tin(json.dumps(record))
        entity = next(
            cast(Json, e)
            for e in cast(list[object], record["entities"])
            if cast(Json, e)["id"] == str(w.ridgeline.entity_id)
        )
        assert entity["tin"] == {"kind": "ein", "presence": "on_file", "last4": EIN_LAST4}
        for tail in ("/overview", "/relationships"):
            _no_tin(json.dumps(_json(await w.call("GET", f"/v1/clients/{client}{tail}", who))))


async def test_ac9_a_tin_never_reaches_the_audit_trail_outbox_logs_or_columns(
    net: Net, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    w = await _world(net)
    await w.seal(w.ridgeline)
    revealed = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), w.partner, body={"reason": "review_return"}
    )
    assert revealed.status_code == 200, revealed.text
    _no_tin(await w.everything_written())
    captured = capsys.readouterr()
    logged = captured.out + captured.err + "\n".join(str(r.__dict__) for r in caplog.records)
    _no_tin(logged)
    # Sealed at rest: no plaintext column, and the sealed bytes are not the digits (P-07 M1).
    columns = await w.seed.rows(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name IN ('tin', 'ssn', 'ein')"
    )
    assert columns == []
    sealed = cast(
        bytes,
        await w.seed.value(
            "SELECT tin_sealed FROM client_entities WHERE tenant_id = $1 AND id = $2",
            w.tenant,
            w.ridgeline.entity_id,
        ),
    )
    assert sealed and EIN_DIGITS.encode() not in sealed and EIN.encode() not in sealed


async def test_ac9_a_reveal_returns_the_value_once_with_no_store_and_one_audit_event(
    net: Net,
) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), w.partner, body={"reason": "prepare_return"}
    )
    body = _json(response)
    assert "no-store" in response.headers.get("cache-control", "")
    assert body["entity_id"] == str(w.ridgeline.entity_id)
    assert body["kind"] == "ein"
    assert str(body["value"]).replace("-", "") == EIN_DIGITS
    assert body["remask_after_seconds"] == 10
    events = await w.audit("tin.revealed")
    assert len(events) == 1
    event = events[0]
    assert event["actor_kind"] == "human"
    assert event["actor_id"] == str(w.partner.user_id)
    _no_tin(json.dumps(event))
    rows = await w.seed.rows(
        "SELECT user_id, client_entity_id, engagement_id, reason_code, actor_kind "
        "FROM tin_reveals WHERE tenant_id = $1",
        w.tenant,
    )
    assert [dict(r) for r in rows] == [
        {
            "user_id": w.partner.user_id,
            "client_entity_id": w.ridgeline.entity_id,
            "engagement_id": w.ridgeline.engagement_id,
            "reason_code": "prepare_return",
            "actor_kind": "human",
        }
    ]


@pytest.mark.parametrize(
    "body",
    [None, {}, {"reason": ""}, {"reason": "curiosity"}, {"reason": "prepare_return", "x": 1}],
)
async def test_ac9_a_reveal_needs_a_registry_reason(net: Net, body: Json | None) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    response = await w.call("POST", _reveal(w.ridgeline.entity_id), w.partner, body=body)
    assert response.status_code == 422, response.text
    _no_tin(response.text)
    assert await w.audit("tin.revealed") == []


async def test_ac9_stale_mfa_asks_for_a_step_up_and_reveals_nothing(net: Net) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    response = await w.call(
        "POST",
        _reveal(w.ridgeline.entity_id),
        w.partner,
        body={"reason": "prepare_return"},
        mfa=False,
    )
    assert response.status_code == 403, response.text
    body = cast(Json, response.json())
    assert body["detail"] == "mfa_step_up_required"
    assert cast(Json, body["facts"])["client_entity_id"] == str(w.ridgeline.entity_id)
    _no_tin(response.text)
    assert await w.audit("tin.revealed") == []


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "eqr_reviewer"])
async def test_ac9_each_role_that_holds_the_reveal_may_reveal_onshore(net: Net, role: str) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    who = await w.person(level="manager" if role != "engagement_partner" else "partner")
    await w.seed.member(w.ridgeline, who, cast(Role, role))
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), who, body={"reason": "verify_identity"}
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("role", ["engagement_partner", "manager"])
async def test_ac9_an_offshore_member_is_refused_403(net: Net, role: str) -> None:
    """SPEC-002 AC-18 (TASK-1207): offshore refuses `tin.reveal` at the condition layer."""
    w = await _world(net)
    await w.seal(w.ridgeline)
    who = await w.person(level="partner", offshore=True)
    await w.seed.member(w.ridgeline, who, cast(Role, role))
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), who, body={"reason": "prepare_return"}
    )
    assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})
    assert await w.audit("tin.revealed") == []
    # The same person reads the client like anyone with the role (offshore is not a wall).
    assert (await w.call("GET", f"/v1/clients/{w.ridgeline.client_id}", who)).status_code == 200


@pytest.mark.parametrize("who_kind", ["senior", "staff", "firm_admin", "firm_partner"])
async def test_ac9_a_person_without_the_action_is_refused_403(net: Net, who_kind: str) -> None:
    """DEC-223: a firm role alone never reveals; senior and staff preparers are deferred."""
    w = await _world(net)
    await w.seal(w.ridgeline)
    if who_kind == "firm_admin":
        who = w.admin
    elif who_kind == "firm_partner":
        who = await w.person(level="partner")
    else:
        who = await w.person(level=who_kind)
        await w.seed.member(w.ridgeline, who, cast(Role, who_kind))
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), who, body={"reason": "prepare_return"}
    )
    assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})
    _no_tin(response.text)
    assert await w.audit("tin.revealed") == []


async def test_ac9_a_role_on_an_archived_engagement_does_not_reveal(net: Net) -> None:
    """DEC-223: the reveal is held through an open engagement (neither archived nor declined)."""
    w = await _world(net)
    await w.seal(w.ridgeline)
    who = await w.person(level="partner")
    await w.seed.member(w.ridgeline, who, "engagement_partner")
    await w.seed.run(
        "UPDATE engagements SET status = 'archived' WHERE tenant_id = $1 AND id = $2",
        w.tenant,
        w.ridgeline.engagement_id,
    )
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), who, body={"reason": "prepare_return"}
    )
    assert response.status_code == 403, response.text
    assert await w.audit("tin.revealed") == []


async def test_ac9_no_tin_on_file_answers_404(net: Net) -> None:
    w = await _world(net)
    response = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), w.partner, body={"reason": "prepare_return"}
    )
    assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_ac9_twenty_reveals_an_hour_then_429_with_retry_after(net: Net) -> None:
    w = await _world(net)
    await w.seal(w.ridgeline)
    for _ in range(20):
        ok = await w.call(
            "POST", _reveal(w.ridgeline.entity_id), w.partner, body={"reason": "prepare_return"}
        )
        assert ok.status_code == 200, ok.text
    refused = await w.call(
        "POST", _reveal(w.ridgeline.entity_id), w.partner, body={"reason": "prepare_return"}
    )
    assert refused.status_code == 429, refused.text
    body = cast(Json, refused.json())
    assert body["detail"] == "tin_reveal_rate_limited"
    assert cast(Json, body["facts"])["limit"] == 20
    assert int(refused.headers["retry-after"]) > 0
    _no_tin(refused.text)
    assert len(await w.audit("tin.revealed")) == 20


async def test_inv1_the_agent_and_the_system_never_reveal_read_or_edit(net: Net) -> None:
    w = await _world(net)
    for action in ("tin.reveal", "client.update", "client.read"):
        decisions = RULES[action].decisions
        assert decisions.get("agent") == "deny" and decisions.get("system") == "deny", action
        assert not {r for r, d in decisions.items() if r.startswith("client_") and d != "deny"} - {
            "client_service"
        }
    person = w.auth(w.partner, firm_role=None)
    resource = await engagement_resource(person.tenant, w.ridgeline.engagement_id)
    run = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(w.tenant, "agent", f"agent:probe:{run}", w.partner.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=w.ridgeline.engagement_id,
        task_scope=frozenset({"tin.reveal"}),
        initiator=person,
        issued_by=_ISSUER,
    )
    with pytest.raises(Forbidden):
        await authorise(agent, "tin.reveal", resource)


# ================================================================================================
# The SSN guard (OQ-4; DEC-223; contract §6)
# ================================================================================================


@pytest.mark.parametrize(("raw", "kind"), [(SSN, "ssn"), (ITIN, "itin")])
async def test_ac9_an_ssn_or_itin_on_a_real_firm_answers_422(
    net: Net, raw: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before C19's gate is registered (T-01-T12 lifts the refusal once it is).
    monkeypatch.setattr(tin_module, "_c19_registered", lambda: False)
    w = await _world(net)
    with pytest.raises(TinKindNotAllowed) as refused:
        await w.seal(w.ridgeline, raw, kind)
    assert refused.value.code == "tin_kind_not_allowed"
    record = _json(await w.call("GET", f"/v1/clients/{w.ridgeline.client_id}", w.partner))
    entity = next(
        cast(Json, e)
        for e in cast(list[object], record["entities"])
        if cast(Json, e)["id"] == str(w.ridgeline.entity_id)
    )
    assert entity["tin"] is None
    # An EIN is accepted on the same firm.
    await w.seal(w.ridgeline)


async def test_ac9_a_synthetic_firm_takes_an_ssn_masked(net: Net) -> None:
    w = await _world(net)
    await w.seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", w.tenant)
    await w.seal(w.ridgeline, SSN, "ssn")
    record = _json(await w.call("GET", f"/v1/clients/{w.ridgeline.client_id}", w.partner))
    raw = json.dumps(record)
    assert SSN not in raw and SSN.replace("-", "") not in raw
    entity = next(
        cast(Json, e)
        for e in cast(list[object], record["entities"])
        if cast(Json, e)["id"] == str(w.ridgeline.entity_id)
    )
    assert entity["tin"] == {"kind": "ssn", "presence": "on_file", "last4": "2208"}


# ================================================================================================
# INV-5: attribution, and PATCH (AC-8; contract §7)
# ================================================================================================


async def test_ac8_a_patch_writes_one_client_updated_naming_the_person_and_no_value(
    net: Net,
) -> None:
    w = await _world(net)
    path = f"/v1/clients/{w.ridgeline.client_id}"
    record = _json(await w.call("GET", path, w.admin))
    descriptor = f"Family office {uuid.uuid4().hex[:6]}"
    _json(
        await w.call(
            "PATCH",
            path,
            w.admin,
            body={"seen_version": record["version"], "descriptor": descriptor},
        )
    )
    events = await w.audit("client.updated")
    assert len(events) == 1
    assert events[0]["actor_kind"] == "human"
    assert events[0]["actor_id"] == str(w.admin.user_id)
    written = await w.everything_written()
    assert descriptor not in written
    outbox = await w.seed.rows(
        "SELECT payload::text AS p FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'client.updated'",
        w.tenant,
    )
    assert len(outbox) == 1 and str(w.ridgeline.client_id) in str(outbox[0]["p"])
    assert _json(await w.call("GET", path, w.admin))["descriptor"] == descriptor


async def test_ac8_a_stale_version_answers_409_and_changes_nothing(net: Net) -> None:
    w = await _world(net)
    path = f"/v1/clients/{w.ridgeline.client_id}"
    version = _json(await w.call("GET", path, w.admin))["version"]
    _json(
        await w.call("PATCH", path, w.admin, body={"seen_version": version, "descriptor": "One"})
    )
    stale = await w.call(
        "PATCH", path, w.admin, body={"seen_version": version, "descriptor": "Two"}
    )
    assert stale.status_code == 409, stale.text
    body = cast(Json, stale.json())
    assert body["detail"] == "stale_version"
    assert cast(Json, body["facts"])["client_id"] == str(w.ridgeline.client_id)
    assert _json(await w.call("GET", path, w.admin))["descriptor"] == "One"
    assert len(await w.audit("client.updated")) == 1


async def test_ac8_a_person_cannot_make_a_prospect_active(net: Net) -> None:
    w = await _world(net)
    await w.seed.run(
        "UPDATE clients SET status = 'prospect' WHERE tenant_id = $1 AND id = $2",
        w.tenant,
        w.ridgeline.client_id,
    )
    path = f"/v1/clients/{w.ridgeline.client_id}"
    version = _json(await w.call("GET", path, w.admin))["version"]
    response = await w.call(
        "PATCH",
        path,
        w.admin,
        body={"seen_version": version, "status_change": {"status": "active"}},
    )
    assert response.status_code == 409, response.text
    assert cast(Json, response.json())["detail"] == "illegal_transition"
    assert await w.audit("client.updated") == []


# ================================================================================================
# Tenant isolation on the new tables (P-07-T07 acceptance; DEC-43)
# ================================================================================================


async def test_inv_another_firm_sees_none_of_the_new_rows_and_gets_404(net: Net) -> None:
    a = await _world(net)
    b = await _world(net)
    for w in (a, b):
        await w.seal(w.ridgeline)
        await add_relationship(
            w.auth(w.admin),
            NewRelationship(
                from_entity_id=w.ridgeline.entity_id,
                to_entity_id=w.ashford.entity_id,
                kind="spouse",
                effective_from=date(2025, 1, 1),
            ),
        )
        _json(
            await w.call(
                "POST",
                _reveal(w.ridgeline.entity_id),
                w.partner,
                body={"reason": "prepare_return"},
            )
        )
    # The app role under firm B's tenant context reads only firm B's rows (RLS).
    async with tenant_session(TenantContext(b.tenant, "system", "p07t13-probe")) as session:
        for sql in (
            "SELECT DISTINCT tenant_id FROM entity_relationships",
            "SELECT DISTINCT tenant_id FROM tin_reveals",
            "SELECT DISTINCT tenant_id FROM client_entities WHERE tin_sealed IS NOT NULL",
        ):
            tenants = set((await session.execute(text(sql))).scalars().all())
            assert tenants == {b.tenant}, sql
    # Over HTTP: firm B's people get 404 for firm A's client and entity, with or without A's
    # tenant header (P-01 AC 2.1.4: a firm one does not hold is 404).
    for tenant in (None, a.tenant):
        for path in (
            f"/v1/clients/{a.ridgeline.client_id}",
            f"/v1/clients/{a.ridgeline.client_id}/relationships",
        ):
            response = await b.call("GET", path, b.admin, tenant=tenant)
            assert response.status_code == 404, (path, tenant, response.text)
        response = await b.call(
            "POST",
            _reveal(a.ridgeline.entity_id),
            b.partner,
            body={"reason": "prepare_return"},
            tenant=tenant,
        )
        assert response.status_code == 404, response.text
        _no_tin(response.text)
    assert str(a.ridgeline.client_id) not in _ids(await _list(b, b.admin))
