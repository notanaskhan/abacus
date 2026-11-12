"""The `tax_return` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

A return is found by its form and year ("2025 Form 1040"), its taxpayer's client name and its K-1
recipients' names: the Ridgeline 1065 lists Jonah Feld, a 25% limited partner, so "feld" finds it
with the context "Jonah Feld, limited partner 25%". A 1040 opens TAX-02; an entity return (1065,
1120-S, 1120, 1041, 990) opens TXP-01 once the manifest builds it, and its client record (CLI-02)
until then (P-02 story 1.1). `data_class` is `tri`: an offshore member needs the disclosure
consent to see a row (§7216). No TIN, amount or return content is indexed.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.organisations.api import client_names
from abacus.modules.platform.api import (
    RelatedParty,
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

# TXP-01 is `planned` in the manifest (T-05): entity returns route to CLI-02 until it is built.
ENTITY_RETURNS_TO_TXP01 = False
_INDIVIDUAL = frozenset({"1040", "1040-NR", "1040-SR"})

_RETURN = text(
    "SELECT work_item_id, engagement_id, client_entity_id, form, tax_year, status, created_at "
    "FROM tax_returns WHERE work_item_id = :id"
)
_RECIPIENTS = text(
    "SELECT display_name, recipient_kind, ownership_note FROM k1_recipients "
    "WHERE work_item_id = :id ORDER BY display_name LIMIT 20"
)
_IDS = text(
    "SELECT work_item_id FROM tax_returns "
    "WHERE (CAST(:after AS uuid) IS NULL OR work_item_id > CAST(:after AS uuid)) "
    "ORDER BY work_item_id LIMIT :limit"
)


def _label(kind: object, note: object) -> str:
    words = str(kind or "partner").replace("_", " ")
    return f"{words} {note}".strip() if note else words


async def build_tax_return(
    tenant: TenantContext, work_item_id: UUID
) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_RETURN, {"id": work_item_id})).mappings().first()
        if row is None:
            return None
        recipients = (await session.execute(_RECIPIENTS, {"id": work_item_id})).mappings().all()
        entity_id = UUID(str(row["client_entity_id"]))
        names = await client_names(session, [entity_id])
    named = names.get(entity_id)
    if named is None:
        return None
    client_id = named.client_id
    related = tuple(
        RelatedParty(
            name=str(r["display_name"]), label=_label(r["recipient_kind"], r["ownership_note"])
        )
        for r in recipients
    )
    form = str(row["form"])
    entity = form not in _INDIVIDUAL
    target_params = {"returnId": str(work_item_id), "family": form}
    if entity and not ENTITY_RETURNS_TO_TXP01:
        target_params = {"clientId": str(client_id), "family": form}
    context: str | None = named.client_entity_name
    if related:
        context = f"{related[0].name}, {related[0].label}"
    return SearchIndexDocument(
        object_id=work_item_id,
        title=f"{row['tax_year']} Form {form}",
        context=context,
        engagement_id=UUID(str(row["engagement_id"])),
        work_item_id=work_item_id,
        client_id=client_id,
        identifiers=(form, str(row["tax_year"])),
        related=related,
        status_code=str(row["status"]),
        source_updated_at=row["created_at"],
        target_params=target_params,
    )


async def tax_return_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _work_item(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("work_item_id")
    return [] if raw is None else [UUID(str(raw))]


TAX_RETURN_PROJECTION = SearchProjection(
    object_type="tax_return",
    group="returns",
    read_action="tax_return.read",
    scope_kind="work_item",
    build=build_tax_return,
    target="TAX-02",
    data_class="tri",
    triggers={
        "tax_return.approved": _work_item,
        "tax_return.ready_to_transmit": _work_item,
        "k1_package.released": _work_item,
    },
    list_ids=tax_return_ids,
)
register_search_projection(TAX_RETURN_PROJECTION)
