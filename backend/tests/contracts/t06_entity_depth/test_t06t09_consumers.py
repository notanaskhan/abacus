"""Consumer tests for the T-06-T07 and T-06-T08 stubs (T-06-T09; SPEC-702; DEC-5518): every golden
figure the T07 row names foots on the typed fixtures, every model field carries a classification
tag (a missing tag fails), every return figure is TRI, and every operation keeps its action and
its 501. The relationships graph omits a walled client with no count. The fixture half is
`apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts`."""

from __future__ import annotations

import inspect
import json
from decimal import Decimal
from typing import cast

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import tri_paths, unclassified_fields
from abacus.modules.organisations import relationships_contract as rel
from abacus.modules.tax import entity_depth_contract as depth
from abacus_tools.synthetic.scenarios.brightwater_hale import entity_depth_slice as ridgeline
from abacus_tools.synthetic.scenarios.brightwater_hale import relationships_slice as graphs

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
D = Decimal


def _models(module: object) -> list[type[BaseModel]]:
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == getattr(module, "__name__", "")
    ]


def test_733_500_is_169_500_plus_360_000_plus_204_000() -> None:
    props = ridgeline.properties()
    assert [p.depreciation for p in props] == [D("169500"), D("360000"), D("204000")]
    assert sum((p.depreciation for p in props), D("0")) == D("733500")
    assert sum((p.land for p in props), D("0")) == D("3600000")


def test_apportionment_46_0_plus_31_5_plus_22_5_is_100_and_ptet_64_096() -> None:
    states = ridgeline.states()
    assert sum((s.apportionment_pct for s in states.states), D("0")) == D("100.0")
    assert sum((s.ptet_paid or D("0") for s in states.states), D("0")) == D("64096")
    numerators = ridgeline.APPORTIONMENT_NUMERATORS
    assert sum(numerators.values(), D("0")) == ridgeline.SCHEDULE_K_LINE_2
    for s in states.states:  # each percentage is its numerator's share, to one decimal
        share = numerators[s.state] / ridgeline.SCHEDULE_K_LINE_2 * 100
        assert abs(share - s.apportionment_pct) < D("0.05")


def test_sum_of_k1_box_2_is_1_231_600() -> None:
    k1 = ridgeline.k1_previews()
    assert k1.box_2_total == k1.schedule_k_line_2 == D("1231600") and k1.tally == "tie"


def test_basis_outside_17_943_095_with_pell_street_ii_off_28_595() -> None:
    rows = ridgeline.partner_basis()
    assert sum((r.outside for r in rows), D("0")) == D("17943095")
    off = [r for r in rows if r.tally == "off"]
    assert [(r.name, r.outside - r.inside) for r in off] == [("Pell Street II LLC", D("28595"))]


@pytest.mark.parametrize("model", [*_models(depth), *_models(rel)], ids=lambda m: m.__name__)
def test_every_field_carries_a_classification_tag(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize(
    "model",
    [depth.TaxDepthFixedAssetsOut, depth.TaxDepthStatesOut, depth.TaxDepthK1PreviewsOut,
     depth.TaxDepthBasisOut, depth.TaxDepthProvisionOut, depth.TaxDepthAaaOut],
    ids=lambda m: m.__name__,
)  # fmt: skip
def test_return_figures_are_tri(model: type[BaseModel]) -> None:
    assert tri_paths(model)


def test_the_graph_omits_a_walled_client_with_no_count() -> None:
    seen = graphs.ridgeline_graph()
    walled = graphs.ridgeline_graph(walled=True)
    labels = {n.label for n in walled.nodes}
    assert not any(graphs.FELD_HOUSEHOLD in label for label in labels)
    assert len(walled.nodes) == len(seen.nodes) - 1
    assert not any(graphs.FELD_HOUSEHOLD in e.label for e in walled.edges)
    assert "hidden" not in json.dumps(walled.model_dump(mode="json")).lower()
    ownership = [e.percent for e in seen.edges if e.percent is not None]
    assert sum(ownership, D("0")) == D("100")


def test_tpl14_shapes_fit_the_models() -> None:
    assert graphs.ridgeline_graph(released=True).banner is not None
    assert graphs.calloway_graph().nodes[-1].external
    assert graphs.single_entity_graph("Bluestem Analytics, LLC").edges == []


def _operations() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for router in (depth.entity_depth_router, rel.relationships_router):
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            extra = cast(dict[str, object], route.openapi_extra or {})
            for method in sorted(route.methods or set()):
                found.append((method.lower(), route.path, str(extra["x-abacus-action"])))
    return found


# S52 (T-06-T33 to T-06-T36; DEC-5833 to DEC-5836): fixed assets, M-3/M-1, basis and states are
# live, so their operations answer without the stub's 501; every other operation is still a stub.
LIVE_PREFIXES = (
    "/v1/tax-returns/{return_id}/fixed-asset",
    "/v1/tax-returns/{return_id}/schedules/m3",
    "/v1/tax-returns/{return_id}/schedules/m1",
    "/v1/tax-returns/{return_id}/basis",
    "/v1/tax-returns/{return_id}/states",
    # T-06-T35: the §754 card's raise and its send to the client.
    "/v1/tax-returns/{return_id}/decision-cards",
    "/v1/decision-cards/{card_id}/send-to-client",
    # S53 T-06-T42 (DEC-5913): the other entities' workpapers (AAA, the provision, functional
    # expenses and their allocation runs, K-1 previews).
    "/v1/tax-returns/{return_id}/schedules/aaa",
    "/v1/tax-returns/{return_id}/provision",
    "/v1/tax-returns/{return_id}/functional-expenses",
    "/v1/tax-returns/{return_id}/k1-previews",
    # S53 T-06-T43/T44 (DEC-5914, DEC-5915): the form faces, their fields, traces and diagnostics.
    "/v1/tax-returns/{return_id}/form-pages",
    "/v1/tax-returns/{return_id}/fields/",
    "/v1/tax-returns/{return_id}/diagnostics",
)


@pytest.mark.parametrize(("method", "path", "action"), _operations())
def test_every_operation_is_declared_with_its_action_and_its_status(
    method: str, path: str, action: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    live = path.startswith(LIVE_PREFIXES)
    assert ("501" in cast(Json, operation["responses"])) is not live, path
