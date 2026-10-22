"""C5 v1 consumer tests for C-01 (close, CLS-03; P-06-T02): `close_intake` binders, the close
variant's incorporation states, the period fields, the screening glyph the CLS-03 card shows and
the incorporate operation a person performs. Schema and matrix only: the routes are stubs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
OBJECTS = cast(
    dict[str, dict[str, dict[str, dict[str, object]]]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"],
)
INCORPORATE = "/v1/engagements/{engagement_id}/request-items/{item_id}/incorporate"


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _options(prop: Json) -> list[Json]:
    return cast(list[Json], prop["anyOf"]) if "anyOf" in prop else [prop]


def _enum(model: str, field: str) -> set[str]:
    return {
        cast(str, v)
        for o in _options(_props(model)[field])
        for v in cast(list[object], o.get("enum", []))
    }


def _formats(model: str, field: str) -> set[str]:
    return {cast(str, o["format"]) for o in _options(_props(model)[field]) if "format" in o}


@pytest.mark.parametrize("model", ["BinderRowOut", "BinderOut", "BinderIn"])
def test_c01_a_close_intake_binder_is_a_binder_kind(model: str) -> None:
    assert "close_intake" in _enum(model, "kind")


@pytest.mark.parametrize("model", ["RequestItemV2Out", "BinderRequestRowOut"])
def test_c01_incorporation_states_are_the_close_variants_codes(model: str) -> None:
    states = _enum(model, "incorporation_state")
    assert states == {"none", "matched", "pending_incorporation", "incorporated"}
    assert _props(model)["incorporation_state"]["default"] == "none"
    # Every state but `none` is a registry code of the close-intake request (SHL-14 d).
    assert states - {"none"} <= set(OBJECTS["request_close"]["codes"])


def test_c01_incorporated_is_terminal_and_pending_is_not() -> None:
    codes = OBJECTS["request_close"]["codes"]
    assert codes["incorporated"]["terminal"] is True
    assert codes["pending_incorporation"]["terminal"] is False


def test_c01_the_record_names_who_incorporated_and_when() -> None:
    assert _formats("RequestItemV2Out", "incorporated_by") == {"uuid"}
    assert _formats("RequestItemV2Out", "incorporated_at") == {"date-time"}


@pytest.mark.parametrize("model", ["RequestItemV2Out", "RequestItemPatchIn"])
def test_c01_a_request_covers_a_period(model: str) -> None:
    assert _formats(model, "period_start") == {"date"}
    assert _formats(model, "period_end") == {"date"}


def test_c01_the_card_glyph_is_the_screening_registry() -> None:
    assert cast(list[str], SCHEMAS["EvidenceScreeningStatus"]["enum"]) == list(
        OBJECTS["evidence_screening"]["codes"]
    )


def test_c01_incorporate_answers_the_request_record_and_documents_a_conflict() -> None:
    op = PATHS[INCORPORATE]["post"]
    responses = cast(Json, op["responses"])
    content = cast(Json, cast(Json, responses["200"])["content"])
    schema = cast(Json, cast(Json, content["application/json"])["schema"])
    assert schema["$ref"] == "#/components/schemas/RequestItemV2Out"
    assert "409" in responses


def test_c01_incorporate_is_a_firm_persons_act() -> None:
    action = cast(str, PATHS[INCORPORATE]["post"]["x-abacus-action"])
    decisions = RULES[action].decisions
    assert decisions.get("agent") in (None, "deny")
    assert not {"client_admin", "client_contributor"} & set(decisions)
    assert {"engagement_partner", "manager", "senior", "client_service"} <= {
        r for r, d in decisions.items() if d == "allow"
    }
