"""T-07-T06 (TASK-8020; T-07 §8.1; SPEC-656 AC-15.4): consumer contract tests for the contracts
T-07 consumes in new ways, run in the providers' stage 2. Each test names the provider field or
value T-07 reads, so a rename fails here first. Plus FW-1 / EW-1's own route inventory and the
typed footing fixtures consumers build on (AC-15.3).

The C4 `instrument_clause` kind itself (ADR-343) registers with T-07-T11; until then this suite
pins the `document_text` verifier the clause kind reuses and the ADR's locator keys."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import get_args

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from abacus.ai_gateway.boundary import REASONS
from abacus.modules.agents.tools.registry import AgentTool, DataClass, ToolKind, ToolRefusal
from abacus.modules.evidence.citations.registry import KINDS
from abacus.modules.practice.compute.calendar import Offset, Rule, due_dates
from abacus.modules.signatures.contract import Purpose
from abacus.modules.signatures.imports import EFILE_PURPOSES
from abacus.modules.tax.estate_contract import estate_router
from abacus.modules.tax.fiduciary_contract import CLAUSE_GOVERNED, fiduciary_router
from abacus.modules.tax.k1_packages import (
    _FORMS,  # pyright: ignore[reportPrivateUsage]  # same module (tax)
)

FIXTURES = Path(__file__).parent / "fixtures"
ADR_343 = Path(__file__).parents[4] / "docs" / "adr" / "ADR-343-citation-kind-instrument-clause.md"


# --- C4: citations (P-03), and the ADR-343 amendment T-07-T11 builds --------------------------


def test_c4_document_text_is_a_kind_the_clause_verifier_reuses() -> None:
    assert "document_text" in KINDS


def test_c4_adr_343_names_the_locator_t07_writes() -> None:
    text = ADR_343.read_text(encoding="utf-8")
    assert "status: accepted" in text
    for key in ("instrument_id", "segmentation_id", "clause_id", "quote_sha256"):
        assert key in text, key


# --- C7: envelopes (N-02) ---------------------------------------------------------------------


def test_c7_form_8879_f_is_a_purpose_in_the_efile_family() -> None:
    assert "form_8879_f" in get_args(Purpose)
    assert "form_8879_f" in EFILE_PURPOSES


# --- C10 with T-02's K-1 packages: the 1041 mode ------------------------------------------------


def test_c10_k1_packages_take_form_1041() -> None:
    assert "1041" in _FORMS


# --- C17: tool registry (P-10) ----------------------------------------------------------------


def test_c17_the_tool_shape_the_three_tax_tools_register() -> None:
    fields = set(AgentTool.__dataclass_fields__)
    assert {"name", "kind", "action", "description", "data_class", "untrusted"} <= fields
    assert {"read", "propose"} <= set(get_args(ToolKind))
    assert "tri" in get_args(DataClass)
    assert "consent_required" in get_args(ToolRefusal)


# --- C19: the §7216 consent gate (T-01) -------------------------------------------------------


def test_c19_the_gateway_refuses_tri_without_both_consents_under_its_own_reason() -> None:
    assert "consent_7216" in REASONS


# --- C21: due-date rules (K-02) ---------------------------------------------------------------


def test_c21_a_706_reads_nine_months_after_death_and_4768_rolls_from_sunday() -> None:
    # AC-14.1: DOD Feb 2, 2026 → Nov 2, 2026; +6 months is Sunday May 2, 2027 → Mon May 3 (§7503).
    rule = Rule(
        form="706",
        fye_rule="any",
        original=Offset(months=9, day=2),
        extension_form="4768",
        extension_months=6,
    )
    dates = due_dates(rule, date(2026, 2, 2), frozenset())
    assert dates.original_due_on == date(2026, 11, 2)
    assert dates.extension_form == "4768"
    assert dates.extended_due_on == date(2027, 5, 3)


def test_c21_a_calendar_1041_extends_to_sep_30() -> None:
    rule = Rule(
        form="1041",
        fye_rule="calendar_year",
        original=Offset(months=3, day=15),
        extension_form="7004",
        extension_months=5,
        extension_day=30,
    )
    dates = due_dates(rule, date(2025, 12, 31), frozenset())
    assert dates.original_due_on == date(2026, 4, 15)
    assert dates.extended_due_on == date(2026, 9, 30)


# --- FW-1 and EW-1 themselves (AC-15.3) -------------------------------------------------------


def _routes(router: APIRouter) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }


def test_ac15_3_fw1_and_ew1_route_inventory() -> None:
    assert len(_routes(fiduciary_router)) == 25
    assert len(_routes(estate_router)) == 11
    assert ("POST", "/v1/tax/returns/{return_id}/instrument/read") in _routes(fiduciary_router)
    assert ("GET", "/v1/tax/returns/{return_id}/estate/computation") in _routes(estate_router)


def test_ac15_3_no_clause_model_carries_text() -> None:
    from abacus.modules.tax.fiduciary_contract import InstrumentClauseOut

    assert "text" not in InstrumentClauseOut.model_fields
    assert "text_sha256" in InstrumentClauseOut.model_fields


def test_ac3_1_the_clause_governed_keys() -> None:
    assert {
        "grantor_status",
        "trust_type",
        "fai_definition",
        "trustee_fees",
        "principal_invaded",
    } == CLAUSE_GOVERNED


def _money(value: str) -> Decimal:
    return Decimal(value)


def test_ac15_3_calloway_foots_430_000_less_30_000_to_400_000() -> None:
    data = json.loads((FIXTURES / "calloway_2025.json").read_text(encoding="utf-8"))
    lines = {line["kind"]: _money(line["amount"]) for line in data["fai_lines"]}
    fai = lines["interest"] + lines["ordinary_dividends"]
    fees = sum(_money(e["amount"]) for e in data["trust_expenses"])
    expected = data["expected"]
    assert fai == _money(expected["fai"]) == Decimal("430000.00")
    assert fai - fees == _money(expected["dni"]) == Decimal("400000.00")
    paid = sum(_money(d["amount"]) for d in data["trust_distributions"])
    assert min(paid, fai - fees) == _money(expected["income_distribution_deduction"])
    boxes = [
        sum(_money(a[box]) for a in expected["allocations"])
        for box in ("box_1", "box_2a", "box_2b")
    ]
    assert boxes == [Decimal("60000.00"), Decimal("180000.00"), Decimal("144000.00")]
    assert sum(_money(a["dni_allocated"]) for a in expected["allocations"]) == paid


def test_ac15_3_thornbury_foots_16_400_000_less_900_000_to_15_500_000() -> None:
    data = json.loads((FIXTURES / "thornbury_706.json").read_text(encoding="utf-8"))
    gross = sum(_money(a["dod_value"]) for a in data["assets"])
    avd = sum(_money(a["avd_value"]) for a in data["assets"])
    basis = sum(_money(a["basis_to_1041"]) for a in data["assets"] if a["basis_to_1041"])
    deductions = sum(_money(d["amount"]) for d in data["deductions"])
    expected = data["expected"]
    assert gross == _money(expected["gross_estate"]) == Decimal("16400000.00")
    assert avd == _money(expected["avd_total"])
    assert basis == _money(expected["basis_to_1041"])
    assert gross - deductions == _money(expected["taxable_estate"]) == Decimal("15500000.00")


@pytest.mark.parametrize("schedule", ["D", "I"])
def test_ac12_1_basis_is_null_for_ird_and_non_probate_life_insurance(schedule: str) -> None:
    data = json.loads((FIXTURES / "thornbury_706.json").read_text(encoding="utf-8"))
    row = next(a for a in data["assets"] if a["schedule"] == schedule)
    assert row["basis_to_1041"] is None
