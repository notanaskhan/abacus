"""Every route declares exactly one action and checks it (ADR-012, ADR-027). PROTECTED.
TASK-007 design §6.

    router = AbacusRouter(prefix="/v1/engagements")

    @router.post("", action="engagement.create", response_model=EngagementOut)
    async def create(body: EngagementIn, ctx: AuthContext = Depends(current_context)) -> ...:
        await authorise(ctx, "engagement.create", Resource(ctx.tenant_id))

The router attaches authentication to every route, so no route can forget it. A route that
returns a success without a successful `authorise` (or a `visible` filter) for its declared action
is turned into a 500 and logged: the response it built never reaches the caller. The guard runs
after the handler, so it can't undo a write: authorise first, before touching anything.
`SELF` is for routes about the signed-in user themself (`/v1/me`), which need no tenant.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from enum import Enum
from typing import Annotated, Final, TypeVar, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from abacus.kernel.classification import classified
from abacus.kernel.logging import get_logger
from abacus.modules.identity.authz import recording_checks
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.service import (
    TENANT_HEADER,
    NoActiveTenant,
    SignedIn,
    Unauthenticated,
    choose_tenant,
    sign_in,
    verify_bearer,
)
from abacus.modules.identity.support import (
    SUPPORT_HEADER,
    Staff,
    SupportSessionInactive,
    audit_support_request,
    staff_from_token,
    support_context,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity

_Endpoint = TypeVar("_Endpoint", bound=Callable[..., object])
SELF: Final = "self"
# SPEC-012 (TASK-027 D5): staff-token routes. Staff aren't firm members, so no firm action applies;
# they are authorised by the staff token and the session rules in `identity.support`.
STAFF: Final = "staff"
# SPEC-013 (Q3): a firm member acting only on their own rows (their notifications). No firm matrix
# action applies; the service filters to the caller, and support contexts are refused.
OWN: Final = "own"
# SPEC-015 (TASK-030 D2): a verified firm-issuer identity with no account or membership needed
# (accepting a client invitation). The service binds it to the invited email.
IDENTITY: Final = "identity"


class ErrorOut(BaseModel):
    detail: Annotated[str, classified("public")]


class FieldErrorOut(BaseModel):
    loc: Annotated[list[str | int], classified("public")]
    msg: Annotated[str, classified("public")]
    type: Annotated[str, classified("public")]


class ValidationErrorOut(BaseModel):
    """What a 422 says: where and what, never the submitted value (abacus.api.app)."""

    detail: Annotated[list[FieldErrorOut], classified("public")]


# Every route documents the errors it can return, so the generated client types them (ADR-013).
_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorOut, "description": "Not authenticated"},
    403: {"model": ErrorOut, "description": "Forbidden"},
    404: {"model": ErrorOut, "description": "Not found"},
    422: {"model": ValidationErrorOut, "description": "Invalid request"},
}
# Further errors a route may declare (`errors=`): conflicts with the resource's state, and an
# unavailable dependency (kernel.errors.DomainConflict, ServiceUnavailable).
_OPTIONAL_RESPONSES: dict[int, dict[str, object]] = {
    409: {"model": ErrorOut, "description": "Conflict with the resource's state"},
    503: {"model": ErrorOut, "description": "Service unavailable"},
}
ACTION_KEY: Final = "x-abacus-action"
_log = get_logger(__name__)


async def current_signed_in(
    authorization: Annotated[str | None, Header()] = None,
) -> SignedIn:
    try:
        return await sign_in(authorization)
    except Unauthenticated:
        raise HTTPException(
            401, "not authenticated", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except NoActiveTenant:
        raise HTTPException(403, "forbidden") from None


async def current_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_abacus_tenant: Annotated[str | None, Header(alias=TENANT_HEADER)] = None,
    x_support_session: Annotated[
        str | None, Header(alias=SUPPORT_HEADER, include_in_schema=False)
    ] = None,
) -> AuthContext:
    if x_support_session is not None:
        return await _support_context(request, authorization, x_abacus_tenant, x_support_session)
    signed_in = await current_signed_in(authorization)
    try:
        return choose_tenant(signed_in, x_abacus_tenant)
    except NoActiveTenant:
        raise HTTPException(403, "forbidden") from None


async def _support_context(
    request: Request, authorization: str | None, firm: str | None, session: str
) -> AuthContext:
    """SPEC-012: read-only, one firm, an active session, each request audited first (fail
    closed). Writes are refused here as well as by the matrix (TASK-027 D2)."""
    if request.method not in ("GET", "HEAD"):
        raise HTTPException(403, "forbidden")
    try:
        ctx = await support_context(authorization, firm, session)
    except SupportSessionInactive:
        raise HTTPException(401, "support_session_inactive") from None
    route = cast(object, request.scope.get("route"))
    template = route.path if isinstance(route, APIRoute) else "unmatched"
    try:
        await audit_support_request(ctx, template, request.method)
    except Exception as exc:
        _log.error("support.audit_failed", error=type(exc).__name__)
        raise HTTPException(503, "service unavailable") from None
    return ctx


async def current_identity(
    authorization: Annotated[str | None, Header()] = None,
) -> VerifiedIdentity:
    """A token from the firm-user issuer, verified; no account required (`IDENTITY` routes)."""
    try:
        return verify_bearer(authorization)
    except (InvalidToken, Unauthenticated):
        raise HTTPException(
            401, "not authenticated", headers={"WWW-Authenticate": "Bearer"}
        ) from None


async def current_member(
    ctx: Annotated[AuthContext, Depends(current_context)],
) -> AuthContext:
    """A firm member themself (`OWN` routes): never a break-glass support context."""
    if ctx.is_support:
        raise HTTPException(403, "forbidden")
    return ctx


async def current_staff(authorization: Annotated[str | None, Header()] = None) -> Staff:
    """A platform staff member (the staff issuer, with MFA): staff routes only (`STAFF`)."""
    try:
        return staff_from_token(authorization)
    except InvalidToken:
        raise HTTPException(
            401, "not authenticated", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def declared_action(route: APIRoute) -> str | None:
    extra = route.openapi_extra or {}
    action = extra.get(ACTION_KEY)
    return action if isinstance(action, str) else None


class AbacusRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[object, object, Response]]:
        handler = super().get_route_handler()
        action = declared_action(self)
        path = self.path

        async def guarded(request: Request) -> Response:
            with recording_checks() as checked:
                response = await handler(request)
            if (
                action not in (SELF, STAFF, OWN, IDENTITY)
                and action not in checked
                and response.status_code < 400
            ):
                _log.error("authz.unchecked_route", path=path, action=str(action))
                return JSONResponse({"detail": "internal error"}, status_code=500)
            return response

        return guarded


class AbacusRouter(APIRouter):
    """An APIRouter whose routes must declare an action and a response model."""

    def __init__(self, *, prefix: str = "", tags: Sequence[str | Enum] | None = None) -> None:
        super().__init__(prefix=prefix, tags=list(tags or []), route_class=AbacusRoute)

    def add_api_route(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        endpoint: Callable[..., object],
        *,
        action: str,
        response_model: object,
        methods: Sequence[str],
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> None:
        if action not in (SELF, STAFF, OWN, IDENTITY) and action not in RULES:
            raise ValueError(f"route {path}: action {action!r} is not in the permission matrix")
        if response_model is None:
            raise ValueError(f"route {path}: a response model is required")
        auth = {
            SELF: current_signed_in,
            STAFF: current_staff,
            OWN: current_member,
            IDENTITY: current_identity,
        }.get(action, current_context)
        super().add_api_route(
            path,
            endpoint,
            response_model=response_model,
            methods=list(methods),
            status_code=status_code,
            dependencies=[Depends(auth)],
            openapi_extra={ACTION_KEY: action},
            responses={**_RESPONSES, **{code: _OPTIONAL_RESPONSES[code] for code in errors}},
        )

    def add_api_websocket_route(self, *args: object, **kwargs: object) -> None:
        raise TypeError("websocket routes are not supported: they would bypass the action check")

    def websocket(  # pyright: ignore[reportIncompatibleMethodOverride] -- refuses
        self, *args: object, **kwargs: object
    ) -> None:
        raise TypeError("websocket routes are not supported: they would bypass the action check")

    def add_route(self, *args: object, **kwargs: object) -> None:
        raise TypeError("plain Starlette routes are not supported: declare an action")

    def _verb(
        self,
        method: str,
        path: str,
        action: str,
        response_model: object,
        status_code: int | None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        def register(endpoint: _Endpoint) -> _Endpoint:
            self.add_api_route(
                path,
                endpoint,
                action=action,
                response_model=response_model,
                methods=[method],
                status_code=status_code,
                errors=errors,
            )
            return endpoint

        return register

    def get(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        *,
        action: str,
        response_model: object,
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("GET", path, action, response_model, status_code, errors)

    def post(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        *,
        action: str,
        response_model: object,
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("POST", path, action, response_model, status_code, errors)

    def put(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        *,
        action: str,
        response_model: object,
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("PUT", path, action, response_model, status_code, errors)

    def patch(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        *,
        action: str,
        response_model: object,
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("PATCH", path, action, response_model, status_code, errors)

    def delete(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self,
        path: str,
        *,
        action: str,
        response_model: object,
        status_code: int | None = None,
        errors: Sequence[int] = (),
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("DELETE", path, action, response_model, status_code, errors)
