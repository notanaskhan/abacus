"""Send-to-client for issues (P-04-T31; DEC-828): review may not import requests, so this glue,
in a module allowed both, registers `requests.api.add_request_item` as review's client-request
sender. The item carries only the client wording a person wrote; nothing of the issue's title or
internal note crosses (the sender is given nothing else)."""

from __future__ import annotations

from datetime import date
from typing import Final
from uuid import UUID

from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import NewRequestItem, add_request_item

AREA: Final = "Review points"


async def send_issue_to_client(
    ctx: AuthContext,
    engagement_id: UUID,
    client_wording: str,
    contact_id: UUID,
    due_on: date | None,
) -> UUID:
    del contact_id, due_on  # the item's addressee and due date follow the request list (P-06)
    made = await add_request_item(
        ctx, engagement_id, NewRequestItem(description=client_wording, audit_area=AREA)
    )
    return made.id
