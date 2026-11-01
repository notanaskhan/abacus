"""The `standards` slice (K-02-T18; K-02 §3, US-3.5, US-5.1; KNW-04): Brightwater Hale's firm
standards and thresholds, loaded the way a firm loads its own. Synthetic, Brightwater Hale only;
nothing here is platform content, and no standard is a constant in the product.

Each standard is created by Margaret Okonkwo (practice leader, `firm_standard.create`) with its
owner, every version arrives as a workbook through the import path (`standards_import`'s format,
the same bytes `POST /v1/standards/{id}/imports` reads, then `standards.import_draft`), and the
owner publishes it (`firm_standard.publish`, owner only). The versions in effect at E0 are the
handoff's: six TY2025 checklists (1040 v6 · 38 · 162 returns, 1065 v4 · 42 · 38, 1120-S v3 · 36 ·
12, 1120 v2 · 33 · 5, 1041 v2 · 31 · 6, 990 v1 · 29 · 1: 224 returns) and the 1040 v7 TY2026
draft; review levels v2 (three tiers); BH-TAX-02 v1; AJE thresholds v2 after v1; variance v3;
materiality v2; document confidence v1; SSARS & CAS v1 with SSARS 27 off. Earlier versions
differ from the next so each publish is a real change.

The firm exists from Sep 1, 2026 on the timeline, so each version is published at setup with an
effective date on the day it is published (publishing refuses a past date); KNW-04's canon
("Published Jan 20, 2026") stays in the fixtures, as K-01's methodology did (DEC-652, DEC-1472).

**Demo-clock examples.** KNW-04 a's "How v2 sorted the August 2026 closes" reads the closes
provider, which C-01 registers; until then the examples fieldset is empty in the product and the
fixture carries Copperleaf's rows (`AUGUST_EXAMPLES`), which foot here as a seed test: four
entries within threshold, 11,860 + 700 + 2,140 + 5,320 = 20,020, and the 14,900 accrual held.

Opt-in (`--slice standards`, which brings `people` for the owners' seats).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "standards"
NEEDS: Final = ("people",)
CREATOR: Final = "MO"  # Margaret Okonkwo, practice leader: creates and imports
FLAGS: Final = ("knowledge.firm_standards",)
TAX_YEAR: Final = 2025
# BH-TAX-02's clients (KNW-04 d), signed by Daniel Reyes.
BH_TAX_02_CLIENTS: Final = (
    "Jonah & Claire Feld",
    "Ridgeline Property Partners, LP",
    "Calloway Family Trust",
    "Marcus & Dana Whitley",
)
# KNW-04 a's August 2026 example (Copperleaf): the four entries within threshold, approved as
# one batch by Raj Malhotra, and the accrual held for Priya Raman.
AUGUST_EXAMPLES: Final = (
    (11_860, "within"),
    (700, "within"),
    (2_140, "within"),
    (5_320, "within"),
)
AUGUST_HELD: Final = 14_900


@dataclass(frozen=True)
class Spec:
    key: str
    kind: str
    name: str
    owner: str  # seat
    versions: tuple[dict[str, object], ...]  # each version's payload, oldest first
    draft: dict[str, object] | None = None  # an unpublished next version
    usage: int | None = None  # returns on the version in effect (checklists)


def _items(form: str, n: int) -> list[dict[str, object]]:
    # The checklist's text is firm content (ADR-056): keyed placeholders, as the fixture holds.
    return [
        {"key": f"{form.lower()}-{i:02d}", "section": "Checks", "text": f"Check {i}"}
        for i in range(1, n + 1)
    ]


def _checklist(form: str, version: int, checks: int, usage: int) -> Spec:
    payloads: tuple[dict[str, object], ...] = tuple(
        {
            "kind": "review_checklist",
            "applies_to": {"form": form, "tax_year": TAX_YEAR},
            "items": _items(form, checks - (version - v)),
        }
        for v in range(1, version + 1)
    )
    draft: dict[str, object] | None = (
        {
            "kind": "review_checklist",
            "applies_to": {"form": form, "tax_year": TAX_YEAR + 1},
            "items": _items(form, checks),
        }
        if form == "1040"
        else None
    )
    return Spec(
        f"bh-{form.lower()}-review-checklist",
        "review_checklist",
        f"{form} Review Checklist",
        "DR",
        payloads,
        draft,
        usage,
    )


def _tiers(third: str) -> list[dict[str, object]]:
    return [
        {
            "tier": 1,
            "name": "Standard",
            "required_levels": ["L1", "L2"],
            "second_partner_review": False,
            "criteria": "The return meets no Tier 2 or Tier 3 criterion",
        },
        {
            "tier": 2,
            "name": "Elevated",
            "required_levels": ["L1", "L2", "L3"],
            "second_partner_review": False,
            "criteria": "Entity returns, multi-state returns and returns with an open IRS notice",
        },
        {
            "tier": 3,
            "name": "High",
            "required_levels": ["L1", "L2", "L3", "L4"],
            "second_partner_review": True,
            "criteria": third,
        },
    ]


def _limit(account_class: str, limit_usd: int) -> dict[str, object]:
    return {
        "account_class": account_class,
        "rule": "limit",
        "limit_usd": limit_usd,
        "approver_level": "senior_or_above",
        "batch": True,
    }


_AJE_TAIL: Final[tuple[dict[str, object], ...]] = (
    {
        "account_class": "All other classes",
        "rule": "review_required",
        "limit_usd": None,
        "approver_level": "manager_or_partner",
        "batch": False,
    },
    {
        "account_class": "Attest clients",
        "rule": "always_held",
        "limit_usd": None,
        "approver_level": "partner",
        "batch": False,
    },
)


def _variance(close_usd: int) -> dict[str, object]:
    return {
        "kind": "variance_thresholds",
        "rows": [
            {"context": "close_flux", "pct": "10", "amount_usd": close_usd},
            {"context": "ssars_review_analytics", "pct": "10", "amount_usd": 50_000},
            {"context": "tax_two_year", "pct": "10", "amount_usd": 5_000},
        ],
    }


def _materiality(ebp_high: str) -> dict[str, object]:
    return {
        "kind": "materiality_ranges",
        "rows": [
            {
                "engagement_kind": "EBP (defined contribution)",
                "benchmark": "Net assets available for benefits",
                "low_pct": "1.0",
                "high_pct": ebp_high,
            },
            {
                "engagement_kind": "For-profit FS audit",
                "benchmark": "Pre-tax income",
                "low_pct": "3",
                "high_pct": "7",
            },
            {
                "engagement_kind": "Not-for-profit",
                "benchmark": "Total expenses",
                "low_pct": "1",
                "high_pct": "2",
            },
        ],
        "performance_materiality": {"low_pct": "50", "high_pct": "75"},
        "clearly_trivial_pct": "5",
    }


STANDARDS: Final[tuple[Spec, ...]] = (
    _checklist("1040", 6, 38, 162),
    _checklist("1065", 4, 42, 38),
    _checklist("1120-S", 3, 36, 12),
    _checklist("1120", 2, 33, 5),
    _checklist("1041", 2, 31, 6),
    _checklist("990", 1, 29, 1),
    Spec(
        "bh-review-levels",
        "review_levels",
        "Review levels",
        "DR",
        (
            {
                "kind": "review_levels",
                "tiers": _tiers(
                    "Positions needing Form 8275 disclosure and first-year complex entities"
                ),
            },
            {
                "kind": "review_levels",
                "tiers": _tiers(
                    "Positions needing Form 8275 disclosure, first-year complex entities, "
                    "returns with K-1s to other Brightwater clients"
                ),
            },
        ),
    ),
    # BH-TAX-02's payload names clients and the signer by id; the loader resolves them.
    Spec("bh-tax-02", "return_approval_policy", "Return approval", "DR", ({},)),
    Spec(
        "bh-aje-thresholds",
        "aje_thresholds",
        "AJE thresholds",
        "PR",
        (
            {
                "kind": "aje_thresholds",
                "rows": [
                    _limit("Payroll accruals", 10_000),
                    _limit("Other accrued expenses", 7_500),
                    _limit("Prepaid expenses", 7_500),
                    _limit("Depreciation", 7_500),
                    _limit("Deferred revenue", 7_500),
                    *_AJE_TAIL,
                ],
            },
            {
                "kind": "aje_thresholds",
                "rows": [
                    _limit("Payroll accruals", 15_000),
                    _limit("Other accrued expenses", 10_000),
                    _limit("Prepaid expenses", 10_000),
                    _limit("Depreciation", 10_000),
                    _limit("Deferred revenue", 10_000),
                    *_AJE_TAIL,
                ],
            },
        ),
    ),
    Spec(
        "bh-variance-thresholds",
        "variance_thresholds",
        "Variance thresholds",
        "PR",
        (_variance(1_000), _variance(2_000), _variance(2_500)),
    ),
    Spec(
        "bh-materiality-ranges",
        "materiality_ranges",
        "Materiality ranges",
        "MO",
        (_materiality("1.5"), _materiality("2.0")),
    ),
    Spec(
        "bh-document-confidence",
        "document_confidence",
        "Document confidence",
        "MO",
        (
            {
                "kind": "document_confidence",
                "hold_below_pct": "90",
                "auto_accept_above_pct": "98",
                "auto_accept_enabled": False,
            },
        ),
    ),
    Spec(
        "bh-ssars-cas",
        "ssars_cas_settings",
        "SSARS & CAS",
        "PR",
        ({"kind": "ssars_cas_settings", "early_adopt_ssars27": False},),
    ),
)


# A-03-T16 (DEC-1767): BH-EBP-210 Table 2, the firm's attribute sample sizes, loaded by the
# `sampling` slice (not the standards slice: KNW-04's E0 list stays as designed). Only the row
# the design shows is canon: moderate RMM, 10 % tolerable, 0 % expected, at 90 % confidence, 25.
TABLE_2: Final = Spec(
    "bh-ebp-210-table-2",
    "attribute_sample_sizes",
    "BH-EBP-210 Table 2 · attribute sample sizes",
    "MO",
    (
        {
            "kind": "attribute_sample_sizes",
            "confidence_pct": "90",
            "rows": [{"rmm": "moderate", "tolerable_pct": "10", "expected_pct": "0", "size": 25}],
        },
    ),
)


def spec_of(key: str) -> Spec:
    return next(s for s in (*STANDARDS, TABLE_2) if s.key == key)


@register_slice(SLICE)
def standards_events() -> list[Event]:
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    start = SETUP_AT + timedelta(hours=2)
    for n, spec in enumerate(STANDARDS):
        base = {"key": spec.key}
        events.append(
            Event(
                f"standard-create:{spec.key}",
                start + timedelta(seconds=n),
                "standards.created",
                CREATOR,
                SLICE,
                {**base, "kind": spec.kind, "name": spec.name, "owner": spec.owner},
            )
        )
        # One version a day from Sep 1, so each publish's effective date follows the last.
        for v in range(1, len(spec.versions) + 1):
            day = start + timedelta(days=v - 1, minutes=5, seconds=n)
            events.append(
                Event(
                    f"standard-import:{spec.key}:v{v}",
                    day,
                    "standards.version_imported",
                    CREATOR,
                    SLICE,
                    {**base, "version": v},
                )
            )
            events.append(
                Event(
                    f"standard-publish:{spec.key}:v{v}",
                    day + timedelta(minutes=5),
                    "standards.version_published",
                    spec.owner,
                    SLICE,
                    {**base, "version": v},
                )
            )
        if spec.draft is not None:
            events.append(
                Event(
                    f"standard-import:{spec.key}:draft",
                    start + timedelta(days=len(spec.versions), minutes=5, seconds=n),
                    "standards.version_imported",
                    CREATOR,
                    SLICE,
                    {**base, "version": len(spec.versions) + 1, "draft": True},
                )
            )
    return events


def payload_of(spec: Spec, version: int) -> dict[str, object]:
    """The version's payload (the unpublished draft after the last published one)."""
    if version <= len(spec.versions):
        return spec.versions[version - 1]
    if spec.draft is None:
        raise LookupError(f"{spec.key} has no version {version}")
    return spec.draft


__all__ = [
    "AUGUST_EXAMPLES",
    "AUGUST_HELD",
    "BH_TAX_02_CLIENTS",
    "NEEDS",
    "SLICE",
    "STANDARDS",
    "TABLE_2",
    "Spec",
    "payload_of",
    "spec_of",
    "standards_events",
]
