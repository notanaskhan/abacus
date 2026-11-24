"""T-06-T41 (TASK-8910; SPEC-702; DEC-5912; amber): workbook-run steps on the live path.

Row acceptance: "Replay of the pre-change histories passes [tests/workflows], and an approved
asset change re-runs only the depreciation and K-1 steps." Here: the recompute edges (an asset
change re-runs depreciation, bonus, capital and the K-1s; a sourcing apportionment and the
K-1s; never import, map, contributions or §706(d)); the approvals start that re-run; 02 is
written from the E3 register with a footing Total row; the new 02 and 08 tie-outs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from abacus.modules.tax import entity_run_plan as plan
from abacus.modules.tax import run_steps
from abacus.modules.tax.entity_sections import sheet_tie_outs

SRC = Path(plan.__file__).parent


def test_an_asset_change_reruns_only_the_depreciation_and_k1_steps() -> None:
    assert plan.steps_for_change("asset_change") == [
        "depreciation_register", "bonus_eligibility", "capital_m2", "federal_k1s",
        "state_k1s_k3s",
    ]  # fmt: skip


def test_a_sourcing_reruns_apportionment_and_the_k1s() -> None:
    assert plan.steps_for_change("sourcing") == [
        "apportionment_ptet", "federal_k1s", "state_k1s_k3s",
    ]  # fmt: skip


def test_the_approvals_start_the_rerun() -> None:
    assets = (SRC / "fixed_assets_service.py").read_text(encoding="utf-8")
    assert 'await rerun_for(ctx, return_id, "asset_change")' in assets
    states = (SRC / "states_service.py").read_text(encoding="utf-8")
    assert 'await rerun_for(ctx, return_id, "sourcing")' in states


@dataclass(frozen=True)
class _Asset:
    id: object
    asset_no: int
    description: str
    placed_in_service_on: date | None
    bonus_pct: Decimal
    disposed: bool = False


def test_02_is_written_from_the_register_and_foots() -> None:
    a, b, land = uuid4(), uuid4(), uuid4()
    found = SimpleNamespace(assets=(
        _Asset(a, 1, "Delivery van", date(2025, 3, 1), Decimal("60")),
        _Asset(b, 2, "Roof", date(2025, 6, 1), Decimal("0")),
        _Asset(land, 3, "Land", None, Decimal("0")),
        _Asset(uuid4(), 4, "Sold forklift", date(2020, 1, 1), Decimal("0"), disposed=True),
    ))  # fmt: skip
    computed = SimpleNamespace(
        by_asset={
            str(a): SimpleNamespace(cost=40000, current=26400),
            str(b): SimpleNamespace(cost=78000, current=1083),
        },
        register=SimpleNamespace(current=27483),
    )
    writes = {w.address: w for w in run_steps.register_writes(found, computed)}  # type: ignore[arg-type]  -- a test double stands in
    assert writes["02!A2"].value == "1" and writes["02!F2"].value == Decimal(26400)
    assert writes["02!A3"].value == "2" and writes["02!G2"].value == Decimal("60")
    assert "02!A4" in writes and writes["02!A4"].value == "Total"
    assert writes["02!F4"].value == Decimal(27483)
    assert "02!A5" not in writes  # land and the disposed asset carry no row


def _cells(**cells: object) -> dict[str, dict[str, object]]:
    return {k.replace("_", "!", 1): {"v": v} for k, v in cells.items()}


def test_the_register_tie_out() -> None:
    values = _cells(**{"02_A2": "1", "02_F2": "26400", "02_A3": "2", "02_F3": "1083",
                       "02_A4": "Total", "02_F4": "27483"})  # fmt: skip
    found = {t.key: t for t in sheet_tie_outs(values)}
    assert found["fa_foots"].state == "tie"
    values["02!F4"] = {"v": "27000"}
    assert {t.key: t for t in sheet_tie_outs(values)}["fa_foots"].state == "off"


def test_the_state_k1_tie_out() -> None:
    values = _cells(**{"06_A2": "Ordinary income", "06_D2": "1000",
                       "08_K2": "Ordinary income", "08_L2": "600",
                       "08_K3": "Ordinary income", "08_L3": "400"})  # fmt: skip
    assert {t.key: t for t in sheet_tie_outs(values)}["state_k1_sum"].state == "tie"
    values["08!L3"] = {"v": "300"}
    assert {t.key: t for t in sheet_tie_outs(values)}["state_k1_sum"].state == "off"
