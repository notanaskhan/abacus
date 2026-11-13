"""The requests module's attention provider (I-02-T11; DEC-4723): `outstanding_pbc`, an
engagement's PBC received of total while any request is outstanding ("Northwind PBC 11 of 24"),
counted by code over its published PBC binders (`pbc_counts`, metadata under `visible()`)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.modules.engagements.api import AttentionRow, engagements_for, work_item_ids_of
from abacus.modules.identity.api import AuthContext


async def outstanding_pbc(ctx: AuthContext, engagements: Sequence[UUID]) -> list[AttentionRow]:
    from abacus.modules.requests.source_documents import pbc_counts

    wanted = set(engagements)
    out: list[AttentionRow] = []
    for e in await engagements_for(ctx):
        if e.id not in wanted:
            continue
        counts = await pbc_counts(ctx, await work_item_ids_of(ctx.tenant, e.id))
        received = sum(r for r, _t in counts.values())
        total = sum(t for _r, t in counts.values())
        if total and received < total:
            out.append(
                AttentionRow(
                    kind="outstanding_pbc",
                    engagement_id=e.id,
                    title=f"{e.client_entity_name} PBC {received} of {total}",
                    detail="Requests outstanding",
                    counts={"received": received, "total": total},
                )
            )
    return out


__all__ = ["outstanding_pbc"]
