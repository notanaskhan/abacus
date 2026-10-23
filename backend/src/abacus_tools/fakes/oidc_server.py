"""A local OpenID Connect sign-in server for the SPA (TASK-012 Q2; SPEC-000 §20). Local only.

Run: python -m abacus_tools.fakes.oidc_server        (serves on 127.0.0.1:9000 + port offset)
     python -m abacus_tools.fakes.oidc_server --jwks (prints the public key set for the API)

The browser flow is authorization code with PKCE (S256), as WorkOS will be (TASK-014):
`/authorize` shows the seeded dev users (`abacus_tools.local.seed_dev`); choosing one redirects
back with a single-use code (60 s), which `/token` exchanges for an RS256 access token (10 min)
signed by `FakeIdentityProvider`. The staff session BFF (P-01-T09) signs in through the same
server at `/v1/auth/callback` (the SPA's origin proxies `/v1`) and also gets a refresh token,
which the `refresh_token` grant rotates on every use. The signing key is kept in
`backend/.local/oidc-key.pem` (gitignored) so tokens survive restarts; `make dev` gives the API
this server's JWKS. Refuses to run outside the local and test environments.

F-04-T27 adds WorkOS AuthKit's hosted email-code sign-in (`abacus_tools.fakes.workos.StaffSignIn`)
beside the chooser, so the scenario's staff sign in as on staging: a work email (SHL-06a), the
emailed code from the local mailbox (b), the authenticator code (c), then the BFF's landing (g),
with "4 attempts left" on a wrong code (e) and the lock after five (f). Two harness readers,
`/_harness/code` and `/_harness/totp`, answer the codes a journey types; this server is local
only, so they never exist anywhere else.
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus_tools.fakes.identity import AUDIENCE, ISSUER, FakeIdentityProvider
from abacus_tools.fakes.workos import StaffSignIn, it_security_person, try_again_at
from abacus_tools.local.worktree_env import port_offset

# This worktree's ports (F-01-T09): only its own SPA may sign in through it.
OFFSET = port_offset()
HOST, PORT = "127.0.0.1", 9000 + OFFSET
CLIENT_ID = "abacus-web"
SPA_ORIGINS = (f"http://localhost:{5173 + OFFSET}", f"http://127.0.0.1:{5173 + OFFSET}")
REDIRECT_URIS = frozenset(
    {f"{origin}/signin/callback" for origin in SPA_ORIGINS}
    | {f"{origin}/v1/auth/callback" for origin in SPA_ORIGINS}  # the BFF (P-01-T09)
)
# The dev users `seed_dev` creates (subject, display name). Sign-in is a choice, not a password.
DEV_USERS = (
    ("dev-leader", "Dana Leader (practice leader)"),
    ("dev-staff", "Sam Staff (staff)"),
    # A client admin on every Dev firm engagement, to see the client side (`/client`).
    ("dev-client", "Casey Client (client admin)"),
    # SPEC-024 (TASK-040): no firm yet, to try self-serve sign-up locally.
    ("dev-new", "Nina New (no firm yet)"),
)
TOKEN_SECONDS = 600
CODE_SECONDS = 60
KEY_FILE = Path(__file__).resolve().parents[3] / ".local" / "oidc-key.pem"


@dataclass(frozen=True)
class _Grant:
    subject: str
    redirect_uri: str
    challenge: str
    expires: float


def _local_only() -> None:
    if settings().environment not in ("local", "test"):
        raise RuntimeError("the fake sign-in server is for local runs and tests only")


def _key() -> rsa.RSAPrivateKey:
    if KEY_FILE.exists():
        loaded = serialization.load_pem_private_key(KEY_FILE.read_bytes(), password=None)
        if not isinstance(loaded, rsa.RSAPrivateKey):
            raise RuntimeError(f"{KEY_FILE} is not an RSA key")
        return loaded
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    # Created owner-only from the start (no window where it is world-readable).
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(pem)
    return key


def provider() -> FakeIdentityProvider:
    return FakeIdentityProvider(issuer=ISSUER, audience=AUDIENCE, key=_key())


_VERIFIER = re.compile(r"[A-Za-z0-9\-._~]{43,128}")  # RFC 7636 §4.1


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _error(status: int, error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status)


_PAGE = (
    "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
    "<title>{title}</title></head><body><main>{body}</main></body></html>"
)


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(title=html.escape(title), body=body))


@dataclass(frozen=True)
class _Flow:
    """The OAuth request an email-code sign-in finishes."""

    redirect_uri: str
    state: str
    challenge: str


def _authorize_query(flow: _Flow) -> str:
    return urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": flow.redirect_uri,
            "state": flow.state,
            "code_challenge": flow.challenge,
            "code_challenge_method": "S256",
        }
    )


def _code_form(action: str, token: str, label: str, button: str, extra: str = "") -> str:
    return (
        f"<form method='post' action='{action}'>"
        f"<input type='hidden' name='token' value='{html.escape(token)}'>"
        f"<label for='code'>{label}</label>"
        "<input id='code' name='code' inputmode='numeric' autocomplete='one-time-code' "
        "pattern='[0-9]{6}' maxlength='6' required>"
        f"{extra}<button type='submit'>{button}</button></form>"
    )


def _attempts(left: int | None) -> str:
    count = left or 0
    return f"That code didn't match. {count} attempt{'' if count == 1 else 's'} left."


def create_app(
    idp: FakeIdentityProvider | None = None, staff: StaffSignIn | None = None
) -> FastAPI:
    _local_only()
    signer = idp or provider()
    sign_in = staff or StaffSignIn()
    flows: dict[str, _Flow] = {}  # pending email-code sign-in token -> its OAuth request
    grants: dict[str, _Grant] = {}
    refresh_tokens: dict[str, str] = {}  # refresh token -> subject; each is single use
    app = FastAPI(title="Abacus local sign-in", docs_url=None, redoc_url=None, openapi_url=None)
    # The SPA posts to /token from its own origin (the browser half of PKCE).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(SPA_ORIGINS),
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )
    base = f"http://{HOST}:{PORT}"

    @app.get("/.well-known/openid-configuration")
    async def discovery() -> JSONResponse:
        return JSONResponse(
            {
                "issuer": ISSUER,
                "authorization_endpoint": f"{base}/authorize",
                "token_endpoint": f"{base}/token",
                "jwks_uri": f"{base}/jwks",
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
            }
        )

    @app.get("/jwks")
    async def jwks() -> Response:
        return Response(signer.jwks(), media_type="application/json")

    @app.get("/authorize")
    async def authorize(request: Request) -> Response:
        q = request.query_params
        if (
            q.get("response_type") != "code"
            or q.get("client_id") != CLIENT_ID
            or q.get("redirect_uri") not in REDIRECT_URIS
            or q.get("code_challenge_method") != "S256"
            or not q.get("code_challenge")
            or not q.get("state")
        ):
            return _error(400, "invalid_request")
        hidden = "".join(
            f'<input type="hidden" name="{name}" value="{html.escape(q.get(name, ""))}">'
            for name in ("redirect_uri", "state", "code_challenge")
        )
        buttons = "".join(
            f'<button name="subject" value="{html.escape(subject)}">{html.escape(label)}</button>'
            for subject, label in DEV_USERS
        )
        email_form = (
            "<h2>Sign in with a work email</h2>"
            f"<form method='post' action='/authorize/email'>{hidden}"
            "<label for='email'>Work email</label>"
            "<input id='email' name='email' type='email' autocomplete='email' "
            "placeholder='name@brightwaterhale.com' required>"
            "<button type='submit'>Continue</button></form>"
        )
        return _page(
            "Sign in (local)",
            "<h1>Sign in (local)</h1><p>Choose a seeded dev user.</p>"
            f"<form method='post' action='/authorize'>{hidden}{buttons}</form>{email_form}",
        )

    # --- the hosted email-code sign-in (F-04-T27; SHL-06a to f) ---

    def _code_page(token: str, error: str | None = None) -> HTMLResponse:
        flow, email = flows[token], sign_in.email_of(token) or ""
        alert = f"<p role='alert'>{html.escape(error)}</p>" if error else ""
        return _page(
            "Check your email",
            "<h1>Check your email</h1>"
            f"<p>We sent a 6-digit code to {html.escape(email)}. It expires in 10 minutes.</p>"
            f"{alert}{_code_form('/authorize/code', token, 'Code', 'Continue')}"
            f"<p><a href='/authorize?{html.escape(_authorize_query(flow))}'>"
            "Use a different email</a></p>",
        )

    def _mfa_page(token: str, error: str | None = None) -> HTMLResponse:
        alert = f"<p role='alert'>{html.escape(error)}</p>" if error else ""
        trust = (
            "<p><input id='trust' name='trust' type='checkbox'>"
            "<label for='trust'>Trust this device for 30 days</label></p>"
        )
        form = _code_form("/authorize/mfa", token, "Authenticator code", "Verify", trust)
        return _page(
            "Two-step verification",
            "<h1>Two-step verification</h1><p>Enter the code from your authenticator app.</p>"
            f"{alert}{form}",
        )

    def _locked_page(until: datetime) -> HTMLResponse:
        return _page(
            "Account locked",
            "<h1>Account locked</h1><p>Too many incorrect codes. "
            f"Try again at {try_again_at(until)}, or ask "
            f"{html.escape(it_security_person())} (IT / Security) to unlock your account.</p>",
        )

    async def _form(request: Request) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}

    @app.post("/authorize/email")
    async def email_start(request: Request) -> Response:
        form = await _form(request)
        redirect_uri = form.get("redirect_uri", "")
        if redirect_uri not in REDIRECT_URIS or not form.get("state") or not form.get("email"):
            return _error(400, "invalid_request")
        token = sign_in.start(form["email"])
        flows[token] = _Flow(redirect_uri, form["state"], form.get("code_challenge", ""))
        return _code_page(token)

    @app.post("/authorize/code")
    async def email_code(request: Request) -> Response:
        form = await _form(request)
        token = form.get("token", "")
        if token not in flows:
            return _error(400, "invalid_request")
        outcome = sign_in.submit_code(token, form.get("code", ""))
        if outcome.state == "mfa_required":
            return _mfa_page(token)
        if outcome.state == "locked" and outcome.locked_until is not None:
            return _locked_page(outcome.locked_until)
        if outcome.state == "expired":
            return _code_page(
                token, "That code has expired. Use a different email to start again."
            )
        if outcome.state == "wrong_code":
            return _code_page(token, _attempts(outcome.attempts_left))
        return _error(400, "invalid_request")

    @app.post("/authorize/mfa")
    async def email_mfa(request: Request) -> Response:
        form = await _form(request)
        token = form.get("token", "")
        flow = flows.get(token)
        if flow is None:
            return _error(400, "invalid_request")
        outcome = sign_in.submit_totp(token, form.get("code", ""))
        if outcome.state == "signed_in" and outcome.subject is not None:
            del flows[token]
            code = secrets.token_urlsafe(32)
            grants[code] = _Grant(
                outcome.subject,
                flow.redirect_uri,
                flow.challenge,
                system_now().timestamp() + CODE_SECONDS,
            )
            query = urlencode({"code": code, "state": flow.state})
            return RedirectResponse(f"{flow.redirect_uri}?{query}", status_code=303)
        if outcome.state == "locked" and outcome.locked_until is not None:
            return _locked_page(outcome.locked_until)
        if outcome.state == "wrong_code":
            return _mfa_page(token, _attempts(outcome.attempts_left))
        return _error(400, "invalid_request")

    @app.get("/_harness/code")
    async def harness_code(email: str) -> JSONResponse:
        """The last emailed sign-in code for a staff email (what `mail().latest()` reads)."""
        return JSONResponse({"code": sign_in.latest_code(email)})

    @app.get("/_harness/totp")
    async def harness_totp(email: str) -> JSONResponse:
        """The code the person's authenticator app shows now."""
        return JSONResponse({"code": sign_in.current_totp(email)})

    @app.post("/authorize")
    async def approve(request: Request) -> Response:
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        redirect_uri, subject = form.get("redirect_uri", ""), form.get("subject", "")
        if redirect_uri not in REDIRECT_URIS or subject not in dict(DEV_USERS):
            return _error(400, "invalid_request")
        code = secrets.token_urlsafe(32)
        grants[code] = _Grant(
            subject,
            redirect_uri,
            form.get("code_challenge", ""),
            system_now().timestamp() + CODE_SECONDS,
        )
        query = urlencode({"code": code, "state": form.get("state", "")})
        return RedirectResponse(f"{redirect_uri}?{query}", status_code=303)

    @app.post("/token")
    async def token(request: Request) -> JSONResponse:
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        if form.get("grant_type") == "refresh_token":
            subject = refresh_tokens.pop(form.get("refresh_token", ""), None)
            if subject is None or form.get("client_id") != CLIENT_ID:
                return _error(400, "invalid_grant")
            return _tokens(subject)
        now = system_now().timestamp()
        for expired in [code for code, g in grants.items() if g.expires < now]:
            del grants[expired]
        grant = grants.pop(form.get("code", ""), None)  # single use, even when it fails
        verifier = form.get("code_verifier", "")
        if (
            form.get("grant_type") != "authorization_code"
            or not _VERIFIER.fullmatch(verifier)
            or form.get("client_id") != CLIENT_ID
            or grant is None
            or grant.expires < system_now().timestamp()
            or form.get("redirect_uri") != grant.redirect_uri
            or _s256(verifier) != grant.challenge
        ):
            return _error(400, "invalid_grant")
        return _tokens(grant.subject)

    def _email_of(subject: str) -> str:
        found = sign_in.by_subject(subject)
        return found.email if found else f"{subject}@dev.abacus.local"

    def _tokens(subject: str) -> JSONResponse:
        # A provider-verified email, as WorkOS sends (SPEC-015, SPEC-024 sign-up).
        # Signed in with MFA just now (TASK-041 D3): fresh-MFA screens work locally, and still
        # ask again once the token is older than 15 minutes.
        access = signer.token(
            subject,
            mfa=True,
            expires_in=TOKEN_SECONDS,
            email=_email_of(subject),
            email_verified=True,
        )
        refresh = secrets.token_urlsafe(32)
        refresh_tokens[refresh] = subject
        return JSONResponse(
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": TOKEN_SECONDS,
                "refresh_token": refresh,
            },
            headers={"Cache-Control": "no-store"},
        )

    return app


def main(argv: list[str]) -> int:
    _local_only()
    if argv[:1] == ["--jwks"]:
        sys.stdout.write(provider().jwks() + "\n")
        return 0
    import uvicorn  # the dev server; imported here so the app factory stays import-light

    uvicorn.run(create_app(), host=HOST, port=PORT, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
