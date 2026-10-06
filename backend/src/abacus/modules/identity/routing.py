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
from typing import Annotated, Final, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

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
)

_Endpoint = TypeVar("_Endpoint", bound=Callable[..., object])
SELF: Final = "self"


class ErrorOut(BaseModel):
    detail: str


class FieldErrorOut(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorOut(BaseModel):
    """What a 422 says: where and what, never the submitted value (abacus.api.app)."""

    detail: list[FieldErrorOut]


# Every route documents the errors it can return, so the generated client types them (ADR-013).
_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorOut, "description": "Not authenticated"},
    403: {"model": ErrorOut, "description": "Forbidden"},
    404: {"model": ErrorOut, "description": "Not found"},
    422: {"model": ValidationErrorOut, "description": "Invalid request"},
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
    signed_in: Annotated[SignedIn, Depends(current_signed_in)],
    x_abacus_tenant: Annotated[str | None, Header(alias=TENANT_HEADER)] = None,
) -> AuthContext:
    try:
        return choose_tenant(signed_in, x_abacus_tenant)
    except NoActiveTenant:
        raise HTTPException(403, "forbidden") from None


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
            if action != SELF and action not in checked and response.status_code < 400:
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
    ) -> None:
        if action != SELF and action not in RULES:
            raise ValueError(f"route {path}: action {action!r} is not in the permission matrix")
        if response_model is None:
            raise ValueError(f"route {path}: a response model is required")
        auth = current_signed_in if action == SELF else current_context
        super().add_api_route(
            path,
            endpoint,
            response_model=response_model,
            methods=list(methods),
            status_code=status_code,
            dependencies=[Depends(auth)],
            openapi_extra={ACTION_KEY: action},
            responses=_RESPONSES,
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
        self, method: str, path: str, action: str, response_model: object, status_code: int | None
    ) -> Callable[[_Endpoint], _Endpoint]:
        def register(endpoint: _Endpoint) -> _Endpoint:
            self.add_api_route(
                path,
                endpoint,
                action=action,
                response_model=response_model,
                methods=[method],
                status_code=status_code,
            )
            return endpoint

        return register

    def get(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self, path: str, *, action: str, response_model: object, status_code: int | None = None
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("GET", path, action, response_model, status_code)

    def post(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self, path: str, *, action: str, response_model: object, status_code: int | None = None
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("POST", path, action, response_model, status_code)

    def put(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self, path: str, *, action: str, response_model: object, status_code: int | None = None
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("PUT", path, action, response_model, status_code)

    def patch(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self, path: str, *, action: str, response_model: object, status_code: int | None = None
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("PATCH", path, action, response_model, status_code)

    def delete(  # pyright: ignore[reportIncompatibleMethodOverride] -- narrows the API
        self, path: str, *, action: str, response_model: object, status_code: int | None = None
    ) -> Callable[[_Endpoint], _Endpoint]:
        return self._verb("DELETE", path, action, response_model, status_code)
