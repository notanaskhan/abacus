"""The QuickBooks Online read connector (A-02-T26; DEC-70, DEC-709; ADR-037, ADR-040).

The first live ledger read. It implements the connector contract and nothing more (CONN-001): OAuth
2.0 authorisation-code with PKCE, a rotating refresh token, the TrialBalance report and a health
read. The OAuth endpoints come from Intuit's discovery document (TASK-3099, DEC-2099), read once a
day per environment; when it can't be read or names an endpoint off Intuit's hosts, the pinned
endpoints below are used, and a changed host or path still meets the egress allowlist, which
refuses it (fail closed). Every response's `intuit_tid` is logged with the endpoint and status, so
a request can be traced with Intuit support. Network access is only through
`kernel.egress.EgressClient` (HTTPS to the registry's declared hosts, GET or HEAD, and POST only to
the two OAuth paths declared as reads: the token exchange and the revoke). It never calls a write
endpoint of the client's books; the interception harness in
`tests/unit/connections/test_qbo_connector.py` proves the requests it sends.

Credentials are this connector's own JSON (`access_token`, `refresh_token`, `realm_id`,
`expires_at`), sealed with the tenant's key at rest by the caller. A refresh that rotates the
refresh token hands the new credentials to `on_rotate`, which the factory wires to reseal them;
until it succeeds the old ones stay sealed. Provider text never leaves here: failures are short
codes (`token_expired`, `invalid_grant`, `revoke_refused`, `provider_unavailable`,
`provider_error`).
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Final, cast

from abacus.kernel.clock import system_now
from abacus.kernel.egress import EgressClient, EgressRefused, EgressResponse
from abacus.kernel.logging import get_logger
from abacus.modules.connections import qbo_throttle
from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Credentials,
    Dataset,
    NotSupported,
    Period,
    RateLimited,
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
# Intuit's OpenID discovery documents (DEC-2099): the authorisation, token and revoke endpoints.
DISCOVERY_HOST: Final = "developer.intuit.com"
DISCOVERY_PATHS: Final = {
    "sandbox": "/.well-known/openid_sandbox_configuration",
    "production": "/.well-known/openid_configuration",
}
_DISCOVERY_TTL: Final = timedelta(hours=24)
_INTUIT_DOMAIN: Final = ".intuit.com"
# HTTPS, a bare host, a plain path: no port, userinfo, query or fragment (CONN-001: no URL lib).
_ENDPOINT_URL: Final = re.compile(r"https://([a-z0-9.-]+)(/[A-Za-z0-9._~/-]*)?")
TID_HEADER: Final = "intuit_tid"
_TID: Final = re.compile(r"[A-Za-z0-9-]{1,64}")
_HEX_RUN: Final = re.compile(r"[0-9a-fA-F]{32,}")
_OAUTH_CODE: Final = re.compile(r"[a-z_]{1,50}")
MEDIA_TYPE: Final = "application/json"
MINOR_VERSION: Final = "75"
REALM_SEPARATOR: Final = "~"
_EARLY_REFRESH: Final = timedelta(minutes=5)
_REAUTH_ERRORS: Final = frozenset({"invalid_grant"})
# C-01-T16 (C9 v2.1): the chart of accounts is read 1,000 at a time (Intuit's page cap); the
# CDC entities name what a sync must pull again.
PAGE_SIZE: Final = 1000
_ACCOUNT_ENTITIES: Final = ("Account",)
# C-02-T26: the vendor list and the two vendor-payment entities CLS-13 reads (read-only).
_VENDOR_ENTITIES: Final = ("Vendor",)
_PAYMENT_ENTITIES: Final = ("BillPayment", "Purchase")
_TXN_ENTITIES: Final = (
    "JournalEntry", "Purchase", "Deposit", "Transfer", "Bill", "BillPayment", "Payment",
    "SalesReceipt", "Invoice", "RefundReceipt", "VendorCredit", "CreditMemo",
)  # fmt: skip
_CDC_ENTITIES: Final = ",".join(_ACCOUNT_ENTITIES + _VENDOR_ENTITIES + _TXN_ENTITIES)
_CURSOR: Final = re.compile(r"[1-9][0-9]{0,6}")
# vendor_payments pages through BillPayment then Purchase: "<entity>:<position>".
_PAYMENT_CURSOR: Final = re.compile(r"(BillPayment|Purchase):([1-9][0-9]{0,6})")
# The GL detail's columns, by Intuit's column keys (the report is read only for these).
GL_COLUMNS: Final = "tx_date,txn_type,doc_num,name,memo,split_acc,subt_nat_amount"

_log = get_logger(__name__)


@dataclass(frozen=True)
class Endpoints:
    authorise: str
    token: str
    revoke: str


PINNED: Final = Endpoints(
    AUTHORISE_URL, f"https://{OAUTH_HOST}{OAUTH_PATH}", f"https://{REVOKE_HOST}{REVOKE_PATH}"
)
_discovered: dict[str, tuple[Endpoints, datetime]] = {}


def reset_discovery() -> None:
    """Forget the discovered endpoints (tests; a process re-reads them daily anyway)."""
    _discovered.clear()


def _intuit_url(value: object) -> str | None:
    """An HTTPS URL on an Intuit host with no port or userinfo, else None."""
    if not isinstance(value, str):
        return None
    match = _ENDPOINT_URL.fullmatch(value)
    return value if match and match.group(1).endswith(_INTUIT_DOMAIN) else None


def _endpoints_from(content: bytes) -> Endpoints | None:
    try:
        raw: object = json.loads(content)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    body = cast(dict[str, object], raw)
    found = [
        _intuit_url(body.get(key))
        for key in ("authorization_endpoint", "token_endpoint", "revocation_endpoint")
    ]
    if any(url is None for url in found):
        return None
    authorise, token, revoke = cast(list[str], found)
    return Endpoints(authorise, token, revoke)


def tid_for_log(tid: str | None) -> str | None:
    """`1-<8 hex>-<24 hex>` as one hex run (DEC-2901). Written with its hyphens, a nine-digit run
    in it reads as a taxpayer ID and the log's backstop masks it, so support can't trace it; a
    hex run of 32 or more is opaque to `kernel.tin_patterns`. To quote one to Intuit, put the
    hyphens back after the first and ninth characters."""
    if tid is None:
        return None
    compact = tid.replace("-", "")
    return compact if _HEX_RUN.fullmatch(compact) else tid


def intuit_tid(headers: Mapping[str, str]) -> str | None:
    """The response's `intuit_tid`, if it has Intuit's shape (header text is untrusted)."""
    for key, value in headers.items():
        if key.lower() == TID_HEADER:
            return value if _TID.fullmatch(value) else None
    return None


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
        # C-01-T16: API calls this connector made, for the meter (C-01-T17); OAuth excluded.
        self.calls = 0

    def capabilities(self) -> Capabilities:
        return Capabilities(
            datasets=frozenset(
                {"trial_balance", "accounts", "gl_detail", "trial_balance_month"}
                | {"vendors", "vendor_payments"}
            ),
            oauth=True,
            incremental=True,
            attachments=False,
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
        return f"{(await self._endpoints()).authorise}?{query}"

    def _basic(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._app.client_id}:{self._app.client_secret}".encode())
        return {
            "Authorization": f"Basic {token.decode()}",
            "Accept": MEDIA_TYPE,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _call(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> EgressResponse:
        try:
            response = await self._client.request(
                method, url, headers=headers, data=data, content=content
            )
        except EgressRefused:
            raise ConnectorError("egress_refused") from None
        except (TimeoutError, OSError):
            raise Unavailable("provider_unavailable") from None
        # Intuit's support traces a request by its intuit_tid (DEC-2099): never a token or body.
        fields = {"endpoint": endpoint, "status": response.status_code}
        tid = tid_for_log(intuit_tid(response.headers))
        if response.status_code >= 400:
            _log.warning("qbo.response", intuit_tid=tid, **fields)
        else:
            _log.info("qbo.response", intuit_tid=tid, **fields)
        return response

    async def _endpoints(self) -> Endpoints:
        """Intuit's discovery document, read at most once a day per environment (DEC-2099)."""
        environment = self._app.environment
        cached = _discovered.get(environment)
        if cached is not None and system_now() - cached[1] < _DISCOVERY_TTL:
            return cached[0]
        try:
            response = await self._call(
                "GET",
                f"https://{DISCOVERY_HOST}{DISCOVERY_PATHS[environment]}",
                endpoint="discovery",
                headers={"Accept": MEDIA_TYPE},
            )
        except (ConnectorError, Unavailable):
            response = None
        found = (
            _endpoints_from(response.content) if response and response.status_code == 200 else None
        )
        if found is None:
            _log.warning("qbo.discovery_unread", environment=environment)
            return PINNED  # not cached: the next call tries the document again
        _discovered[environment] = (found, system_now())
        return found

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
            (await self._endpoints()).token,
            endpoint="token",
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
            (await self._endpoints()).token,
            endpoint="token",
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
        """End the grant at Intuit (DEC-2901): a JSON body, as Intuit's SDKs send it, and only a
        200 counts. A refusal never reads as revoked, so the caller records it as refused."""
        held = self._held()
        response = await self._call(
            "POST",
            (await self._endpoints()).revoke,
            endpoint="revoke",
            headers={**self._basic(), "Content-Type": MEDIA_TYPE},
            content=json.dumps({"token": held.refresh_token}).encode(),
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise Unavailable("provider_unavailable")
        if response.status_code != 200:
            code = _oauth_error(response.content)
            _log.warning(
                "qbo.revoke_refused",
                status=response.status_code,
                error=code if _OAUTH_CODE.fullmatch(code) else None,
            )
            raise ConnectorError("revoke_refused")

    def _held(self) -> QboCredentials:
        if self._credentials is None:
            raise ConnectorError("token_expired")
        return self._credentials

    async def _get(self, path: str, endpoint: str) -> EgressResponse:
        """One read of the books, inside the realm's limiter and the provider's breaker
        (ADR-043), counted for the meter. A 429 is `rate_limited` with Intuit's Retry-After."""
        held = self._held()
        realm = _realm(held.realm_id)
        async with qbo_throttle.Slot(realm):
            self.calls += 1
            response = await self._call(
                "GET",
                f"https://{self._app.api_host}/v3/company/{realm}{path}",
                endpoint=endpoint,
                headers={"Authorization": f"Bearer {held.access_token}", "Accept": MEDIA_TYPE},
            )
        if response.status_code == 429:
            qbo_throttle.failed()
            raise RateLimited("rate_limited", qbo_throttle.retry_after(dict(response.headers)))
        if response.status_code >= 500:
            qbo_throttle.failed()
            raise Unavailable("provider_unavailable")
        qbo_throttle.succeeded()
        if response.status_code == 401:
            raise ConnectorError("token_expired")
        if response.status_code != 200:
            raise ConnectorError("provider_error")
        return response

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        """The provider's bytes for one dataset and period (ADR-038). `trial_balance` and
        `trial_balance_month` read the TrialBalance report for the period (a month for the
        close engine); `gl_detail` reads the GeneralLedger report's register columns for the
        period (one month a pull: large reports in date-range chunks, ADR-043); `accounts` reads
        the chart of accounts a page at a time, `cursor` the next start position."""
        if dataset not in self.capabilities().datasets:
            raise NotSupported("dataset")
        start, end = period.start.isoformat(), period.end.isoformat()
        if dataset in ("trial_balance", "trial_balance_month"):
            response = await self._get(
                f"/reports/TrialBalance?start_date={start}&end_date={end}"
                f"&accounting_method=Accrual&minorversion={MINOR_VERSION}",
                dataset,
            )
            request = f"{dataset} {start}..{end}"
            return RawPayload(response.content, MEDIA_TYPE, PROVIDER, system_now(), request)
        if dataset == "gl_detail":
            response = await self._get(
                f"/reports/GeneralLedger?start_date={start}&end_date={end}"
                f"&accounting_method=Accrual&columns={_percent(GL_COLUMNS)}"
                f"&minorversion={MINOR_VERSION}",
                dataset,
            )
            request = f"gl_detail {start}..{end}"
            return RawPayload(response.content, MEDIA_TYPE, PROVIDER, system_now(), request)
        if dataset == "vendor_payments":
            return await self._vendor_payments(period, cursor)
        position = 1
        if cursor is not None:
            if not _CURSOR.fullmatch(cursor):
                raise ConnectorError("invalid_cursor")
            position = int(cursor)
        entity = "Vendor" if dataset == "vendors" else "Account"
        # Intuit query language over integers the connector computes, never caller text.
        query = " ".join(
            ("select * from", entity, "startposition", str(position), "maxresults", str(PAGE_SIZE))
        )
        response = await self._get(
            f"/query?query={_percent(query)}&minorversion={MINOR_VERSION}", dataset
        )
        returned = _row_count(response.content, entity)
        following = str(position + PAGE_SIZE) if returned == PAGE_SIZE else None
        return RawPayload(
            response.content, MEDIA_TYPE, PROVIDER, system_now(),
            f"{dataset} from {position}", next_cursor=following,
        )  # fmt: skip

    async def _vendor_payments(self, period: Period, cursor: str | None) -> RawPayload:
        """C-02-T26: one page of the period's BillPayment rows, then of its Purchase rows (checks,
        cash and card purchases carry `PaymentType` and `PaymentMethodRef`). Dates and integers
        only, computed here; never caller text."""
        entity, position = "BillPayment", 1
        if cursor is not None:
            match = _PAYMENT_CURSOR.fullmatch(cursor)
            if match is None:
                raise ConnectorError("invalid_cursor")
            entity, position = match.group(1), int(match.group(2))
        query = " ".join(
            (
                "select * from", entity,
                f"where TxnDate >= '{period.start.isoformat()}'",
                f"and TxnDate <= '{period.end.isoformat()}'",
                "startposition", str(position), "maxresults", str(PAGE_SIZE),
            )
        )  # fmt: skip
        response = await self._get(
            f"/query?query={_percent(query)}&minorversion={MINOR_VERSION}", "vendor_payments"
        )
        returned = _row_count(response.content, entity)
        following: str | None
        if returned == PAGE_SIZE:
            following = f"{entity}:{position + PAGE_SIZE}"
        elif entity == "BillPayment":
            following = "Purchase:1"
        else:
            following = None
        return RawPayload(
            response.content, MEDIA_TYPE, PROVIDER, system_now(),
            f"vendor_payments {entity} {period.start.isoformat()}..{period.end.isoformat()} "
            f"from {position}",
            next_cursor=following,
        )

    async def changes_since(self, since: datetime) -> Sequence[str]:
        """Which datasets changed since `since` (Intuit's CDC; at most 30 days back): `accounts`
        when an account changed, `gl_detail` and `trial_balance_month` when any transaction
        did. Only names leave here; the sync pulls the datasets again."""
        stamp = since.astimezone(UTC).isoformat(timespec="seconds")
        response = await self._get(
            f"/cdc?entities={_CDC_ENTITIES}&changedSince={_percent(stamp)}"
            f"&minorversion={MINOR_VERSION}",
            "cdc",
        )
        entities = _cdc_entities(response.content)
        changed: list[str] = []
        if entities & set(_ACCOUNT_ENTITIES):
            changed.append("accounts")
        if entities & set(_TXN_ENTITIES):
            changed.extend(("gl_detail", "trial_balance_month"))
        if entities & set(_VENDOR_ENTITIES):
            changed.append("vendors")
        if entities & set(_PAYMENT_ENTITIES):
            changed.append("vendor_payments")
        return tuple(changed)

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise NotSupported("attachments")

    async def health(self) -> bool:
        held = self._held()
        await self._get(
            f"/companyinfo/{_realm(held.realm_id)}?minorversion={MINOR_VERSION}", "companyinfo"
        )
        return True


def _row_count(content: bytes, entity: str) -> int:
    """How many `entity` rows a query page returned (0 for anything unreadable: no next page)."""
    try:
        raw: object = json.loads(content)
    except ValueError:
        return 0
    if not isinstance(raw, dict):
        return 0
    response = cast(dict[str, object], raw).get("QueryResponse")
    if not isinstance(response, dict):
        return 0
    rows = cast(dict[str, object], response).get(entity)
    return len(cast(list[object], rows)) if isinstance(rows, list) else 0


def _cdc_entities(content: bytes) -> set[str]:
    """The entity names a CDC response carries rows for (names only; rows are re-read)."""
    try:
        raw: object = json.loads(content)
    except ValueError:
        raise ConnectorError("provider_error") from None
    found: set[str] = set()
    known = set(_ACCOUNT_ENTITIES + _VENDOR_ENTITIES + _TXN_ENTITIES)
    blocks = cast(dict[str, object], raw).get("CDCResponse") if isinstance(raw, dict) else None
    for block in cast(list[object], blocks) if isinstance(blocks, list) else []:
        responses = (
            cast(dict[str, object], block).get("QueryResponse")
            if isinstance(block, dict)
            else None
        )
        for response in cast(list[object], responses) if isinstance(responses, list) else []:
            if not isinstance(response, dict):
                continue
            for name, rows in cast(dict[str, object], response).items():
                if name in known and isinstance(rows, list) and rows:
                    found.add(name)
    return found


def _oauth_error(content: bytes) -> str:
    try:
        raw: object = json.loads(content)
    except ValueError:
        return ""
    return str(cast(dict[str, object], raw).get("error", "")) if isinstance(raw, dict) else ""
