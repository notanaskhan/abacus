"""Q-01-T24 / SPEC-050 AC-24 and ADR-152 (P-45): the operational routes, written from the spec.

Spec: "exactly the routes on the public-route list (P-45) answer without a token: `GET /healthz`
(process liveness, no DB) and `GET /readyz` (both app and identity DB roles ping, Temporal
reachable, scanner reachable, the platform KMS key usable); ROUTE-001 fails the build for any
route outside `AbacusRouter` not on the list. ... `/readyz` fails when a DB role, Temporal, the
scanner or the platform KMS key is unreachable." ADR-152: the allowlist is `/healthz`, `/readyz`
and (P-08, later) `GET /v1/portal/branding`; nothing else.

Public names only are taken from the code: `create_app()`, `PUBLIC_ROUTES`, `READINESS_CHECKS`
(replaced by fakes to make each dependency fail on its own) and
`abacus_tools.quality.banned_patterns`.
The app is driven in process over ASGI; no network but loopback.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Protocol, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from abacus.api import create_app
from abacus.api import public_routes as public_routes_module
from abacus.api.public_routes import PUBLIC_ROUTES, READINESS_CHECKS
from abacus_tools.quality import banned_patterns as bp

from .support import cached_app, closed_endpoint, use_environment

PUBLIC_ALLOWLIST = {"/healthz", "/readyz", "/v1/portal/branding"}  # ADR-152 and P-08
LEAKY_ERROR = "postgresql://svc_user:hunter2-fake-password@db.internal.example:5432/abacus"
Check = Callable[[], Awaitable[None]]


class _RouteContext(Protocol):
    @property
    def original_route(self) -> object: ...


class _Included(Protocol):
    def effective_route_contexts(self) -> Iterator[_RouteContext]: ...


def all_routes(app: FastAPI) -> list[APIRoute]:
    found: list[APIRoute] = []
    for item in app.routes:
        if isinstance(item, APIRoute):
            found.append(item)
        elif hasattr(item, "effective_route_contexts"):
            for context in cast(_Included, item).effective_route_contexts():
                assert isinstance(context.original_route, APIRoute)
                found.append(context.original_route)
        else:
            raise AssertionError(f"a route kind this test does not know: {item!r}")
    return found


def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def app() -> FastAPI:
    return cached_app({"ABACUS_ENVIRONMENT": "local"})


async def ok() -> None:
    return None


def failing(message: str = LEAKY_ERROR) -> Check:
    async def check() -> None:
        raise ConnectionError(message)

    return check


async def hangs() -> None:
    await asyncio.sleep(120)


def use_checks(monkeypatch: pytest.MonkeyPatch, **replace: Check) -> None:
    """All readiness checks pass, except the ones given (by position name `check_<n>`)."""
    checks = tuple(
        (name, replace.get(f"check_{index}", ok))
        for index, (name, _) in enumerate(READINESS_CHECKS)
    )
    monkeypatch.setattr(public_routes_module, "READINESS_CHECKS", checks)


# --- exactly the listed routes answer without a token -------------------------------------------


def test_ac24_the_public_route_list_is_inside_the_adr_allowlist() -> None:
    assert set(PUBLIC_ROUTES) <= PUBLIC_ALLOWLIST
    assert {"/healthz", "/readyz"} <= set(PUBLIC_ROUTES)


async def test_ac24_every_other_route_refuses_a_caller_without_a_token(app: FastAPI) -> None:
    routes = all_routes(app)
    assert len(routes) > 50  # the sweep is not vacuous
    unexpected: list[tuple[str, str, int]] = []
    async with client(app) as http:
        for route in routes:
            if route.path in PUBLIC_ROUTES:
                continue
            url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), route.path)
            for method in sorted(route.methods or ()):
                body: dict[str, str] | None = {} if method in {"POST", "PUT", "PATCH"} else None
                response = await http.request(method, url, json=body)
                if response.status_code not in {401, 403}:
                    unexpected.append((method, route.path, response.status_code))
    assert unexpected == []


async def test_ac24_the_only_routes_registered_outside_the_router_are_the_listed_ones(
    app: FastAPI,
) -> None:
    open_paths = {
        path
        for path, handler in PUBLIC_ROUTES.items()
        for route in all_routes(app)
        if route.path == path and route.endpoint is handler
    }
    assert open_paths == set(PUBLIC_ROUTES)
    # No docs UI, schema or branding route answers without a token either (P-08 adds branding
    # to the list under its own ADR).
    async with client(app) as http:
        for path in ("/docs", "/redoc", "/openapi.json", "/v1/portal/branding", "/", "/metrics"):
            assert (await http.get(path)).status_code in {401, 403, 404}, path


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_ac24_the_public_routes_answer_get_only(
    app: FastAPI, path: str, method: str
) -> None:
    async with client(app) as http:
        assert (await http.request(method, path)).status_code in {404, 405}


# --- /healthz -----------------------------------------------------------------------------------


async def test_ac24_healthz_answers_200_without_a_token(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.get("/healthz")
    assert response.status_code == 200


async def test_ac24_healthz_calls_no_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Process liveness, no DB: with every dependency broken and every readiness check set to
    explode, the process is still alive."""
    closed = closed_endpoint()
    use_environment(
        monkeypatch,
        {
            "ABACUS_ENVIRONMENT": "local",
            "ABACUS_DATABASE_URL": f"postgresql+asyncpg://app@{closed}/abacus",
            "ABACUS_IDENTITY_DATABASE_URL": f"postgresql+asyncpg://identity@{closed}/abacus",
            "ABACUS_TEMPORAL_TARGET": closed,
            "ABACUS_SCANNER_ENDPOINT": closed,
        },
    )
    use_checks(monkeypatch, **{f"check_{i}": failing() for i in range(len(READINESS_CHECKS))})
    async with client(create_app()) as http:
        started = time.monotonic()  # the request, not app start-up (slow on a CI runner)
        response = await http.get("/healthz")
        elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert elapsed < 2


# --- /readyz ------------------------------------------------------------------------------------


def test_ac24_readiness_covers_the_five_dependencies_the_spec_names() -> None:
    """Both DB roles, Temporal, the scanner and the platform KMS key."""
    assert len(READINESS_CHECKS) == 5
    assert len({name for name, _ in READINESS_CHECKS}) == 5


async def test_ac24_readyz_is_200_when_every_dependency_answers(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_checks(monkeypatch)
    async with client(app) as http:
        response = await http.get("/readyz")  # no token
    assert response.status_code == 200


@pytest.mark.parametrize("position", range(5))
async def test_ac24_readyz_fails_when_any_one_dependency_is_unreachable(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, position: int
) -> None:
    use_checks(monkeypatch, **{f"check_{position}": failing()})
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503


@pytest.mark.parametrize("position", range(5))
async def test_ac24_readyz_never_echoes_an_error_text(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, position: int
) -> None:
    use_checks(monkeypatch, **{f"check_{position}": failing()})
    async with client(app) as http:
        response = await http.get("/readyz")
    for leaked in ("hunter2", "svc_user", "db.internal.example", "postgresql://"):
        assert leaked not in response.text
        assert leaked not in str(dict(response.headers))


async def test_ac24_a_hung_dependency_cannot_hang_the_probe(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_checks(monkeypatch, check_2=hangs)
    started = time.monotonic()
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503
    assert time.monotonic() - started < 15  # a load balancer gives up long before


async def test_ac24_readyz_checks_the_dependencies_together_not_one_after_another(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow() -> None:
        await asyncio.sleep(0.8)

    use_checks(monkeypatch, **{f"check_{i}": slow for i in range(5)})
    started = time.monotonic()
    async with client(app) as http:
        response = await http.get("/readyz")
    assert response.status_code == 200
    assert time.monotonic() - started < 3  # five at 0.8 s in series would take 4 s


async def test_ac24_readyz_with_the_real_checks_fails_when_nothing_is_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = closed_endpoint()
    use_environment(
        monkeypatch,
        {
            "ABACUS_ENVIRONMENT": "local",
            "ABACUS_DATABASE_URL": f"postgresql+asyncpg://app@{closed}/abacus",
            "ABACUS_IDENTITY_DATABASE_URL": f"postgresql+asyncpg://identity@{closed}/abacus",
            "ABACUS_TEMPORAL_TARGET": closed,
            "ABACUS_SCANNER_ENDPOINT": closed,
            "ABACUS_SCANNER_TIMEOUT_SECONDS": "1",
        },
    )
    async with client(create_app()) as http:
        response = await http.get("/readyz")
    assert response.status_code == 503


# --- ROUTE-001 (the build fails for any other unauthenticated route) ----------------------------


def route_rules_fired(root: Path, relative: str, source: str) -> bool:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return any(v.rule_id == "ROUTE-001" for v in bp.scan(root))


@pytest.mark.parametrize(
    "source",
    [
        "from fastapi import APIRouter\nrouter = APIRouter()\n\n\n"
        '@router.get("/v1/leak")\nasync def leak() -> None: ...\n',
        'from fastapi import FastAPI\napp = FastAPI()\napp.add_api_route("/v1/leak", handler)\n',
        'from fastapi import FastAPI\napp = FastAPI()\n\n\n@app.get("/v1/leak")\n'
        "async def leak() -> None: ...\n",
    ],
)
def test_ac24_route001_fails_a_route_outside_the_router(tmp_path: Path, source: str) -> None:
    assert route_rules_fired(tmp_path, "src/abacus/modules/example/routes.py", source)


def test_ac24_route001_fails_an_extra_path_on_the_public_list(tmp_path: Path) -> None:
    source = 'PUBLIC_ROUTES = {"/healthz": a, "/readyz": b, "/v1/export": c}\n'
    assert route_rules_fired(tmp_path, "src/abacus/api/public_routes.py", source)


def test_ac24_route001_accepts_the_listed_public_paths(tmp_path: Path) -> None:
    source = 'PUBLIC_ROUTES = {"/healthz": a, "/readyz": b}\n'
    assert not route_rules_fired(tmp_path, "src/abacus/api/public_routes.py", source)
