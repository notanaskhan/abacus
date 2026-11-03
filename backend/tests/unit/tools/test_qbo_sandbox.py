"""The QuickBooks sandbox command (F-09-T05): sandbox only, keys from the environment, the
`state` check on the redirect, PKCE, tokens kept 0600, and egress held to the connector's hosts."""

from __future__ import annotations

import base64
import hashlib
import stat
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlsplit

import pytest

from abacus.kernel.egress import EgressClient, EgressRefused, EgressResponse
from abacus_tools import qbo_sandbox as tool

KEYS = {tool.ID_ENV: "ABsandboxclient123", tool.SECRET_ENV: "sandbox-secret"}


def test_app_reads_the_keys_from_the_environment() -> None:
    app = tool.app(dict(KEYS))
    assert (app.client_id, app.environment) == ("ABsandboxclient123", "sandbox")


@pytest.mark.parametrize("missing", [tool.ID_ENV, tool.SECRET_ENV])
def test_app_refuses_without_both_keys(missing: str) -> None:
    env = dict(KEYS)
    del env[missing]
    with pytest.raises(tool.Refused):
        tool.app(env)


def test_app_refuses_production() -> None:
    with pytest.raises(tool.Refused, match="sandbox"):
        tool.app({**KEYS, tool.ENVIRONMENT_ENV: "production"})


def test_pkce_challenge_is_s256_of_the_verifier() -> None:
    verifier, challenge = tool.pkce_pair()
    digest = hashlib.sha256(verifier.encode()).digest()
    assert challenge == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert len(verifier) >= 43


def test_callback_joins_code_and_realm() -> None:
    path = "/callback?code=AB11xyz&state=s-1&realmId=9341452"
    assert tool.callback_code(path, "s-1") == "AB11xyz~9341452"


def test_callback_refuses_another_state() -> None:
    with pytest.raises(tool.Refused, match="CSRF"):
        tool.callback_code("/callback?code=AB11&state=other&realmId=1", "s-1")


def test_callback_refuses_an_intuit_error() -> None:
    with pytest.raises(tool.Refused, match="access_denied"):
        tool.callback_code("/callback?error=access_denied&state=s-1", "s-1")


def test_callback_refuses_a_missing_realm() -> None:
    with pytest.raises(tool.Refused, match="realmId"):
        tool.callback_code("/callback?code=AB11&state=s-1", "s-1")


def test_tokens_are_saved_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "tokens.json"
    tool.save(path, b"{}")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert tool.load(path) == b"{}"


def test_load_without_tokens_says_connect_first(tmp_path: Path) -> None:
    with pytest.raises(tool.Refused, match="connect"):
        tool.load(tmp_path / "absent.json")


def test_tokens_path_can_be_moved(tmp_path: Path) -> None:
    moved = tmp_path / "t.json"
    assert tool.tokens_path({tool.TOKENS_ENV: str(moved)}) == moved
    assert tool.tokens_path({}) == tool.DEFAULT_TOKENS


class Offline:
    """No network in unit tests: every request answers 404."""

    async def request(self, method: str, url: str, **_: object) -> EgressResponse:
        return EgressResponse(404, {}, b"")


async def test_sign_in_asks_for_the_accounting_scope_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key, value in KEYS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(tool, "egress_client", lambda: cast(EgressClient, Offline()))
    connector = tool.connector_for(tmp_path / "t.json", None)
    url = await connector.authorise_url("s-1", tool.redirect_uri(8765), code_challenge="abc")
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == ["com.intuit.quickbooks.accounting"]
    assert query["redirect_uri"] == ["http://localhost:8765/callback"]
    assert query["code_challenge_method"] == ["S256"]


async def test_egress_never_reaches_payments(monkeypatch: pytest.MonkeyPatch) -> None:
    client = tool.egress_client()
    with pytest.raises(EgressRefused):
        await client.request(
            "POST", "https://sandbox.api.intuit.com/quickbooks/v4/payments/charges"
        )
    with pytest.raises(EgressRefused):
        await client.request(
            "POST", "https://sandbox-quickbooks.api.intuit.com/v3/company/1/invoice"
        )
    await client.close()
