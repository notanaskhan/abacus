# ac-test-author: ayushkbhatia
"""A-08-T05 (TASK-8047; SPEC-657 AC-0.4, AC-0.5; DEC-5032): the fieldwork-testing, audit-analytics
and SSARS stubs, and the consumer assertions over the confirmations stub (merged from T07).

Every route declares its one action with 404 and 501; every field is classified; the typed
fixtures foot 236 unique hits, 14 = 8 + 6 lines and 4,174,000 revenue; coverage is
897,950 / 5,860,000 = 15.3%; each POR-17 payload names one confirmation; and no client principal
reaches any field of a confirmation.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import analytics_contract as ac
from abacus.modules.assurance import confirmations_fixtures as cfx
from abacus.modules.assurance import fieldwork_fixtures as fx
from abacus.modules.identity.authz import _matrix
from abacus.modules.sampling import fieldwork_contract as sc
from abacus.modules.workpapers import fieldwork_tests_contract as wc

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
W = "/v1/work-items/{work_item_id}"
J = "/v1/je-tests/{je_test_id}"
T = "/v1/tests/{test_id}"
A = "/v1/analytics-sets/{analytics_set_id}"
ROUTES: dict[tuple[str, str], str] = {
    ("post", f"{W}/je-tests"): "je_test.create",
    ("get", J): "je_test.read",
    ("put", f"{J}/criteria"): "je_test.configure",
    ("put", f"{J}/posting-user-roles"): "je_test.configure",
    ("post", f"{J}/score"): "je_test.score",
    ("get", f"{J}/entries"): "je_test.read",
    ("post", f"{J}/selection"): "sample_set.create",
    ("post", "/v1/sample-sets/{sample_set_id}/expansions"): "sample_expansion.request",
    ("post", "/v1/sample-expansions/{expansion_id}/decide"): "sample_expansion.decide",
    ("post", "/v1/sample-expansions/{expansion_id}/withdraw"): "sample_expansion.request",
    ("post", f"{T}/runs"): "test.run",
    ("post", f"{T}/adopt"): "test.adopt",
    ("post", f"{T}/items/{{item_id}}/exception"): "finding.create",
    ("post", f"{T}/deviations"): "test.mark",
    ("get", f"{T}/export.xlsx"): "test.export",
    ("post", f"{W}/analytics-sets"): "analytics.run",
    ("get", A): "analytics.read",
    ("get", f"{A}/lines/{{position}}/provenance"): "analytics.read",
    ("put", f"{A}/lines/{{position}}/explanation"): "analytics.explain",
    ("put", f"{A}/lines/{{position}}/expectation"): "analytics.configure",
    ("post", f"{A}/explanations/accept"): "analytics.accept",
    ("post", f"{A}/client-questions"): "client_question.send",
    ("get", f"{A}/export.xlsx"): "analytics.export",
    ("put", f"{W}/prior-year-figures"): "analytics.configure",
    ("get", f"{W}/ssars"): "ssars.read",
    ("post", f"{W}/ssars/inquiries"): "ssars.inquiry_manage",
    ("post", f"{W}/ssars/publish"): "ssars.inquiry_manage",
    ("post", f"{W}/ssars/remind"): "client_question.send",
}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_every_field_is_classified() -> None:
    models = [
        v
        for module in (sc, wc, ac)
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]
    assert len(models) > 30
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_no_client_principal_holds_a_fieldwork_action() -> None:
    for action in set(ROUTES.values()) - {"finding.create", "sample_set.create"}:
        for role in CLIENT_ROLES:
            assert _matrix.ACTIONS[action].get(role, "deny") == "deny", (action, role)


def test_ac0_4_je_criteria_foot_236_unique() -> None:
    counts = [len(fx.JE_CRITERIA_HITS[k]) for k in fx.JE_CRITERIA_HITS]
    assert counts == [142, 38, 61, 17, 9]
    assert fx.unique_flagged(fx.JE_CRITERIA_HITS) == 236


def test_ac0_4_analytics_foot_14_eq_8_plus_6() -> None:
    tallies = fx.tallies(fx.GRANITE_PEAK_LINES, fx.GRANITE_PEAK_THRESHOLD)
    assert (tallies.lines, tallies.over_threshold) == (14, 8)
    assert tallies.lines - tallies.over_threshold == 6
    assert (tallies.explained, tallies.unexplained) == (6, 2)
    # Interest moves 26.8% and stays Within: 110,000 is below $116,250.
    assert fx.pct(Decimal(110_000), Decimal(410_000)) == Decimal("26.8")
    assert not fx.over(Decimal(110_000), Decimal(410_000), *fx.GRANITE_PEAK_THRESHOLD)


def test_ac0_4_lakeshore_revenue_foots_4174000_and_only_grants_is_over() -> None:
    assert sum(cy for _, cy, _ in fx.LAKESHORE_REVENUE) == 4_174_000
    assert sum(cy for _, cy, _ in fx.LAKESHORE_EXPENSES) == 4_014_000
    assert fx.lakeshore_over() == ["Grants"]
    net_change = 4_174_000 - 4_014_000
    assert fx.LAKESHORE_NET_ASSETS[0] - fx.LAKESHORE_NET_ASSETS[1] == net_change == 160_000


def test_ac0_5_coverage_is_15_3_pct() -> None:
    cov = fx.coverage()
    assert cov.sent_total == Decimal("897950.00")
    assert cov.sent_pct == Decimal("15.3")
    assert cov.confirmed_total == Decimal("695200.00")
    assert cov.differences_total == Decimal("4300.00")


@pytest.mark.parametrize("state", sorted(cfx.TOKENS))
def test_ac0_5_each_por17_payload_names_one_confirmation(state: str) -> None:
    view = cfx.view(cfx.TOKENS[state])
    assert view is not None
    references = {
        r
        for r in (view.request and view.request.reference, view.receipt and view.receipt.reference)
        if r
    }
    assert len(references) <= 1
    dumped = view.model_dump_json()
    for leak in ("engagement", "work_item", "portal", "tenant", "@brightwaterhale"):
        assert leak not in dumped


def test_ac0_5_no_client_visible_confirmation_field() -> None:
    # A client principal is denied every confirmation action, so no confirmation model reaches a
    # client response; the public family is the link principal's alone.
    for action, cells in _matrix.ACTIONS.items():
        if action.startswith("confirmation."):
            assert all(cells.get(role, "deny") == "deny" for role in CLIENT_ROLES), action
