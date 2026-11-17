"""G-04-T03 (SPEC-680; SPEC-681 AC-15; DEC-5203): the console, plan & usage and support stubs.

Every route declares exactly one matrix action and a 501; console routes declare a staff action
and authenticate with the staff token, firm routes a firm action and the firm context; no
console route approves, grants or opens a support session; the Brightwater figures tie.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.routing import APIRoute

from abacus.modules.identity.api import current_context, current_staff
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.routing import declared_action, staff_action
from abacus.modules.platform import g04_fixtures as fx
from abacus.modules.platform.console_contract import router as console_router
from abacus.modules.platform.plan_usage_contract import router as plan_router
from abacus.modules.platform.support_contract import router as support_router

FIRM_ROUTES = [r for r in (*plan_router.routes, *support_router.routes) if isinstance(r, APIRoute)]
STAFF_ROUTES = [r for r in console_router.routes if isinstance(r, APIRoute)]


def _deps(route: APIRoute) -> set[object]:
    return {d.call for d in route.dependant.dependencies}


# G-04-T09 to T11 built the rest (DEC-5416 to DEC-5418): only these still answer 501, their writers
# being ops-only (provisioning, incidents, publications; DEC-5416, DEC-5417).
STILL_STUBBED = {
    ("POST", "/v1/platform/tenants"),
    ("POST", "/v1/platform/tenants/{tenant_code}/sandbox"),
    ("GET", "/v1/platform/provisioning/{workflow_id}"),
    ("GET", "/v1/platform/status/incidents"),
    ("POST", "/v1/platform/status/incidents"),
    ("POST", "/v1/platform/status/incidents/{incident_id}/updates"),
    ("POST", "/v1/platform/status/incidents/{incident_id}/resolve"),
    ("GET", "/v1/platform/publications"),
    ("POST", "/v1/platform/publications/{kind}/{publication_id}/publish"),
    ("POST", "/v1/platform/publications/{kind}/{publication_id}/withdraw"),
}


@pytest.mark.parametrize(
    "route", FIRM_ROUTES + STAFF_ROUTES, ids=lambda r: f"{r.methods} {r.path}"
)
def test_one_action_and_a_501_only_while_stubbed(route: APIRoute) -> None:
    action = declared_action(route)
    assert action is not None and action in RULES
    stubbed = any((m, route.path) in STILL_STUBBED for m in route.methods or ())
    assert (501 in route.responses) == stubbed


@pytest.mark.parametrize("route", STAFF_ROUTES, ids=lambda r: f"{r.methods} {r.path}")
def test_console_routes_are_staff_only(route: APIRoute) -> None:
    action = declared_action(route)
    assert action is not None and staff_action(action)
    deps = _deps(route)
    assert current_staff in deps and current_context not in deps
    assert route.path.startswith("/v1/platform/")


@pytest.mark.parametrize("route", FIRM_ROUTES, ids=lambda r: f"{r.methods} {r.path}")
def test_firm_routes_are_firm_scoped(route: APIRoute) -> None:
    action = declared_action(route)
    assert action is not None and not staff_action(action)
    assert current_context in _deps(route)


def test_ac15_no_console_route_decides_a_support_session() -> None:
    for route in STAFF_ROUTES:
        assert not any(w in route.path for w in ("approve", "grant", "activate", "view-as"))
        assert "support-sessions/" not in route.path  # the console only lists sessions


def test_fixture_figures_tie_to_the_handoff() -> None:
    assert fx.tiles() == {
        "tenants": 6,
        "healthy": 4,
        "degraded": 1,
        "onboarding": 1,
        "seats_used": 404,
        "seats_provisioned": 490,
    }
    assert fx.seats_footer() == (
        "Seats used 46 + 128 + 212 + 18 + 0 = 404 of 490 provisioned (sandbox excluded)."
    )
    assert fx.used_oct_1() == 14_920
    assert fx.percent(fx.used_oct_1(), fx.INCLUDED_MINUTES) == Decimal("74.6")
    assert fx.next_alert(fx.used_oct_1()) == (75, 80)
    assert fx.percent(fx.USED_OCT_9, fx.INCLUDED_MINUTES) == Decimal("91.2")
    assert fx.INCLUDED_MINUTES - fx.USED_OCT_9 == 1_760
    assert fx.percent(fx.USED_OCT_14, fx.INCLUDED_MINUTES) == Decimal("104.3")
    assert fx.over_included(fx.USED_OCT_14) == 860
    assert fx.engagement_pct() == 83
    assert fx.rate_band_people() == fx.SEATS_TOTAL == 46
