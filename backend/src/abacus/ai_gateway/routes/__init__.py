"""Model routes (SPEC-010; ADR-073). PROTECTED.

The same model family through two routes: `direct` (the provider's API) and `bedrock` (Amazon
Bedrock inside our AWS trust boundary); `fake` serves synthetic environments. Provider SDKs are
imported only in this package (ADR-019, AC-8). Each route's provider is built lazily from settings.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final, Literal

from abacus.ai_gateway.providers import (
    ConversingProvider,
    ModelProvider,
    Tier,
    conversing,
    provider,
)
from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, Route, settings

PARITY_DAYS: Final = 90
_providers: dict[Route, ModelProvider] = {}


def model_id(tier: Tier, route: Route) -> str | None:
    """The tier's model on `route`, or None when the route can't serve it."""
    return settings().model_catalog[tier].ids.get(route)


def route_provider(route: Route) -> ModelProvider:
    if route == "fake":
        return provider()  # the configured FakeModel (synthetic environments only)
    found = _providers.get(route)
    if found is None:
        if route == "direct":
            from abacus.ai_gateway.routes.direct import AnthropicDirect

            found = AnthropicDirect()
        else:
            from abacus.ai_gateway.routes.bedrock import AnthropicOnBedrock

            found = AnthropicOnBedrock()
        _providers[route] = found
    return found


def route_converser(route: Route) -> ConversingProvider:
    """P-10-T12: the route's `converse()`. Eligibility for a loop spec is parity's question
    (`routes/parity.py`); this only refuses a provider without seam v2."""
    return conversing(route_provider(route))


def configure_route(route: Route, provider_: ModelProvider | None) -> None:
    """Tests and tools: replace (or with None, reset) a real route's provider."""
    if provider_ is None:
        _providers.pop(route, None)
    else:
        _providers[route] = provider_


def route_enabled(route: Route) -> bool:
    """Listed in `model_routes`, and (real routes) a parity report passed within 90 days (Q2)."""
    s = settings()
    if route not in s.model_routes:
        return False
    if route == "fake":
        # Synthetic environments only (D1): elsewhere the fake route is never used.
        return s.environment in SYNTHETIC_ENVIRONMENTS
    parity = s.route_parity.get(route)
    if parity is None:
        return False
    return system_now().date() - parity.checked_on <= timedelta(days=PARITY_DAYS)


SpecShape = Literal["single", "loop"]


def route_enabled_for(route: Route, shape: SpecShape) -> bool:
    """P-10-T13 (ADR-234 §7): a loop-shaped spec (multi-turn tool use) needs a route whose
    parity report, under 90 days old, also passed tools and documents. The fake route serves
    loops in synthetic environments (its trajectories are the conformance fixtures)."""
    if not route_enabled(route):
        return False
    if shape == "single" or route == "fake":
        return True
    parity = settings().route_parity.get(route)
    return parity is not None and parity.tool_parity


def loop_routes(routes: tuple[Route, ...]) -> tuple[Route, ...]:
    """The routes, in order, a loop spec may use; empty means the spec is refused."""
    return tuple(r for r in routes if route_enabled_for(r, "loop"))
