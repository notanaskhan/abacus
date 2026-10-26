"""SPEC-025 AC-7 (per person; TASK-045) as G2 v2 keeps it, and G2 v2 itself (SPEC-332 AC-13 to
AC-16; ADR-164 items 2 to 4; P-07-T24).

TASK-045's rule (a staff engagement role grants a marked action only once that person has
confirmed for the engagement) is G2 v2's strictest configuration: an attest client's engagement in
a firm with `g2_blocks_view` on. The `fakes` fixture defaults to it, so the `test_ac7_*` cases
prove that configuration unchanged; the `test_ac13_*` to `test_ac16_*` cases flip the attest flag
and the setting.

The engagement role, walls, the firm's settings, the attest flag and the engagements module's
confirmation lookup are replaced by fakes; `authz._independence` is set directly, as
`register_independence` would.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import yaml
from sqlalchemy import ColumnElement, Uuid, column, literal_column

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
    visible,
)
from abacus.modules.identity.authz import matrix, recording_checks
from abacus.modules.identity.authz.matrix import (
    FIRM_SETTING_KEYS,
    G2_BLOCKS_VIEW,
    RULES,
    STORED_SETTING_KEYS,
    STRICTER_SETTING_KEYS,
)
from abacus.modules.identity.repository import GRANT_ROLES_OF, FirmPolicy
from abacus_tools.codegen import permission_matrix as pm

# The `conditions_met` fixture (conftest.py): a resource whose condition facts are met.
MeetConditions = Callable[[Resource, AuthContext, str], Resource]

DOCUMENT = cast(dict[str, object], yaml.safe_load(pm.source()))
ACTIONS = cast(dict[str, dict[str, str]], DOCUMENT["actions"])
STAFF_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer")
MARKED = sorted(a for a, entries in ACTIONS.items() if entries.get("independence") == "required")
MARKED_STAFF = [(a, r) for a in MARKED for r in STAFF_ROLES if ACTIONS[a].get(r) == "allow"]
MARKED_STAFF_IDS = [f"{a}-{r}" for a, r in MARKED_STAFF]


class Fakes:
    def __init__(self) -> None:
        self.role: str | None = "staff"
        self.confirmed = False
        self.lookups: list[tuple[uuid.UUID, uuid.UUID]] = []
        # G2 v2's strictest configuration by default (TASK-045's rule): see the module docstring.
        self.attest: bool | None = True
        self.blocks_view = True
        self.attest_lookups: list[uuid.UUID] = []

    async def attest_of(self, tenant: TenantContext, engagement_id: uuid.UUID) -> bool | None:
        self.attest_lookups.append(engagement_id)
        return self.attest

    async def policy(self, tenant: TenantContext) -> FirmPolicy:
        return FirmPolicy({}, frozenset({G2_BLOCKS_VIEW}) if self.blocks_view else frozenset())

    async def engagement_role(self, *args: object) -> str | None:
        return self.role

    async def walled(self, *args: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def confirmed_for(
        self, tenant: TenantContext, engagement_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        self.lookups.append((engagement_id, user_id))
        return self.confirmed


def _confirmed_column(engagement_id: object, user_id: uuid.UUID) -> ColumnElement[bool]:
    return literal_column("independence_confirmed")


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    made = Fakes()
    monkeypatch.setattr(authz, "engagement_role", made.engagement_role)
    monkeypatch.setattr(authz, "walled_clients", made.walled)
    monkeypatch.setattr(authz, "_independence", (_confirmed_column, made.confirmed_for))
    monkeypatch.setattr(authz.LOOKUPS, "attest", made.attest_of)
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", None)
    monkeypatch.setattr(authz, "firm_policy", made.policy)
    return made


def _person(*, support: str | None = None) -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), "support" if support else "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role=support,  # pyright: ignore[reportArgumentType] -- a support role under test
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _on(ctx: AuthContext | AgentContext, engagement_id: uuid.UUID | None = None) -> Resource:
    return Resource.engagement(ctx.tenant_id, engagement_id or uuid.uuid4(), archived=False)


def _agent(initiator: AuthContext, engagement_id: uuid.UUID) -> AgentContext:
    run_id = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(initiator.tenant_id, "agent", f"agent:engagement.agent:{run_id}"),
        agent_id="engagement.agent",
        agent_run_id=run_id,
        engagement_id=engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


async def _layer(ctx: AuthContext | AgentContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource)
    return raised.value.layer


def _sql(expression: ColumnElement[bool]) -> str:
    return " ".join(str(expression.compile()).split())


def test_ac7_the_client_data_actions_are_marked() -> None:
    assert MARKED == [
        "adjustment.approve",  # SPEC-301 (TASK-302)
        "adjustment.propose",
        "adjustment.record_response",
        "agent_run.read",  # SPEC-318 (TASK-461)
        "archive.lock",  # SPEC-314 (TASK-332)
        "assurance.record_archive",  # A-01-T02 (TASK-1101)
        "assurance.record_phase",
        "assurance.record_release",
        "citation.create",  # P-03-T02 (C4 v1)
        "citation.read",
        "citation.relink",
        # ADR-164 item 2 (P-07-T24): client-facing, G2 for the acting member on attest clients.
        "client_access.grant",
        "comment.create",  # SPEC-032 (TASK-062)
        "comment.read",
        "comment.share",
        "completion.decide",  # SPEC-314 (TASK-332)
        "completion.read",  # SPEC-314 (TASK-332)
        "completion.record",  # SPEC-314 (TASK-332)
        "connection.disconnect",  # A-02-T06 security review (DEC-379): POR-16 f
        "connection.read",  # A-02 §4.4 (TASK-1185)
        "connection.read_log",
        "connection.reconnect_request",  # A-02 §4.4 (TASK-1185)
        "connection.retry",  # A-02 security review (DEC-316): firm side, attest client data
        "dashboard.read",  # SPEC-317 (TASK-460)
        "decision.decide",  # P-04-T08 (TASK-414)
        "decision.notify",  # P-04-T08 (TASK-414)
        "decision.read",  # P-04-T08 (TASK-414)
        "decision.reassess",  # P-04-T08 (TASK-414)
        "decision.request_analysis",  # P-04-T08 (TASK-414)
        "entry_assessment.adopt",  # SPEC-044 (TASK-109)
        "entry_assessment.request",  # SPEC-037 Q4 (TASK-085)
        "eqr.concur",  # SPEC-314 (TASK-332)
        "evidence.accept",
        "evidence.read",
        "evidence.reject",
        "evidence.unlock",  # P-03-T02 (C4 v1)
        "evidence.upload",
        "export.create",  # A-01-T17 (TASK-1261): an engagement export is client data
        "export.download",
        "export.read",
        "finding.communicate",  # SPEC-301 (TASK-302)
        "finding.conclude_severity",
        "finding.propose_severity",
        "finding.raise",  # SPEC-043 (TASK-107)
        # P-06-T14: the send is client data, per person; a draft is not (SPEC-027 AC-8, DEC-220).
        "follow_up.send",
        "guidance_draft.decide",  # SPEC-035 (TASK-073)
        "guidance_draft.read",
        "guidance_draft.request",
        "inbox_match.read",  # SPEC-033 (TASK-066)
        "inbox_match.request",
        "item.sign_prepared",  # SPEC-040 (TASK-100)
        "item.sign_reviewed",
        "ledger.pull",  # A-02 §4.4 (TASK-1185)
        "ledger_import.upload",  # SPEC-028 (TASK-052)
        "mapping_set.edit",  # SPEC-316 (TASK-345)
        "materiality.decide",  # SPEC-300 (TASK-301)
        "materiality.set",  # SPEC-037 (TASK-083)
        "message.send",  # ADR-164 item 2 (P-07-T24): client-facing
        "misstatement.set",  # SPEC-043 (TASK-107)
        "pii.reveal",  # P-03-T02 (C4 v1)
        "procedure.configure",
        "procedure.read",
        "procedure.run",
        "proposal.approve",  # P-04-T08 (TASK-414)
        "proposal.follow_up",  # P-04-T08 (TASK-414)
        "proposal.read",  # P-04-T08 (TASK-414)
        "proposal.reject",  # P-04-T08 (TASK-414)
        "proposal.route",  # P-04-T08 (TASK-414)
        "proposal.undo",  # P-04-T08 (TASK-414)
        "report.approve",  # SPEC-314 (TASK-332)
        "report.release",  # SPEC-314 (TASK-332)
        "representation.edit",  # SPEC-301 (TASK-302)
        "request_item.send",  # P-06-T01 (TASK-415)
        "review.assign",
        "review.read",
        "review.take",
        "review_decision.undo",  # P-01-T13 (TASK-1001)
        "review_note.clear",  # SPEC-041 (TASK-103)
        "review_note.raise",
        "review_note.read",  # P-04-T07 (TASK-413)
        "review_note.respond",
        "review_note.withdraw",  # P-04-T07 (TASK-413)
        "risk.approve",  # SPEC-300 (TASK-301)
        "risk.assess",
        "run_content.read",  # DEC-87 (TASK-5002)
        "run_trace.export",  # SPEC-318 (TASK-461)
        "sample.approve",  # SPEC-040 (TASK-100)
        "screening.feedback",  # P-06-T15 (SHL-20 f)
        "screening.request",
        "sign_off.bulk",  # P-04-T07 (TASK-413)
        "sign_off.create",  # P-04-T07 (TASK-413)
        "sign_off.eqr",  # SPEC-308 (TASK-319)
        "sign_off.manager",
        "sign_off.partner",
        "sign_off.prepare",
        "sign_off.read",  # P-04-T07 (TASK-413)
        "sign_off.review",
        "statement.approve",  # SPEC-312 (TASK-324)
        "suggestion.resolve",  # P-04-T08 (TASK-414)
        "tie_out_check.define",  # SPEC-310 (TASK-321)
        "trial_balance.adopt",  # SPEC-309 (TASK-320)
        "trial_balance.annotate",
        "trial_balance.export",  # A-02 §4.4 (TASK-1185)
        "trial_balance.read",
        "upload_review.read",  # SPEC-030 (TASK-059 D1)
        "upload_review.request",  # SPEC-030 (TASK-058)
        "workpaper.edit",  # SPEC-308 (TASK-319)
        "workpaper.read",
        "workpaper.sign_ready",  # SPEC-037 (TASK-084)
        "workpaper.sign_reviewed",
    ]
    assert all(RULES[a].independence for a in MARKED)
    assert not RULES["request_item.read"].independence


@pytest.mark.parametrize(("action", "role"), MARKED_STAFF, ids=MARKED_STAFF_IDS)
async def test_ac7_a_confirmed_staff_member_is_allowed(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role, fakes.confirmed = role, True
    ctx = _person()
    await authorise(ctx, action, conditions_met(_on(ctx), ctx, role))


@pytest.mark.parametrize(("action", "role"), MARKED_STAFF, ids=MARKED_STAFF_IDS)
async def test_ac7_an_unconfirmed_staff_member_is_refused_at_independence(
    fakes: Fakes, action: str, role: str
) -> None:
    fakes.role = role  # requested or declined: anything but confirmed
    ctx = _person()
    engagement_id = uuid.uuid4()
    assert await _layer(ctx, action, _on(ctx, engagement_id)) == "independence"
    assert fakes.lookups == [(engagement_id, ctx.user_id)]


async def test_ac7_an_unconfirmed_member_still_sees_what_is_asked(fakes: Fakes) -> None:
    ctx = _person()
    await authorise(ctx, "request_item.read", _on(ctx))
    assert fakes.lookups == []


@pytest.mark.parametrize(
    ("action", "role"),
    [("evidence.upload", "client_admin"), ("connection.read_log", "client_admin")],
)
async def test_ac7_client_roles_are_not_bound_by_the_firms_independence(
    fakes: Fakes, action: str, role: str
) -> None:
    fakes.role = role
    ctx = _person()
    await authorise(ctx, action, _on(ctx))
    assert fakes.lookups == []


async def test_ac7_break_glass_support_is_not_bound(fakes: Fakes) -> None:
    fakes.role = None
    ctx = _person(support="platform_support_content")
    await authorise(ctx, "evidence.read", _on(ctx))
    assert fakes.lookups == []


async def test_ac7_a_system_run_is_not_bound(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    ctx = system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=engagement_id,
        on_behalf_of=uuid.uuid4(),
    )
    await authorise(
        ctx, "evidence.upload", Resource.engagement(ctx.tenant_id, engagement_id, archived=False)
    )
    assert fakes.lookups == []


async def test_ac7_an_agent_of_an_unconfirmed_person_is_refused(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    agent = _agent(_person(), engagement_id)
    assert await _layer(agent, "evidence.read", _on(agent, engagement_id)) == "delegation"
    fakes.confirmed = True
    await authorise(agent, "evidence.read", _on(agent, engagement_id))


async def test_ac7_unregistered_means_refused(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    fakes.confirmed = True
    ctx = _person()
    assert await _layer(ctx, "evidence.read", _on(ctx)) == "independence"


async def test_ac7_the_answer_is_read_once_per_request(fakes: Fakes) -> None:
    fakes.confirmed = True
    ctx = _person()
    resource = _on(ctx)
    with recording_checks():
        await authorise(ctx, "evidence.read", resource)
        await authorise(ctx, "review.read", resource)
    assert len(fakes.lookups) == 1


async def test_ac7_confirming_on_one_engagement_does_not_open_another(fakes: Fakes) -> None:
    ctx = _person()
    confirmed_on = uuid.uuid4()

    async def only_one(tenant: object, engagement_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return engagement_id == confirmed_on

    authz._independence = (_confirmed_column, only_one)  # pyright: ignore[reportPrivateUsage] -- restored by the fixture's monkeypatch
    await authorise(ctx, "evidence.read", _on(ctx, confirmed_on))
    assert await _layer(ctx, "evidence.read", _on(ctx)) == "independence"


# --- visible ---------------------------------------------------------------------------------


def test_ac7_visible_requires_a_confirmation_for_staff_roles(fakes: Fakes) -> None:
    sql = _sql(visible(_person(), "connection.read_log", column("engagement_id", Uuid())))
    assert "independence_confirmed" in sql
    # Staff roles need the confirmation; client roles reach their rows without one, through
    # their grants on the engagement, its client or its client entity (F-03-T26, DEC-211).
    assert sql.count("engagement_members.role IN") == 1
    assert sql.count("client_access_grants.role IN") == 3
    assert sql.startswith("(engagement_id IN (SELECT anon_1.scope_id")
    assert " OR engagement_id IN (SELECT engagement_members.engagement_id" in sql
    assert sql.index("independence_confirmed") > sql.index("engagement_members.role IN")


def test_ac7_visible_unregistered_leaves_only_client_reach(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    expression = visible(_person(), "connection.read_log", column("engagement_id", Uuid()))
    assert "independence_confirmed" not in _sql(expression)
    assert "engagement_members" not in _sql(expression)
    assert _sql(expression).count("client_access_grants.role IN") == 3  # three scope kinds
    # client_admin's grant roles (DEC-211), on every scope kind alike.
    params = expression.compile().params
    assert [params[f"role_{i}"] for i in (1, 2, 3)] == [sorted(GRANT_ROLES_OF["client_admin"])] * 3


def test_ac7_visible_with_only_staff_roles_unregistered_is_false(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    sql = _sql(visible(_person(), "review.read", column("engagement_id", Uuid())))
    assert sql.startswith("false")


def test_ac7_visible_for_an_unmarked_read_is_unchanged(fakes: Fakes) -> None:
    sql = _sql(visible(_person(), "request_item.read", column("engagement_id", Uuid())))
    assert "independence_confirmed" not in sql


# --- G2 v2 (SPEC-332 AC-13 to AC-16; ADR-164 items 2 to 4; P-07-T24) -------------------------

MARKED_READS = [(a, r) for a, r in MARKED_STAFF if RULES[a].reads]
MARKED_WRITES = [(a, r) for a, r in MARKED_STAFF if not RULES[a].reads]
READ_IDS = [f"{a}-{r}" for a, r in MARKED_READS]
WRITE_IDS = [f"{a}-{r}" for a, r in MARKED_WRITES]


def test_ac13_both_kinds_are_exercised() -> None:
    assert MARKED_READS and MARKED_WRITES
    assert ("sign_off.prepare", "staff") in MARKED_WRITES
    assert ("client_access.grant", "manager") in MARKED_WRITES
    assert ("message.send", "senior") in MARKED_WRITES
    assert ("request_item.send", "staff") in MARKED_WRITES


@pytest.mark.parametrize(("action", "role"), MARKED_READS, ids=READ_IDS)
async def test_ac13_a_pending_member_of_an_attest_engagement_reads(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role, fakes.blocks_view = role, False
    ctx = _person()
    await authorise(ctx, action, conditions_met(_on(ctx), ctx, role))
    assert fakes.attest_lookups == []  # a read without the setting never asks


@pytest.mark.parametrize(("action", "role"), MARKED_WRITES, ids=WRITE_IDS)
async def test_ac13_a_pending_member_of_an_attest_engagement_is_refused_every_marked_act(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role, fakes.blocks_view = role, False
    ctx = _person()
    engagement_id = uuid.uuid4()
    resource = conditions_met(_on(ctx, engagement_id), ctx, role)
    assert await _layer(ctx, action, resource) == "independence"
    assert fakes.attest_lookups == [engagement_id]


@pytest.mark.parametrize(("action", "role"), MARKED_WRITES, ids=WRITE_IDS)
async def test_ac13_a_cleared_member_acts(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role, fakes.blocks_view, fakes.confirmed = role, False, True
    ctx = _person()
    await authorise(ctx, action, conditions_met(_on(ctx), ctx, role))
    assert fakes.attest_lookups == []  # cleared: the attest flag is never read


@pytest.mark.parametrize(("action", "role"), MARKED_STAFF, ids=MARKED_STAFF_IDS)
async def test_ac14_nothing_is_gated_on_a_non_attest_engagement(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role, fakes.attest = role, False  # even with the stricter setting on
    ctx = _person()
    await authorise(ctx, action, conditions_met(_on(ctx), ctx, role))


@pytest.mark.parametrize(("action", "role"), MARKED_READS, ids=READ_IDS)
async def test_ac15_g2_blocks_view_refuses_reads_on_attest_engagements_only(
    fakes: Fakes, conditions_met: MeetConditions, action: str, role: str
) -> None:
    fakes.role = role
    ctx = _person()
    resource = conditions_met(_on(ctx), ctx, role)
    assert await _layer(ctx, action, resource) == "independence"
    fakes.attest = False
    await authorise(ctx, action, resource)


def test_ac15_the_stricter_setting_can_never_grant() -> None:
    assert G2_BLOCKS_VIEW in STRICTER_SETTING_KEYS
    assert not STRICTER_SETTING_KEYS & FIRM_SETTING_KEYS
    assert STORED_SETTING_KEYS == FIRM_SETTING_KEYS | STRICTER_SETTING_KEYS
    with pytest.raises(ValueError, match=r"permission matrix: evidence\.read\.staff"):
        matrix._rule(  # pyright: ignore[reportPrivateUsage] -- the matrix parser under test
            "evidence.read", {"staff": f"firm_setting({G2_BLOCKS_VIEW})"}
        )


def test_ac15_the_migration_check_lists_every_stored_key() -> None:
    from pathlib import Path

    migration = Path(__file__).parents[3] / "migrations/versions/0138_g2_blocks_view.py"
    after = migration.read_text().split("_AFTER = (", 1)[1].split(")\n", 1)[0]
    assert all(f"'{key}'" in after for key in STORED_SETTING_KEYS)


@pytest.mark.parametrize("unknown", ["none", "unregistered"])
async def test_ac16_an_unknown_attest_flag_counts_as_attest(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch, unknown: str
) -> None:
    fakes.blocks_view = False
    if unknown == "none":
        fakes.attest = None
    else:
        monkeypatch.setattr(authz.LOOKUPS, "attest", None)
    ctx = _person()
    assert await _layer(ctx, "evidence.upload", _on(ctx)) == "independence"


async def test_ac16_firm_roles_are_not_bound(fakes: Fakes) -> None:
    fakes.role = None
    for firm_role in ("firm_admin", "practice_leader"):
        ctx = _person(support=firm_role)
        await authorise(ctx, "agent_run.read", _on(ctx))
    assert fakes.lookups == []


async def test_ac16_client_roles_are_not_bound_on_attest_engagements(fakes: Fakes) -> None:
    fakes.role = "client_admin"
    ctx = _person()
    await authorise(ctx, "evidence.upload", _on(ctx))
    assert fakes.lookups == [] and fakes.attest_lookups == []


async def test_ac16_break_glass_support_is_not_bound_on_attest_engagements(fakes: Fakes) -> None:
    fakes.role = None
    ctx = _person(support="platform_support_content")
    await authorise(ctx, "connection.read_log", _on(ctx))
    assert fakes.lookups == [] and fakes.attest_lookups == []


async def test_ac16_a_system_run_is_not_bound_on_attest_engagements(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    ctx = system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=engagement_id,
        on_behalf_of=uuid.uuid4(),
    )
    await authorise(
        ctx, "evidence.upload", Resource.engagement(ctx.tenant_id, engagement_id, archived=False)
    )
    assert fakes.lookups == [] and fakes.attest_lookups == []


async def test_ac16_an_agent_is_bound_through_its_initiator(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    agent = _agent(_person(), engagement_id)
    fakes.blocks_view = False
    await authorise(agent, "evidence.read", _on(agent, engagement_id))  # the initiator reads
    fakes.blocks_view = True
    assert await _layer(agent, "evidence.read", _on(agent, engagement_id)) == "delegation"
    fakes.attest = False
    await authorise(agent, "evidence.read", _on(agent, engagement_id))


async def test_ac16_walls_come_before_independence(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id = uuid.uuid4()

    async def walled(*_: object) -> frozenset[uuid.UUID]:
        return frozenset({client_id})

    monkeypatch.setattr(authz, "walled_clients", walled)
    fakes.confirmed = True
    ctx = _person()
    resource = Resource.engagement(
        ctx.tenant_id, uuid.uuid4(), archived=False, client_id=client_id
    )
    assert await _layer(ctx, "evidence.read", resource) == "wall"
    assert fakes.lookups == []


def test_ac15_visible_admits_pending_staff_unless_the_setting_applies(fakes: Fakes) -> None:
    expression = visible(_person(), "connection.read_log", column("engagement_id", Uuid()))
    sql = _sql(expression)
    # staff: member AND (confirmed OR NOT (the firm's g2_blocks_view AND attest)).
    assert "independence_confirmed OR NOT (EXISTS (SELECT firm_setting_values.key" in sql
    assert "firm_setting_values.value IS true" in sql
    assert G2_BLOCKS_VIEW in expression.compile().params.values()


def test_ac15_visible_reads_the_attest_flag_when_registered(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def attest(engagement_id: object) -> ColumnElement[bool]:
        return literal_column("engagement_is_attest")

    monkeypatch.setattr(authz.LOOKUPS, "attest_column", attest)
    sql = _sql(visible(_person(), "review.read", column("engagement_id", Uuid())))
    assert "AND engagement_is_attest" in sql
