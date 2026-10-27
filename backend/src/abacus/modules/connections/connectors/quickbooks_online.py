"""The QuickBooks Online read connector (A-02-T26; DEC-70, DEC-709; ADR-037, ADR-040).

The first live ledger read. It implements the connector contract and nothing more (CONN-001):
OAuth 2.0 authorisation-code with PKCE, a rotating refresh token, the TrialBalance report and a
health read. Network access is only through `kernel.egress.EgressClient` (HTTPS to the registry's
declared hosts, GET or HEAD, and POST only to the two OAuth paths declared as reads: the token
exchange and the revoke). It never calls a write endpoint of the client's books; the interception
harness in `tests/unit/connections/test_qbo_read_only.py` proves the requests it sends.

Credentials are this connector's own JSON (`access_token`, `refresh_token`, `realm_id`,
`expires_at`), sealed with the tenant's key at rest by the caller. A refresh that rotates the
refresh token hands the new credentials to `on_rotate`, which the factory wires to reseal them;
until it succeeds the old ones stay sealed. Provider text never leaves here: failures are short
codes (`token_expired`, `invalid_grant`, `provider_unavailable`, `provider_error`).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar, Final, cast

from abacus.kernel.clock import system_now
from abacus.kernel.egress import EgressClient, EgressRefused, EgressResponse
from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Credentials,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
    Unavailable,
)

PROVIDER: Final = "quickbooks_online"
AUTHORISE_URL: Final = "https://appcenter.intuit.com/connect/oauth2"
OAUTH_HOST: Final = "oauth.platform.intuit.com"
OAUTH_PATH: Final = "/oauth2/v1/tokens/bearer"
REVOKE_HOST: Final = "developer.api.intuit.com"
REVOKE_PATH: Final = "/v2/oauth2/tokens/revoke"
API_HOSTS: Final = {
    "sandbox": "sandbox-quickbooks.api.intuit.com",
    "production": "quickbooks.api.intuit.com",
}
# The read-only accounting scope; never `payment` or anything that writes.
SCOPE: Final = "com.intuit.quickbooks.accounting"
MEDIA_TYPE: Final = "application/json"
MINOR_VERSION: Final = "75"
REALM_SEPARATOR: Final = "~"
_EARLY_REFRESH: Final = timedelta(minutes=5)
_REAUTH_ERRORS: Final = frozenset({"invalid_grant"})


@dataclass(frozen=True)
class QboCredentials:
    access_token: str
    refresh_token: str
    realm_id: str
    expires_at: datetime

    def sealed_form(self) -> Credentials:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "realm_id": self.realm_id,
                "expires_at": self.expires_at.isoformat(),
            },
            sort_keys=True,
        ).encode()

    @classmethod
    def opened(cls, blob: Credentials) -> QboCredentials:
        try:
            raw = cast(dict[str, str], json.loads(blob))
            return cls(
                raw["access_token"],
                raw["refresh_token"],
                raw["realm_id"],
                datetime.fromisoformat(raw["expires_at"]),
            )
        except (ValueError, KeyError, TypeError):
            raise ConnectorError("credentials_unreadable") from None


@dataclass(frozen=True)
class QboApp:
    """The firm-independent app registration (settings): client id, secret and environment."""

    client_id: str
    client_secret: str
    environment: str

    @property
    def api_host(self) -> str:
        return API_HOSTS[self.environment]


def _realm(value: str) -> str:
    if not value.isdigit() or len(value) > 32:
        raise ConnectorError("invalid_realm")
    return value


_UNRESERVED: Final = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _percent(value: str) -> str:
    """RFC 3986 percent-encoding of a query value (the redirect URI's `:` and `/` included)."""
    return "".join(
        c if c in _UNRESERVED else "".join(f"%{b:02X}" for b in c.encode()) for c in value
    )


def _safe(value: str) -> str:
    """OAuth values are URL-safe by construction; anything else is refused, not escaped."""
    if not value or not value.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise ConnectorError("invalid_state")
    return value


class QuickBooksOnlineConnector(Connector):
    provider: ClassVar[str] = PROVIDER

    def __init__(
        self,
        app: QboApp,
        client: EgressClient,
        credentials: Credentials | None = None,
        on_rotate: Callable[[Credentials], Awaitable[None]] | None = None,
    ) -> None:
        self._app = app
        self._client = client
        self._credentials = QboCredentials.opened(credentials) if credentials else None
        self._on_rotate = on_rotate

    def capabilities(self) -> Capabilities:
        return Capabilities(
            datasets=frozenset({"trial_balance"}), oauth=True, incremental=False, attachments=False
        )

    async def authorise_url(
        self, state: str, redirect_uri: str, *, code_challenge: str | None = None
    ) -> str:
        if code_challenge is None:
            raise ConnectorError("pkce_required")
        query = "&".join(
            f"{k}={_percent(v)}"
            for k, v in (
                ("client_id", _safe(self._app.client_id)),
                ("response_type", "code"),
                ("scope", SCOPE),
                ("redirect_uri", redirect_uri),
                ("state", _safe(state)),
                ("code_challenge", _safe(code_challenge)),
                ("code_challenge_method", "S256"),
            )
        )
        return f"{AUTHORISE_URL}?{query}"

    def _basic(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._app.client_id}:{self._app.client_secret}".encode())
        return {
            "Authorization": f"Basic {token.decode()}",
            "Accept": MEDIA_TYPE,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _call(
        self, method: str, url: str, *, headers: dict[str, str], data: dict[str, str] | None = None
    ) -> EgressResponse:
        try:
            return await self._client.request(method, url, headers=headers, data=data)
        except EgressRefused:
            raise ConnectorError("egress_refused") from None
        except (TimeoutError, OSError):
            raise Unavailable("provider_unavailable") from None

    def _tokens(self, response: EgressResponse, realm_id: str) -> QboCredentials:
        if response.status_code == 400:
            code = _oauth_error(response.content)
            raise ConnectorError("invalid_grant" if code in _REAUTH_ERRORS else "access_denied")
        if response.status_code >= 500:
            raise Unavailable("provider_unavailable")
        if response.status_code != 200:
            raise ConnectorError("provider_error")
        try:
            body = cast(dict[str, object], json.loads(response.content))
            access, refresh = str(body["access_token"]), str(body["refresh_token"])
            seconds = int(cast(int, body["expires_in"]))
        except (ValueError, KeyError, TypeError):
            raise ConnectorError("provider_error") from None
        return QboCredentials(access, refresh, realm_id, system_now() + timedelta(seconds=seconds))

    async def exchange_code(
        self, code: str, redirect_uri: str, *, code_verifier: str | None = None
    ) -> Credentials | None:
        if code_verifier is None:
            raise ConnectorError("pkce_required")
        # Intuit names the company the client chose only on the redirect (`realmId`); the portal
        # callback forwards it inside the code as `<code>~<realmId>` (DEC-709).
        code, sep, realm_id = code.partition(REALM_SEPARATOR)
        if not sep:
            raise ConnectorError("invalid_realm")
        realm = _realm(realm_id)
        response = await self._call(
            "POST",
            f"https://{OAUTH_HOST}{OAUTH_PATH}",
            headers=self._basic(),
            data={
                "grant_type": "authorization_code",
                "code": _safe(code),
                "redirect_uri": redirect_uri,
                "code_verifier": _safe(code_verifier),
            },
        )
        self._credentials = self._tokens(response, realm)
        return self._credentials.sealed_form()

    async def refresh(self) -> None:
        held = self._held()
        if held.expires_at - system_now() > _EARLY_REFRESH:
            return
        response = await self._call(
            "POST",
            f"https://{OAUTH_HOST}{OAUTH_PATH}",
            headers=self._basic(),
            data={"grant_type": "refresh_token", "refresh_token": held.refresh_token},
        )
        try:
            rotated = self._tokens(response, held.realm_id)
        except ConnectorError as exc:
            # A refused refresh token is the client's to fix (C20 reauth reason).
            raise ConnectorError(
                "token_expired" if exc.code == "invalid_grant" else exc.code
            ) from None
        self._credentials = rotated
        if self._on_rotate is not None:
            await self._on_rotate(rotated.sealed_form())

    async def revoke(self) -> None:
        held = self._held()
        response = await self._call(
            "POST",
            f"https://{REVOKE_HOST}{REVOKE_PATH}",
            headers=self._basic(),
            data={"token": held.refresh_token},
        )
        if response.status_code >= 500:
            raise Unavailable("provider_unavailable")
        if response.status_code not in (200, 400):  # 400: already revoked
            raise ConnectorError("provider_error")

    def _held(self) -> QboCredentials:
        if self._credentials is None:
            raise ConnectorError("token_expired")
        return self._credentials

    async def _get(self, path: str) -> EgressResponse:
        held = self._held()
        response = await self._call(
            "GET",
            f"https://{self._app.api_host}/v3/company/{_realm(held.realm_id)}{path}",
            headers={"Authorization": f"Bearer {held.access_token}", "Accept": MEDIA_TYPE},
        )
        if response.status_code == 401:
            raise ConnectorError("token_expired")
        if response.status_code == 429 or response.status_code >= 500:
            raise Unavailable("provider_unavailable")
        if response.status_code != 200:
            raise ConnectorError("provider_error")
        return response

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        if dataset not in self.capabilities().datasets:
            raise NotSupported("dataset")
        start, end = period.start.isoformat(), period.end.isoformat()
        response = await self._get(
            f"/reports/TrialBalance?start_date={start}&end_date={end}"
            f"&accounting_method=Accrual&minorversion={MINOR_VERSION}"
        )
        request = f"trial_balance {start}..{end}"
        return RawPayload(response.content, MEDIA_TYPE, PROVIDER, system_now(), request)

    async def changes_since(self, since: datetime) -> Sequence[str]:
        raise NotSupported("incremental")

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise NotSupported("attachments")

    async def health(self) -> bool:
        held = self._held()
        await self._get(f"/companyinfo/{_realm(held.realm_id)}?minorversion={MINOR_VERSION}")
        return True


def _oauth_error(content: bytes) -> str:
    try:
        return str(cast(dict[str, object], json.loads(content)).get("error", ""))
    except ValueError:
        return ""
