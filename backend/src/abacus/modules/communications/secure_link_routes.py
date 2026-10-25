"""`POST /v1/portal/links/renew` (P-08-T21; SPEC-320 AC-14; epic Story 5.1): pre-session, always
202 with one body for any token on any host, padded to one duration; a new link goes only to the
address the old one went to (`secure_links.renew_link`). The SPA's toast names the address from
its own state, never from here."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header
from fastapi.responses import JSONResponse, Response

from abacus.modules.communications.secure_links import renew_link
from abacus.modules.identity.api import (
    PRE_SESSION,
    AbacusRouter,
    PortalLinkRenewIn,
    PortalLinkRenewOut,
)

router = AbacusRouter(prefix="/v1/portal/links", tags=["portal-auth"])


@router.post("/renew", action=PRE_SESSION, response_model=PortalLinkRenewOut, status_code=202)
async def portal_link_renew_route(
    body: PortalLinkRenewIn, host: Annotated[str | None, Header()] = None
) -> Response:
    await renew_link(host, body.link_token)
    response = JSONResponse(PortalLinkRenewOut().model_dump(mode="json"), status_code=202)
    response.headers["Cache-Control"] = "no-store"
    return response
