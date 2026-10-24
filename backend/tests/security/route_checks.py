"""The checks behind the generated `test_route_introspection.py` (Q-02-T15; ADR-012, ADR-027,
ADR-152). Each returns the problems it found, so a passing case is an empty list and a failing
one says what is wrong with which route.

- `route_problems`: a route `AbacusRouter` built declares exactly one action, the action is in
  the permission matrix or is a route marker (SELF, STAFF, OWN, IDENTITY, PRE_SESSION), it has a
  response model (or answers 204), and it carries exactly the authentication that action needs.
  A pre-session route (ADR-165) must also be on the protected exception list.
- `public_problems`: every route answering without a token is on the public-route list
  (`PUBLIC_ROUTES`) and on the protected exception list (`PUBLIC_ROUTE_EXCEPTIONS`, ROUTE-001),
  GET only and out of the OpenAPI document; and every listed path is served.
- `openapi_problems`: a second source. Every operation in the OpenAPI document names an action
  and is one of the generated routes, so a route the flattening missed still fails.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import cache
from typing import cast

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import BaseRoute

from abacus.api import create_app
from abacus.api.public_routes import PUBLIC_ROUTES
from abacus.modules.identity.api import (
    ACTION_KEY,
    IDENTITY,
    OWN,
    PORTAL_PUBLIC,
    PRE_SESSION,
    RULES,
    SELF,
    STAFF,
    AbacusRoute,
    current_context,
    current_member,
    current_signed_in,
    current_staff,
)
from abacus.modules.identity.routing import current_invitee, portal_public, pre_session
from abacus_tools.quality.banned_patterns import PUBLIC_ROUTE_EXCEPTIONS

# The authentication each route marker needs; every matrix action needs `current_context`.
MARKER_AUTH: dict[str, Callable[..., object]] = {
    SELF: current_signed_in,
    STAFF: current_staff,
    OWN: current_member,
    # P-08-T18 (DEC-275): the hosted identity, or a portal session's person before any grant;
    # sign-up and the staff acceptance also take `current_identity` alone at the route.
    IDENTITY: current_invitee,
    PRE_SESSION: pre_session,
    PORTAL_PUBLIC: portal_public,
}
AUTHENTICATION: frozenset[Callable[..., object]] = frozenset(
    {current_context, *MARKER_AUTH.values()}
)
NO_CONTENT = 204


@cache
def app() -> FastAPI:
    """The app as production builds it, once per test session."""
    return create_app()


def find(application: FastAPI, method: str, path: str) -> BaseRoute | None:
    for context in iter_route_contexts(application.routes):
        route = context.original_route
        methods = cast("set[str] | None", getattr(route, "methods", None)) or set()
        if context.path == path and method in methods:
            return route
    return None


def _authentication(route: APIRoute) -> list[Callable[..., object]]:
    found = [cast("Callable[..., object] | None", d.dependency) for d in route.dependencies]
    return [d for d in found if d is not None and d in AUTHENTICATION]


def route_problems(application: FastAPI, method: str, path: str, action: str) -> list[str]:
    route = find(application, method, path)
    if route is None:
        return [f"{method} {path} is not served"]
    if not isinstance(route, AbacusRoute):
        return [f"{method} {path} is not built by AbacusRouter: nothing checks an action"]
    problems: list[str] = []
    declared = (route.openapi_extra or {}).get(ACTION_KEY)
    if not isinstance(declared, str) or not declared:
        problems.append(f"{method} {path} declares no action")
    elif declared not in RULES and declared not in MARKER_AUTH:
        problems.append(f"{method} {path}: {declared!r} is not a matrix action or route marker")
    if isinstance(declared, str) and declared != action:
        problems.append(f"{method} {path} declares {declared!r}, generated as {action!r}")
    if route.response_model is None and route.status_code != NO_CONTENT:
        problems.append(f"{method} {path} has no response model")
    if declared in (PRE_SESSION, PORTAL_PUBLIC) and path not in PUBLIC_ROUTE_EXCEPTIONS:
        problems.append(f"{method} {path} is public but not on the ROUTE-001 exception list")
    want = MARKER_AUTH.get(declared, current_context) if isinstance(declared, str) else None
    auth = _authentication(route)
    if want is None or auth != [want]:
        names = [getattr(a, "__name__", "?") for a in auth]
        problems.append(f"{method} {path} is authenticated by {names}, not by its action's")
    return problems


def public_problems(application: FastAPI, unauthenticated: Iterable[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    served_paths: set[str] = set()
    for method, path in unauthenticated:
        served_paths.add(path)
        if path not in PUBLIC_ROUTES or path not in PUBLIC_ROUTE_EXCEPTIONS:
            problems.append(f"{method} {path} answers without a token and is not on the P-45 list")
            continue
        if method != "GET":
            problems.append(f"{method} {path}: a public route answers GET only")
        route = find(application, method, path)
        if isinstance(route, APIRoute) and route.include_in_schema:
            problems.append(f"{method} {path}: a public route stays out of the OpenAPI document")
    missing = sorted(set(PUBLIC_ROUTES) - served_paths)
    return problems + [f"{path} is on the public-route list but not served" for path in missing]


def openapi_problems(application: FastAPI, routes: Iterable[tuple[str, str, str]]) -> list[str]:
    generated = {(method, path): action for method, path, action in routes}
    document = cast("dict[str, dict[str, dict[str, object]]]", application.openapi()["paths"])
    problems: list[str] = []
    for path, operations in document.items():
        for verb, operation in operations.items():
            method = verb.upper()
            if (method, path) not in generated:
                problems.append(f"{method} {path} is documented but not a generated route")
            elif operation.get(ACTION_KEY) != generated[(method, path)]:
                problems.append(f"{method} {path} documents {operation.get(ACTION_KEY)!r}")
    return problems
