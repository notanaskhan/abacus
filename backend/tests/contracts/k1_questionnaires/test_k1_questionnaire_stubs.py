"""T-02-T02 (TASK-2117; SPEC-502 AC-5): the K-1 package and questionnaire stubs on the wire
(`docs/contracts/k1-packages.md`, `questionnaires.md`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.requests import questionnaires_contract
from abacus.modules.tax import k1_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
ROOT = Path(__file__).resolve().parents[4]
ROUTES = [
    ("get", "/v1/tax-returns/{return_id}/k1-packages", "k1_package.read"),
    ("get", "/v1/k1-packages/{package_id}", "k1_package.read"),
    ("get", "/v1/k1-packages/{package_id}/documents/{document_id}", "k1_package.read"),
    (
        "post",
        "/v1/tax-returns/{return_id}/k1-packages:share-internal",
        "k1_package.share_internal",
    ),
    ("get", "/v1/tax-returns/{return_id}/k1-packages/release-check", "k1_package.read"),
    ("post", "/v1/tax-returns/{return_id}/k1-packages:release", "k1_package.release"),
    ("post", "/v1/k1-releases/{release_id}:undo", "k1_package.release"),
    ("post", "/v1/k1-packages/{package_id}:resend", "k1_package.resend"),
    ("get", "/v1/k1-recipients/{recipient_id}/details-changes", "k1_recipient.review_details"),
    ("post", "/v1/recipient-details-changes/{change_id}:accept", "k1_recipient.review_details"),
    ("post", "/v1/recipient-details-changes/{change_id}:reject", "k1_recipient.review_details"),
    ("post", "/v1/questionnaire-templates:import", "questionnaire_template.import"),
    ("get", "/v1/questionnaire-templates", "questionnaire_template.read"),
    (
        "post",
        "/v1/questionnaire-templates/{template_id}/versions/{version}:publish",
        "questionnaire_template.publish",
    ),
    ("post", "/v1/request-lists/{request_list_id}/questionnaires", "questionnaire.create"),
    ("post", "/v1/questionnaires", "questionnaire.create"),
    ("post", "/v1/questionnaires/{questionnaire_id}/questions", "questionnaire.ask"),
    ("post", "/v1/questions/{question_id}:send", "questionnaire.ask"),
    ("get", "/v1/request-lists/{request_list_id}/questionnaires", "questionnaire.read"),
    ("get", "/v1/questionnaires/{questionnaire_id}", "questionnaire.read"),
    ("get", "/v1/portal/questionnaires", "portal_questionnaire.read"),
    ("get", "/v1/portal/questionnaires/{questionnaire_id}", "portal_questionnaire.read"),
    (
        "put",
        "/v1/portal/questionnaires/{questionnaire_id}/answers/{question_id}",
        "portal_questionnaire.answer",
    ),
    (
        "post",
        "/v1/portal/questionnaires/{questionnaire_id}:mark-done",
        "portal_questionnaire.complete",
    ),
    ("post", "/v1/portal/questionnaires/{questionnaire_id}:submit", "portal_questionnaire.submit"),
    ("get", "/v1/portal/k1s", "portal_k1.read"),
    ("get", "/v1/portal/k1s/{package_id}", "portal_k1.read"),
    ("get", "/v1/portal/k1s/{package_id}/download", "portal_k1.download"),
    (
        "post",
        "/v1/portal/k1-recipients/{recipient_id}/details-changes",
        "portal_k1.update_details",
    ),
    ("post", "/v1/portal/k1s/{package_id}/e-furnishing-consent", "portal_k1.update_details"),
]


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_ac5_every_route_declares_its_action_and_is_a_stub(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert "501" in cast(Json, op["responses"])


def test_ac5_box_amounts_and_answers_are_tri() -> None:
    models: list[type[BaseModel]] = [
        v
        for module in (k1_contract, questionnaires_contract)
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]
    for model in models:
        assert unclassified_fields(model) == [], model.__name__
    assert k1_contract.K1BoxLineOut.model_json_schema()["properties"]["amount"].get("x-tri")
    assert "x-tri" in json.dumps(questionnaires_contract.AnswerIn.model_json_schema())


def test_ac5_a_package_row_carries_no_tin() -> None:
    """End review: a list row never carries a TIN, even masked (ADR-031); the recipient's own
    detail shows it as `MaskedTinOut`."""
    fields = set(k1_contract.K1PackageOut.model_fields)
    assert not {"tin", "tin_last4", "ssn", "ein"} & fields


def test_ac5_the_contract_docs_exist() -> None:
    assert (ROOT / "docs/contracts/k1-packages.md").is_file()
    assert (ROOT / "docs/contracts/questionnaires.md").is_file()
