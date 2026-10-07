"""AC-20: the OpenAPI document and the committed client input (TASK-008 contract, "OpenAPI")."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abacus.api.export_openapi import document

REPO = Path(__file__).resolve().parents[4]
COMMITTED = REPO / "packages" / "api-client" / "openapi.json"
Json = dict[str, object]
METHODS = {"get", "post", "put", "patch", "delete"}
OPERATIONS = {
    "me",
    "create_engagement",
    "list_engagements",
    "get_engagement",
    "create_request_item",
    "list_request_items",
    "start_retrieval",
    "get_retrieval",
}
ROUTES = {
    ("post", "/v1/engagements"): ("create_engagement", "engagement.create"),
    ("get", "/v1/engagements"): ("list_engagements", "engagement.read_metadata"),
    ("get", "/v1/engagements/{engagement_id}"): ("get_engagement", "engagement.read_metadata"),
    ("post", "/v1/engagements/{engagement_id}/request-items"): (
        "create_request_item",
        "request_item.create",
    ),
    ("get", "/v1/engagements/{engagement_id}/request-items"): (
        "list_request_items",
        "request_item.read",
    ),
    ("post", "/v1/engagements/{engagement_id}/retrievals"): (
        "start_retrieval",
        "evidence.upload",
    ),
    ("get", "/v1/engagements/{engagement_id}/retrievals/{sync_run_id}"): (
        "get_retrieval",
        "request_item.read",
    ),
}
RETRIEVALS = "/v1/engagements/{engagement_id}/retrievals"


def _operations() -> list[tuple[str, str, Json]]:
    paths = cast(dict[str, Json], json.loads(document())["paths"])
    return [
        (method, path, cast(Json, op))
        for path, item in paths.items()
        for method, op in item.items()
        if method in METHODS
    ]


def test_ac20_the_document_is_deterministic() -> None:
    assert document() == document() == document()


def test_ac20_the_document_is_sorted_two_space_indented_json_with_a_trailing_newline() -> None:
    text = document()
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    parsed = json.loads(text)
    assert text == json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert text.startswith('{\n  "')


def test_ac20_the_listed_operation_ids_are_present() -> None:
    ids = {cast(str, op["operationId"]) for _m, _p, op in _operations()}
    assert ids >= OPERATIONS


def test_ac20_operation_ids_are_unique() -> None:
    ids = [cast(str, op["operationId"]) for _m, _p, op in _operations()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(("route", "expected"), sorted(ROUTES.items()))
def test_ac20_each_route_has_its_operation_id_and_action(
    route: tuple[str, str], expected: tuple[str, str]
) -> None:
    method, path = route
    paths = cast(dict[str, Json], json.loads(document())["paths"])
    operation = cast(Json, paths[path][method])
    assert (operation["operationId"], operation["x-abacus-action"]) == expected


def test_ac20_every_operation_carries_an_action() -> None:
    operations = _operations()
    assert len(operations) >= 8
    for method, path, op in operations:
        action = op.get("x-abacus-action")
        assert isinstance(action, str) and action, (method, path)


def test_ac20_the_committed_openapi_json_equals_the_document() -> None:
    assert COMMITTED.read_text(encoding="utf-8") == document()


# --- security and error responses (contract revision 1) ------------------------------------------


def test_ac20_the_document_declares_bearer_security_at_the_top_level() -> None:
    parsed = cast(Json, json.loads(document()))
    assert parsed["security"] == [{"bearer": []}]
    schemes = cast(dict[str, Json], cast(Json, parsed["components"])["securitySchemes"])
    scheme = schemes["bearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme["bearerFormat"] == "JWT"


def test_ac20_every_operation_documents_the_error_responses() -> None:
    for method, path, op in _operations():
        responses = cast(dict[str, Json], op["responses"])
        for status in ("401", "403", "404", "422"):
            assert status in responses, (method, path, status)
        for status in ("401", "403", "404"):
            assert json.dumps(responses[status]).count("ErrorOut") >= 1, (path, status)
            assert "ValidationErrorOut" not in json.dumps(responses[status])
        assert "ValidationErrorOut" in json.dumps(responses["422"]), path


def test_ac20_the_error_schemas_have_the_contract_shape() -> None:
    schemas = cast(dict[str, Json], cast(Json, json.loads(document())["components"])["schemas"])
    error = cast(dict[str, Json], schemas["ErrorOut"]["properties"])
    assert set(error) == {"detail"}
    assert error["detail"]["type"] == "string"
    validation = cast(dict[str, Json], schemas["ValidationErrorOut"]["properties"])
    assert set(validation) == {"detail"}
    assert "FieldErrorOut" in json.dumps(validation["detail"])
    field = cast(dict[str, Json], schemas["FieldErrorOut"]["properties"])
    assert set(field) == {"loc", "msg", "type"}


def test_ac20_no_schema_declares_input_or_ctx() -> None:
    schemas = cast(dict[str, Json], cast(Json, json.loads(document())["components"])["schemas"])
    for name, schema in schemas.items():
        properties = cast(dict[str, Json], schema.get("properties", {}))
        assert "input" not in properties, name
        assert "ctx" not in properties, name


def test_ac20_the_committed_client_input_has_the_same_security_and_error_schemas() -> None:
    committed = cast(Json, json.loads(COMMITTED.read_text(encoding="utf-8")))
    assert committed["security"] == [{"bearer": []}]
    schemas = cast(dict[str, Json], cast(Json, committed["components"])["schemas"])
    assert {"ErrorOut", "ValidationErrorOut", "FieldErrorOut"} <= set(schemas)


# --- retrievals (TASK-010b revision 1) -----------------------------------------------------------


def _operation(path: str, method: str) -> Json:
    paths = cast(dict[str, Json], json.loads(document())["paths"])
    return cast(Json, paths[path][method])


def test_ac20_start_retrieval_answers_202_and_declares_409_and_503() -> None:
    responses = cast(dict[str, Json], _operation(RETRIEVALS, "post")["responses"])
    assert "202" in responses
    assert "200" not in responses
    for status in ("409", "503"):
        assert status in responses
        assert "ErrorOut" in json.dumps(responses[status])
        assert "ValidationErrorOut" not in json.dumps(responses[status])


def test_ac20_get_retrieval_answers_200() -> None:
    responses = cast(
        dict[str, Json],
        _operation(RETRIEVALS + "/{sync_run_id}", "get")["responses"],
    )
    assert "200" in responses


def test_ac20_the_retrieval_response_schema_has_the_contract_fields() -> None:
    schemas = cast(dict[str, Json], cast(Json, json.loads(document())["components"])["schemas"])
    properties = cast(dict[str, Json], schemas["RetrievalOut"]["properties"])
    assert set(properties) == {
        "sync_run_id",
        "request_item_id",
        "status",
        "failure_code",
        "evidence_version_id",
        "started_at",
        "finished_at",
        "queued_reason",  # TASK-018b (SPEC-003 AC-13)
        "estimated_start_at",
    }


def test_ac20_the_retrieval_request_schema_forbids_extra_fields() -> None:
    schemas = cast(dict[str, Json], cast(Json, json.loads(document())["components"])["schemas"])
    body = schemas["RetrievalIn"]
    assert body["additionalProperties"] is False
    assert set(cast(dict[str, Json], body["properties"])) == {
        "request_item_id",
        "period_start",
        "period_end",
    }
