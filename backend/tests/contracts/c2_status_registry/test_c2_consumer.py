"""C2 v1 consumer tests (F-03-T19; F-03-T10): every status enum in the API comes from the status
registry, as the stored codes, and the UI data is generated from the same file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml

from abacus.api.export_openapi import document
from abacus.kernel import _statuses

REPO = Path(__file__).resolve().parents[4]
REGISTRY = cast(
    dict[str, dict[str, dict[str, dict[str, object]]]],
    yaml.safe_load((REPO / "docs" / "product" / "status-vocabulary.yaml").read_text())["objects"],
)
SCHEMAS = cast(dict[str, dict[str, object]], json.loads(document())["components"]["schemas"])


def _class(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("_")) + "Status"


def test_c2_each_api_status_enum_is_its_objects_stored_codes() -> None:
    found = {_class(o): o for o in REGISTRY}
    in_api = [name for name in SCHEMAS if name in found]
    assert {"EngagementStatus", "RequestStatus"} <= set(in_api)
    for name in in_api:
        codes = REGISTRY[found[name]]["codes"]
        stored = [c for c, f in codes.items() if not f["derived"]]
        assert SCHEMAS[name]["enum"] == stored


def test_c2_derived_codes_are_never_stored_and_match_is_never_a_status() -> None:
    assert "overdue" not in _statuses.STORED["request"]
    variants = {f["variant"] for o in REGISTRY.values() for f in o["codes"].values()}
    assert "match" not in variants


def test_c2_the_ui_data_is_generated_from_the_registry() -> None:
    generated = (REPO / "packages" / "ui" / "src" / "status.gen.ts").read_text()
    assert generated.startswith("// GENERATED from docs/product/status-vocabulary.yaml")
    assert '"uploaded"' in generated and '"Uploaded \u2013 needs review"' in generated
