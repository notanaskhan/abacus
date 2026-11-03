"""Drive the QuickBooks Online connector against Intuit's sandbox from a laptop (F-09-T05;
A-02-T26; DEC-70, DEC-709). Sandbox only: it refuses anything else.

    python -m abacus_tools.qbo_sandbox connect [--port 8765] [--no-browser]
    python -m abacus_tools.qbo_sandbox health
    python -m abacus_tools.qbo_sandbox trial-balance [--start 2026-01-01] [--end 2026-11-03]
    python -m abacus_tools.qbo_sandbox refresh [--force]
    python -m abacus_tools.qbo_sandbox revoke

It runs the product's own `QuickBooksOnlineConnector` through the product's `EgressClient`, held
to the write-capability registry's QuickBooks hosts and read POSTs, so what it proves is what the
product sends: PKCE and a checked `state` on sign-in, the token exchange, the TrialBalance read,
the companyinfo health read, the rotating refresh and the revoke. The scope is the connector's
own (`com.intuit.quickbooks.accounting`); there is no payments or OpenID call.

The app's development keys are read only from `ABACUS_QBO_CLIENT_ID` and
`ABACUS_QBO_CLIENT_SECRET` (the names the product's settings read): never an argument, never
printed. `connect` serves one request on `http://localhost:<port>/callback`, which must be a
redirect URI on the app's Development keys page. Sandbox tokens are kept in
`~/.abacus/qbo-sandbox.json` (mode 0600, outside the repository; `ABACUS_QBO_SANDBOX_TOKENS`
moves it); `revoke` deletes the file.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import webbrowser
from dataclasses import replace
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Final
from urllib.parse import parse_qs, urlsplit

from abacus.kernel.clock import system_now
from abacus.kernel.egress import EgressClient, configure_egress
from abacus.modules.connections.api import ConnectorError, Period, Unavailable
from abacus.modules.connections.api import quickbooks_online as qbo
from abacus.modules.integrations.api import (
    egress_allowlist,
    egress_hosts_by_connector,
    egress_read_posts,
)

ID_ENV: Final = "ABACUS_QBO_CLIENT_ID"
SECRET_ENV: Final = "ABACUS_QBO_CLIENT_SECRET"
ENVIRONMENT_ENV: Final = "ABACUS_QBO_ENVIRONMENT"
TOKENS_ENV: Final = "ABACUS_QBO_SANDBOX_TOKENS"
DEFAULT_TOKENS: Final = Path.home() / ".abacus" / "qbo-sandbox.json"
DEFAULT_PORT: Final = 8765
CALLBACK_PATH: Final = "/callback"
CALLBACK_SECONDS: Final = 300


class Refused(Exception):
    """The command was refused before anything was sent, or the provider refused it."""


def app(environ: dict[str, str] | None = None) -> qbo.QboApp:
    """The development keys from the environment, sandbox only (never echoed)."""
    env = environ if environ is not None else dict(os.environ)
    client_id, client_secret = env.get(ID_ENV, "").strip(), env.get(SECRET_ENV, "").strip()
    if not client_id or not client_secret:
        raise Refused(f"set {ID_ENV} and {SECRET_ENV} (the app's Development keys)")
    if env.get(ENVIRONMENT_ENV, "sandbox") != "sandbox":
        raise Refused(f"{ENVIRONMENT_ENV} must be 'sandbox'; this tool never reaches real books")
    return qbo.QboApp(client_id, client_secret, "sandbox")


def tokens_path(environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else dict(os.environ)
    return Path(env[TOKENS_ENV]) if env.get(TOKENS_ENV) else DEFAULT_TOKENS


def redirect_uri(port: int) -> str:
    return f"http://localhost:{port}{CALLBACK_PATH}"


def pkce_pair() -> tuple[str, str]:
    """(verifier, S256 challenge), RFC 7636; both URL-safe base64 without padding."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def callback_code(path: str, state: str) -> str:
    """The connector's `<code>~<realmId>` from Intuit's redirect, after the `state` check."""
    query = {k: v[0] for k, v in parse_qs(urlsplit(path).query).items()}
    if "error" in query:
        raise Refused(f"Intuit returned {query['error']!r}")
    if not secrets.compare_digest(query.get("state", ""), state):
        raise Refused("state does not match: not this sign-in (CSRF check)")
    code, realm = query.get("code", ""), query.get("realmId", "")
    if not code or not realm:
        raise Refused("the redirect carried no code or realmId")
    return f"{code}{qbo.REALM_SEPARATOR}{realm}"


def save(path: Path, sealed: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(sealed)
    path.chmod(0o600)


def load(path: Path) -> bytes:
    if not path.exists():
        raise Refused(f"no sandbox tokens at {path}; run `connect` first")
    return path.read_bytes()


def egress_client() -> EgressClient:
    configure_egress(
        egress_allowlist(), egress_read_posts(), by_connector=egress_hosts_by_connector()
    )
    return EgressClient(connector=qbo.PROVIDER)


def connector_for(path: Path, credentials: bytes | None) -> qbo.QuickBooksOnlineConnector:
    async def rotate(sealed: bytes) -> None:
        save(path, sealed)
        print("refresh token rotated; saved")

    return qbo.QuickBooksOnlineConnector(app(), egress_client(), credentials, on_rotate=rotate)


def _wait_for_callback(port: int) -> str:
    """Serve one request on localhost and return its path (the redirect's query string)."""
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlsplit(self.path).path != CALLBACK_PATH:
                self.send_error(404)
                return
            seen.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Received. You can close this tab and go back to the terminal.")

        def log_message(self, format: str, *args: object) -> None:
            return  # the query holds the code: never log it

    deadline = time.monotonic() + CALLBACK_SECONDS
    with HTTPServer(("localhost", port), Handler) as server:
        server.timeout = 5
        while not seen and time.monotonic() < deadline:
            server.handle_request()  # returns on a request or after `timeout`
    if not seen:
        raise Refused(f"no redirect within {CALLBACK_SECONDS} seconds")
    return seen[0]


async def connect(path: Path, port: int, open_browser: bool) -> None:
    connector = connector_for(path, None)
    state = secrets.token_urlsafe(24)
    verifier, challenge = pkce_pair()
    uri = redirect_uri(port)
    url = await connector.authorise_url(state, uri, code_challenge=challenge)
    print(f"Sign in and pick a sandbox company:\n\n  {url}\n")
    print(f"Waiting on {uri} (register it under Development keys > Redirect URIs) ...")
    if open_browser:
        webbrowser.open(url)
    callback = await asyncio.to_thread(_wait_for_callback, port)
    code = callback_code(callback, state)
    sealed = await connector.exchange_code(code, uri, code_verifier=verifier)
    if sealed is None:  # pragma: no cover (QBO always returns credentials)
        raise Refused("no credentials returned")
    save(path, sealed)
    held = qbo.QboCredentials.opened(sealed)
    print(f"connected: realm {held.realm_id}, access token until {held.expires_at:%H:%M:%S %Z}")
    print(f"tokens saved to {path} (0600)")


async def health(path: Path) -> None:
    connector = connector_for(path, load(path))
    await connector.refresh()  # no-op unless within 5 minutes of expiry
    await connector.health()
    print("health: companyinfo read ok")


async def trial_balance(path: Path, start: date, end: date) -> None:
    connector = connector_for(path, load(path))
    await connector.refresh()
    payload = await connector.pull("trial_balance", Period(start, end), None)
    report = json.loads(payload.content)
    header = report.get("Header", {})
    rows = report.get("Rows", {}).get("Row", [])
    print(
        f"{header.get('ReportName', 'TrialBalance')} {header.get('StartPeriod')}.."
        f"{header.get('EndPeriod')} {header.get('Currency', '')}: {len(rows)} rows, "
        f"{len(payload.content)} bytes"
    )
    for row in rows[:10]:
        cells = [c.get("value", "") for c in row.get("ColData", [])]
        if cells:
            print("  " + " | ".join(cells))


async def refresh(path: Path, force: bool) -> None:
    sealed = load(path)
    if force:  # pretend the access token is about to expire, so the connector refreshes
        held = qbo.QboCredentials.opened(sealed)
        sealed = replace(held, expires_at=system_now()).sealed_form()
    connector = connector_for(path, sealed)
    await connector.refresh()
    if not force:
        print("refresh: not due (more than 5 minutes left); use --force to rotate now")


async def revoke(path: Path) -> None:
    connector = connector_for(path, load(path))
    await connector.revoke()
    path.unlink()
    print(f"revoked; {path} deleted")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.qbo_sandbox")
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("connect", help="sign in to a sandbox company and save its tokens")
    c.add_argument("--port", type=int, default=DEFAULT_PORT)
    c.add_argument("--no-browser", action="store_true")
    commands.add_parser("health", help="the connector's companyinfo health read")
    tb = commands.add_parser("trial-balance", help="the connector's TrialBalance pull")
    today = system_now().date()
    tb.add_argument("--start", type=date.fromisoformat, default=date(today.year, 1, 1))
    tb.add_argument("--end", type=date.fromisoformat, default=today)
    r = commands.add_parser("refresh", help="rotate the refresh token")
    r.add_argument("--force", action="store_true")
    commands.add_parser("revoke", help="revoke the tokens at Intuit and delete the file")
    args = parser.parse_args(argv)

    path = tokens_path()
    try:
        match args.command:
            case "connect":
                asyncio.run(connect(path, args.port, not args.no_browser))
            case "health":
                asyncio.run(health(path))
            case "trial-balance":
                asyncio.run(trial_balance(path, args.start, args.end))
            case "refresh":
                asyncio.run(refresh(path, args.force))
            case "revoke":
                asyncio.run(revoke(path))
            case _:  # pragma: no cover (argparse refuses other commands)
                parser.error(f"unknown command {args.command!r}")
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except Unavailable as exc:
        print(f"Intuit unavailable: {exc}; try again", file=sys.stderr)
        return 3
    except ConnectorError as exc:
        hint = " (run `connect` again)" if str(exc) in ("token_expired", "invalid_grant") else ""
        print(f"connector error: {exc}{hint}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
