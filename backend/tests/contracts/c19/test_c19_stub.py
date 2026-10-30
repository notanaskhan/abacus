"""T-01-T01 (TASK-2105; SPEC-501 AC-1 to AC-4): the C19 v1 stub on the wire, in the matrix and in
the module API (`docs/contracts/c19-consent-gate.md`).

Every C19 route declares its action and is a stub; every write denies the agent, the system and
the client principals; the fields are classified with TRI tagged where they carry return figures;
no field is a plaintext TIN; the module API raises until T-01-T10."""

from __future__ import annotations

import inspect
import json
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import CLIENTS_TAX_PROFILE, CONSENTS_REGISTRY
from abacus.kernel.classification import unclassified_fields
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import api as organisations_api
from abacus.modules.organisations import consents_contract as contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
MODELS: list[type[BaseModel]] = [
    v
    for v in vars(contract).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
]
WRITES = (
    "consent.request",
    "consent.record",
    "consent.export",
    "consent.evidence_download",
    "consent_template.manage",
    "consent_template.publish",
    "tax_election.manage",
    "tax_authorization.manage",
    "transcript.upload",
    "transcript.compare",
)
NEVER = ("agent", "system", "client_admin", "client_contributor", "third_party")
ROUTES = [
    ("get", "/v1/consents", "consent.read"),
    ("get", "/v1/consents/summary", "consent.read"),
    ("get", "/v1/consents/{consent_id}", "consent.read"),
    (
        "get",
        "/v1/consents/{consent_id}/documents/{document_id}/evidence",
        "consent.evidence_download",
    ),
    ("post", "/v1/consents/requests", "consent.request"),
    ("post", "/v1/consents/renewals", "consent.request"),
    ("post", "/v1/consents/records", "consent.record"),
    ("post", "/v1/consents/{consent_id}/declines", "consent.record"),
    ("post", "/v1/consents/{consent_id}/revocations", "consent.record"),
    ("post", "/v1/consents/exports", "consent.export"),
    ("get", "/v1/client-entities/{client_entity_id}/consents", "consent.read"),
    ("post", "/v1/consent-templates/imports", "consent_template.manage"),
    ("post", "/v1/consent-templates/{template_id}/publish", "consent_template.publish"),
    ("get", "/v1/client-entities/{client_entity_id}/tax-profile", "tax_profile.read"),
    ("put", "/v1/client-entities/{client_entity_id}/elections/{kind}", "tax_election.manage"),
    ("get", "/v1/client-entities/{client_entity_id}/authorizations", "tax_authorization.manage"),
    ("post", "/v1/client-entities/{client_entity_id}/authorizations", "tax_authorization.manage"),
    (
        "post",
        "/v1/client-entities/{client_entity_id}/authorizations/requests",
        "tax_authorization.manage",
    ),
    ("post", "/v1/client-entities/{client_entity_id}/transcripts", "transcript.upload"),
    ("post", "/v1/transcripts/{transcript_id}/comparisons", "transcript.compare"),
]


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_ac1_every_route_declares_its_action_and_is_a_stub(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert "501" in cast(Json, op["responses"])


@pytest.mark.parametrize("action", (*WRITES, "consent.read", "tax_profile.read"))
def test_ac2_no_agent_system_or_client_holds_a_c19_action(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in NEVER:
        assert decisions.get(principal, "deny") == "deny", (action, principal)


def test_ac2_recording_exporting_and_templates_need_a_fresh_second_factor() -> None:
    for action in (
        "consent.record",
        "consent.export",
        "consent_template.manage",
        "consent_template.publish",
    ):
        assert RULES[action].mfa_recent, action


def test_ac3_every_field_is_classified_and_return_figures_are_tri() -> None:
    for model in MODELS:
        assert unclassified_fields(model) == [], model.__name__
    tri = contract.TranscriptLineDiffOut.model_json_schema()
    assert json.dumps(tri).count('"x-tri": true') >= 3


def test_ac3_no_field_holds_a_plaintext_tin() -> None:
    for model in MODELS:
        for name in model.model_fields:
            assert name not in {"tin", "ssn", "ein", "itin"}, (model.__name__, name)


def test_ac4_the_flags_exist_and_default_off() -> None:
    assert CONSENTS_REGISTRY.default == "false"
    assert CLIENTS_TAX_PROFILE.default == "false"


def test_ac4_the_module_api_is_exported_and_built() -> None:
    # The stub raised until T-01-T11 built C19 condition 6; the verdict is now the real reader
    # (its behaviour is test_t01t11_consent_gate's), so here: exported, async, no longer a stub.
    assert {"consent_state", "tri_consent_verdict"} <= set(organisations_api.__all__)
    verdict = organisations_api.tri_consent_verdict
    assert inspect.iscoroutinefunction(verdict)
    assert "NotImplementedError" not in inspect.getsource(verdict)
