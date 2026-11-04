"""ADR-078 independent tests, part 1 (N-04-T15; N-04 US-4.1 to US-4.4), written apart from the
compute library (T04), the core (T06) and intake (T07): goldens for the CP3219A and preferential
income paths, Hypothesis purity and idempotence, intake's lifecycle guards in their order (not
ready, low confidence, duplicate), and the matrix: every notice write is denied to the agent and
every portal principal, and the TIN-bearing writes require an onshore user.
"""

from __future__ import annotations

import inspect
from decimal import Decimal as D
from pathlib import Path
from typing import cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.notices import intake
from abacus.modules.notices.compute import bracket, notice_types, underreporter
from abacus.modules.notices.compute.underreporter import InformationReturn, ProposedLine

ROOT = Path(__file__).resolve().parents[4]
MATRIX = cast(
    dict[str, dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/notices.yaml").read_text())[
        "actions"
    ],
)
WRITES = sorted(a for a in MATRIX if a.split(".")[1] not in {"read"})
PORTAL = ("client_admin", "client_contributor", "third_party")


def test_cp3219a_is_an_underreporter_notice() -> None:
    t = notice_types.type_of("CP3219A")
    assert t.analysis_kind == "underreporter_comparison"


def test_preferential_income_is_never_bracket_checked() -> None:
    check = bracket.check("mfj", 2024, D("100000"), D("110000"), D("1500.00"), preferential=True)
    assert (check.checked, check.agrees, check.reason) == (False, False, bracket.PREFERENTIAL)
    assert check.notice == D("1500.00")


def test_whitley_difference_is_explained_by_the_two_missing_1099_ints() -> None:
    c = underreporter.compare(
        {"interest": D("412.00")},
        [ProposedLine("interest", "Taxable interest", D("412.00"), D("3532.00"))],
        [
            InformationReturn("Front Range Bank", "1099-INT", D("1870.00"), on_return=False),
            InformationReturn("Lakeview Credit Union", "1099-INT", D("1250.00"), on_return=False),
        ],
    )
    assert (c.income_difference, c.unreported, c.difference_explained) == (
        D("3120.00"),
        D("3120.00"),
        True,
    )


money = st.decimals(min_value=D("0"), max_value=D("1000000"), places=2)


@given(filed=money, corrected=money, missing=money)
def test_the_comparison_is_pure_and_idempotent(filed: D, corrected: D, missing: D) -> None:
    args = (
        {"interest": filed},
        [ProposedLine("interest", "Taxable interest", filed, corrected)],
        [InformationReturn("Payer", "1099-INT", missing, on_return=False)],
    )
    a = underreporter.compare(*args)
    b = underreporter.compare(*args)
    assert a == b
    assert a.stamp.inputs_hash == b.stamp.inputs_hash
    if a.difference_explained:
        assert a.income_difference == a.unreported != 0


@given(
    ti=st.integers(min_value=0, max_value=1_000_000),
    step=st.integers(min_value=0, max_value=50_000),
)
def test_tax_is_monotone_in_income(ti: int, step: int) -> None:
    table = bracket.schedule(2024, "mfj")
    assert table is not None
    assert bracket.tax(D(ti + step), table) >= bracket.tax(D(ti), table)


def test_intake_guards_run_in_order_not_ready_then_low_confidence_then_duplicate() -> None:
    source = inspect.getsource(intake.create_notice)
    order = [
        source.index(name)
        for name in ("NotReady", "LowConfidenceUnconfirmed", "DuplicateUnresolved")
    ]
    assert order == sorted(order)
    assert D("0.90") == intake.LOW_CONFIDENCE


@pytest.mark.parametrize("action", WRITES)
def test_every_notice_write_denies_the_agent_and_every_portal_principal(action: str) -> None:
    cell = MATRIX[action]
    assert cell.get("agent") == "deny", action
    for principal in PORTAL:
        assert cell.get(principal, "deny") == "deny", (action, principal)


@pytest.mark.parametrize("action", ["notice.record_as_filed", "notice.analyze"])
def test_tin_bearing_writes_require_an_onshore_user(action: str) -> None:
    assert MATRIX[action]["not_offshore"] == "required"
