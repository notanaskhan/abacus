"""AC-1: the local sign-in server (TASK-012 interface contract, "Local sign-in").

The app is driven over `httpx.ASGITransport`; the signing key lives in a temporary `KEY_FILE`.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from abacus.modules.identity.api import InvalidToken, JwtVerifier
from abacus_tools.fakes import oidc_server
from abacus_tools.fakes.identity import AUDIENCE, ISSUER

REDIRECT = "http://localhost:5173/signin/callback"
VERIFIER = "v" * 64


def _challenge(verifier: str = VERIFIER) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _authorize_params(**overrides: str) -> dict[str, str]:
    params = {
        "response_type": "code",
        "client_id": "abacus-web",
        "redirect_uri": REDIRECT,
        "code_challenge_method": "S256",
        "code_challenge": _challenge(),
        "state": "state-1",
    }
    params.update(overrides)
    return params


@pytest.fixture(autouse=True)
def key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "keys" / "oidc-key.pem"
    monkeypatch.setattr(oidc_server, "KEY_FILE", path)
    return path


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=oidc_server.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://idp.test") as http:
        yield http


async def _code(
    client: httpx.AsyncClient, subject: str = "dev-leader", redirect: str = REDIRECT
) -> str:
    response = await client.post(
        "/authorize",
        data={
            "redirect_uri": redirect,
            "state": "state-1",
            "code_challenge": _challenge(),
            "subject": subject,
        },
    )
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["code"][0]


def _exchange(code: str, **overrides: str) -> dict[str, str]:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": "abacus-web",
        "code_verifier": VERIFIER,
    }
    form.update(overrides)
    return form


def test_ac1_refuses_environments_other_than_local_and_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oidc_server, "settings", lambda: SimpleNamespace(environment="production"))
    with pytest.raises(RuntimeError):
        oidc_server.create_app()


def test_ac1_runs_in_the_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oidc_server, "settings", lambda: SimpleNamespace(environment="test"))
    assert oidc_server.create_app() is not None


async def test_ac1_discovery_names_the_endpoints(client: httpx.AsyncClient) -> None:
    body = (await client.get("/.well-known/openid-configuration")).json()
    assert body["issuer"] == ISSUER
    assert body["authorization_endpoint"].endswith("/authorize")
    assert body["token_endpoint"].endswith("/token")
    assert body["jwks_uri"].endswith("/jwks")
    assert body["code_challenge_methods_supported"] == ["S256"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"response_type": "token"},
        {"client_id": "someone-else"},
        {"redirect_uri": "http://evil.test/signin/callback"},
        {"code_challenge_method": "plain"},
        {"code_challenge": ""},
        {"state": ""},
    ],
)
async def test_ac1_authorize_rejects_invalid_requests(
    client: httpx.AsyncClient, overrides: dict[str, str]
) -> None:
    response = await client.get("/authorize", params=_authorize_params(**overrides))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


@pytest.mark.parametrize("missing", ["response_type", "client_id", "redirect_uri", "state"])
async def test_ac1_authorize_rejects_missing_parameters(
    client: httpx.AsyncClient, missing: str
) -> None:
    params = _authorize_params()
    del params[missing]
    assert (await client.get("/authorize", params=params)).status_code == 400


async def test_ac1_authorize_lists_the_dev_users(client: httpx.AsyncClient) -> None:
    response = await client.get("/authorize", params=_authorize_params())
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for subject, _label in oidc_server.DEV_USERS:
        assert f'value="{subject}"' in response.text


async def test_ac1_authorize_escapes_every_value(client: httpx.AsyncClient) -> None:
    hostile = '"><script>alert(1)</script>'
    response = await client.get("/authorize", params=_authorize_params(state=hostile))
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


async def test_ac1_approve_redirects_with_code_and_state(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/authorize",
        data={
            "redirect_uri": REDIRECT,
            "state": "abc 123",
            "code_challenge": _challenge(),
            "subject": "dev-staff",
        },
    )
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    query = parse_qs(location.query)
    assert query["state"] == ["abc 123"]
    assert query["code"][0]


@pytest.mark.parametrize(
    ("subject", "redirect"),
    [("nobody", REDIRECT), ("dev-leader", "http://evil.test/signin/callback")],
)
async def test_ac1_approve_rejects_unknown_subject_or_redirect(
    client: httpx.AsyncClient, subject: str, redirect: str
) -> None:
    response = await client.post(
        "/authorize",
        data={
            "redirect_uri": redirect,
            "state": "s",
            "code_challenge": _challenge(),
            "subject": subject,
        },
    )
    assert response.status_code == 400


async def test_ac1_token_exchange_issues_a_verifiable_bearer_token(
    client: httpx.AsyncClient,
) -> None:
    code = await _code(client, "dev-leader")
    response = await client.post("/token", data=_exchange(code))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    issued = body.pop("access_token")
    assert body == {"token_type": "Bearer", "expires_in": 600}
    jwks = (await client.get("/jwks")).text
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks)
    assert verifier.verify(issued).subject == "dev-leader"


async def test_ac1_token_is_for_the_chosen_subject(client: httpx.AsyncClient) -> None:
    code = await _code(client, "dev-staff")
    body = (await client.post("/token", data=_exchange(code))).json()
    jwks = (await client.get("/jwks")).text
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks)
    assert verifier.verify(body["access_token"]).subject == "dev-staff"


async def test_ac1_code_is_single_use(client: httpx.AsyncClient) -> None:
    code = await _code(client)
    assert (await client.post("/token", data=_exchange(code))).status_code == 200
    replay = await client.post("/token", data=_exchange(code))
    assert replay.status_code == 400
    assert replay.json() == {"error": "invalid_grant"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"code_verifier": "w" * 64},
        {"redirect_uri": "http://127.0.0.1:5173/signin/callback"},
        {"client_id": "someone-else"},
        {"grant_type": "password"},
    ],
)
async def test_ac1_failed_exchange_is_invalid_grant_and_burns_the_code(
    client: httpx.AsyncClient, overrides: dict[str, str]
) -> None:
    code = await _code(client)
    failed = await client.post("/token", data=_exchange(code, **overrides))
    assert failed.status_code == 400
    assert failed.json() == {"error": "invalid_grant"}
    retry = await client.post("/token", data=_exchange(code))
    assert retry.status_code == 400


async def test_ac1_unknown_code_is_invalid_grant(client: httpx.AsyncClient) -> None:
    response = await client.post("/token", data=_exchange("never-issued"))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant"}


async def test_ac1_code_expires_after_sixty_seconds(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1_000_000.0]
    monkeypatch.setattr(oidc_server, "time", SimpleNamespace(time=lambda: now[0]))
    code = await _code(client)
    now[0] += 61
    response = await client.post("/token", data=_exchange(code))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant"}


async def test_ac1_code_is_valid_just_inside_sixty_seconds(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1_000_000.0]
    monkeypatch.setattr(oidc_server, "time", SimpleNamespace(time=lambda: now[0]))
    code = await _code(client)
    now[0] += 59
    assert (await client.post("/token", data=_exchange(code))).status_code == 200


async def test_ac1_cors_allows_only_the_spa_origins_for_post(client: httpx.AsyncClient) -> None:
    allowed = await client.options(
        "/token",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in allowed.headers["access-control-allow-methods"]
    other = await client.options(
        "/token",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in other.headers
    delete = await client.options(
        "/token",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"},
    )
    assert "DELETE" not in delete.headers.get("access-control-allow-methods", "")


def test_ac1_the_key_persists_across_restarts(key_file: Path) -> None:
    first = oidc_server.provider().jwks()
    assert key_file.exists()
    second = oidc_server.provider().jwks()
    assert json.loads(first)["keys"][0]["n"] == json.loads(second)["keys"][0]["n"]


def test_ac1_a_token_from_another_key_does_not_verify(key_file: Path) -> None:
    token = oidc_server.provider().token("dev-leader")
    key_file.unlink()
    other = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=oidc_server.provider().jwks())
    with pytest.raises(InvalidToken):
        other.verify(token)


def test_ac1_key_file_is_private_to_the_owner(key_file: Path) -> None:
    oidc_server.provider()
    assert key_file.stat().st_mode & 0o077 == 0
