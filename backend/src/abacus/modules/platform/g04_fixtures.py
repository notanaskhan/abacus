"""Brightwater Hale's G-04 figures for the stubs, fixture scenarios and goldens (G-04-T03;
SPEC-680 AC-1, AC-26, AC-28, AC-32, AC-35, AC-36, AC-53, AC-54; DEC-5203).

Transcribed from the PLT-01, ADM-14 and SHL-05 handoffs (demo clock Mon Sep 14, 2026, 9:24 AM
CT for the console and the drawer; Thu Oct 1, Fri Oct 9 and Wed Oct 14, 2026 for ADM-14 a, b, c).
Every derived figure (tile counts, the seats footer, meter totals and percentages, thresholds,
minutes left, the overage, rate-band head counts) is computed here by code, never typed. The
seed slices (G-04-T13) load the same facts; the services (G-04-T09 to T12) replace these
computations and the goldens pin them. Synthetic data only.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal, NamedTuple

Health = Literal["healthy", "degraded", "onboarding"]


class Tenant(NamedTuple):
    code: str
    name: str
    seats_used: int
    seats_total: int
    modules: tuple[str, ...]
    health: Health
    reason: str | None
    channel: str
    since: date
    sandbox_of: str | None = None


# PLT-01 a: six rows, in the handoff's order.
TENANTS: Final = (
    Tenant(
        "tnt_bh01",
        "Brightwater Hale LLP",
        46,
        46,
        ("tax_services", "audit_assurance", "client_accounting", "advisory"),
        "healthy",
        None,
        "Stable · 2026.9",
        date(2026, 1, 5),
    ),
    Tenant(
        "tnt_bh01-sbx",
        "Brightwater Hale LLP — Training sandbox",
        0,
        0,
        ("tax_services", "audit_assurance", "client_accounting", "advisory"),
        "healthy",
        None,
        "Stable · 2026.9",
        date(2026, 1, 5),
        "tnt_bh01",
    ),
    Tenant(
        "tnt_tr07",
        "Tidewell Rourke & Co. LLP",
        128,
        140,
        ("tax_services", "audit_assurance"),
        "healthy",
        None,
        "Stable · 2026.9",
        date(2026, 3, 2),
    ),
    Tenant(
        "tnt_km03",
        "Kessling Mott LLP",
        212,
        220,
        ("tax_services", "audit_assurance", "client_accounting"),
        "degraded",
        "tax_engine_sync_latency",
        "Early access · 2026.10-rc1",
        date(2026, 2, 9),
    ),
    Tenant(
        "tnt_op12",
        "Ostrander Pike CPAs",
        18,
        20,
        ("tax_services",),
        "healthy",
        None,
        "Stable · 2026.9",
        date(2026, 4, 20),
    ),
    Tenant(
        "tnt_aw15",
        "Ainsley Ward Partners",
        0,
        64,
        ("tax_services", "client_accounting"),
        "onboarding",
        "first_admin_invited",
        "Stable · 2026.9",
        date(2026, 9, 10),
    ),
)


def tiles(tenants: tuple[Tenant, ...] = TENANTS) -> dict[str, int]:
    """PLT-01 a tiles (AC-1): every tenant counts; seats exclude sandboxes."""
    counted = [t for t in tenants if t.sandbox_of is None]
    return {
        "tenants": len(tenants),
        "healthy": sum(t.health == "healthy" for t in tenants),
        "degraded": sum(t.health == "degraded" for t in tenants),
        "onboarding": sum(t.health == "onboarding" for t in tenants),
        "seats_used": sum(t.seats_used for t in counted),
        "seats_provisioned": sum(t.seats_total for t in counted),
    }


def seats_footer(tenants: tuple[Tenant, ...] = TENANTS) -> str:
    counted = [t for t in tenants if t.sandbox_of is None]
    t = tiles(tenants)
    terms = " + ".join(str(x.seats_used) for x in counted)
    return (
        f"Seats used {terms} = {t['seats_used']} of {t['seats_provisioned']} provisioned "
        "(sandbox excluded)."
    )


# ADM-14: Brightwater's plan and usage month (anchor 15: `2026-09` is Sep 15 to Oct 14).
INCLUDED_MINUTES: Final = 20_000
SEATS_TOTAL: Final = 46
SEATS_USED: Final = 46
USAGE_MONTH: Final = "2026-09"
ANCHOR_DAY: Final = 15
THRESHOLDS: Final = (75, 90, 100)
# ADM-14 a, Thu Oct 1, 9:20 AM: minutes by service line (stored integers from P-10's ledger).
BY_SERVICE_LINE_OCT_1: Final = (
    ("tax_services", 8_640),
    ("audit_assurance", 4_610),
    ("client_accounting", 1_420),
    ("advisory_attest", 120),
    ("firm_operations", 130),
)
USED_OCT_9: Final = 18_240  # ADM-14 b, Fri Oct 9, 4:30 PM
USED_OCT_14: Final = 20_860  # ADM-14 c, Wed Oct 14, 5:00 PM
ENGAGEMENT_DEFAULT: Final = 1_500
ENGAGEMENT_ALERT_PCT: Final = 80
GRANITE_PEAK_USED: Final = 1_240  # Granite Peak FY2026 FS audit


def used_oct_1() -> int:
    return sum(minutes for _, minutes in BY_SERVICE_LINE_OCT_1)


def percent(used: int, of: int) -> Decimal:
    """One decimal place, half up: 14,920 of 20,000 reads 74.6%."""
    return (Decimal(used) * 100 / Decimal(of)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def threshold_minutes(pct: int, included: int = INCLUDED_MINUTES) -> int:
    return included * pct // 100


def next_alert(used: int, included: int = INCLUDED_MINUTES) -> tuple[int, int] | None:
    """The next threshold not yet crossed and the minutes to it (ADM-14 a helper)."""
    for pct in THRESHOLDS:
        if used < threshold_minutes(pct, included):
            return pct, threshold_minutes(pct, included) - used
    return None


def over_included(used: int, included: int = INCLUDED_MINUTES) -> int:
    return max(used - included, 0)


def engagement_pct(used: int = GRANITE_PEAK_USED, budget: int = ENGAGEMENT_DEFAULT) -> int:
    """Whole percent, half up: 1,240 of 1,500 reads 83%."""
    return int((Decimal(used) * 100 / Decimal(budget)).quantize(Decimal("1"), ROUND_HALF_UP))


# ADM-14 a, Billing rates (the fake provider, synthetic firms only): (label, people, rate).
RATE_BANDS: Final = (
    ("Partner", 7, Decimal(450)),
    ("Manager & reviewer", 7, Decimal(300)),
    ("Senior", 11, Decimal(210)),
    ("Staff & preparer", 19, Decimal(150)),
    ("Operations", 2, None),
)
RATES_EFFECTIVE: Final = date(2026, 1, 1)


def rate_band_people() -> int:
    return sum(people for _, people, _ in RATE_BANDS)


# SHL-05 e at E0: the seven components in order; the incident note is the CCH row's.
STATUS_COMPONENTS: Final = (
    ("accrued_app", "Accrued app", "core", "operational", None),
    ("agents_workbench", "Agents & Workbench", "core", "operational", None),
    ("client_portal", "Client portal", "core", "operational", None),
    ("esign_identity", "E-signature & identity verification", "core", "operational", None),
    (
        "cch_axcess_tax_export",
        "CCH Axcess Tax export",
        "integration",
        "needs_attention",
        "Delays up to 15 min since 8:40 AM CT",
    ),
    ("qbo_sync", "QuickBooks Online sync", "integration", "operational", None),
    ("m365_mail_ingest", "Microsoft 365 mail ingest", "integration", "operational", None),
)

# SHL-05 d: help groups and article titles from the handoff.
HELP_GROUPS: Final = (
    ("suggested", "Suggested for this page", ("Reading the Tax Returns status tiles",)),
    ("tax_returns", "Tax returns", ("What 'Draft K-1 · pre-release' blocks",)),
    (
        "agents_approvals",
        "Agents & approvals",
        (
            "Approving agent proposals and checkpoints",
            "Within-threshold batch approvals and BH AJE thresholds v2",
        ),
    ),
    (
        "client_portal",
        "Client portal",
        ("Inviting a client's spouse or delegate", "Sending Form 8879 for e-signature"),
    ),
)
RELATED_ARTICLE: Final = ("Exporting a return to CCH Axcess: statuses and retries", 4)
SUGGESTIONS: Final = ("Ask about a sync", "Report a problem with an agent run")
