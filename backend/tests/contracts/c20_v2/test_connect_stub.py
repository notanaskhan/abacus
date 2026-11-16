# ac-test-author: ayushkbhatia
"""W-01-T06 (TASK-8064; SPEC-659 AC-1 to AC-3, AC-7, AC-8, AC-17; DEC-5049): consumer tests for
N's C20 v2 Connect stub. One action per operation with 404 and 501; every field classified; the
agent and every portal principal hold none of the Connect actions; firm connect and disconnect
need fresh MFA; no route starts a client connection (R1); the catalogue content foots.
"""

from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.identity.authz import _matrix
from abacus.modules.integrations import connect_contract as cc
from abacus_tools.synthetic.scenarios.brightwater_hale import connect_catalog as cat

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
K = "/v1/integrations/{key}"
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/integrations/catalog"): "integration_catalog.read",
    ("get", K): "integration_catalog.read",
    ("get", f"{K}/events"): "integration_catalog.read",
    ("get", f"{K}/client-companies"): "integration.read_client_companies",
    ("post", f"{K}/connect"): "integration.connect_firm",
    ("post", "/v1/me/integrations/{key}/connect"): "integration.connect_personal",
    ("post", "/v1/integrations/connect/complete"): "integration.complete_connect",
    ("post", f"{K}/disconnect"): "integration.disconnect_firm",
    ("post", "/v1/me/integrations/{key}/disconnect"): "integration.disconnect_personal",
    ("post", f"{K}/interest"): "integration.interest",
    ("post", "/v1/platform/integration-catalog/imports"): "integration_catalog.import",
    ("get", "/v1/platform/integration-catalog/imports"): "integration_catalog.import",
}
PORTAL = ("client_admin", "client_contributor", "third_party", "client_service", "link_principal")


# W-01-T07, T08 implemented the catalogue, Notify me, connect, complete and disconnect; these are
# still the stub's (W-01-T15 detail, events and client companies; the operator's import routes,
# which no principal can reach: AC-32 is the ops command).
STILL_STUBBED: frozenset[tuple[str, str]] = frozenset(
    {
        ("get", K),
        ("get", f"{K}/events"),
        ("get", f"{K}/client-companies"),
        ("post", "/v1/platform/integration-catalog/imports"),
        ("get", "/v1/platform/integration-catalog/imports"),
    }
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) in STILL_STUBBED)


def test_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(cc).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == cc.__name__
    ]
    assert len(models) > 20
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_ac8_the_agent_and_every_portal_principal_hold_no_connect_action() -> None:
    for action in set(ROUTES.values()):
        cells = _matrix.ACTIONS[action]
        assert cells.get("agent", "deny") == "deny", action
        assert cells.get("system", "deny") == "deny", action
        assert all(cells.get(r, "deny") == "deny" for r in PORTAL), action


def test_ac7_firm_connect_and_disconnect_are_it_and_firm_admin_with_fresh_mfa() -> None:
    for action in ("integration.connect_firm", "integration.disconnect_firm"):
        cells = _matrix.ACTIONS[action]
        allowed = {r for r, d in cells.items() if d == "allow"}
        assert allowed == {"security_admin", "firm_admin"}, action
        assert cells.get("mfa_recent") == "required", action


def test_ac32_no_firm_principal_imports_the_catalogue() -> None:
    cells = _matrix.ACTIONS["integration_catalog.import"]
    assert not [r for r, d in cells.items() if d == "allow"]


def test_ac17_no_route_starts_a_client_connection() -> None:
    posts = [p for p, ops in PATHS.items() if p.startswith("/v1/integrations") and "post" in ops]
    assert all("client" not in p for p in posts), posts


def test_ac1_ac3_the_catalogue_content_foots() -> None:
    assert cat.status_counts(cat.E0) == {
        "all": 53,
        "connected": 9,
        "available": 38,
        "coming_soon": 6,
    }
    assert cat.status_counts(cat.E2) == {
        "all": 55,
        "connected": 9,
        "available": 40,
        "coming_soon": 6,
    }
    assert sum(cat.category_counts(cat.E0).values()) == 65
    assert sum(cat.category_counts(cat.E2).values()) == 67
    assert cat.connected_names() == [
        "CCH Axcess Tax",
        "CCH Axcess Practice",
        "QuickBooks Online",
        "NetSuite",
        "Sage Intacct",
        "Xero",
        "Box",
        "Microsoft 365",
        "DocuSign",
    ]


def test_ac5_no_tile_carries_kit_or_payment_copy() -> None:
    # DEC-89 / DF-36: no payment-collection copy anywhere (the kit's Stripe text is wrong); the
    # Stripe row itself stays and only reads payments and payouts.
    text = json.dumps(cat.document()).lower()
    for banned in ("collect payment", "accept payments", "payment link", "get paid", "lorem"):
        assert banned not in text
    stripe = next(r for r in cat.document()["items"] if r["key"] == "stripe")
    assert stripe["description"].lower().startswith("read client payments and payouts")
