"""Adjustments in the trial balance and the summary of uncorrected misstatements (SPEC-311;
TASK-322; A-06 F3, F4).

- The trial balance's layers: an entry the partner approved, or the client accepted, is
  recorded and appears in its AJE or RJE column and in Final. A proposed entry is a count only;
  a declined (passed) entry never enters a layer.
- The summary of uncorrected misstatements (SUM): the passed entries, each entry's amount, and
  the aggregate against the decided materiality, all computed by code (ADR-050). Whether the
  aggregate is material stays the partner's judgement; code only states where it falls.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import Judgment, ProgressFact, get_ref
from abacus.modules.fieldwork.completion import status_of
from abacus.modules.fieldwork.planning import materiality_history
from abacus.modules.fieldwork.repository import (
    adjustment_events_of,
    adjustment_lines_of,
    engagement_adjustments,
    engagement_progress_rows,
    engagement_risks,
    materiality_decisions,
    materiality_versions,
    newest_risk_versions,
    risk_approvals,
)
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.ledger.api import AdjustmentEntry, EntryLine, EntrySet

RECORDED: Final = frozenset({"approved", "client_accepted"})
_ZERO: Final = Decimal("0.00")
Band = Literal["clearly_trivial", "below_performance", "below_overall", "above_overall"]


def _ref(kind: str, number: int) -> str:
    return f"{kind.upper()}-{number}"


async def adjustment_entries(tenant: TenantContext, engagement_id: UUID) -> EntrySet:
    """The ledger's adjustment source (registered in api.py)."""
    async with tenant_session(tenant) as session:
        entries = await engagement_adjustments(session, engagement_id)
        ids = [a.id for a in entries]
        lines = await adjustment_lines_of(session, ids)
        events = await adjustment_events_of(session, ids)
    recorded: list[AdjustmentEntry] = []
    pending = 0
    for a in entries:
        status = status_of([e for e in events if e.adjustment_id == a.id])
        if status == "proposed":
            pending += 1
        if status not in RECORDED:
            continue
        recorded.append(
            AdjustmentEntry(
                _ref(a.kind, a.number),
                "rje" if a.kind == "rje" else "aje",
                tuple(
                    EntryLine(x.account_code, x.debit, x.credit)
                    for x in lines
                    if x.adjustment_id == a.id
                ),
            )
        )
    return EntrySet(tuple(recorded), pending)


@dataclass(frozen=True)
class PassedEntry:
    id: UUID
    ref: str
    description: str
    amount: Decimal  # the entry's debits (equal to its credits)
    accounts: list[str]


@dataclass(frozen=True)
class Summary:
    entries: list[PassedEntry]
    aggregate: Decimal
    overall: Decimal | None
    performance: Decimal | None
    trivial: Decimal | None
    materiality_decided: bool
    band: Band | None  # None without materiality
    headroom: Decimal | None  # overall materiality minus the aggregate


def band_of(aggregate: Decimal, overall: Decimal, performance: Decimal, trivial: Decimal) -> Band:
    if aggregate <= trivial:
        return "clearly_trivial"
    if aggregate < performance:
        return "below_performance"
    if aggregate < overall:
        return "below_overall"
    return "above_overall"


async def uncorrected_for(ctx: AuthContext, engagement_id: UUID) -> Summary:
    """AC-4: passed entries and their aggregate against materiality."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        entries = await engagement_adjustments(session, engagement_id)
        ids = [a.id for a in entries]
        lines = await adjustment_lines_of(session, ids)
        events = await adjustment_events_of(session, ids)
    passed: list[PassedEntry] = []
    for a in entries:
        if status_of([e for e in events if e.adjustment_id == a.id]) != "client_declined":
            continue
        mine = [x for x in lines if x.adjustment_id == a.id]
        passed.append(
            PassedEntry(
                a.id,
                _ref(a.kind, a.number),
                a.description,
                sum((x.debit for x in mine), _ZERO),
                list(dict.fromkeys(x.account_code for x in mine)),
            )
        )
    aggregate = sum((p.amount for p in passed), _ZERO)
    versions = await materiality_history(ctx, engagement_id)
    chosen = next((v for v in versions if v.status == "decided"), None) or (
        versions[0] if versions else None
    )
    if chosen is None:
        return Summary(passed, aggregate, None, None, None, False, None, None)
    return Summary(
        passed,
        aggregate,
        chosen.overall,
        chosen.performance,
        chosen.trivial,
        chosen.status == "decided",
        band_of(aggregate, chosen.overall, chosen.performance, chosen.trivial),
        chosen.overall - aggregate,
    )


# --- Judgments for the EQR digest (SPEC-314; TASK-332) ----------------------------------------


async def judgments(tenant: TenantContext, engagement_id: UUID) -> list[Judgment]:
    """Materiality, significant risks and the uncorrected misstatements, stated by code."""
    async with tenant_session(tenant) as session:
        versions = await materiality_versions(session, engagement_id)
        decisions = await materiality_decisions(session, [v.id for v in versions[:1]])
        risks = await engagement_risks(session, engagement_id)
        risk_versions = await newest_risk_versions(session, [r.id for r in risks])
        approvals = await risk_approvals(session, [v.id for v in risk_versions.values()])
        entries = await engagement_adjustments(session, engagement_id)
        ids = [a.id for a in entries]
        lines = await adjustment_lines_of(session, ids)
        events = await adjustment_events_of(session, ids)
    out: list[Judgment] = []
    current = versions[0] if versions else None
    decided = current is not None and current.id in decisions
    if current is not None:
        out.append(
            Judgment(
                "materiality",
                "Materiality",
                (
                    ("Overall", f"{current.overall:,.2f}"),
                    ("Performance", f"{current.performance:,.2f}"),
                    ("Clearly trivial", f"{current.trivial:,.2f}"),
                    ("Benchmark", current.benchmark),
                    ("Status", "Decided by the partner" if decided else "Proposed"),
                ),
                decided,
            )
        )
    significant = [v for v in risk_versions.values() if v.significant]
    rebuttals = [v for v in risk_versions.values() if v.fraud == "rebuttal"]
    asking = significant + [v for v in rebuttals if v not in significant]
    approved = [v for v in asking if v.id in approvals]
    out.append(
        Judgment(
            "significant_risks",
            "Significant risks",
            (
                ("Risks assessed", str(len(risk_versions))),
                ("Significant", str(len(significant))),
                ("Fraud presumption rebutted", str(len(rebuttals))),
                ("Approved by the partner", f"{len(approved)} of {len(asking)}"),
            ),
            len(approved) == len(asking),
        )
    )
    passed = [
        a
        for a in entries
        if status_of([e for e in events if e.adjustment_id == a.id]) == "client_declined"
    ]
    aggregate = sum((x.debit for x in lines if x.adjustment_id in {a.id for a in passed}), _ZERO)
    facts: list[tuple[str, str]] = [
        ("Passed entries", str(len(passed))),
        ("Aggregate", f"{aggregate:,.2f}"),
    ]
    if current is not None:
        band = band_of(aggregate, current.overall, current.performance, current.trivial)
        facts.append(("Against materiality", BAND_WORDS[band]))
    out.append(
        Judgment("uncorrected_misstatements", "Uncorrected misstatements", tuple(facts), True)
    )
    return out


BAND_WORDS: Final = {
    "clearly_trivial": "Clearly trivial",
    "below_performance": "Below performance materiality",
    "below_overall": "Above performance materiality",
    "above_overall": "At or above overall materiality",
}


# --- Progress for the engagement dashboard (SPEC-317; TASK-346) -------------------------------


async def progress(tenant: TenantContext, engagement_id: UUID) -> list[ProgressFact]:
    """Procedures run, findings concluded, entries awaiting approval and passed, by code."""
    async with tenant_session(tenant) as session:
        procedures, findings, severities = await engagement_progress_rows(session, engagement_id)
        entries = await engagement_adjustments(session, engagement_id)
        events = await adjustment_events_of(session, [a.id for a in entries])
    concluded = {s.finding_id for s in severities if s.stage == "concluded"}
    statuses = [status_of([e for e in events if e.adjustment_id == a.id]) for a in entries]
    selected = sum(1 for p in procedures if p.status == "selected")
    failed = sum(1 for p in procedures if p.status == "failed")
    return [
        ProgressFact(
            "fieldwork", "procedures", "Procedures run", selected, len(procedures), failed > 0
        ),
        ProgressFact(
            "fieldwork",
            "findings",
            "Findings concluded",
            len(concluded & {f.id for f in findings}),
            len(findings),
            len(findings) > len(concluded),
        ),
        ProgressFact(
            "fieldwork",
            "entries_awaiting",
            "Proposed entries awaiting approval",
            statuses.count("proposed"),
            None,
            statuses.count("proposed") > 0,
        ),
        ProgressFact(
            "fieldwork",
            "passed_entries",
            "Passed entries",
            statuses.count("client_declined"),
            None,
            False,
        ),
    ]
