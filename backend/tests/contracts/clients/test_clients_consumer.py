"""Clients v1 consumer contract tests (P-07-T06; SPEC-321 AC-20 to AC-22): what CLI-01 and CLI-02
rely on, read from the OpenAPI document as a consumer reads the generated client. Schema shape
only; they run in the provider's CI against the stub and keep holding once the routes are live.

- the index is the P-36 envelope and its row carries what CLI-01's columns need;
- no schema anywhere carries a hidden-by-wall count or field (DEC-43, INV-3);
- a TIN reaches a consumer only as `MaskedTinOut` (kind, presence, four digits, Restricted) or in
  the one reveal response; a plain-TIN field anywhere else fails here;
- client and portal statuses are exactly the registry's codes (C2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VOCABULARY = Path(__file__).resolve().parents[4] / "docs" / "product" / "status-vocabulary.yaml"
OBJECTS = cast(dict[str, Json], yaml.safe_load(VOCABULARY.read_text())["objects"])

# A field whose name says it holds a taxpayer ID (whole word, or a `_tin`/`tin_` part).
TIN_NAME = re.compile(r"(^|_)(tin|ssn|ein|itin|taxpayer_id|tax_id)(_|$)")
WALL_NAME = re.compile(r"(hidden|walled|wall_count|by_wall)")
MASKED = "#/components/schemas/MaskedTinOut"
# The one schema allowed a plain TIN: the reveal response, reached only by the reveal route.
REVEAL = ("TinRevealOut", "value")


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _refs(prop: Json) -> set[str]:
    found: set[str] = set()
    for key in ("$ref",):
        if key in prop:
            found.add(cast(str, prop[key]))
    for option in cast(list[Json], prop.get("anyOf", [])):
        found |= _refs(option)
    if "items" in prop:
        found |= _refs(cast(Json, prop["items"]))
    return found


def _codes(obj: str) -> set[str]:
    return set(cast(dict[str, object], OBJECTS[obj]["codes"]))


def _enum(schema: str) -> set[str]:
    return set(cast(list[str], SCHEMAS[schema]["enum"]))


# --- CLI-01: the envelope and the row -----------------------------------------------------------


def test_ac20_the_index_is_the_p36_envelope_with_an_exact_total() -> None:
    page = _props("ListPage_ClientRowOut_")
    assert set(page) == {"items", "next_cursor", "total", "total_capped", "counts", "facets"}
    assert page["total"]["type"] == "integer"  # DEC-47: exact, never null for clients
    get = PATHS["/v1/clients"]["get"]
    names = {cast(str, p["name"]) for p in cast(list[Json], get["parameters"])}
    assert {"kind", "office_id", "partner_id", "service_line", "status", "q", "cursor"} <= names


def test_ac20_the_row_carries_cli01s_columns() -> None:
    row = _props("ClientRowOut")
    assert {
        "name",
        "kind",
        "entity_count",
        "service_lines",
        "is_attest_client",
        "office_name",
        "relationship_partner_initials",
        "portal_status",
        "open_request_count",
        "last_activity_at",
        "allowed_actions",
    } <= set(row)


def test_ac20_the_record_carries_subbar_facts_tab_counts_and_a_version() -> None:
    record = _props("ClientRecordOut")
    assert {"tab_counts", "version", "allowed_actions", "entities", "status"} <= set(record)
    assert set(_props("ClientTabCountsOut")) >= {"engagements", "relationships", "contacts"}


# --- DEC-43: no wall count, anywhere --------------------------------------------------------


@pytest.mark.parametrize("schema", sorted(SCHEMAS))
def test_ac21_no_schema_has_a_hidden_by_wall_field(schema: str) -> None:
    assert not [p for p in _props(schema) if WALL_NAME.search(p)], schema


def test_ac21_the_clients_list_takes_no_wall_parameter() -> None:
    params = cast(list[Json], PATHS["/v1/clients"]["get"]["parameters"])
    assert not [p for p in params if WALL_NAME.search(cast(str, p["name"]))]


# --- Masked TIN shape only ----------------------------------------------------------------------


@pytest.mark.parametrize("schema", sorted(SCHEMAS))
def test_ac22_no_schema_carries_a_plain_tin(schema: str) -> None:
    for name, prop in _props(schema).items():
        if TIN_NAME.search(name):
            # A TIN-named field is the masked shape, by reference, and nothing else.
            assert _refs(prop) == {MASKED}, f"{schema}.{name} is not MaskedTinOut"


def test_ac22_the_masked_shape_is_kind_presence_and_four_restricted_digits() -> None:
    masked = _props("MaskedTinOut")
    assert set(masked) == {"kind", "presence", "last4"}
    assert set(cast(list[str], masked["kind"]["enum"])) == {"ssn", "ein", "itin"}
    assert masked["last4"]["cls"] == "restricted"
    assert {"type": "string", "pattern": "^[0-9]{4}$"} in cast(
        list[Json], masked["last4"]["anyOf"]
    )


def test_ac22_the_list_row_never_carries_a_restricted_field() -> None:
    assert all(p.get("cls") != "restricted" for p in _props("ClientRowOut").values())
    assert MASKED not in {r for p in _props("ClientRowOut").values() for r in _refs(p)}


def test_ac22_the_plain_value_is_only_in_the_reveal_response_and_restricted() -> None:
    schema, field = REVEAL
    assert _props(schema)[field]["cls"] == "restricted"
    users = [
        (path, method)
        for path, ops in PATHS.items()
        for method, op in ops.items()
        if f"#/components/schemas/{schema}" in json.dumps(op.get("responses", {}))
    ]
    assert users == [("/v1/client-entities/{entity_id}/tin/reveal", "post")]


# --- C2 status codes ----------------------------------------------------------------------------


def test_ac20_client_and_portal_statuses_are_the_registry_codes() -> None:
    assert _enum("ClientStatus") == _codes("client")
    assert _enum("InvitationStatus") == _codes("invitation")
    assert _props("ClientRowOut")["status"]["$ref"] == "#/components/schemas/ClientStatus"
    assert _props("ClientRowOut")["portal_status"]["$ref"] == (
        "#/components/schemas/InvitationStatus"
    )
