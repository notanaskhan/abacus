"""The real-data rehearsal (Q-02-T48; Q-02 §10 DoD 5; DEC-958). Staging only, nightly, as an ops
one-off task on the release image (`ops-task.yml`, `rehearsal-nightly.yml`); never from a laptop
against a hosted database.

    python -m abacus_tools.rehearsal run --tenant <uuid> --admin <uuid> --partner <uuid> \
        --engagement <uuid> --tax-engagement <uuid>

The rehearsal tenant is a real (non-synthetic) firm that holds only synthetic content. Each night
the walk resets it, then goes through what a real firm meets on its way to client data, in order:
every refusal reason the boundary can give it (`route`, `firm`, `agent`, `stage`,
`tax_return_information`, `engagement`, `pii_in_context`, `ai_paused`), the firm admin's opt-in,
the agent in shadow (a shadow run's start is marked shadow), the partner's exclusion, the
live-stage guard (`agents.api.check_live` refuses without a report and with one below the SPEC-036
Q1 floor or QD-10, and accepts one that meets both), an access event written and read back with
its attribution, the firm's audit chain sealed and verified, and the human-only rules: the agent
principal can neither opt in nor exclude (INV-1), and each change names the person or operator who
made it (INV-5). It ends by resetting the firm again. `terms` is not walked: the register covers
Bedrock on staging, and the register is protected content (DEC-958).

Each step prints one line, `ok` or `FAIL` with a reason in words (no client data: the tenant holds
none). The exit code is the number of failed steps, capped at 1.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.ai_gateway.boundary import (
    DataBoundaryRefused,
    clear_cache,
    enforce_boundary,
    hold_facts_for,
    refuse_pii_in_context,
)
from abacus.kernel.access import AccessSubject, record_reads
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.uow.chain import seal_checkpoint, verify_chain
from abacus.modules.agents.api import (
    AGENTS,
    NamedReport,
    ShadowReportRequired,
    StageNotReady,
    check_live,
    shadow_score,
    starts_in_shadow,
)
from abacus.modules.engagements.api import set_ai_exclusion_of
from abacus.modules.evidence.api import CONTENT_READ_KIND as EVIDENCE_READ
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    is_synthetic_firm,
    set_ai_client_data_setting,
)
from abacus_tools.agent_stage import set_stage
from abacus_tools.db_connect import connect as connect_db

AGENT: Final = "evidence.screener"
PROMPT: Final = "rehearsal"
NOTE: Final = "Q-02-T48 nightly rehearsal"
_PAUSE_WAIT: Final = 11.0  # the controls cache is 10 seconds


@dataclass(frozen=True)
class Rehearsal:
    tenant: UUID
    admin: UUID
    partner: UUID
    engagement: UUID
    tax_engagement: UUID


@dataclass
class Report:
    lines: list[str] = field(default_factory=list[str])
    failed: int = 0

    def ok(self, step: str) -> None:
        self.lines.append(f"ok    {step}")

    def fail(self, step: str, why: str) -> None:
        self.failed += 1
        self.lines.append(f"FAIL  {step}: {why}")


def _person(r: Rehearsal, user_id: UUID) -> AuthContext:
    """A firm person acting now, with a fresh second factor (the rehearsal's own members)."""
    return AuthContext(
        tenant=TenantContext(r.tenant, "human", str(user_id)),
        user_id=user_id,
        membership_id=user_id,
        firm_role="firm_admin" if user_id == r.admin else None,
        mfa_at=system_now() - timedelta(seconds=30),
    )


def _agent(r: Rehearsal) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(r.tenant, "agent", AGENT),
        user_id=r.admin,
        membership_id=r.admin,
        firm_role=None,
        mfa_at=None,
    )


def _uncleared() -> str:
    return next(a.id for a in AGENTS.values() if a.client_data != "cleared")


async def _refused(
    report: Report,
    step: str,
    want: str,
    call: Callable[[], Awaitable[object]],
) -> None:
    try:
        await call()
    except DataBoundaryRefused as refused:
        if refused.reason == want:
            report.ok(step)
        else:
            report.fail(step, f"refused for {refused.reason}, expected {want}")
        return
    report.fail(step, f"not refused, expected {want}")


def _boundary(
    r: Rehearsal, route: str = "bedrock", agent: str | None = AGENT, engagement: UUID | None = None
) -> Callable[[], Awaitable[object]]:
    tenant = TenantContext(r.tenant, "system", "rehearsal")

    async def call() -> object:
        return await enforce_boundary(
            tenant,
            route,  # pyright: ignore[reportArgumentType] -- a Route literal
            PROMPT,
            agent_id=agent,
            engagement_id=engagement if engagement is not None else r.engagement,
        )

    return call


async def _pause(r: Rehearsal, on: bool) -> None:
    """The firm's AI kill switch, as the operator (`abacus_ops`; Q-01-T36)."""
    url = settings().ops_database_url
    if url is None:
        raise RuntimeError("ops_database_url is not set")
    connection = await connect_db(url.get_secret_value().replace("+asyncpg", "", 1))
    try:
        await connection.fetchval(
            "SELECT set_platform_control('ai_pause', 'firm', $1, NULL, $2, $3, 'rehearsal', NULL)",
            r.tenant,
            on,
            NOTE,
        )
    finally:
        await connection.close()


async def _reset(r: Rehearsal) -> None:
    await set_ai_client_data_setting(_person(r, r.admin), False)
    await set_stage(r.tenant, AGENT, "off", NOTE)
    await set_ai_exclusion_of(_person(r, r.partner), r.engagement, False, None)
    clear_cache(r.tenant)


async def _actors(r: Rehearsal, since: object) -> dict[str, set[str]]:
    tenant = TenantContext(r.tenant, "system", "rehearsal")
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT action, actor_id FROM audit_events WHERE occurred_at >= :since "
                "AND action IN ('firm.ai_client_data_on', 'engagement.ai_excluded', "
                "'agent_stage.changed', 'ai.boundary_refused')"
            ),
            {"since": since},
        )
        found: dict[str, set[str]] = {}
        for action, actor in rows:
            found.setdefault(str(action), set()).add(str(actor))
        return found


async def walk(r: Rehearsal) -> Report:
    report = Report()
    started = system_now()
    hold_facts_for(0)  # read every firm fact fresh (DEC-337)
    tenant = TenantContext(r.tenant, "system", "rehearsal")
    if await is_synthetic_firm(tenant):
        report.fail("tenant", "the rehearsal tenant is synthetic; it must be a real firm")
        return report
    report.ok("tenant is a real firm")
    await _reset(r)

    # Before the opt-in: the route and the firm.
    await _refused(report, "refused: route", "route", _boundary(r, route="direct"))
    await _refused(report, "refused: firm (not opted in)", "firm", _boundary(r))

    # INV-1: the agent can't opt the firm in or exclude an engagement.
    try:
        await set_ai_client_data_setting(_agent(r), True)
        report.fail("INV-1 opt-in", "the agent principal opted the firm in")
    except Forbidden:
        report.ok("INV-1 opt-in refused to the agent")
    try:
        await set_ai_exclusion_of(_agent(r), r.engagement, True, "agent")
        report.fail("INV-1 exclusion", "the agent principal excluded an engagement")
    except Forbidden:
        report.ok("INV-1 exclusion refused to the agent")

    # The firm admin opts in; then the agent and its stage.
    await set_ai_client_data_setting(_person(r, r.admin), True)
    report.ok("opted in by the firm admin")
    await _refused(report, "refused: agent", "agent", _boundary(r, agent=_uncleared()))
    await _refused(report, "refused: stage (off)", "stage", _boundary(r))

    # Shadow: calls pass, and a run starting now is marked shadow (its output stays hidden).
    await set_stage(r.tenant, AGENT, "shadow", NOTE)
    clear_cache(r.tenant)
    try:
        basis = await _boundary(r)()
        report.ok(f"shadow: boundary passes ({getattr(basis, 'basis', '?')})")
    except DataBoundaryRefused as refused:
        report.fail("shadow", f"refused for {refused.reason}")
    async with tenant_session(tenant) as session:
        if await starts_in_shadow(session, tenant, AGENT):
            report.ok("shadow: a run starting now is a shadow run")
        else:
            report.fail("shadow", "a run starting now is not marked shadow")

    # Refusals that hold whatever the stage.
    await _refused(
        report,
        "refused: tax_return_information",
        "tax_return_information",
        _boundary(r, engagement=r.tax_engagement),
    )

    async def pii() -> object:
        await refuse_pii_in_context(tenant, "bedrock", PROMPT, "context", 0)
        return None

    await _refused(report, "refused: pii_in_context", "pii_in_context", pii)

    # The partner excludes the engagement: every route is refused, the fake one too.
    await set_ai_exclusion_of(_person(r, r.partner), r.engagement, True, NOTE)
    clear_cache(r.tenant)
    await _refused(report, "refused: engagement (excluded)", "engagement", _boundary(r, "fake"))
    await set_ai_exclusion_of(_person(r, r.partner), r.engagement, False, None)
    clear_cache(r.tenant)

    # The firm's AI kill switch.
    await _pause(r, True)
    await asyncio.sleep(_PAUSE_WAIT)
    try:
        await _refused(report, "refused: ai_paused", "ai_paused", _boundary(r))
    finally:
        await _pause(r, False)

    # The live-stage guard (Q-02-T50): no report, a report below the floors, one that meets them.
    try:
        await check_live(r.tenant, AGENT, None)
        report.fail("live guard", "live accepted without a shadow report")
    except ShadowReportRequired:
        report.ok("live guard: refused without a report")
    score = await shadow_score(tenant, AGENT, system_now())
    named = NamedReport(score.sha256, system_now())
    try:
        await check_live(r.tenant, AGENT, named)
        if score.passes:
            report.ok("live guard: a report meeting Q1 and QD-10 is accepted")
        else:
            report.fail("live guard", "a report below the floors was accepted")
    except StageNotReady:
        if score.passes:
            report.fail("live guard", "a report meeting both floors was refused")
        else:
            report.ok("live guard: refused below the SPEC-036 Q1 floor or QD-10")

    # An access event, written and read back with its attribution (Q-02-T20; INV-5).
    partner = _person(r, r.partner)
    written = await record_reads(
        partner.tenant,
        EVIDENCE_READ,
        [AccessSubject("engagement", r.engagement, engagement_id=r.engagement)],
    )
    async with tenant_session(tenant) as session:
        seen = (
            await session.execute(
                text(
                    "SELECT count(*) FROM access_events WHERE actor_id = :actor "
                    "AND occurred_at >= :since"
                ),
                {"actor": r.partner, "since": started},
            )
        ).scalar_one()
    if written == 1 and int(seen) >= 1:
        report.ok("access event written and attributed to the partner")
    else:
        report.fail("access events", f"wrote {written}, read back {seen}")

    # INV-5: each change names who made it.
    actors = await _actors(r, started)
    if actors.get("firm.ai_client_data_on") == {str(r.admin)}:
        report.ok("INV-5 opt-in attributed to the firm admin")
    else:
        report.fail("INV-5 opt-in", "the opt-in is not attributed to the firm admin alone")
    if actors.get("engagement.ai_excluded") == {str(r.partner)}:
        report.ok("INV-5 exclusion attributed to the partner")
    else:
        report.fail("INV-5 exclusion", "the exclusion is not attributed to the partner alone")
    if any(a.startswith("platform:") for a in actors.get("agent_stage.changed", set())):
        report.ok("INV-5 stage changes attributed to the platform operator")
    else:
        report.fail("INV-5 stage", "a stage change is not attributed to the operator")

    await _reset(r)
    # The chain last, so tonight's events are inside a sealed checkpoint.
    await seal_checkpoint(r.tenant)
    bad = await verify_chain(r.tenant)
    if bad:
        report.fail("audit chain", f"mismatch at checkpoint(s) {', '.join(map(str, bad))}")
    else:
        report.ok("audit chain sealed and verified")
    return report


async def _run(r: Rehearsal) -> int:
    url = settings().database_url
    if url is None:
        print("refused: ABACUS_DATABASE_URL is not set", file=sys.stderr)
        return 2
    if settings().environment != "staging":
        print("refused: the rehearsal runs on staging only", file=sys.stderr)
        return 2
    configure_engine(url.get_secret_value())
    try:
        found = await walk(r)
    finally:
        await dispose_engine()
    for line in found.lines:
        print(line)
    return 1 if found.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.rehearsal")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    for name in ("--tenant", "--admin", "--partner", "--engagement", "--tax-engagement"):
        run.add_argument(name, type=UUID, required=True)
    args = parser.parse_args(argv)
    rehearsal = Rehearsal(
        args.tenant, args.admin, args.partner, args.engagement, args.tax_engagement
    )
    return asyncio.run(_run(rehearsal))


if __name__ == "__main__":
    sys.exit(main())
