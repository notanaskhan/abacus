"""PLT-01 a's six tenant rows and the figures derived from them, for the G-04 stubs' tests and
goldens (G-04-T03; SPEC-680 AC-1; DEC-5203). Moved out of `abacus.modules.platform.g04_fixtures`
(TASK-8869): the synthetic firms' names are content, never a product constant (P-08-T22 T14).
Synthetic data only (DEC-1530)."""

from __future__ import annotations

from datetime import date
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
