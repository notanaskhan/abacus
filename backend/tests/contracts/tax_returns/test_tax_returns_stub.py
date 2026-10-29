"""T-02-T01 (TASK-2116; SPEC-502 AC-4): the tax-returns v1 stub on the wire
(`docs/contracts/tax-returns.md`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.tax import returns_contract as contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
ROOT = Path(__file__).resolve().parents[4]
ROUTES = [
    ("get", "/v1/tax-returns", "tax_return.read_metadata"),
    ("get", "/v1/tax-returns/summary", "tax_return.read_metadata"),
    ("post", "/v1/tax-returns:bulk-assign", "tax_return.assign"),
    ("get", "/v1/tax-returns/{return_id}", "tax_return.read_metadata"),
    ("get", "/v1/tax-returns/{return_id}/overview", "tax_return.read"),
    ("get", "/v1/tax-returns/{return_id}/intake", "tax_return.read"),
    ("post", "/v1/tax-returns/{return_id}/assignments", "tax_return.assign"),
    ("post", "/v1/tax-returns/{return_id}/transitions", "tax_return.status_change"),
]


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_ac4_every_route_declares_its_action_and_is_a_stub(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert "501" in cast(Json, op["responses"])


def test_ac4_t02_declares_no_final_approval_route() -> None:
    finals = [p for p in PATHS if p.endswith("/final-approval")]
    for path in finals:
        for op in PATHS[path].values():
            assert op.get("x-abacus-action") in {
                "tax_return.read",
                "tax_return.approve",
            }
    assert "final" not in json.dumps([r[1] for r in ROUTES])


def test_ac4_fields_are_classified_and_engine_figures_are_tri() -> None:
    models = [
        v
        for v in vars(contract).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
    ]
    for model in models:
        assert unclassified_fields(model) == [], model.__name__
    amount = contract.EngineSummaryLineOut.model_json_schema()["properties"]["amount"]
    assert amount.get("x-tri") is True


def test_ac4_the_contract_doc_exists() -> None:
    assert (ROOT / "docs/contracts/tax-returns.md").is_file()
