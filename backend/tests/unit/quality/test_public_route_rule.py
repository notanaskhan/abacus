"""ADR-152 (P-45; Q-01-T16): ROUTE-001 holds the public-route list to the protected exception list,
and keeps `app.py` from registering a path of its own."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

PUBLIC_ROUTES_FILE = "src/abacus/api/public_routes.py"
APP_FILE = "src/abacus/api/app.py"


def _flags(root: Path, rel: str, source: str) -> bool:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return any(v.rule_id == "ROUTE-001" and v.path == rel for v in bp.scan(root))


@pytest.mark.parametrize(
    "source",
    [
        'PUBLIC_ROUTES = {"/healthz": a, "/readyz": b}\n',
        'PUBLIC_ROUTES: Final[Mapping[str, Handler]] = {"/healthz": a}\n',
    ],
)
def test_adr152_listed_public_paths_are_allowed(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, PUBLIC_ROUTES_FILE, source)


@pytest.mark.parametrize(
    "source",
    [
        'PUBLIC_ROUTES = {"/healthz": a, "/v1/anything": b}\n',
        'PUBLIC_ROUTES = {"/healthz/": a}\n',
        "PUBLIC_ROUTES = build()\n",
        "PUBLIC_ROUTES = {path: a}\n",
        "x = 1\n",
    ],
)
def test_adr152_a_public_path_off_the_exception_list_is_flagged(
    tmp_path: Path, source: str
) -> None:
    assert _flags(tmp_path, PUBLIC_ROUTES_FILE, source)


@pytest.mark.parametrize(
    "source",
    [
        'app.add_api_route("/v1/anything", handler)\n',
        'app.get("/v1/anything")\n',
        'app.mount("/files", files)\n',
    ],
)
def test_adr152_a_path_registered_in_app_py_is_flagged(tmp_path: Path, source: str) -> None:
    assert _flags(tmp_path, APP_FILE, source)


@pytest.mark.parametrize(
    "source",
    [
        "app.add_api_route(path, handler, methods=['GET'])\n",
        "app.include_router(router)\n",
        "app.add_middleware(TrustedHosts, allowed=hosts)\n",
        'route = request.scope.get("route")\n',
    ],
)
def test_adr152_app_py_may_build_the_app(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, APP_FILE, source)


def test_adr152_the_real_public_list_is_on_the_exception_list() -> None:
    from abacus.api.public_routes import PUBLIC_ROUTES

    assert set(PUBLIC_ROUTES) <= bp.PUBLIC_ROUTE_EXCEPTIONS
