"""The AI-policy contract stub, v1 (G-02-T15; `docs/contracts/ai-policy.md`): every route declares
exactly one matrix action and answers 404 with `ai_policy.v1` off and 501 with it on, after the
matrix (security review L1); the family is exactly these routes; every field is classified; no
input carries an unknown field; the draft's If-Match is required; the agent, the system and every
client principal hold no write (INV-1, INV-4); the decline note is the only free text."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._flags import AI_POLICY_V1
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.agents import ai_policy_contract as contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
CONTRACT_DOC = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "ai-policy.md"
BASE = "/v1/firm/ai-policy"

ROUTES: dict[tuple[str, str], str] = {
    ("get", BASE): "ai_policy.read",
    ("get", f"{BASE}/versions"): "ai_policy.read",
    ("get", f"{BASE}/versions/{{version_no}}"): "ai_policy.read",
    ("get", f"{BASE}/effective"): "ai_policy.read",
    ("get", f"{BASE}/draft"): "ai_policy.draft",
    ("put", f"{BASE}/draft"): "ai_policy.draft",
    ("delete", f"{BASE}/draft"): "ai_policy.draft",
    ("post", f"{BASE}/versions"): "ai_policy.publish",
    ("post", f"{BASE}/versions/{{version_no}}/approve"): "ai_policy.approve",
    ("post", f"{BASE}/versions/{{version_no}}/decline"): "ai_policy.approve",
    ("post", f"{BASE}/versions/{{version_no}}/withdraw"): "ai_policy.publish",
}
NAMED = (
    "AiPolicyOut",
    "AiPolicyVersionOut",
    "AiPolicyVersionDetailOut",
    "AiPolicyVersionPageOut",
    "AiPolicyDraftOut",
    "EffectiveAiPolicyOut",
    "GateRowOut",
    "ImmediateControlsOut",
    "SubProcessorOut",
)
MODELS: tuple[type[BaseModel], ...] = (
    contract.AiPolicyOut,
    contract.AiPolicyVersionDetailOut,
    contract.AiPolicyVersionPageOut,
    contract.AiPolicyDraftOut,
    contract.EffectiveAiPolicyOut,
    contract.AiPolicyDraftIn,
    contract.AiPolicyPublishIn,
    contract.AiPolicyDeclineIn,
)
WRITES = ("ai_policy.draft", "ai_policy.publish", "ai_policy.approve")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_g02t15_each_route_declares_its_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_g02t15_the_family_is_these_routes() -> None:
    served = {
        (method, path) for path, ops in PATHS.items() if path.startswith(BASE) for method in ops
    }
    assert served == set(ROUTES)


@pytest.mark.parametrize("name", NAMED)
def test_g02t15_the_named_models_are_published(name: str) -> None:
    assert name in SCHEMAS


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_adr031_the_decline_note_is_the_only_free_text_and_confidential() -> None:
    assert level_of(contract.AiPolicyDeclineIn.model_fields["note"]) == "confidential"
    assert level_of(contract.PolicyPersonOut.model_fields["display_name"]) == "confidential"


def _sections() -> dict[str, object]:
    return {
        "autonomy": {"level": 1},
        "gates": [{"action_key": "aje.approve_batch", "policy_acceptance_on": False}],
        "policy_principal": {"on": False},
        "auto_mode_defaults": {"tax_return": True, "monthly_close": True},
        "client_data": {},
        "governance": {"override_tolerance_pct": 6},
    }


def test_ac38_a_loosening_reaches_the_validator_and_unknown_fields_never_do() -> None:
    # Shape only here: turning the principal on is the validator's 422 (T23), not a model error.
    loosened = _sections()
    loosened["policy_principal"] = {"on": True}
    contract.AiPolicyDraftIn.model_validate({"sections": loosened})
    with pytest.raises(ValidationError):
        contract.AiPolicyDraftIn.model_validate({"sections": {**_sections(), "extra": {}}})
    with pytest.raises(ValidationError):
        contract.AiPolicyPublishIn.model_validate(
            {"effective_from": "2026-09-15", "approver_user_id": str(uuid.uuid4()), "x": 1}
        )


def test_ac36_the_draft_writes_require_if_match() -> None:
    for method in ("put", "delete"):
        params = cast(list[Json], PATHS[f"{BASE}/draft"][method].get("parameters", []))
        assert any(p.get("name") == "If-Match" and p.get("required") for p in params), method


@pytest.mark.parametrize("action", WRITES)
def test_ac45_no_agent_system_or_client_holds_a_policy_write(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


@pytest.mark.parametrize("action", ["ai_policy.publish", "ai_policy.approve"])
def test_ac37_publish_and_approve_ask_for_a_fresh_second_factor(action: str) -> None:
    assert RULES[action].mfa_recent


def test_the_contract_doc_names_every_route() -> None:
    text = CONTRACT_DOC.read_text("utf-8")
    for method, path in ROUTES:
        assert f"`{method.upper()} {path}`" in text, (method, path)


# --- the gate: matrix first, then the flag (security review L1) ---------------------------------


def _ctx(firm_role: str | None, *, client: bool = False, kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # pyright: ignore[reportArgumentType] -- an actor kind code
        user,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- a firm role code
        None,
        client=client,
    )


def _flags(monkeypatch: pytest.MonkeyPatch, value: bool) -> list[Flag]:
    seen: list[Flag] = []

    async def flag_enabled(_tenant: object, flag: Flag) -> bool:
        seen.append(flag)
        return value

    monkeypatch.setattr(contract, "flag_enabled", flag_enabled)
    return seen


def _authorise(monkeypatch: pytest.MonkeyPatch, *, allow: bool) -> None:
    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        if not allow:
            raise Forbidden(action, "role")

    monkeypatch.setattr(contract, "authorise", authorise)


async def test_g02t15_flag_off_is_404_and_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorise(monkeypatch, allow=True)
    _flags(monkeypatch, False)
    with pytest.raises(NotFound):
        await contract._stub(_ctx("quality_partner"), "ai_policy.read")  # pyright: ignore[reportPrivateUsage]
    seen = _flags(monkeypatch, True)
    with pytest.raises(NotImplementedYet):
        await contract._stub(_ctx("quality_partner"), "ai_policy.read")  # pyright: ignore[reportPrivateUsage]
    assert seen == [AI_POLICY_V1]


async def test_l1_the_matrix_answers_before_the_flag_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _flags(monkeypatch, True)
    _authorise(monkeypatch, allow=False)
    with pytest.raises(Forbidden):
        await contract._stub(_ctx(None, kind="agent"), "ai_policy.publish")  # pyright: ignore[reportPrivateUsage]
    _authorise(monkeypatch, allow=True)
    with pytest.raises(NotFound):  # INV-4: a client principal learns nothing, not even a 403
        await contract._stub(_ctx(None, client=True), "ai_policy.read")  # pyright: ignore[reportPrivateUsage]
    assert seen == []
