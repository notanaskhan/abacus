"""`third_party.uploaded` (R-01-T13; R-01 §4.7; INV-5): when a third party uploads to a request
delegated to them, the request's firm owner is told in the app ("Sam Ortiz (Keystone) uploaded to
SOC 1 bridge letter", resolved at read time from identifiers, DEC-61). Subscribes to evidence's
`evidence.uploaded`; the uploader's open delegation of the request decides, so a client's own
upload never makes one. Identifiers only; nothing about the file is copied."""

from __future__ import annotations

from typing import Annotated, ClassVar, Final
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.requests.api import delegate_upload

_ACTOR: Final = "portal:third_party_uploaded"


class ThirdPartyUploaded(DomainEvent):
    """A third party uploaded to a request delegated to them; `owner_user_id` is the request's
    firm owner (None: the engagement's leads hear of it)."""

    event_type: ClassVar[str] = "third_party.uploaded"

    engagement_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    uploaded_by: Annotated[UUID, classified("internal")]
    owner_user_id: Annotated[UUID | None, classified("internal")] = None


def _uuid(payload: dict[str, object], key: str) -> UUID | None:
    value = payload.get(key)
    try:
        return UUID(str(value)) if value is not None else None
    except ValueError:
        return None


async def on_evidence_uploaded(event: OutboxEvent) -> None:
    item_id = _uuid(event.payload, "request_item_id")
    version_id = _uuid(event.payload, "evidence_version_id")
    uploader = _uuid(event.payload, "uploaded_by")
    if item_id is None or version_id is None or uploader is None:
        return
    tenant = TenantContext(event.tenant_id, "system", _ACTOR)
    found = await delegate_upload(tenant, item_id, uploader)
    if found is None:
        return  # not a third party's upload (a client's own, or the delegation ended)
    async with uow(tenant) as tx:
        tx.emit(
            ThirdPartyUploaded(
                engagement_id=found.engagement_id,
                request_item_id=item_id,
                evidence_version_id=version_id,
                uploaded_by=uploader,
                owner_user_id=found.firm_owner_user_id,
            )
        )
        tx.record(
            "third_party.upload_noticed",
            target=Target("request_item", item_id),
            after=Ref(evidence_version_id=version_id, uploaded_by=uploader),
            scope=Scope(engagement_id=found.engagement_id),
        )


SUBSCRIPTIONS = {"evidence.uploaded": on_evidence_uploaded}
