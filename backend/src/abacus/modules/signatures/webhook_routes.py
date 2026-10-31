"""`POST /v1/webhooks/docuseal/{tenant_id}/{install_id}` (ADR-152 amendment, DEC-1281): the
DocuSeal webhook, no principal (`PROVIDER_WEBHOOK`); the receiver verifies the signature first
(`webhook.receive_docuseal_webhook`). Every answer is empty: nothing is echoed."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Header, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from abacus.kernel.clock import system_now
from abacus.modules.identity.api import PROVIDER_WEBHOOK, AbacusRouter
from abacus.modules.signatures.webhook import receive_docuseal_webhook

webhook_router = AbacusRouter(prefix="/v1/webhooks", tags=["webhooks"])


class WebhookAcceptedOut(BaseModel):
    """Nothing: a delivery is acknowledged with an empty body (ADR-152)."""

    model_config = ConfigDict(frozen=True)


@webhook_router.post(
    "/docuseal/{tenant_id}/{install_id}",
    action=PROVIDER_WEBHOOK,
    response_model=WebhookAcceptedOut,
    status_code=202,
    errors=(413,),
)
async def docuseal_webhook_route(
    tenant_id: UUID,
    install_id: UUID,
    request: Request,
    x_docuseal_signature: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> Response:
    status = await receive_docuseal_webhook(
        tenant_id, install_id, await request.body(), x_docuseal_signature, system_now().timestamp()
    )
    return Response(status_code=status, headers={"Cache-Control": "no-store"})
