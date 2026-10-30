"""N-02-T03 stubs and N-02-T04 consumer contract tests (`docs/contracts/c7-envelopes.md`;
SPEC-381). Every C7 route declares its one matrix action and answers 404 for the wrong kind of
principal, 404 with `signatures.envelopes` off and 501 with it on; every field is classified;
every final verb denies the agent and the system (AC-16) while the agent may draft; and the view
models SIG-01, SIG-02, POR-06 and ENG-04 build against carry registry status words, a masked IP
only, no TIN or SSN field, `allowed_actions`, and a reserved `signing_session`."""

from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast, get_args

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import SIGNATURES_ENVELOPES
from abacus.kernel._statuses import EnvelopeSignerStatus, EnvelopeStatus, LetterStatus
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.engagements import letter_contract as letters
from abacus.modules.identity.api import AbacusRouter, AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.signatures import contract as c7

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
Endpoint = Callable[..., Awaitable[object]]

FINAL_VERBS = (
    "envelope.send",
    "envelope.remind",
    "envelope.void",
    "envelope.import_record",
    "envelope.record_wet_signature",
    "envelope.countersign",
    "envelope.evidence_download",
    "signer.reveal_ip",
    "envelope_policy.manage",
    "letter.approve",
    "letter.send",
    "letter.amend",
    "portal_envelopes.read",
    "portal_envelopes.sign",
    "portal_envelopes.decline",
    "portal_envelopes.download",
)


def _routes(*routers: AbacusRouter) -> list[APIRoute]:
    out = [r for router in routers for r in router.routes if isinstance(r, APIRoute)]
    assert out
    return out


FIRM = [(r, c7) for r in _routes(c7.router, c7.policies_router)] + [
    (r, letters) for r in _routes(letters.letter_router)
]
PORTAL = _routes(c7.portal_router)
# Live since N-02-T08 (record-mode import; DEC-818): their own codes, never 501.
IMPORTS = frozenset({"import_envelope_record_route", "stage_envelope_import_file_route"})
# N-02-T13 (DEC-1055): the hub routes keep the contract's own actions.
LIVE_ACTIONS = {
    "list_envelopes_route": "envelope.read",
    "envelope_summary_route": "envelope.read",
    "get_envelope_route": "envelope.read",
    "void_envelope_route": "envelope.void",
    "reveal_signer_ip_route": "signer.reveal_ip",
    "envelope_evidence_route": "envelope.evidence_download",
    # N-02-T20 (DEC-1178): SIG-02's builder.
    "create_envelope_draft_route": "envelope.draft",
    "update_envelope_draft_route": "envelope.draft",
    "validate_envelope_route": "envelope.draft",
    "send_envelope_route": "envelope.send",
    "undo_envelope_send_route": "envelope.send",
    "envelope_page_route": "envelope.read",  # N-02-T20 follow-up: the masked preview page
}
LIVE = frozenset(
    {
        *IMPORTS,
        # N-02-T13 (DEC-1055): the hub, the drawer and its actions.
        "list_envelopes_route",
        "envelope_summary_route",
        "get_envelope_route",
        "void_envelope_route",
        "reveal_signer_ip_route",
        "envelope_evidence_route",
        # N-02-T20 (DEC-1178): drafts, edits, checks, Send and Undo.
        "create_envelope_draft_route",
        "update_envelope_draft_route",
        "validate_envelope_route",
        "send_envelope_route",
        "undo_envelope_send_route",
        "envelope_page_route",
    }
)
STUBBED = [(r, m) for r, m in FIRM if r.name not in LIVE]


def _models(module: ModuleType) -> list[type[BaseModel]]:
    return [
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]


MODELS = _models(c7) + _models(letters)


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


def _call(endpoint: Endpoint, ctx: AuthContext) -> Awaitable[object]:
    params = inspect.signature(endpoint).parameters
    return endpoint(**{n: (ctx if n == "ctx" else None) for n in params})


@pytest.mark.parametrize("route", [r for r, _m in STUBBED] + PORTAL, ids=lambda r: r.name)
def test_n02t03_each_route_declares_one_matrix_action_and_is_a_stub(route: APIRoute) -> None:
    method = next(iter(route.methods or {"GET"})).lower()
    op = PATHS[route.path][method]
    assert op["x-abacus-action"] in RULES
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize(("route", "module"), STUBBED, ids=[r.name for r, _m in STUBBED])
async def test_n02t03_firm_routes_client_404_then_action_then_flag_then_501(
    route: APIRoute, module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Flag] = []
    asked: list[str] = []
    state = {"on": False}

    async def flag_enabled(_tenant: object, f: Flag) -> bool:
        seen.append(f)
        return state["on"]

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        asked.append(action)

    monkeypatch.setattr(module, "flag_enabled", flag_enabled)
    monkeypatch.setattr(module, "authorise", authorise)
    endpoint = cast(Endpoint, route.endpoint)
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx(client=True))
    assert (seen, asked) == ([], [])
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx())
    method = next(iter(route.methods or {"GET"})).lower()
    assert asked == [PATHS[route.path][method]["x-abacus-action"]]
    assert seen == [SIGNATURES_ENVELOPES]
    state["on"] = True
    with pytest.raises(NotImplementedYet):
        await _call(endpoint, _ctx())


@pytest.mark.parametrize("route", PORTAL, ids=lambda r: r.name)
async def test_n02t03_portal_routes_firm_404_then_flag_then_501(
    route: APIRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Flag] = []
    state = {"on": False}

    async def flag_enabled(_tenant: object, f: Flag) -> bool:
        seen.append(f)
        return state["on"]

    monkeypatch.setattr(c7, "flag_enabled", flag_enabled)
    endpoint = cast(Endpoint, route.endpoint)
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx())
    assert seen == []
    with pytest.raises(NotFound):
        await _call(endpoint, _ctx(client=True))
    state["on"] = True
    with pytest.raises(NotImplementedYet):
        await _call(endpoint, _ctx(client=True))


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize("action", FINAL_VERBS)
def test_ac16_every_final_verb_denies_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


def test_ac16_the_agent_may_draft_only() -> None:
    assert RULES["envelope.draft"].decisions.get("agent") == "allow"
    assert RULES["letter.draft"].decisions.get("agent") == "allow"


def test_ac5_ac9_ac13_reveal_policy_and_approval_need_a_fresh_second_factor() -> None:
    for action in ("signer.reveal_ip", "envelope_policy.manage", "letter.approve"):
        assert RULES[action].mfa_recent, action
    assert RULES["signer.reveal_ip"].not_offshore
    assert RULES["signer.reveal_ip"].requires_reason


def test_portal_actions_are_scope_only() -> None:
    for action in FINAL_VERBS:
        if action.startswith("portal_envelopes."):
            assert RULES[action].scope_only, action


# --- Consumers (N-02-T04) ------------------------------------------------------------------------


def test_ac8_no_sms_identity_method_exists() -> None:
    assert "sms_code" not in get_args(c7.IdentityMethod)
    assert set(get_args(c7.IdentityMethod)) == {"kba", "email_code", "in_person_id", "firm_sso"}


def test_ac5_evidence_carries_a_masked_ip_only() -> None:
    fields = set(c7.EvidenceItem.model_fields)
    assert "ip_masked" in fields
    assert not {"ip", "ip_sealed", "ip_address"} & fields


def test_no_shape_has_a_tin_or_ssn_field() -> None:
    for model in MODELS:
        for name in model.model_fields:
            assert not {"ssn", "tin", "itin", "ein"} & set(name.split("_")), (
                model.__name__,
                name,
            )


def test_sig01_rows_and_drawer_carry_allowed_actions_and_registry_words() -> None:
    assert "allowed_actions" in c7.EnvelopeListRow.model_fields
    assert c7.EnvelopeListRow.model_fields["status"].annotation is EnvelopeStatus
    assert c7.SignerOut.model_fields["status"].annotation is EnvelopeSignerStatus
    assert "verification_failed" in {s.value for s in EnvelopeSignerStatus}


def test_por06_signing_session_and_outcome_are_reserved() -> None:
    fields = c7.PortalEnvelopeView.model_fields
    assert fields["signing_session"].default is None
    assert fields["outcome"].default is None
    assert "paper_form_follows" in fields


def test_eng04_letter_words_are_df31() -> None:
    assert {s.value for s in LetterStatus} == {
        "not_started",
        "draft",
        "partner_approved",
        "sent",
        "signed",
        "not_required",
        "superseded",
    }
    assert "approval_content_hash" in letters.ComposerLetterOut.model_fields


@pytest.mark.parametrize("route", [r for r, _m in FIRM if r.name in LIVE], ids=lambda r: r.name)
def test_n02t08_the_live_import_routes_declare_their_action_and_no_501(route: APIRoute) -> None:
    method = next(iter(route.methods or {"GET"})).lower()
    op = PATHS[route.path][method]
    assert op["x-abacus-action"] == LIVE_ACTIONS.get(route.name, "envelope.import_record")
    assert "501" not in set(cast(Json, op["responses"]))
