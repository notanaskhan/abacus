"""C5 v1 consumer tests for T-02 (tax returns; P-06-T02): firm-provided items linked to a K-1
package, binders rolled from the prior year, the binder close rule, the BND-01 season filters and
the human-only operations T-02 drives. Schema and matrix only: the routes are stubs."""

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
BINDER_CODES = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"][
        "binder"
    ]["codes"],
)
ITEMS = "/v1/engagements/{engagement_id}/request-items/{item_id}"


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _options(prop: Json) -> list[Json]:
    return cast(list[Json], prop["anyOf"]) if "anyOf" in prop else [prop]


def _ref(model: str, field: str) -> str | None:
    refs = [o["$ref"] for o in _options(_props(model)[field]) if "$ref" in o]
    return cast(str, refs[0]).rsplit("/", 1)[1] if refs else None


def _enum(model: str, field: str) -> set[str]:
    out: set[str] = set()
    for option in _options(_props(model)[field]):
        out |= set(cast(list[str], option.get("enum", [])))
        if "const" in option:
            out.add(cast(str, option["const"]))
    return out


def _nullable(model: str, field: str) -> bool:
    return any(o.get("type") == "null" for o in _options(_props(model)[field]))


# --- Firm-provided items and the K-1 link -------------------------------------------------------


@pytest.mark.parametrize("model", ["RequestItemV2Out", "BinderRequestRowOut"])
def test_t02_a_request_is_a_client_upload_or_firm_provided(model: str) -> None:
    assert _enum(model, "kind") == {"client_upload", "firm_provided"}


def test_t02_a_new_request_defaults_to_a_client_upload() -> None:
    assert _props("RequestItemV2Out")["kind"]["default"] == "client_upload"


@pytest.mark.parametrize("model", ["LinkedRefOut", "LinkedRefIn"])
def test_t02_a_linked_ref_is_an_opaque_kind_and_id_including_a_k1_package(model: str) -> None:
    assert set(_props(model)) == {"kind", "id"}
    assert SCHEMAS[model]["additionalProperties"] is False
    assert _enum(model, "kind") == {"workpaper", "procedure_step", "k1_package"}
    assert _props(model)["id"]["format"] == "uuid"


def test_t02_the_record_reads_and_the_edit_sets_the_link() -> None:
    assert _ref("RequestItemV2Out", "linked_ref") == "LinkedRefOut"
    assert _nullable("RequestItemV2Out", "linked_ref")
    assert _ref("RequestItemPatchIn", "linked_ref") == "LinkedRefIn"
    assert _nullable("BinderRequestRowOut", "linked_count")  # "Linked (n)" or "—"


# --- Binders from the prior year and the close rule ----------------------------------------------


def test_t02_a_binder_can_start_from_the_prior_year_binder() -> None:
    assert SCHEMAS["BinderIn"]["additionalProperties"] is False
    assert set(cast(list[str], SCHEMAS["BinderIn"]["required"])) == {"work_item_id", "kind"}
    assert {o.get("format") for o in _options(_props("BinderIn")["from_binder_id"])} == {
        "uuid",
        None,
    }
    assert "prior_year_binder" in _enum("BinderOut", "created_from")
    assert _enum("BinderOut", "created_from") == {
        "blank",
        "template",
        "prior_year_binder",
        "engine_import",
    }
    assert _nullable("BinderOut", "prior_year_source_ref")


@pytest.mark.parametrize("model", ["RequestItemV2Out", "BinderRequestRowOut"])
def test_t02_a_rolled_request_carries_the_prior_year_tag(model: str) -> None:
    assert _enum(model, "source_tag") == {"prior_year"}
    assert _nullable(model, "source_tag")


def test_t02_a_closed_binder_names_its_close_rule_by_code() -> None:
    assert "closed" in cast(list[str], SCHEMAS["BinderStatus"]["enum"])
    assert BINDER_CODES["closed"]["terminal"] is True
    assert (
        _props("BinderOut")["closed_reason"]["cls"] == "internal"
    )  # a registered code, not prose
    assert _nullable("BinderOut", "closed_at") and _nullable("BinderOut", "closed_reason")


def test_t02_binder_statuses_are_the_registry_codes() -> None:
    assert cast(list[str], SCHEMAS["BinderStatus"]["enum"]) == list(BINDER_CODES)


def test_t02_a_second_binder_on_a_work_item_is_part_n() -> None:
    assert _props("BinderOut")["part"]["type"] == "integer"
    assert _props("BinderRowOut")["part"]["type"] == "integer"
    assert _props("BinderRowOut")["work_item_label"]["cls"] == "confidential"  # "2025 Form 1040"


# --- The BND-01 index T-02 filters by season ----------------------------------------------------


def test_t02_the_index_filters_by_service_season_preparer_and_activity() -> None:
    params = {
        cast(str, p["name"]): cast(Json, p["schema"])
        for p in cast(list[Json], PATHS["/v1/binders"]["get"]["parameters"])
    }
    assert {"service", "season", "office", "preparer", "status", "q", "cursor", "limit"} <= set(
        params
    )
    assert params["client_activity"]["enum"] == ["any", "none_30_days"]
    assert params["limit"]["maximum"] == 200
    page = _props("ListPage_BinderRowOut_")
    assert {"items", "next_cursor", "total", "total_capped", "counts", "facets"} <= set(page)


# --- Human-only operations T-02 drives ----------------------------------------------------------

HUMAN_ONLY = [
    ("post", "/v1/binders"),
    ("post", "/v1/binders/{binder_id}/duplicate"),
    ("post", "/v1/binders/{binder_id}/publish"),
    ("post", f"{ITEMS}/send"),
    ("post", f"{ITEMS}/delegate"),
]


@pytest.mark.parametrize(("method", "path"), HUMAN_ONLY)
def test_t02_each_human_only_operation_denies_the_agent(method: str, path: str) -> None:
    action = cast(str, PATHS[path][method]["x-abacus-action"])
    assert RULES[action].decisions.get("agent") in (None, "deny")
    # Firm people only: no client role creates, publishes, sends or delegates.
    assert not {"client_admin", "client_contributor"} & set(RULES[action].decisions)
