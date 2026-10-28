"""Setting an agent's stage for a firm from the staff route (Q-02-T07; SPEC-036 §4.5, Q1, Q3).

Platform staff only (the route's STAFF marker). One unit of work in the firm's
tenant: `agent_stage_set` (migration 0181) appends the stage row and refuses `live` before 50
shadow runs over 14 days (the application role cannot write `agent_stages` itself), and the unit
records `agent_stage.changed` and emits `ai_boundary.facts_changed`, so the worker forgets the
firm's boundary facts too (Q-02-T08); this process forgets them at once.

Q-02-T50 (DEC-811): `live` also names the shadow report it was decided on (its SHA-256 and the
instant it was computed as of). The service recomputes that report, refuses a digest that differs
(409 `shadow_report_changed`) or a report older than 7 days (409 `shadow_report_stale`), and
refuses live unless it passes both SPEC-036 Q1 and QD-10 (409 `stage_not_ready {criterion}`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.ai_gateway import BoundaryFactsChanged, forget_boundary_facts
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.shadow_score import shadow_score
from abacus.modules.agents.spec import AGENTS

Stage = Literal["shadow", "live", "off"]
STAGES: Final = ("shadow", "live", "off")  # the audit names a stage by its index, as the command
_SET: Final = text("SELECT agent_stage_set(:tenant, :agent, :stage, :staff, :note)")


class StageNotReady(DomainConflict):
    """`live` needs 50 shadow runs of the agent for the firm over 14 days (SPEC-036 Q1)."""

    code = "stage_not_ready"


class ShadowReportRequired(DomainConflict):
    """`live` names the shadow report it was decided on (Q-02-T50)."""

    code = "shadow_report_required"


class ShadowReportChanged(DomainConflict):
    """The report recomputed as of its instant has another digest: re-read the report."""

    code = "shadow_report_changed"


class ShadowReportStale(DomainConflict):
    """The report is older than 7 days, or dated in the future: compute it again."""

    code = "shadow_report_stale"


REPORT_MAX_AGE: Final = timedelta(days=7)


@dataclass(frozen=True)
class NamedReport:
    sha256: str
    as_of: datetime


async def check_live(firm_id: UUID, agent_id: str, report: NamedReport | None) -> None:
    """Q-02-T50: the named report is the one the data gives as of its instant, fresh, and passing
    SPEC-036 Q1 and QD-10. Read in the firm's tenant as the platform."""
    tenant = TenantContext(firm_id, "system", "platform:stage-guard")
    now = system_now()
    if report is None:
        # Too early is said first (`stage_not_ready`); a ready agent still needs its report named.
        current = await shadow_score(tenant, agent_id, now)
        if not current.spec036_q1:
            raise StageNotReady(facts={"agent_id": agent_id, "criterion": "spec036_q1"})
        if not current.qd10:
            raise StageNotReady(facts={"agent_id": agent_id, "criterion": "qd10"})
        raise ShadowReportRequired(facts={"agent_id": agent_id})
    if report.as_of.tzinfo is None or report.as_of > now or now - report.as_of > REPORT_MAX_AGE:
        raise ShadowReportStale(facts={"agent_id": agent_id})
    found = await shadow_score(tenant, agent_id, report.as_of)
    if found.sha256 != report.sha256:
        raise ShadowReportChanged(facts={"agent_id": agent_id})
    if not found.spec036_q1:
        raise StageNotReady(facts={"agent_id": agent_id, "criterion": "spec036_q1"})
    if not found.qd10:
        raise StageNotReady(facts={"agent_id": agent_id, "criterion": "qd10"})


class UnknownAgent(DomainInvalid):
    """Only an agent the registry declares has a stage. Like the founder's command, a stage may be
    set before the agent is cleared for client data; the gateway reads it only once it is."""

    code = "unknown_agent"


async def set_agent_stage(
    staff_id: UUID,
    firm_id: UUID,
    agent_id: str,
    stage: Stage,
    note: str,
    report: NamedReport | None = None,
) -> UUID:
    """The new stage row's id; 404 for an unknown firm, 409 `stage_not_ready`,
    `shadow_report_required`, `shadow_report_changed` or `shadow_report_stale`, 422
    `unknown_agent`."""
    if agent_id not in AGENTS:
        raise UnknownAgent(facts={"agent_id": agent_id})
    if stage == "live":
        await check_live(firm_id, agent_id, report)
    actor = f"staff:{staff_id}"
    try:
        # A staff member decides: the firm's trail names them as `support` (identity.support's
        # way), never `system`, with the request's context (security review, 2026-10-26).
        async with uow(TenantContext(firm_id, "support", actor)) as tx:
            stage_id = (
                await tx.session.execute(
                    _SET,
                    {
                        "tenant": firm_id,
                        "agent": agent_id,
                        "stage": stage,
                        "staff": actor,
                        "note": note,
                    },
                )
            ).scalar_one()
            tx.record(
                "agent_stage.changed",
                target=Target("agent_stage", UUID(str(stage_id))),
                after=Ref(stage=STAGES.index(stage)),
            )
            tx.emit(BoundaryFactsChanged())
    except DBAPIError as exc:
        message = str(exc.orig) if exc.orig is not None else ""
        if "firm_not_found" in message:
            raise NotFound("firm") from None
        if "stage_not_ready" in message:
            raise StageNotReady(facts={"agent_id": agent_id}) from None
        raise
    forget_boundary_facts(firm_id)
    return UUID(str(stage_id))
