"""The console BFF's routes (G-04-T14; TASK-8548; DEC-5532). PROTECTED.

`/v1/platform/auth/*` under the `PRE_SESSION` marker (routing.PRE_SESSION_PATHS): a sign-in is a
top-level navigation to the staff provider; the callback sets the `__Host-abacus-console` cookie
and lands on the console's own `/signin/callback` (with `?to=` or `?error=`); a refresh needs the
cookie, `X-Abacus-CSRF: 1` and the console's own Origin and answers a memory-only access token; a
sign-out ends the session behind the cookie (same CSRF and Origin rules). Every answer is
`Cache-Control: no-store`.
"""

from __future__ import annotations

from typing import Annotated, cast
from urllib.parse import urlencode

from fastapi import Cookie, Header, Query
from fastapi.responses import JSONResponse, RedirectResponse, Response

from abacus.modules.identity.platform_staff_session import (
    COOKIE_NAME,
    SPA_CALLBACK_PATH,
    begin_sign_in,
    complete_sign_in,
    console_origin,
    end_session,
    refresh_session,
)
from abacus.modules.identity.routes import AuthRedirectOut, SessionTokenOut, SignedOutOut
from abacus.modules.identity.routing import PRE_SESSION, AbacusRouter
from abacus.modules.identity.staff_session import (
    ABSOLUTE_SECONDS,
    CSRF_HEADER,
    MAX_RETURN_TO,
    RefreshReused,
    SessionExpired,
    SignInRefused,
)

console_auth_router = AbacusRouter(prefix="/v1/platform/auth", tags=["console auth"])


def _set_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        value,
        max_age=ABSOLUTE_SECONDS,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


def _same_console(csrf: str | None, origin: str | None) -> bool:
    return csrf == "1" and origin is not None and origin.rstrip("/") == console_origin()


def _refusal(detail: str, status: int = 401) -> JSONResponse:
    response = JSONResponse({"detail": detail}, status_code=status)
    _clear_cookie(response)
    return cast(JSONResponse, _no_store(response))


@console_auth_router.get(
    "/sign-in",
    action=PRE_SESSION,
    response_model=AuthRedirectOut,
    status_code=302,
    errors=(503,),
)
async def console_sign_in_route(
    return_to: Annotated[str | None, Query(max_length=MAX_RETURN_TO)] = None,
    reauthenticate: bool = False,
) -> Response:
    """To the staff provider's authorize page with server-side state and PKCE (10 minutes)."""
    return _no_store(
        RedirectResponse(
            await begin_sign_in(return_to, reauthenticate=reauthenticate), status_code=302
        )
    )


@console_auth_router.get(
    "/callback",
    action=PRE_SESSION,
    response_model=AuthRedirectOut,
    status_code=302,
    errors=(503,),
)
async def console_callback_route(
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
    previous: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """Start the session, set the cookie and land on the console's callback page; a refusal lands
    there with its code instead."""
    landing = console_origin() + SPA_CALLBACK_PATH
    try:
        started = await complete_sign_in(code, state, previous_cookie=previous)
    except SignInRefused as refused:
        response = RedirectResponse(
            f"{landing}?{urlencode({'error': refused.code})}", status_code=302
        )
        _clear_cookie(response)
        return _no_store(response)
    response = RedirectResponse(f"{landing}?{urlencode({'to': started.return_to})}", 302)
    _set_cookie(response, started.cookie)
    return _no_store(response)


@console_auth_router.post(
    "/refresh",
    action=PRE_SESSION,
    response_model=SessionTokenOut,
    errors=(503,),
)
async def console_refresh_route(
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    origin: Annotated[str | None, Header()] = None,
    activity: Annotated[str | None, Header(alias="X-Abacus-Activity", max_length=16)] = None,
) -> Response:
    """Cookie-authenticated, with the CSRF header and the console's own Origin. Only a refresh
    marked `X-Abacus-Activity: user` moves the idle clock (as the firm BFF, DEC-535)."""
    if not _same_console(csrf, origin):
        return _no_store(JSONResponse({"detail": "forbidden"}, status_code=403))
    try:
        refreshed = await refresh_session(cookie, active=activity == "user")
    except RefreshReused:
        return _refusal("session_refresh_reused")
    except SessionExpired:
        return _refusal("session_expired")
    body = SessionTokenOut(access_token=refreshed.access_token, expires_in=refreshed.expires_in)
    response = JSONResponse(body.model_dump())
    _set_cookie(response, refreshed.cookie)
    return _no_store(response)


@console_auth_router.post(
    "/sign-out",
    action=PRE_SESSION,
    response_model=SignedOutOut,
)
async def console_sign_out_route(
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    origin: Annotated[str | None, Header()] = None,
) -> Response:
    """End the session behind the cookie and clear it; the old value no longer refreshes."""
    if not _same_console(csrf, origin):
        return _no_store(JSONResponse({"detail": "forbidden"}, status_code=403))
    ended = await end_session(cookie)
    response = JSONResponse(SignedOutOut(ended=ended).model_dump())
    _clear_cookie(response)
    return _no_store(response)
