"""The team, acceptance, independence and conflict contract stubs, v1 (P-07-T29;
`docs/contracts/acceptance-independence.md`; DEC-326): every route exists with its one matrix
action and answers 404 with its flag off (501 with it on, until the task that makes it live);
the decision and conclusion option sets are SPEC-332's; a conflict result can be redacted with no
name or client; every field is classified and no model carries a wall count; every human-only
action denies the agent and the system and no client role holds any action. The consumer suite
is P-07-T31's."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel._flags import ENGAGEMENTS_ACCEPTANCE_V2, ENGAGEMENTS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.kernel.errors import NotFound
from abacus.modules.engagements import acceptance_contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import conflicts_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
E = "/v1/engagements/{engagement_id}"
ACC = f"{E}/acceptance"
IND = f"{E}/independence"
CHECK = "/v1/conflict-checks"

# (method, path) -> the one matrix action (P-07 §4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", ACC): "acceptance.read",
    ("put", f"{ACC}/answers/{{section_code}}"): "acceptance.prepare",
    ("post", f"{ACC}/flags"): "acceptance.prepare",
    ("post", f"{ACC}/manual-checks/{{section_code}}/request"): "acceptance.prepare",
    ("post", f"{ACC}/manual-checks/{{section_code}}/complete"): "acceptance.prepare",
    ("post", f"{ACC}/send-to-partner"): "acceptance.prepare",
    ("post", f"{ACC}/conditions/{{condition_id}}/complete"): "acceptance.prepare",
    ("post", f"{ACC}/risk-partner-review"): "acceptance.request_review",
    ("post", f"{ACC}/risk-partner-review/complete"): "acceptance.complete_review",
    ("post", f"{ACC}/decision"): "acceptance.decide",
    ("get", IND): "independence.read",
    ("get", f"{IND}/rotation"): "independence.read",
    ("post", f"{IND}/confirm"): "independence.confirm",
    ("post", f"{IND}/decline"): "independence.confirm",
    ("post", f"{IND}/reminders"): "independence.remind",
    ("get", f"{IND}/nas"): "independence.read",
    ("put", f"{IND}/nas/{{service_code}}"): "nas.evaluate",
    ("post", f"{IND}/breaches"): "independence.breach_manage",
    ("post", f"{IND}/breaches/{{breach_id}}/events"): "independence.breach_manage",
    ("post", f"{IND}/conclude"): "independence.conclude",
    ("get", f"{E}/team/approval"): "engagement.read_metadata",
    ("post", f"{E}/team/approve"): "team.approve",
    ("put", f"{E}/team/{{user_id}}/portal-visibility"): "engagement.update",
    ("get", f"{E}/eqr/candidates"): "eqr.assign",
    ("post", f"{E}/eqr"): "eqr.assign",
    ("post", f"{E}/eqr/eligibility/approve"): "eqr.approve_eligibility",
    ("post", CHECK): "conflict.run",
    ("get", f"{CHECK}/{{check_id}}"): "conflict.run",
    ("post", f"{CHECK}/{{check_id}}/results/{{result_id}}/clear"): "conflict.clear",
    ("post", "/v1/screening-records"): "screening.record",
}
# ENG-05's team rows and the confirmation requests are live since P-07-T30 (TASK-1197); CLI-07's
# acceptance routes since P-07-T35 (TASK-1258); conflicts and screening since P-07-T36
# (TASK-1259); independence v2 since P-07-T41 (TASK-1325).
LIVE: set[tuple[str, str]] = {
    *((m, p) for (m, p) in ROUTES if p.startswith(IND)),
    *((m, p) for (m, p) in ROUTES if p.startswith(ACC)),
    *((m, p) for (m, p) in ROUTES if p.startswith((CHECK, "/v1/screening-records"))),
    ("get", f"{E}/team/approval"),
    ("post", f"{E}/team/approve"),
    ("put", f"{E}/team/{{user_id}}/portal-visibility"),
    ("get", f"{E}/eqr/candidates"),
    ("post", f"{E}/eqr"),
    ("post", f"{E}/eqr/eligibility/approve"),
    ("post", f"{IND}/reminders"),
}
STUBBED = set(ROUTES) - LIVE
HUMAN_ONLY = {
    "acceptance.decide",
    "acceptance.complete_review",
    "independence.confirm",
    "independence.conclude",
    "conflict.clear",
    "team.approve",
    "eqr.approve_eligibility",
}
NEW_ACTIONS = {
    "acceptance.read",
    "acceptance.complete_review",
    "acceptance.prepare",
    "acceptance.request_review",
    "acceptance.decide",
    "independence.read",
    "independence.remind",
    "independence.conclude",
    "independence.breach_manage",
    "nas.evaluate",
    "team.approve",
    "eqr.assign",
    "eqr.approve_eligibility",
    "conflict.run",
    "conflict.clear",
    "screening.record",
}
CLIENT_ROLES = {"client_admin", "client_contributor"}
PREFIXES = (
    "Acceptance",
    "ManualCheck",
    "SourceRef",
    "RiskPartner",
    "PriorAcceptance",
    "SendToPartner",
    "Condition",
    "MemberConfirmation",
    "Independence",
    "Rotation",
    "Confirm",
    "Decline",
    "Reminders",
    "Nas",
    "Breach",
    "Conclude",
    "TeamApproval",
    "PortalVisibility",
    "Eqr",
    "ConflictCheck",
    "ConflictResult",
    "ConflictClear",
    "Subject",
    "Screening",
)


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema]["properties"])


def _enum(schema: str, field: str) -> set[str]:
    prop = _props(schema)[field]
    if "anyOf" in prop:
        prop = next(p for p in cast(list[Json], prop["anyOf"]) if p.get("type") != "null")
    if "$ref" in prop:
        ref = cast(str, prop["$ref"]).rsplit("/", 1)[-1]
        return set(cast(list[str], SCHEMAS[ref]["enum"]))
    return set(cast(list[str], prop["enum"]))


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) in STUBBED)


def test_the_decision_and_conclusion_option_sets_are_the_specs() -> None:
    assert _enum("AcceptanceDecisionIn", "option") == {
        "accept",
        "accept_with_conditions",
        "decline",
    }
    assert _enum("ConcludeIn", "option") == {
        "independent",
        "independent_with_safeguards",
        "not_independent",
    }
    assert {"rationale", "conditions", "seen_version"} <= set(_props("AcceptanceDecisionIn"))
    assert _enum("ConflictClearIn", "assessment") == {
        "clear",
        "same_family_not_adverse",
        "not_adverse",
        "counterparty_review",
        "conflict",
    }
    assert _enum("ScreeningRecordIn", "result") == {"no_match", "match", "not_applicable"}


def test_a_conflict_result_can_be_redacted_with_no_name_or_client() -> None:
    result = _props("ConflictResultOut")
    required = set(cast(list[str], SCHEMAS["ConflictResultOut"].get("required", [])))
    assert {"redacted", "match_kind"} <= required
    # Everything that could name or point at a walled client is optional (null when redacted).
    assert not {"matched_client_id", "matched_name", "matched_ref_id"} & required
    assert {"matched_client_id", "matched_name"} <= set(result)
    assert _enum("ConflictResultOut", "match_kind") == {
        "exact",
        "trigram",
        "relationship",
        "counterparty",
    }
    assert _props("ConflictCheckIn")["names"]["maxItems"] == 50


def test_the_eqr_checks_and_eligibility_are_codes() -> None:
    assert _enum("EqrCheckOut", "code") == {
        "not_on_team",
        "cooling_off",
        "competence",
        "independence",
        "capacity",
    }
    assert _enum("EqrCandidateOut", "eligibility") == {"eligible", "not_eligible"}


def test_every_field_is_classified_and_no_model_has_a_wall_count() -> None:
    seen = 0
    for name, schema in SCHEMAS.items():
        if name.startswith(PREFIXES):
            props = cast(dict[str, Json], schema.get("properties", {}))
            assert all("cls" in p for p in props.values()), name
            assert not {p for p in props if "wall" in p or "hidden" in p}, name
            seen += 1
    assert seen >= 30


@pytest.mark.parametrize("action", sorted(NEW_ACTIONS | {"independence.confirm"}))
def test_the_agent_and_the_system_are_denied_and_no_client_role_holds_it(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    assert not {r for r, d in rule.decisions.items() if d != "deny"} & CLIENT_ROLES


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY))
def test_human_only_actions_are_held_by_people_only(action: str) -> None:
    granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
    assert granted and not granted & {"agent", "system", *CLIENT_ROLES}


def test_the_decision_and_conclusion_need_fresh_mfa_and_the_ep() -> None:
    for action in ("acceptance.decide", "independence.conclude"):
        granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
        assert granted == {"engagement_partner"}, action
    assert {r for r, d in RULES["team.approve"].decisions.items() if d != "deny"} == {
        "engagement_partner"
    }
    assert {r for r, d in RULES["eqr.approve_eligibility"].decisions.items() if d != "deny"} == {
        "quality_partner"
    }


def _ctx(kind: ActorKind = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


E_ID = uuid.uuid4()


async def test_the_flags_gate_each_half_after_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Security review (DEC-326): authorise first, then the flag, then 501 (the audits order)."""
    seen: list[object] = []

    async def allowed(_ctx: object, action: str, _engagement_id: object) -> None:
        seen.append(action)

    async def authorised(_ctx: object, action: str, _resource: object) -> None:
        seen.append(action)

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(acceptance_contract, "_allowed", allowed)
    monkeypatch.setattr(conflicts_contract, "authorise", authorised)
    for module in (acceptance_contract, conflicts_contract):
        monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await acceptance_contract._acceptance_gate(_ctx(), "acceptance.read", E_ID)  # pyright: ignore[reportPrivateUsage] -- the gate
    with pytest.raises(NotFound):
        await acceptance_contract._team_gate(_ctx(), "team.approve", E_ID)  # pyright: ignore[reportPrivateUsage] -- the gate
    with pytest.raises(NotFound):
        await conflicts_contract._gate(_ctx(), "conflict.run")  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == [
        "acceptance.read",
        ENGAGEMENTS_ACCEPTANCE_V2,
        "team.approve",
        ENGAGEMENTS_V2,
        "conflict.run",
        ENGAGEMENTS_ACCEPTANCE_V2,
    ]
    for module in (acceptance_contract, conflicts_contract):
        monkeypatch.setattr(module, "flag_enabled", on)
    await acceptance_contract._acceptance_gate(_ctx(), "acceptance.read", E_ID)  # pyright: ignore[reportPrivateUsage] -- live (P-07-T41)
    await acceptance_contract._team_gate(_ctx(), "team.approve", E_ID)  # pyright: ignore[reportPrivateUsage] -- live
    await conflicts_contract._gate(_ctx(), "conflict.run")  # pyright: ignore[reportPrivateUsage] -- live


@pytest.mark.parametrize("flag_on", [False, True])
@pytest.mark.parametrize("who", ["agent", "system", "client"])
async def test_agent_system_and_client_are_refused_whatever_the_flag(
    monkeypatch: pytest.MonkeyPatch, flag_on: bool, who: str
) -> None:
    """Security review (DEC-326): refused before the flag is read or any row is looked up."""
    flags: list[object] = []

    async def flag(_tenant: object, f: object) -> bool:
        flags.append(f)
        return flag_on

    for module in (acceptance_contract, conflicts_contract):
        monkeypatch.setattr(module, "flag_enabled", flag)
    ctx = _ctx("human", client=True) if who == "client" else _ctx(cast(ActorKind, who))
    with pytest.raises(Forbidden):
        await acceptance_contract._acceptance_gate(ctx, "acceptance.decide", E_ID)  # pyright: ignore[reportPrivateUsage] -- the gate
    with pytest.raises(Forbidden):
        await acceptance_contract._team_gate(ctx, "engagement.read_metadata", E_ID)  # pyright: ignore[reportPrivateUsage] -- the gate
    with pytest.raises(Forbidden):
        await conflicts_contract._gate(ctx, "conflict.clear")  # pyright: ignore[reportPrivateUsage] -- the gate
    assert flags == []


def test_the_new_codes_are_in_the_catalogue() -> None:
    catalogue = Path(__file__).resolve().parents[4] / "docs/architecture/error-codes.yaml"
    codes = cast(dict[str, Json], yaml.safe_load(catalogue.read_text())["codes"])
    expected = {
        "decision_locked": 409,
        "rationale_required": 422,
        "acceptance_not_ready": 409,
        "review_required": 409,
        "independence_preconditions_unmet": 409,
        "not_self": 409,
        "eqr_on_team": 409,
        "eqr_approver_is_ep": 409,
        "eqr_approver_on_engagement": 409,
        "eqr_approval_required": 409,
        "eqr_not_eligible": 409,
    }
    assert {code: codes[code]["status"] for code in expected} == expected
