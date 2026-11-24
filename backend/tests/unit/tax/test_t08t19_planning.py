"""T-08-T19 (TASK-8914; SPEC-710 AC-27; T-08 AC5.1, AC5.5, AC5.7; DEC-5916; amber): planning
rules, calculators, the consent filter and the strip, by code.

Row acceptance: "Daniel's portfolio reads 58 clients, $1.2M and 1 consent-blocked, Ferris is Not
screened with no model call, and Feld's savings compute to about 1,810." Here: the Feld bunching
estimate is 1,811 from the return's own lines and the TY2025 parameters (5,659 x 32%); the
handoff's other estimates (Shah 8,225, Whitley 1,650) come from the same calculators; a filing
unit without both consents is Not screened (the screen calls no narrator for it: the
integration test); and the strip over a 71-opportunity portfolio across 58 clients reads 58,
about $1.2M and 1 consent-blocked.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from abacus.modules.tax.planning import calculators as calc
from abacus.modules.tax.planning import rules
from abacus.modules.tax.planning import service as ps

D = Decimal
P = calc.parameters(2025)
BACKEND = Path(ps.__file__).resolve().parents[5]


def _facts(lines: dict[str, str], form: str = "1040") -> rules.ReturnFacts:
    status: calc.FilingStatus = "mfj"
    return rules.ReturnFacts(
        form, 2025, status, {k.replace("_", ".", 1): D(v) for k, v in lines.items()}
    )


FELD = _facts({"1040_11": "598030", "scha_5e": "10591", "scha_8a": "18240", "scha_11": "12500",
                 "1040_15": "496000"})  # fmt: skip


def test_feld_savings_compute_to_about_1810() -> None:
    found = rules.daf_bunching(FELD, P)
    assert found is not None
    f = found.estimate.figures
    assert (f["floor"], f["without_gifts"], f["standard"]) == ("2990", "28831", "31500")
    assert (f["unbunched"], f["bunched"], f["difference"]) == ("76682", "82341", "5659")
    assert f["rate_pct"] == "32" and found.estimate.savings == D("1811")
    assert found.title == "Bunch 2026–2027 gifts through a donor-advised fund"  # noqa: RUF001
    text = rules.rationale(found)
    assert "28,831" in text and "31,500" in text and "about 1,811" in text and "2,990" in text
    basis = found.estimate.basis()
    assert basis["parameter_version"] == "ty2025.v1"
    assert basis["inputs"] == {"1040.11": "598030", "scha.11": "12500", "scha.5e": "10591",
                               "scha.8a": "18240"}  # fmt: skip


def test_bunching_needs_itemized_without_gifts_below_the_standard_deduction() -> None:
    above = _facts({"1040_11": "598030", "scha_5e": "10591", "scha_8a": "28240",
                      "scha_11": "12500", "1040_15": "496000"})  # fmt: skip
    assert rules.daf_bunching(above, P) is None
    small = _facts({"1040_11": "98030", "scha_5e": "1000", "scha_8a": "2000", "scha_11": "900",
                      "1040_15": "60000"})  # fmt: skip
    assert rules.daf_bunching(small, P) is None
    assert rules.daf_bunching(_facts({"scha_11": "12500"}, "1120s"), P) is None


def test_the_handoffs_other_estimates_come_from_the_same_calculators() -> None:
    shah = rules.solo_401k(_facts({"sch1_3": "184000", "1040_15": "560000"}), P)
    assert shah is not None and shah.estimate.savings == D("8225")  # 23,500 x 35%
    assert rules.solo_401k(_facts({"sch1_3": "184000", "sch1_16": "12000"}), P) is None
    whitley = rules.dependent_care_fsa(_facts({"f2441_3": "9400", "1040_15": "180000"}), P)
    assert whitley is not None and whitley.estimate.savings == D("1650")  # 7,500 x 22%
    assert whitley.title == "Dependent care FSA at the new 7,500 limit (2026)"
    assert rules.dependent_care_fsa(_facts({"f2441_3": "9400", "f2441_12": "5000"}), P) is None


def test_risk_and_eligibility_rules_carry_no_estimate() -> None:
    comp = rules.reasonable_compensation(
        _facts({"1120s_7": "60000", "1120s_21": "410000"}, "1120s"), P
    )
    assert comp is not None and comp.estimate.savings is None
    assert comp.title == "Reasonable compensation review for the owner"
    assert (
        rules.reasonable_compensation(
            _facts({"1120s_7": "260000", "1120s_21": "410000"}, "1120s"), P
        )
        is None
    )
    young = rules.ReturnFacts("1040", 2025, "single", {"1040.4a": D("30000"),
                                                       "scha.11": D("8000")}, 60)  # fmt: skip
    assert rules.qcd(young, P) is None  # 62 by 2027: not within the planning years
    near = rules.ReturnFacts("1040", 2025, "single", {"1040.4a": D("30000"),
                                                      "scha.11": D("8000")}, 69)  # fmt: skip
    assert rules.qcd(near, P) is not None  # 71 by 2027
    varga = rules.ReturnFacts("1040", 2025, "single", {"1040.4a": D("30000"),
                                                       "scha.11": D("8000")}, 68)  # fmt: skip
    assert rules.qcd(varga, P) is None  # 70 by 2027: not yet 70 1/2
    roth = rules.roth_conversion(_facts({"1040_15": "150000", "1040_4b": "20000"}), P)
    assert roth is not None and roth.estimate.figures["room"] == "56700"  # 206,700 - 150,000
    assert rules.roth_conversion(_facts({"1040_15": "450000", "1040_4b": "20000"}), P) is None


def test_marginal_rates_follow_the_reviewed_brackets() -> None:
    assert calc.marginal_rate(D("496000"), "mfj", P) == D("32")
    assert calc.marginal_rate(D("501050"), "mfj", P) == D("32")
    assert calc.marginal_rate(D("501051"), "mfj", P) == D("35")
    assert calc.marginal_rate(D("900000"), "single", P) == D("37")
    assert calc.bracket_room(D("900000"), "single", P) == D("0")
    with pytest.raises(LookupError):
        calc.parameters(1999)


def test_the_consent_filter() -> None:
    assert ps.consent_status("tax_service", tri_valid=True, other_services=False) == "open"
    # Ferris: half-signed consents, so the model may not narrate: Not screened, no outreach.
    assert ps.consent_status("tax_service", tri_valid=False, other_services=False) == (
        "not_screened"
    )
    assert ps.consent_status("non_tax_product", tri_valid=True, other_services=False) is None
    assert ps.consent_status("non_tax_product", tri_valid=True, other_services=True) == "open"


def test_filing_status_from_the_return_or_the_filing_unit() -> None:
    assert ps.filing_status("hoh", "individual") == "hoh"
    assert ps.filing_status(None, "household_mfj") == "mfj"
    assert ps.filing_status(None, "individual") == "single"
    assert ps.filing_status("qss", None) == "mfj"


def _opportunity(client: UUID, status: ps.Status, savings: str | None) -> ps.Opportunity:
    return ps.Opportunity(
        id=uuid4(), engagement_id=uuid4(), work_item_id=uuid4(), client_id=client,
        client_name="c", source_kind="rule", rule_key="daf_bunching", category="charitable",
        product_kind="tax_service", title="t", status=status, previous_status=None,
        est_savings=None if savings is None else D(savings), rationale="r",
        rationale_source="template", consent_basis="301_7216_2h", owner_user_id=None,
        project_engagement_id=None, raised_message_id=None, raised_at=None, row_version=1,
        tax_year=2025,
    )  # fmt: skip


def test_the_strip_reads_58_clients_about_1_2m_and_1_consent_blocked() -> None:
    clients = [uuid4() for _ in range(58)]
    items: list[ps.Opportunity] = []
    # 71 live opportunities over 58 clients: 58 open (one per client, 20,000 each = 1,160,000),
    # 8 more open on the first clients (5,000 each = 40,000), 2 accepted, 1 declined (closed),
    # 1 raised, 1 not screened (the consent-blocked client), plus 3 dismissed (hidden).
    items += [_opportunity(c, "open", "20000") for c in clients]
    items += [_opportunity(clients[i], "open", "5000") for i in range(8)]
    items += [_opportunity(clients[i], "accepted", "3203") for i in range(2)]
    items += [_opportunity(clients[10], "raised", None)]
    items += [_opportunity(clients[11], "not_screened", None)]
    items += [_opportunity(clients[12], "declined", "900")]
    items += [_opportunity(clients[13], "dismissed", "700") for _ in range(3)]
    found = ps.summarise(items, 2025)
    assert found.clients_to_contact == 58 and found.clients == 58
    assert found.opportunities == 70  # live: open 66 + accepted 2 + raised 1 + not screened 1
    assert found.est_savings == D("1200000")  # "about $1.2M": open and raised estimates
    assert found.consent_blocked == 1
    assert found.talking_points == "template"


def test_manual_rule_keys_fit_the_column_and_routes_are_live() -> None:
    import re

    key = "manual.txt03_add_to_planning.0123456789abcdef"
    assert re.fullmatch(r"[a-z][a-z0-9_.]{0,59}", key)
    contract = (BACKEND / "src/abacus/modules/tax/practice_tools_contract.py").read_text("utf-8")
    start = contract.index('"/planning-summary"')
    end = contract.index('f"{_R}/amendments"')
    assert "NotImplementedYet" not in contract[start:end]
    for call in ("ps.summary(", "ps.opportunities(", "ps.prepare_raise(", "ps.raise_with_client(",
                 "ps.create_project(", "ps.decline(", "ps.dismiss(", "ps.restore(",
                 "ps.create_manual("):  # fmt: skip
        assert call in contract[start:end]


def test_the_parameter_file_is_pinned_and_awaits_its_cpa_review() -> None:
    assert P.version_ref == "ty2025.v1" and P.planning_years == (2026, 2027)
    assert P.standard_deduction["mfj"] == D("31500")
    assert P.get("dependent_care_fsa", "limit") == D("7500")
    assert P.reviewed_by is None  # the CPA signs the TY2025 planning memo (DEC-5916)
