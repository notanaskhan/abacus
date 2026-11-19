"""ADM-11's dashboard read (Q-05-T08; TASK-8715; SPEC-711 AC-1, AC-2; DEC-5711).

The register's objectives and open findings (practice's own tables), the override projection
(Q-05-T07), and the signals other modules register (`register_quality_signal`: independence gaps,
open consultations, accuracy), combined by `compute/quality_dashboard.py`. An office narrows the
override rate only; objectives stay firm-wide.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.practice import overrides
from abacus.modules.practice.compute.quality_dashboard import (
    FindingFacts,
    ObjectiveFacts,
    at_risk_objectives,
    components,
    days_to,
)

Signal = Callable[[TenantContext], Awaitable[int]]
_signals: dict[str, Signal] = {}
SIGNALS: Final = ("independence_gap", "consultations_open")


def register_quality_signal(name: str, reader: Signal) -> None:
    """A module's count behind one dashboard signal (independence gaps, open consultations)."""
    if name not in SIGNALS:
        raise ValueError(f"unknown quality signal {name!r}")
    _signals[name] = reader


_OBJECTIVES = text("SELECT component, health_flag FROM qm_objectives WHERE active")
_FINDINGS = text("SELECT status, due_on FROM qm_findings WHERE status <> 'remediated'")
_SETTINGS = text("SELECT evaluation_as_of_month_day FROM qm_settings LIMIT 1")


ONE_PLACE: Final = Decimal("0.1")


async def accuracy(tenant: TenantContext, cycle: int) -> dict[str, object]:
    """ADM-11 f (AC-4; S51 partials): the cycle's draft-vs-final accuracy over the prior tax
    year's filed returns: of the fields the agent drafted, how many a person changed by the
    final; 1 - changed ÷ fields to one place (None with nothing drafted). Firm-wide."""
    from abacus.modules.review.api import draft_accuracy
    from abacus.modules.tax.api import filed_return_worksheets

    filed, worksheets = await filed_return_worksheets(tenant, cycle - 1)
    fields, changed = await draft_accuracy(tenant, "return_worksheet", worksheets)
    rate = (
        None
        if fields == 0
        else (100 - Decimal(changed) * 100 / Decimal(fields)).quantize(ONE_PLACE, ROUND_HALF_UP)
    )
    return {"returns_filed": filed, "fields": fields, "changed": changed, "accuracy": rate}


async def dashboard(
    tenant: TenantContext, now: datetime, office: UUID | None
) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        objectives = [
            ObjectiveFacts(str(r[0]), r[1] == "at_risk")
            for r in (await session.execute(_OBJECTIVES)).all()
        ]
        findings = [
            FindingFacts(None, str(r[0]), cast(date | None, r[1]))
            for r in (await session.execute(_FINDINGS)).all()
        ]
        month_day = await session.scalar(_SETTINGS) or "12-15"
    rates = await overrides.overrides(tenant, now, "30d", office)
    over = sum(1 for r in cast(list[dict[str, object]], rates["rows"]) if r["above_tolerance"])
    signals = {name: await reader(tenant) for name, reader in _signals.items()}
    signals["agent_over_tolerance"] = over
    today = now.date()
    health = components(objectives, findings, signals, today)
    month, day = (int(p) for p in str(month_day).split("-"))
    evaluation = date(today.year, month, day)
    if evaluation < today:
        evaluation = date(today.year + 1, month, day)
    return {
        "cycle_year": today.year,
        "office_id": office,
        "objectives_firm_wide": True,
        "tiles": {
            "objectives_at_risk": at_risk_objectives(objectives, health),
            "objectives": len(objectives),
            "findings_open": len(findings),
            "override_rate": rates["rate"],
            "overrides": rates["overrides"],
            "outputs": rates["outputs"],
            "tolerance_pct": rates["tolerance_pct"],
            "accuracy": (await accuracy(tenant, today.year))["accuracy"],
            "consultations_open": signals.get("consultations_open", 0),
            "days_to_evaluation": days_to(evaluation, today),
        },
        "components": [
            {"component": h.component, "health": h.health, "signals": list(h.signals)}
            for h in health
        ],
    }


__all__ = ["SIGNALS", "dashboard", "register_quality_signal"]
