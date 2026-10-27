"""The portal's pre-session family (P-08-T10; ADR-168; SPEC-320 AC-6 to AC-8): start, verify,
resend and refresh answer before any session, under the `PRE_SESSION` marker; sign-out is the
person's own (`OWN`). With `portal.sign_in_v2` off for a firm no code is sent for its host, and
every start still answers the same 202.

The second step (P-08-T17; SPEC-320 AC-10, AC-11): a verify for a person the MFA floor covers
answers `mfa_required` or `mfa_setup_required` with a single-use `mfa_token` and no session;
`/mfa`, `/mfa/setup` and `/mfa/setup/verify` finish it. A trusted device is the
`__Host-abacus-portal-device` cookie.

Errors carry identifier facts only: 401 `code_mismatch {tries_left}`, 423 `sign_in_locked
{locked_until}`, 410 `code_expired`, 429 `resend_too_soon {resend_available_at}`; 401
`mfa_mismatch {tries_left}`, 423 `mfa_locked {locked_until}`, 410 `mfa_expired`, 503
`mfa_unavailable`.

The pause and links (P-08-T21; SPEC-320 AC-14, AC-20): while the host's firm has the
`portal_sign_in` control on, start, verify, resend and the second-step routes answer 503
`sign_in_paused` (refresh and signed-in routes are untouched, so sessions carry on). A start with
a `link_token` that can't be used answers 404 `link_expired`, one answer for every reason."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header
from fastapi.responses import JSONResponse, Response

from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.portal_contract import (
    PortalMfaIn,
    PortalMfaSetupIn,
    PortalMfaSetupOut,
    PortalMfaSetupVerifyIn,
    PortalMfaSetupVerifyOut,
    PortalSignInResendIn,
    PortalSignInStartIn,
    PortalSignInStartOut,
    PortalSignInVerifyIn,
    PortalSignInVerifyOut,
)
from abacus.modules.identity.portal_idp import PortalIdpUnavailable
from abacus.modules.identity.portal_mfa import (
    DEVICE_COOKIE,
    MfaExpired,
    MfaLocked,
    MfaMismatch,
    second_step,
    setup_second_step,
    verify_setup,
)
from abacus.modules.identity.portal_session import (
    COOKIE_NAME,
    CodeExpired,
    CodeMismatch,
    LinkUnusable,
    PortalSessionEnded,
    PortalTokens,
    ResendTooSoon,
    SecondStepRequired,
    SignInLocked,
    SignInPaused,
    check_not_paused,
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


def _session_out(tokens: PortalTokens) -> PortalSignInVerifyOut:
    return PortalSignInVerifyOut(
        state="signed_in",
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        landing=tokens.landing,  # pyright: ignore[reportArgumentType] -- a PortalLanding code
    )


def _signed_in(tokens: PortalTokens) -> Response:
    response = JSONResponse(_session_out(tokens).model_dump(mode="json", exclude_none=True))
    _set_cookie(response, tokens.cookie)
    return _no_store(response)


def _paused() -> Response:
    return _error(503, "sign_in_paused")


def _mfa_error(exc: Exception) -> Response:
    if isinstance(exc, MfaMismatch):
        return _error(401, "mfa_mismatch", {"tries_left": exc.tries_left})
    if isinstance(exc, MfaLocked):
        return _error(423, "mfa_locked", {"locked_until": _iso(exc.locked_until)})
    if isinstance(exc, PortalIdpUnavailable):
        return _error(503, "mfa_unavailable")
    return _error(410, "mfa_expired")


@portal_auth_router.post(
    "/start",
    action=PRE_SESSION,
    response_model=PortalSignInStartOut,
    status_code=202,
    errors=(503,),
)
async def portal_start_route(
    body: PortalSignInStartIn, host: Annotated[str | None, Header()] = None
) -> Response:
    """Always 202 with the same shape, for any email on any host; 404 `link_expired` for a link
    that can't be used; 503 `sign_in_paused`."""
    try:
        await check_not_paused(host)
        found = await start_sign_in(
            host,
            body.email,
            invitation_token=body.invitation_token,
            link_token=body.link_token,
        )
    except SignInPaused:
        return _paused()
    except LinkUnusable:
        return _error(404, "link_expired")
    out = PortalSignInStartOut(
        challenge_id=found.challenge_id,
        code_expires_at=found.code_expires_at,
        resend_available_at=found.resend_available_at,
    )
    return _no_store(JSONResponse(out.model_dump(mode="json"), status_code=202))


@portal_auth_router.post(
    "/verify",
    action=PRE_SESSION,
    response_model=PortalSignInVerifyOut,
    errors=(410, 423, 503),
)
async def portal_verify_route(
    body: PortalSignInVerifyIn,
    host: Annotated[str | None, Header()] = None,
    previous: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    device: Annotated[str | None, Cookie(alias=DEVICE_COOKIE)] = None,
) -> Response:
    try:
        await check_not_paused(host)
        tokens = await verify_code(
            host, body.challenge_id, body.code, previous_cookie=previous, device_cookie=device
        )
    except SignInPaused:
        return _paused()
    except SecondStepRequired as step:
        out = PortalSignInVerifyOut(state=step.state, mfa_token=step.mfa_token)
        return _no_store(JSONResponse(out.model_dump(mode="json", exclude_none=True)))
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
    errors=(410, 429, 503),
)
async def portal_resend_route(
    body: PortalSignInResendIn, host: Annotated[str | None, Header()] = None
) -> Response:
    try:
        await check_not_paused(host)
        found = await resend_code(host, body.challenge_id)
    except SignInPaused:
        return _paused()
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


@portal_auth_router.post(
    "/mfa", action=PRE_SESSION, response_model=PortalSignInVerifyOut, errors=(410, 423, 503)
)
async def portal_mfa_route(
    body: PortalMfaIn,
    host: Annotated[str | None, Header()] = None,
    user_agent: Annotated[str | None, Header()] = None,
    previous: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """The second step: a TOTP or a backup code; "trust this device" sets the device cookie."""
    try:
        await check_not_paused(host)
        done = await second_step(
            host,
            body.mfa_token,
            totp=body.totp,
            backup_code=body.backup_code,
            trust_device=body.trust_device,
            previous_cookie=previous,
            user_agent=user_agent,
        )
    except SignInPaused:
        return _paused()
    except (MfaMismatch, MfaLocked, MfaExpired, PortalIdpUnavailable) as exc:
        return _mfa_error(exc)
    response = _signed_in(done.tokens)
    if done.device_cookie is not None:
        response.set_cookie(
            DEVICE_COOKIE,
            done.device_cookie,
            max_age=done.device_days * 86400,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
    return response


@portal_auth_router.post(
    "/mfa/setup", action=PRE_SESSION, response_model=PortalMfaSetupOut, errors=(410, 503)
)
async def portal_mfa_setup_route(
    body: PortalMfaSetupIn, host: Annotated[str | None, Header()] = None
) -> Response:
    """A new TOTP factor for a person with none: the QR code's URI and the key, once."""
    try:
        await check_not_paused(host)
        key = await setup_second_step(host, body.mfa_token)
    except SignInPaused:
        return _paused()
    except (MfaExpired, PortalIdpUnavailable) as exc:
        return _mfa_error(exc)
    out = PortalMfaSetupOut(otpauth_uri=key.otpauth_uri, manual_key=key.manual_key)
    return _no_store(JSONResponse(out.model_dump(mode="json")))


@portal_auth_router.post(
    "/mfa/setup/verify",
    action=PRE_SESSION,
    response_model=PortalMfaSetupVerifyOut,
    errors=(410, 423, 503),
)
async def portal_mfa_setup_verify_route(
    body: PortalMfaSetupVerifyIn,
    host: Annotated[str | None, Header()] = None,
    previous: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """The new factor's first code: enrolled, 8 backup codes once, and the session."""
    try:
        await check_not_paused(host)
        done = await verify_setup(host, body.mfa_token, body.totp, previous_cookie=previous)
    except SignInPaused:
        return _paused()
    except (MfaMismatch, MfaLocked, MfaExpired, PortalIdpUnavailable) as exc:
        return _mfa_error(exc)
    out = PortalMfaSetupVerifyOut(
        backup_codes=list(done.backup_codes), session=_session_out(done.tokens)
    )
    response = JSONResponse(out.model_dump(mode="json", exclude_none=True))
    _set_cookie(response, done.tokens.cookie)
    return _no_store(response)


@portal_auth_router.post("/refresh", action=PRE_SESSION, response_model=PortalSignInVerifyOut)
async def portal_refresh_route(
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    origin: Annotated[str | None, Header()] = None,
    host: Annotated[str | None, Header()] = None,
    activity: Annotated[str | None, Header(alias="X-Abacus-Activity", max_length=16)] = None,
) -> Response:
    """Cookie-authenticated, with the CSRF header and the portal host's own Origin. Only a
    refresh marked `X-Abacus-Activity: user` moves the idle clock; an absent mark is never
    activity (DEC-583)."""
    if csrf != "1" or origin is None or host is None or origin.rstrip("/") != f"https://{host}":
        return _error(403, "forbidden")
    try:
        tokens = await refresh_portal_session(cookie, host, active=activity == "user")
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
    """End the person's own portal session (the token signed out with, and the cookie's) and
    clear the cookie."""
    ended = await sign_out_portal(ctx, cookie)
    response = JSONResponse(SignedOutOut(ended=ended).model_dump())
    _clear_cookie(response)
    return _no_store(response)
