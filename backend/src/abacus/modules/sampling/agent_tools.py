"""`sampling.read_selected_entry` on C17 (A-08-T23; A-08 §6; ADR-233, ADR-049).

One selected item of a sample-set version on the run's engagement: its position, key, why it was
selected and its amount. Read only; the runtime authorised `sample_set.read`. The key and the
display come from the client's ledger: untrusted.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")

_ITEM = text(
    "SELECT s.engagement_id, i.position, i.record_key, i.selection_reason, i.display, r.amount "
    "FROM sample_items i JOIN sample_set_versions v ON v.id = i.sample_set_version_id "
    "JOIN sample_sets s ON s.id = v.sample_set_id "
    "LEFT JOIN population_records r ON r.population_id = v.population_id "
    "AND r.ordinal = i.population_record_ordinal "
    "WHERE i.sample_set_version_id = :v AND i.position = :p"
)


class SelectedEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_set_version_id: Annotated[UUID, Int]
    position: Annotated[int, Field(ge=1, le=10_000), Int]


class SelectedEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Int]  # `<version>:<position>`
    position: Annotated[int, Int]
    record_key: Annotated[str, Conf]
    selection_reason: Annotated[str, Int]
    amount: Annotated[Decimal | None, Conf] = None
    score: Annotated[str | None, Int] = None


@agent_tool(
    name="sampling.read_selected_entry", kind="read", action="sample_set.read",
    data_class="confidential", input_model=SelectedEntryIn, output_model=SelectedEntryOut,
    untrusted=("record_key",), records_read="sample_item",
)  # fmt: skip
async def read_selected_entry(agent: AgentContext, args: SelectedEntryIn) -> SelectedEntryOut:
    async with tenant_session(agent.tenant) as session:
        row = (
            (await session.execute(_ITEM, {"v": args.sample_set_version_id, "p": args.position}))
            .mappings()
            .first()
        )
    if row is None or row["engagement_id"] != agent.engagement_id:
        raise NotFound("sample_item")
    display = row["display"]
    shown = json.loads(display) if isinstance(display, str) else dict(display or {})
    return SelectedEntryOut(
        id=f"{args.sample_set_version_id}:{row['position']}",
        position=int(row["position"]),
        record_key=str(row["record_key"]),
        selection_reason=str(row["selection_reason"]),
        amount=row["amount"],
        score=None if shown.get("score") is None else str(shown["score"]),
    )
