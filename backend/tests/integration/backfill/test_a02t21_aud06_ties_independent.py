# ac-test-author: ayushkbhatia
"""SPEC-333 AC-5, AC-9 to AC-13, AC-17, AC-26 to AC-28 (live half), A-02 epic AC-2.5, AC-3.1 to
AC-3.4 (A-02-T21, TASK-1474): the AUD-06 read model, the tie engine and service, and the
trial balance as a reviewable target.

The row's acceptance: the suite covers walls, independence, agent refusal and tie goldens. Also
here: another firm (404, never 403: DEC-43), roles the matrix denies, `allowed_actions`, the
`newer_snapshots` count, results computed on read (never stored), `citation_required`, the issue
link's `Idempotency-Key` (replay, reuse, set once, another engagement's issue), a stale check
version, and "Changed after sign-off" when a tie changes after a sign-off.

Boundary: `create_app()` over HTTP on the migrated test database; snapshots through
`ledger.api.record_snapshot`; the expected values' citations through
`evidence.api.record_citations` (the only public writer: `POST /v1/citations` is reserved, C4
§3.6); agent refusals through `identity.api.authorise` with an agent context (an agent has no
bearer token). The tie goldens are SPEC-333 AC-10 and AC-11: the loan rollforward 288,500.00 +
96,200.00 - 57,450.00 - 14,850.00 = 312,400.00, and BrokerWindow at 1,606,560.00 against
1,608,120.00 reads off 1,560.00.

C9 §6 says 403 for `independence_pending`; `error-codes.yaml` lists the code at 409 for the
sign-off path only. The read path follows C9 (TASK-1336 names a 403 read-path refusal); the
status is asserted as C9 says and the drift is recorded in TASK-1474.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import Forbidden, agent_context_for_run, authorise

from .support import Net, Person
from .tb_support import (
    Books,
    Json,
    books,
    dec,
    detail,
    stranger_firm,
    without_independence,
)

HUMAN_ONLY: Final = (
    "trial_balance.adopt",
    "trial_balance.annotate",
    "trial_balance.export",
    "tie_out_check.define",
)


@pytest.fixture
async def world(net: Net) -> Books:
    return await books(net)


async def _tb(world: Books) -> uuid.UUID:
    tb_id = await world.adopted()
    await world.annotate(tb_id)
    return tb_id


async def _citation(world: Books, tb_id: uuid.UUID, account: str, value: str) -> str:
    cid, ok, reason, _match = await world.cite_line(tb_id, world.current, account, value=value)
    assert ok, reason
    return str(cid)


async def _define(
    world: Books, tb_id: uuid.UUID, body: Json, who: Person | None = None
) -> tuple[int, Json]:
    response = await world.call("POST", world.path(tb_id, "/checks"), who, body)
    return response.status_code, cast(Json, response.json())


async def _broker(world: Books, tb_id: uuid.UUID, who: Person | None = None) -> tuple[int, Json]:
    cite = await _citation(world, tb_id, "1230", "1606560.00")
    return await _define(
        world,
        tb_id,
        {
            "label": "BrokerWindow ↔ broker statement",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1608120.00",
            "citation_ids": [cite],
            "tolerance": "0.00",
        },
        who,
    )


async def _rollforward(world: Books, tb_id: uuid.UUID) -> tuple[int, Json]:
    cite = await _citation(world, tb_id, "2500", "312400.00")
    return await _define(
        world,
        tb_id,
        {
            "label": "Loan rollforward",
            "kind": "rollforward",
            "accounts": ["2500"],
            "column": "eoy",
            "negate": True,
            "components": [
                {"label": "Beginning balance", "sign": 1, "value": "288500.00"},
                {"label": "Draws", "sign": 1, "value": "96200.00"},
                {"label": "Repayments", "sign": -1, "value": "57450.00"},
                {"label": "Forgiven", "sign": -1, "value": "14850.00"},
            ],
            "citation_ids": [cite],
        },
    )


async def _checks(world: Books, tb_id: uuid.UUID) -> dict[str, Json]:
    response = await world.call("GET", world.path(tb_id, "/checks"))
    assert response.status_code == 200, response.text
    return {cast(str, c["label"]): c for c in cast(list[Json], response.json())}


async def _issue(world: Books, engagement_id: uuid.UUID | None = None) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO issues (tenant_id, engagement_id, record_ref, kind, title_sealed) "
            "VALUES ($1, $2, '{}'::jsonb, 'exception', '\\x01'::bytea) RETURNING id",
            world.tenant_id,
            engagement_id or world.site.engagement_id,
        ),
    )


def _routes(world: Books, tb_id: uuid.UUID, check_id: str | None = None) -> list[tuple[str, str]]:
    check = check_id or str(uuid.uuid4())
    return [
        ("GET", world.base),
        ("GET", world.path(tb_id)),
        ("GET", world.path(tb_id, "/candidates")),
        ("GET", world.path(tb_id, "/leadsheets")),
        ("GET", world.path(tb_id, "/layers/unadjusted")),
        ("GET", world.path(tb_id, "/leadsheets/Investments")),
        ("GET", world.path(tb_id, "/checks")),
        ("GET", world.path(tb_id, "/export.xlsx")),
        ("POST", world.path(tb_id, f"/checks/{check}/issue-link")),
    ]


# --- AC-9 · Walls, another firm, independence (INV-3) --------------------------------------------


async def test_ac9_a_walled_member_gets_404_on_every_route_with_no_hidden_count(
    world: Books, net: Net
) -> None:
    tb_id = await _tb(world)
    walled = await world.seed.person(world.tenant_id)
    await world.seed.member(world.site, walled, "engagement_partner")
    await net.wall(world.admin, walled, world.site)
    gone = world.site.engagement_id
    for method, path in _routes(world, tb_id):
        body = {"issue_id": str(uuid.uuid4()), "seen_version": 1} if method == "POST" else None
        headers = {"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"}
        refused = await world.call(method, path, walled, body, headers=headers)
        missing = await world.call(
            method,
            path.replace(str(gone), str(uuid.uuid4())),
            world.partner,
            body,
            headers=headers,
        )
        assert refused.status_code == 404, (path, refused.text)
        assert refused.json() == missing.json(), path
        assert str(tb_id) not in refused.text
        assert "count" not in refused.text and "total" not in refused.text


async def test_ac9_another_firm_gets_404_never_403(world: Books, net: Net) -> None:
    tb_id = await _tb(world)
    stranger = await stranger_firm(net)
    for method, path in _routes(world, tb_id):
        body = {"issue_id": str(uuid.uuid4()), "seen_version": 1} if method == "POST" else None
        headers = {"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"}
        refused = await world.call(method, path, stranger, body, headers=headers)
        assert refused.status_code == 404, (path, refused.text)


async def test_ac9_a_firm_member_off_the_team_gets_no_figures(world: Books) -> None:
    tb_id = await _tb(world)
    outsider = await world.seed.person(world.tenant_id)
    for method, path in _routes(world, tb_id)[:7]:
        refused = await world.call(method, path, outsider)
        assert refused.status_code in (403, 404), (path, refused.text)
        assert "16500000" not in refused.text


async def test_ac9_a_member_without_independence_is_refused_independence_pending(
    world: Books,
) -> None:
    tb_id = await _tb(world)
    pending = await without_independence(world.seed, world.site)
    for path in (
        world.path(tb_id, "/layers/unadjusted"),
        world.path(tb_id, "/leadsheets/Investments"),
    ):
        refused = await world.call("GET", path, pending)
        assert refused.status_code == 403, refused.text  # C9 §6
        assert detail(refused) == "independence_pending"
        assert "16500000" not in refused.text


async def test_ac9_a_client_user_never_reads_the_trial_balance(world: Books) -> None:
    tb_id = await _tb(world)
    client = await world.seed.client_contact(world.site)
    for _method, path in _routes(world, tb_id)[:7]:
        refused = await world.call("GET", path, client)
        assert refused.status_code in (403, 404), (path, refused.text)


# --- INV-1 · The agent holds no C9 action --------------------------------------------------------


@pytest.mark.parametrize("action", [*HUMAN_ONLY, "trial_balance.read"])
async def test_inv1_the_agent_principal_is_refused_every_c9_action(
    world: Books, action: str
) -> None:
    agent = await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=world.site.engagement_id,
        task_scope=frozenset({action, "engagement.read"}),
        initiator_user_id=world.partner.user_id,
    )
    resource = await engagement_resource_of(
        TenantContext(world.tenant_id, "system", "test"), world.site.engagement_id
    )
    with pytest.raises(Forbidden):
        await authorise(agent, action, resource)


async def test_inv1_the_check_rows_refuse_an_agent_definer(world: Books) -> None:
    from asyncpg import PostgresError

    tb_id = await _tb(world)
    status, check = await _broker(world, tb_id)
    assert status == 201, check
    with pytest.raises(PostgresError):
        await world.seed.run(
            "INSERT INTO tie_out_check_versions (tenant_id, check_id, version_no, label, "
            "actual_selector, expected, citation_ids, reason, created_by, actor_kind) "
            "SELECT tenant_id, check_id, version_no + 1, label, actual_selector, expected, "
            "citation_ids, 'agent edit', created_by, 'agent' FROM tie_out_check_versions "
            "WHERE tenant_id = $1",
            world.tenant_id,
        )
    with pytest.raises(PostgresError):  # an expected value with no citation, at the table too
        await world.seed.run(
            "INSERT INTO tie_out_check_versions (tenant_id, check_id, version_no, label, "
            "actual_selector, expected, citation_ids, reason, created_by, actor_kind) "
            "SELECT tenant_id, check_id, version_no + 1, label, actual_selector, expected, "
            "'{}', 'uncited', created_by, 'human' FROM tie_out_check_versions "
            "WHERE tenant_id = $1",
            world.tenant_id,
        )


# --- AC-5, AC-17 · The read model: server figures, allowed actions, newer snapshots --------------


async def test_ac5_every_figure_of_the_view_comes_from_the_server_as_a_decimal_string(
    world: Books,
) -> None:
    tb_id = await _tb(world)
    view = await world.view(tb_id)
    groups = {cast(str, g["label"]): g for g in cast(list[Json], view["groups"])}
    assert dec(groups["Investments"]["eoy"]) == dec("16500000.00")
    assert dec(groups["Investments"]["boy"]) == dec("13940000.00")
    assert dec(groups["Debt"]["eoy"]) == dec("-312400.00")
    for group in groups.values():
        assert isinstance(group["eoy"], str)
        for line in cast(list[Json], group["lines"]):
            assert isinstance(line["eoy"], str)
            assert line["aje"] is None and line["rje"] is None and line["final"] is None
    assert view["display_unit"] == "cents"
    assert view["version_no"] == view["current_version_no"] == 1
    assert view["newer_snapshots"] == 1


async def test_ac5_allowed_actions_follow_the_matrix_per_role(world: Books) -> None:
    tb_id = await _tb(world)
    seen: dict[str, set[str]] = {}
    for role in ("partner", "senior", "staff", "reviewer"):
        response = await world.layer(tb_id, who=cast(Person, getattr(world, role)))
        assert response.status_code == 200, (role, response.text)
        seen[role] = set(cast(list[str], response.json().get("allowed_actions") or []))
    assert {"trial_balance.adopt", "trial_balance.export"} <= seen["partner"]
    assert "trial_balance.export" in seen["senior"]
    assert "trial_balance.export" not in seen["staff"]
    assert "trial_balance.adopt" in seen["staff"]
    assert not seen["reviewer"] & set(HUMAN_ONLY)


@pytest.mark.parametrize("who", ["reviewer"])
async def test_ac12_roles_the_matrix_denies_cannot_define_or_annotate(
    world: Books, who: str
) -> None:
    tb_id = await _tb(world)
    status, _ = await _broker(world, tb_id, getattr(world, who))
    assert status == 403
    annotated = await world.call(
        "POST",
        world.path(tb_id, "/annotations"),
        getattr(world, who),
        {"accounts": [{"account_code": "1900", "area": "Cash"}], "reason": "x"},
    )
    assert annotated.status_code == 403, annotated.text


# --- AC-10, AC-11 · Tie goldens, computed on read ------------------------------------------------


async def test_ac10_the_loan_rollforward_ties_at_312400(world: Books) -> None:
    tb_id = await _tb(world)
    status, check = await _rollforward(world, tb_id)
    assert status == 201, check
    found = (await _checks(world, tb_id))["Loan rollforward"]
    result = cast(Json, found["result"])
    assert result["status"] == "tie", result
    assert dec(result["actual"]) == dec("312400.00")
    formula = cast(str, result["formula"]).replace("\u2212", "-")
    assert formula == "288,500.00 + 96,200.00 - 57,450.00 - 14,850.00 = 312,400.00"


async def test_ac11_brokerwindow_reads_off_1560_and_flags_its_line(world: Books) -> None:
    tb_id = await _tb(world)
    status, check = await _broker(world, tb_id)
    assert status == 201, check
    found = (await _checks(world, tb_id))["BrokerWindow ↔ broker statement"]
    result = cast(Json, found["result"])
    assert result["status"] == "off"
    assert dec(result["actual"]) == dec("1606560.00")
    assert dec(result["expected"]) == dec("1608120.00")
    assert dec(result["difference"]).copy_abs() == dec("1560.00")
    view = await world.view(tb_id)
    summary = cast(Json, view["checks"])
    assert summary["off"] == 1 and summary["tie"] == 0
    lines = {
        cast(str, line["account_code"]): line
        for g in cast(list[Json], view["groups"])
        for line in cast(list[Json], g["lines"])
    }
    flags = cast(list[Json], lines["1230"]["flags"])
    assert [f["kind"] for f in flags] == ["does_not_tie"]
    assert flags[0]["check_id"] == found["id"]
    assert not lines["1210"]["flags"]


async def test_ac11_results_are_computed_on_read_and_never_stored(world: Books) -> None:
    """The same check ties once v2 agrees BrokerWindow at 1,608,120.00: nobody edited it."""
    tb_id = await _tb(world)
    status, check = await _broker(world, tb_id)
    assert status == 201, check
    assert (await world.reversion(tb_id)).status_code == 201
    found = (await _checks(world, tb_id))["BrokerWindow ↔ broker statement"]
    assert found["version_no"] == check["version_no"]
    assert cast(Json, found["result"])["status"] == "tie"
    assert cast(Json, (await world.view(tb_id))["checks"])["off"] == 0


async def test_ac10_a_balanced_check_ties_when_debits_equal_credits(world: Books) -> None:
    tb_id = await _tb(world)
    status, check = await _define(
        world, tb_id, {"label": "Balances to 0", "kind": "balanced", "column": "eoy"}
    )
    assert status == 201, check
    result = cast(Json, (await _checks(world, tb_id))["Balances to 0"]["result"])
    assert result["status"] == "tie", result


# --- AC-12 · Citations and agents ----------------------------------------------------------------


async def test_ac12_an_expected_value_without_a_citation_is_refused(world: Books) -> None:
    tb_id = await _tb(world)
    status, body = await _define(
        world,
        tb_id,
        {
            "label": "Uncited",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1608120.00",
            "citation_ids": [],
        },
    )
    assert status == 422, body  # error-codes.yaml (C9 §6 says 409)
    assert body["detail"] == "citation_required"
    assert await world.count("tie_out_checks") == 0
    assert not [a for a, _ in await world.actions() if a.startswith("tie_out_check.")]


async def test_ac12_a_citation_id_of_another_engagement_does_not_count(world: Books) -> None:
    tb_id = await _tb(world)
    other = await world.seed.site(world.tenant_id, world.admin.user_id, "Harlow")
    from .tb_support import work_item

    await world.seed.member(other, world.partner, "engagement_partner")
    await work_item(world.seed, other, world.admin.user_id)
    from .tb_support import EOY, snapshot

    foreign_snapshot = await snapshot(world.tenant_id, world.partner.user_id, other.entity_id, EOY)
    adopted = await world.call(
        "POST",
        f"/v1/engagements/{other.engagement_id}/trial-balances",
        body={"snapshot_id": str(foreign_snapshot), "label": "standard", "display_unit": "cents"},
    )
    assert adopted.status_code == 201, adopted.text
    other_tb = uuid.UUID(cast(str, cast(Json, adopted.json()["trial_balance"])["id"]))
    cid, ok, _r, _m = await world.cite_line(
        other_tb, foreign_snapshot, "1230", value="1606560.00", engagement_id=other.engagement_id
    )
    assert ok
    status, body = await _define(
        world,
        tb_id,
        {
            "label": "Borrowed citation",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1608120.00",
            "citation_ids": [str(cid)],
        },
    )
    assert status in (404, 422), body
    assert await world.count("tie_out_checks") == 0


async def test_ac12_defining_and_editing_are_audited_as_the_person(world: Books) -> None:
    tb_id = await _tb(world)
    status, check = await _broker(world, tb_id, world.senior)
    assert status == 201, check
    assert check["defined_by_name"] == "Marcus Delaney"
    stale = await world.call(
        "PUT",
        world.path(tb_id, f"/checks/{check['id']}"),
        world.senior,
        {
            "label": "BrokerWindow ↔ broker statement",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1606560.00",
            "citation_ids": check["citation_ids"],
            "reason": "Statement re-read",
            "seen_version": cast(int, check["version_no"]) + 5,
        },
    )
    assert stale.status_code == 409 and detail(stale) == "tie_out_check_stale", stale.text
    edited = await world.call(
        "PUT",
        world.path(tb_id, f"/checks/{check['id']}"),
        world.senior,
        {
            "label": "BrokerWindow ↔ broker statement",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1606560.00",
            "citation_ids": check["citation_ids"],
            "reason": "Statement re-read",
            "seen_version": check["version_no"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert cast(Json, edited.json()["result"])["status"] == "tie"
    audited = await world.actions()
    assert ("tie_out_check.defined", "human") in audited
    assert ("tie_out_check.updated", "human") in audited


# --- AC-11, AC-28 · The issue link: Idempotency-Key, set once ------------------------------------


async def test_ac28_the_issue_link_needs_an_idempotency_key(world: Books) -> None:
    tb_id = await _tb(world)
    _, check = await _broker(world, tb_id)
    issue = await _issue(world)
    refused = await world.call(
        "POST",
        world.path(tb_id, f"/checks/{check['id']}/issue-link"),
        body={"issue_id": str(issue), "seen_version": check["version_no"]},
    )
    assert refused.status_code in (400, 422), refused.text
    assert not [a for a, _ in await world.actions() if a == "tie_out_check.issue_linked"]


async def test_ac11_the_issue_link_replays_on_its_key_and_is_set_once(world: Books) -> None:
    tb_id = await _tb(world)
    _, check = await _broker(world, tb_id)
    issue, other = await _issue(world), await _issue(world)
    path = world.path(tb_id, f"/checks/{check['id']}/issue-link")
    key = {"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"}
    body: Json = {"issue_id": str(issue), "seen_version": check["version_no"]}
    first = await world.call("POST", path, world.senior, body, headers=key)
    assert first.status_code == 201, first.text
    linked = cast(Json, first.json())
    assert linked["issue_id"] == str(issue)
    assert linked["linked_by_user_id"] == str(world.senior.user_id)
    replay = await world.call("POST", path, world.senior, body, headers=key)
    assert replay.status_code == 201 and replay.json() == linked
    reused = await world.call(
        "POST", path, world.senior, {**body, "issue_id": str(other)}, headers=key
    )
    assert reused.status_code == 422 and detail(reused) == "idempotency_key_reused", reused.text
    again = await world.call(
        "POST",
        path,
        world.senior,
        {"issue_id": str(other), "seen_version": linked["version_no"]},
        headers={"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"},
    )
    assert again.status_code == 409, again.text
    assert detail(again) in ("tie_out_check_issue_linked", "tie_out_check_stale")
    linked_events = [a for a, _ in await world.actions() if a == "tie_out_check.issue_linked"]
    assert len(linked_events) == 1
    flags = [
        f
        for g in cast(list[Json], (await world.view(tb_id))["groups"])
        for line in cast(list[Json], g["lines"])
        for f in cast(list[Json], line["flags"])
    ]
    assert [f["issue_id"] for f in flags] == [str(issue)]
    assert (await _checks(world, tb_id))["BrokerWindow ↔ broker statement"]["issue_id"] == str(
        issue
    )


async def test_ac11_an_issue_of_another_engagement_is_404_and_a_stale_version_409(
    world: Books,
) -> None:
    tb_id = await _tb(world)
    _, check = await _broker(world, tb_id)
    other = await world.seed.site(world.tenant_id, world.admin.user_id, "Harlow")
    foreign = await _issue(world, other.engagement_id)
    path = world.path(tb_id, f"/checks/{check['id']}/issue-link")
    refused = await world.call(
        "POST",
        path,
        body={"issue_id": str(foreign), "seen_version": check["version_no"]},
        headers={"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"},
    )
    assert refused.status_code == 404, refused.text
    stale = await world.call(
        "POST",
        path,
        body={"issue_id": str(await _issue(world)), "seen_version": 99},
        headers={"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"},
    )
    assert stale.status_code == 409 and detail(stale) == "tie_out_check_stale", stale.text


async def test_ac11_the_issue_link_refuses_extra_fields_and_reviewers(world: Books) -> None:
    tb_id = await _tb(world)
    _, check = await _broker(world, tb_id)
    path = world.path(tb_id, f"/checks/{check['id']}/issue-link")
    issue = await _issue(world)
    extra = await world.call(
        "POST",
        path,
        body={"issue_id": str(issue), "seen_version": check["version_no"], "by": "agent"},
        headers={"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"},
    )
    assert extra.status_code == 422, extra.text
    reviewer = await world.call(
        "POST",
        path,
        world.reviewer,
        {"issue_id": str(issue), "seen_version": check["version_no"]},
        headers={"Idempotency-Key": f"a02t21-{uuid.uuid4().hex}"},
    )
    assert reviewer.status_code == 403, reviewer.text


# --- AC-13 · The trial balance as a reviewable: a tie changed after a sign-off -------------------


async def test_ac13_a_tie_changed_after_a_sign_off_makes_it_read_changed(world: Books) -> None:
    tb_id = await _tb(world)
    _, check = await _broker(world, tb_id, world.senior)
    signed = await world.call("POST", world.path(tb_id, "/sign-offs/prepare"), world.senior)
    assert signed.status_code == 201, signed.text
    before = await world.seed.rows(
        "SELECT * FROM sign_offs WHERE tenant_id = $1 ORDER BY id", world.tenant_id
    )
    detail_before = await world.call("GET", world.path(tb_id))
    levels = {
        cast(str, x["name"]): x
        for x in cast(list[Json], cast(Json, detail_before.json())["sign_offs"])
    }
    assert levels["preparer"]["stale"] is False
    edited = await world.call(
        "PUT",
        world.path(tb_id, f"/checks/{check['id']}"),
        world.senior,
        {
            "label": "BrokerWindow ↔ broker statement",
            "kind": "tie",
            "accounts": ["1230"],
            "column": "eoy",
            "expected": "1606560.00",
            "citation_ids": check["citation_ids"],
            "reason": "Statement re-read",
            "seen_version": check["version_no"],
        },
    )
    assert edited.status_code == 200, edited.text
    after = await world.call("GET", world.path(tb_id))
    levels = {
        cast(str, x["name"]): x for x in cast(list[Json], cast(Json, after.json())["sign_offs"])
    }
    assert levels["preparer"]["stale"] is True
    assert (
        await world.seed.rows(
            "SELECT * FROM sign_offs WHERE tenant_id = $1 ORDER BY id", world.tenant_id
        )
        == before
    )  # no sign-off row was updated


async def test_ac13_an_agent_cannot_sign_off_the_trial_balance(world: Books) -> None:
    agent = await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=world.site.engagement_id,
        task_scope=frozenset({"sign_off.prepare", "engagement.read"}),
        initiator_user_id=world.partner.user_id,
    )
    resource = await engagement_resource_of(
        TenantContext(world.tenant_id, "system", "test"), world.site.engagement_id
    )
    with pytest.raises(Forbidden):
        await authorise(agent, "sign_off.prepare", resource)
