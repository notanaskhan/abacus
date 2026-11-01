"""The item-request fan-out (A-03-T13, TASK-2712; A-03 F4, US-4.1; DEC-1763).

From an approved sample set version: one request per (template, sample item), each linked to its
item (`linked_ref {type: sample_item, sample_set_version_id, position, record_key}`) in the
`sample` wave with the due date, through `requests.api.create_items_bulk` in one unit of work.
A template addressed to a client contact (POR-03) stays with the client; one addressed to a
third-party contact (POR-14) is delegated, per item, to that contact through P-06's delegation
(the per-item `request_item` grant), so Sam Ortiz sees exactly his 25 and nothing else (INV-4).

- `preview`: the counts by surface and, per recipient, how many requests they will see; the
  preview names no seed, size, parameter or population hash (INV-4).
- `create`: 409 `sample_not_approved` unless the version is approved; `Idempotency-Key`: a
  replay of the same key and body answers the first response and creates nothing. Audited
  `sample_set.requests_generated {count, por03, por14, batch_id}`.

A client recipient must be the engagement's client's contact, else 422 `recipient_not_contact`;
a third-party recipient must also hold a portal sign-in (P-06's `contact_not_portal_user`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import (
    client_contact_names,
    client_contact_organisations,
    contact_portal_user,
)
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import (
    BulkItem,
    ContactNotPortalUser,
    create_items_bulk,
    delegate_item,
)
from abacus.modules.sampling import sample_set_repository as repo
from abacus.modules.sampling.contract import (
    ItemRequestPreviewOut,
    ItemRequestsCreatedOut,
    ItemRequestsIn,
    ItemRequestTemplateIn,
    RecipientPreviewOut,
)
from abacus.modules.sampling.sample_sets import TARGET, Row, SetFound, set_for, version_row

ACTION: Final = "sample_set.generate_requests"
POR03: Final = "POR-03"
POR14: Final = "POR-14"
_DESCRIPTION: Final = 500


# Requests come from an approved version only (AUD-11 b's disabled CTA); the code's summary is
# fieldwork's (SPEC-040), the same rule.
class SampleNotApproved(DomainConflict):
    code = "sample_not_approved"


class RecipientNotContact(DomainInvalid):
    """A template names someone who is not the engagement's client's contact."""

    code = "recipient_not_contact"


def _surface(template: ItemRequestTemplateIn) -> str:
    return POR14 if template.third_party_contact_id is not None else POR03


def _recipient(template: ItemRequestTemplateIn) -> UUID:
    found = template.third_party_contact_id or template.contact_id
    if found is None or (template.contact_id and template.third_party_contact_id):
        raise RecipientNotContact(facts={"field": "templates"})
    return found


async def _approved(
    ctx: AuthContext, sample_set_id: UUID, version_no: int
) -> tuple[SetFound, Row, list[repo.Row]]:
    found = await set_for(ctx, sample_set_id, ACTION)
    version = await version_row(ctx, sample_set_id, version_no)
    if version["status"] != "approved":
        raise SampleNotApproved(facts={"status": version["status"]})
    async with tenant_session(ctx.tenant) as session:
        items = await repo.items(session, cast(UUID, version["id"]))
    return found, version, items


async def _names(
    ctx: AuthContext, engagement_id: UUID, body: ItemRequestsIn
) -> dict[UUID, tuple[str, str | None]]:
    """Each recipient's name and organisation, refusing anyone not the client's contact."""
    ids = list(dict.fromkeys(_recipient(t) for t in body.templates))
    names = await client_contact_names(ctx.tenant, engagement_id, ids)
    if set(ids) - set(names):
        raise RecipientNotContact(facts={"field": "templates"})
    out: dict[UUID, tuple[str, str | None]] = {}
    for contact in ids:
        organisations = await client_contact_organisations(ctx.tenant, engagement_id, [contact])
        out[contact] = (names[contact], organisations[0] if organisations else None)
    return out


def _by_surface(body: ItemRequestsIn, items: Sequence[repo.Row]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for template in body.templates:
        counts[_surface(template)] += len(items)
    return {surface: counts.get(surface, 0) for surface in (POR03, POR14)}


async def preview(
    ctx: AuthContext, sample_set_id: UUID, version_no: int, body: ItemRequestsIn
) -> ItemRequestPreviewOut:
    """ "125 requests · 100 to POR-03 · 25 to POR-14", and each recipient's own count."""
    found, _, items = await _approved(ctx, sample_set_id, version_no)
    names = await _names(ctx, found.engagement_id, body)
    per: Counter[tuple[UUID, str]] = Counter()
    for template in body.templates:
        per[(_recipient(template), _surface(template))] += len(items)
    by_surface = _by_surface(body, items)
    return ItemRequestPreviewOut(
        total=sum(by_surface.values()),
        by_surface=by_surface,
        recipients=[
            RecipientPreviewOut(
                name=names[contact][0],
                organisation=names[contact][1],
                surface=surface,  # pyright: ignore[reportArgumentType] -- one of the two
                requests=count,
            )
            for (contact, surface), count in sorted(
                per.items(), key=lambda kv: (kv[0][1], names[kv[0][0]][0])
            )
        ],
    )


def _bulk(
    found: SetFound, version: Row, items: Sequence[repo.Row], body: ItemRequestsIn
) -> list[BulkItem]:
    area = str(found.row["title"])
    out: list[BulkItem] = []
    for template in body.templates:
        for item in items:
            key = str(item["record_key"])
            out.append(
                BulkItem(
                    description=f"{template.description} · {key}"[:_DESCRIPTION],
                    audit_area=area,
                    linked_ref={
                        "type": "sample_item",
                        "sample_set_version_id": str(version["id"]),
                        "position": int(item["position"]),
                        "record_key": key,
                        "recipient_contact_id": str(_recipient(template)),
                    },
                )
            )
    return out


async def _create(
    ctx: AuthContext, sample_set_id: UUID, version_no: int, body: ItemRequestsIn
) -> ItemRequestsCreatedOut:
    found, version, items = await _approved(ctx, sample_set_id, version_no)
    await _names(ctx, found.engagement_id, body)
    # Every third party can sign in before anything is written, so a delegation can't fail
    # after the requests exist.
    for template in body.templates:
        third = template.third_party_contact_id
        if (
            third is not None
            and await contact_portal_user(ctx.tenant, found.engagement_id, third) is None
        ):
            raise ContactNotPortalUser
    batch_id = uuid4()
    planned = _bulk(found, version, items, body)
    by_surface = _by_surface(body, items)
    async with uow(ctx.tenant) as tx:
        ids = await create_items_bulk(
            tx,
            ctx,
            found.engagement_id,
            planned,
            wave=body.wave,
            due_on=body.due_on,
            batch_id=batch_id,
        )
        tx.record(
            "sample_set.requests_generated",
            target=Target(TARGET, cast(UUID, version["id"])),
            after=Ref(
                count=len(ids),
                por03=by_surface[POR03],
                por14=by_surface[POR14],
                batch_id=batch_id,
            ),
        )
    # A third party's requests are delegated one by one through P-06's delegation, which issues
    # each per-item grant (DEC-1763: grants are identity's own writes, outside this unit of work).
    for planned_item, item_id in zip(planned, ids, strict=True):
        template_contact = UUID(cast(str, planned_item.linked_ref["recipient_contact_id"]))
        template = next(t for t in body.templates if _recipient(t) == template_contact)
        if template.third_party_contact_id is not None:
            await delegate_item(ctx, found.engagement_id, item_id, template.third_party_contact_id)
    return ItemRequestsCreatedOut(created=len(ids), by_surface=by_surface, batch_id=batch_id)


async def create(
    ctx: AuthContext,
    sample_set_id: UUID,
    version_no: int,
    body: ItemRequestsIn,
    idempotency_key: str,
) -> ItemRequestsCreatedOut:
    """`POST …/item-requests` (201); a replay of the key and body answers the first response."""
    await set_for(ctx, sample_set_id, ACTION)  # a replay's caller is still authorised

    async def run() -> tuple[int, dict[str, object]]:
        out = await _create(ctx, sample_set_id, version_no, body)
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="sample_set.item_requests",
        key=idempotency_key,
        body={
            "sample_set_id": str(sample_set_id),
            "version_no": version_no,
            **body.model_dump(mode="json"),
        },
        run=run,
    )
    return ItemRequestsCreatedOut.model_validate(stored.body)
