"""`assurance.read_materiality` on C17 (W-02-T11; W-02 §6; ADR-233, ADR-049; DEC-4716).

The engagement's planning materiality as decided (the newest version): overall, performance
materiality and its percentage, the clearly trivial threshold and its percentage, the benchmark
and the version. Read only; the agent never sets, proposes or decides materiality (the
recommender's card is a person's decision, A-04). The runtime authorised `materiality.read`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")


class MaterialityIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None


class MaterialityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decided: Annotated[bool, Int]
    version: Annotated[int | None, Int] = None
    overall: Annotated[Decimal | None, Conf] = None
    performance: Annotated[Decimal | None, Conf] = None
    performance_pct: Annotated[Decimal | None, Conf] = None
    clearly_trivial: Annotated[Decimal | None, Conf] = None
    clearly_trivial_pct: Annotated[Decimal | None, Conf] = None
    benchmark: Annotated[str | None, Conf] = None


@agent_tool(
    name="assurance.read_materiality", kind="read", action="materiality.read",
    data_class="confidential", input_model=MaterialityIn, output_model=MaterialityOut,
    records_read="materiality_version",
)  # fmt: skip
async def read_materiality(agent: AgentContext, args: MaterialityIn) -> MaterialityOut:
    from abacus.modules.assurance import materiality

    engagement = args.engagement_id or agent.engagement_id
    if engagement is None:
        raise NotFound("engagement")
    found = await materiality.record(agent, engagement)  # type: ignore[arg-type] -- the run's context
    if not found.versions:
        return MaterialityOut(decided=False)
    v = found.versions[-1]
    return MaterialityOut(
        decided=True,
        version=getattr(v, "version_no", None),
        overall=getattr(v, "overall", None),
        performance=getattr(v, "pm", None),
        performance_pct=getattr(v, "pm_pct", None),
        clearly_trivial=getattr(v, "ct", None),
        clearly_trivial_pct=getattr(v, "ct_pct", None),
        benchmark=getattr(v, "benchmark_key", None),
    )


__all__ = ["read_materiality"]
