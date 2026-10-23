"""The portal's pre-session family (P-08-T10; ADR-168; SPEC-320 AC-6 to AC-8): start, verify,
resend and refresh answer before any session, under the `PRE_SESSION` marker; sign-out is the
person's own (`OWN`). With `portal.sign_in_v2` off for a firm no code is sent for its host, and
every start still answers the same 202.

Errors carry identifier facts only: 401 `code_mismatch {tries_left}`, 423 `sign_in_locked
{locked_until}`, 410 `code_expired`, 429 `resend_too_soon {resend_available_at}`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header
from fastapi.responses import JSONResponse, Response

from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.portal_contract import (
    PortalSignInResendIn,
    PortalSignInStartIn,
    PortalSignInStartOut,
    PortalSignInVerifyIn,
    PortalSignInVerifyOut,
)
from abacus.modules.identity.portal_session import (
    COOKIE_NAME,
    CodeExpired,
    CodeMismatch,
    PortalSessionEnded,
    PortalTokens,
    ResendTooSoon,
    SignInLocked,
    refresh_portal_session,
    resend_code,
    sign_out_portal,
    start_sign_in,
    verify_code,
)
from abacus.modules.identity.routes import SignedOutOut
from abacus.modules.identity.routing import OWN, PRE_SESSION, AbacusRouter, current_member
from abacus.modules.identity.staff_session import CSRF_HEADER

portal_auth_router = AbacusRouter(prefix="/v1/portal/auth", tags=["portal-auth"])


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


def _error(status: int, detail: str, facts: dict[str, str | int] | None = None) -> Response:
    body: dict[str, object] = {"detail": detail}
    if facts:
        body["facts"] = facts
    return _no_store(JSONResponse(body, status_code=status))


def _set_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        COOKIE_NAME, value, path="/", secure=True, httponly=True, samesite="strict"
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")


def _signed_in(tokens: PortalTokens) -> Response:
    body = PortalSignInVerifyOut(
        state="signed_in",
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        landing=tokens.landing,  # pyright: ignore[reportArgumentType] -- a PortalLanding code
    )
    response = JSONResponse(body.model_dump(mode="json", exclude_none=True))
    _set_cookie(response, tokens.cookie)
    return _no_store(response)


@portal_auth_router.post(
    "/start", action=PRE_SESSION, response_model=PortalSignInStartOut, status_code=202
)
async def portal_start_route(
    body: PortalSignInStartIn, host: Annotated[str | None, Header()] = None
) -> Response:
    """Always 202 with the same shape, for any email on any host."""
    found = await start_sign_in(host, body.email)
    out = PortalSignInStartOut(
        challenge_id=found.challenge_id,
        code_expires_at=found.code_expires_at,
        resend_available_at=found.resend_available_at,
    )
    return _no_store(JSONResponse(out.model_dump(mode="json"), status_code=202))


@portal_auth_router.post(
    "/verify", action=PRE_SESSION, response_model=PortalSignInVerifyOut, errors=(410, 423)
)
async def portal_verify_route(
    body: PortalSignInVerifyIn, host: Annotated[str | None, Header()] = None
) -> Response:
    try:
        tokens = await verify_code(host, body.challenge_id, body.code)
    except CodeMismatch as miss:
        return _error(401, "code_mismatch", {"tries_left": miss.tries_left})
    except SignInLocked as locked:
        return _error(423, "sign_in_locked", {"locked_until": _iso(locked.locked_until)})
    except CodeExpired:
        return _error(410, "code_expired")
    return _signed_in(tokens)


@portal_auth_router.post(
    "/resend",
    action=PRE_SESSION,
    response_model=PortalSignInStartOut,
    status_code=202,
    errors=(410, 429),
)
async def portal_resend_route(
    body: PortalSignInResendIn, host: Annotated[str | None, Header()] = None
) -> Response:
    try:
        found = await resend_code(host, body.challenge_id)
    except ResendTooSoon as soon:
        return _error(
            429, "resend_too_soon", {"resend_available_at": _iso(soon.resend_available_at)}
        )
    except CodeExpired:
        return _error(410, "code_expired")
    out = PortalSignInStartOut(
        challenge_id=found.challenge_id,
        code_expires_at=found.code_expires_at,
        resend_available_at=found.resend_available_at,
    )
    return _no_store(JSONResponse(out.model_dump(mode="json"), status_code=202))


@portal_auth_router.post("/refresh", action=PRE_SESSION, response_model=PortalSignInVerifyOut)
async def portal_refresh_route(
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    origin: Annotated[str | None, Header()] = None,
    host: Annotated[str | None, Header()] = None,
) -> Response:
    """Cookie-authenticated, with the CSRF header and the portal host's own Origin."""
    if csrf != "1" or origin is None or host is None or origin.rstrip("/") != f"https://{host}":
        return _error(403, "forbidden")
    try:
        tokens = await refresh_portal_session(cookie, host)
    except PortalSessionEnded:
        response = _error(401, "session_expired")
        _clear_cookie(response)
        return response
    return _signed_in(tokens)


@portal_auth_router.post("/sign-out", action=OWN, response_model=SignedOutOut)
async def portal_sign_out_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """End the person's own portal session and clear the cookie."""
    ended = await sign_out_portal(ctx, cookie)
    response = JSONResponse(SignedOutOut(ended=ended).model_dump())
    _clear_cookie(response)
    return _no_store(response)
