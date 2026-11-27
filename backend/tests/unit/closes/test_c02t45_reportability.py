"""C-02-T45 (TASK-9003; C-02 F9 US-9.1; ADR-050): the reportability engine over Copperleaf's 2026
payments. Row acceptance: "The engine marks exactly six Copperleaf vendors reportable at $2,000,
excludes Cascade Coffee's $41,260 card payments and keeps Hartwell & Lowe reportable as an
attorney." Rents (a person's classification, DEC-6009) report on 1099-MISC box 1."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import information_returns as irc
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as seed

THRESHOLD = irc.Threshold(D("2000.00"), None)
ENTITY: dict[str, str] = {
    "Larimer Street Properties, LLC": "llc_p",
    "Brightwater Hale LLP": "partnership",
    "Sound Electric Contractors, LLC": "single_member_llc",
    "Elena Ruiz Design": "individual",
    "Hartwell & Lowe LLP": "partnership",
    "Mile High Window Cleaning": "individual",
    "Front Range Plumbing Co.": "individual",
    "Rocky Ridge Dairy Co.": "c_corporation",
    "Kestrel Marketing Co.": "s_corporation",
    "Cedar Mutual Insurance Co.": "c_corporation",
    "Front Range Bank": "c_corporation",
    "Cascade Coffee Importers, Inc.": "unknown",
}


def _classify(vendor: seed.Vendor) -> irc.Classification:
    method = {"card": "card", "ach": "ach"}.get(seed.PAID_BY.get(vendor.name, "check"), "check")
    return irc.classify(
        irc.VendorFacts(
            ENTITY[vendor.name],
            vendor.is_attorney,
            None,
            paid_rents=vendor.name == "Larimer Street Properties, LLC",
        ),
        [irc.Payment(method, vendor.amount, 1)],
        THRESHOLD,
    )


def test_c02t45_acceptance_exactly_six_copperleaf_vendors_are_reportable() -> None:
    found = {v.name: _classify(v) for v in seed.VENDORS}
    reportable = sorted(n for n, c in found.items() if c.reportability == "reportable")
    assert reportable == sorted(
        [
            "Larimer Street Properties, LLC",
            "Brightwater Hale LLP",
            "Sound Electric Contractors, LLC",
            "Elena Ruiz Design",
            "Hartwell & Lowe LLP",
            "Mile High Window Cleaning",
        ]
    )
    for vendor in seed.VENDORS:  # the engine agrees with the seed's own treatment column
        assert found[vendor.name].reportability == vendor.treatment, vendor.name


def test_c02t45_acceptance_cascade_coffees_card_payments_are_excluded() -> None:
    cascade = next(v for v in seed.VENDORS if v.name.startswith("Cascade"))
    assert _classify(cascade) == irc.Classification("paid_by_card", D("0.00"), None, None)


def test_c02t45_acceptance_hartwell_and_lowe_stay_reportable_as_an_attorney() -> None:
    hartwell = next(v for v in seed.VENDORS if v.name.startswith("Hartwell"))
    assert _classify(hartwell) == irc.Classification("reportable", D("3600.00"), "nec", "1")
    # an attorney is reportable even as a corporation
    assert (
        irc.classify(
            irc.VendorFacts("c_corporation", True, None),
            [irc.Payment("check", D("3600"), 1)],
            THRESHOLD,
        ).reportability
        == "reportable"
    )


def test_c02t45_rents_report_on_1099_misc_box_1() -> None:
    larimer = next(v for v in seed.VENDORS if v.name.startswith("Larimer"))
    assert _classify(larimer) == irc.Classification("reportable", D("78400.00"), "misc", "1")


@pytest.mark.parametrize(
    ("facts", "amount", "expected"),
    [
        (
            irc.VendorFacts("individual", False, None, paid_rents=True),
            "1999.99",
            "below_threshold",
        ),
        (
            irc.VendorFacts("c_corporation", False, None, paid_rents=True),
            "50000",
            "exempt_corporation",
        ),
        (
            irc.VendorFacts("individual", False, "exempt_payee", paid_rents=True),
            "5000",
            "exempt_corporation",
        ),
    ],
)
def test_c02t45_rents_never_make_a_vendor_reportable_on_their_own(
    facts: irc.VendorFacts, amount: str, expected: str
) -> None:
    found = irc.classify(facts, [irc.Payment("ach", D(amount), 1)], THRESHOLD)
    assert (found.reportability, found.form, found.box) == (expected, None, None)


def test_c02t45_an_attorney_who_is_paid_rent_still_reports_fees_on_nec() -> None:
    """Gross proceeds and rents to one payee are separate boxes; the engine reports the vendor's
    classification it was given: attorney fees win (NEC box 1), as the CLS-13 seed shows."""
    found = irc.classify(
        irc.VendorFacts("partnership", True, None, paid_rents=True),
        [irc.Payment("check", D("3600"), 1)],
        THRESHOLD,
    )
    assert (found.form, found.box) == ("nec", "1")
