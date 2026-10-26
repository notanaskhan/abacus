"""A run's model calls as the gateway recorded them (TASK-461; P-09 run trace).

Read-only, for a caller that has authorised on the run: when each attempt happened, its outcome,
route and token counts. The model id is never returned (the trace shows the runtime label).

`model_calls_for` (Q-02-T41; ADR-169 §3) is the run record's source, read by the run's own
workflow in a system context: it does carry the model id, route, region, inputs hash, data
boundary basis and terms version, because a run record keeps them for the engagement's
retention. Never shown on the trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext, tenant_session


@dataclass(frozen=True)
class Attempt:
    at: datetime
    outcome: str
    route: str
    tier: str
    prompt: str  # prompt id and version, e.g. "evidence.screen@3"
    input_tokens: int
    output_tokens: int


async def attempts_for(tenant: TenantContext, run_id: UUID) -> list[Attempt]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT created_at, outcome, route, tier, prompt_id, prompt_version, "
                "input_tokens, output_tokens FROM usage_records "
                "WHERE agent_run_id = :run ORDER BY created_at, id"
            ),
            {"run": run_id},
        )
        return [
            Attempt(r[0], r[1], r[2], r[3], f"{r[4]}@{r[5]}", int(r[6]), int(r[7]))
            for r in rows.all()
        ]


@dataclass(frozen=True)
class ModelCall:
    """One recorded model call, with what a run record keeps of it (ADR-169 §3)."""

    at: datetime
    outcome: str
    prompt: str  # prompt id and version, e.g. "evidence.screen@v0"
    model: str
    route: str
    region: str | None
    inputs_hash: str
    boundary_basis: str | None
    terms_version: str | None


def route_region(route: str) -> str | None:
    """Where a route runs inference: Bedrock in its configured region, the provider's API in the
    United States (DEC-87), the fake route on this machine."""
    regions: dict[Route, str] = {
        "bedrock": settings().bedrock_region,
        "direct": "us",
        "fake": "local",
    }
    return regions.get(route)  # pyright: ignore[reportArgumentType] -- a stored route code


async def model_calls_for(tenant: TenantContext, run_id: UUID) -> list[ModelCall]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT created_at, outcome, prompt_id, prompt_version, model, route, "
                "inputs_hash, boundary_basis, terms_version FROM usage_records "
                "WHERE agent_run_id = :run ORDER BY created_at, id"
            ),
            {"run": run_id},
        )
        return [
            ModelCall(
                r[0], r[1], f"{r[2]}@{r[3]}", r[4], r[5], route_region(r[5]), r[6], r[7], r[8]
            )
            for r in rows.all()
        ]
