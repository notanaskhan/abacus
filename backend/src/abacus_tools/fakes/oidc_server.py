"""A local OpenID Connect sign-in server for the SPA (TASK-012 Q2; SPEC-000 §20). Local only.

Run: python -m abacus_tools.fakes.oidc_server        (serves on 127.0.0.1:9000)
     python -m abacus_tools.fakes.oidc_server --jwks (prints the public key set for the API)

The browser flow is authorization code with PKCE (S256), as WorkOS will be (TASK-014):
`/authorize` shows the seeded dev users (`abacus_tools.local.seed_dev`); choosing one redirects
back with a single-use code (60 s), which `/token` exchanges for an RS256 access token (10 min)
signed by `FakeIdentityProvider`. The signing key is kept in `backend/.local/oidc-key.pem`
(gitignored) so tokens survive restarts; `make dev` gives the API this server's JWKS. Refuses to
run outside the local and test environments.
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from abacus.kernel.config import settings
from abacus_tools.fakes.identity import AUDIENCE, ISSUER, FakeIdentityProvider

HOST, PORT = "127.0.0.1", 9000
CLIENT_ID = "abacus-web"
REDIRECT_URIS = frozenset(
    {
        "http://localhost:5173/signin/callback",
        "http://127.0.0.1:5173/signin/callback",
    }
)
# The dev users `seed_dev` creates (subject, display name). Sign-in is a choice, not a password.
DEV_USERS = (
    ("dev-leader", "Dana Leader (practice leader)"),
    ("dev-staff", "Sam Staff (staff)"),
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


def create_app(idp: FakeIdentityProvider | None = None) -> FastAPI:
    _local_only()
    signer = idp or provider()
    grants: dict[str, _Grant] = {}
    app = FastAPI(title="Abacus local sign-in", docs_url=None, redoc_url=None, openapi_url=None)
    # The SPA posts to /token from its own origin (the browser half of PKCE).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted({uri.removesuffix("/signin/callback") for uri in REDIRECT_URIS}),
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
                "grant_types_supported": ["authorization_code"],
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
        page = (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<title>Sign in (local)</title></head><body><main><h1>Sign in (local)</h1>"
            f"<p>Choose a seeded dev user.</p><form method='post' action='/authorize'>{hidden}"
            f"{buttons}</form></main></body></html>"
        )
        return HTMLResponse(page)

    @app.post("/authorize")
    async def approve(request: Request) -> Response:
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        redirect_uri, subject = form.get("redirect_uri", ""), form.get("subject", "")
        if redirect_uri not in REDIRECT_URIS or subject not in dict(DEV_USERS):
            return _error(400, "invalid_request")
        code = secrets.token_urlsafe(32)
        grants[code] = _Grant(
            subject, redirect_uri, form.get("code_challenge", ""), time.time() + CODE_SECONDS
        )
        query = urlencode({"code": code, "state": form.get("state", "")})
        return RedirectResponse(f"{redirect_uri}?{query}", status_code=303)

    @app.post("/token")
    async def token(request: Request) -> JSONResponse:
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        now = time.time()
        for expired in [code for code, g in grants.items() if g.expires < now]:
            del grants[expired]
        grant = grants.pop(form.get("code", ""), None)  # single use, even when it fails
        verifier = form.get("code_verifier", "")
        if (
            form.get("grant_type") != "authorization_code"
            or not _VERIFIER.fullmatch(verifier)
            or form.get("client_id") != CLIENT_ID
            or grant is None
            or grant.expires < time.time()
            or form.get("redirect_uri") != grant.redirect_uri
            or _s256(verifier) != grant.challenge
        ):
            return _error(400, "invalid_grant")
        # A provider-verified email, as WorkOS sends (SPEC-015, SPEC-024 sign-up).
        access = signer.token(
            grant.subject,
            expires_in=TOKEN_SECONDS,
            email=f"{grant.subject}@dev.abacus.local",
            email_verified=True,
        )
        return JSONResponse(
            {"access_token": access, "token_type": "Bearer", "expires_in": TOKEN_SECONDS},
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
