"""A-06-T32 (TASK-6006; DEC-2606; ADR-078): the completion golden figures against the scenario.

Acceptance (the task row): "The seed tests fail on any figure drift between the scenario,
fixtures and screens." The figure book (`brightwater_hale/completion_figures.json`) is transcribed
from the epic; this side checks the Brightwater Hale scenario that `make seed` loads, and
`apps/web/src/fixtures/contracts/completion-figures.test.ts` checks the screens' fixtures against
the same book. The 26-row sign-off matrix is not seeded (DEC-2391): its check fails strictly until
it is, so the gap can't be forgotten.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from abacus_tools.synthetic.scenarios.brightwater_hale import completion_slice as seed

HERE: Final = Path(__file__).resolve().parent
BOOK: Final = cast(
    dict[str, dict[str, object]],
    json.loads(
        (HERE / "brightwater_hale" / "completion_figures.json").read_text(encoding="utf-8")
    ),
)
GOLDEN: Final = HERE.parent


def _usd(value: object) -> Decimal:
    return Decimal(str(value))


def test_ac_nine_findings_in_four_bands() -> None:
    book = BOOK["findings"]
    severities = [e.severity for e in seed.EXCEPTIONS]
    bands = [
        severities.count("significant_deficiency"),
        severities.count("deficiency"),
        severities.count(None),
        len(seed.FINDINGS),
    ]
    assert bands == book["bands"]
    assert sum(bands) == book["total"] == len(seed.EXCEPTIONS) + len(seed.FINDINGS)


def _passed(ref: str) -> dict[str, str]:
    finding = next(f for f in seed.FINDINGS if f.ref == ref)
    return finding.effect


def test_ac_the_sum_rolls_over_and_iron_curtains_from_the_seeded_entries() -> None:
    book = BOOK["sum"]
    passed = [e.finding for e in seed.ENTRIES if e.decision == "client_declined"]
    assert passed == ["F-07", "F-08"]
    rollover = sum(_usd(_passed(r)["change_in_net_assets"]) for r in passed)
    iron = sum(_usd(_passed(r)["net_assets"]) for r in passed)
    assert (
        rollover == _usd(book["rollover"]) == _usd(book["projected"]) - _usd(book["py_reversal"])
    )
    assert iron == _usd(book["iron_curtain"]) == _usd(book["projected"]) - _usd(book["accrued"])
    pct = (rollover / _usd(book["pm"]) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    assert pct == _usd(book["pct_of_pm"])


def test_ac_pm_is_the_materiality_goldens() -> None:
    golden = (GOLDEN / "materiality" / "northwind_py2025.yaml").read_text(encoding="utf-8")
    assert str(BOOK["sum"]["pm"]) in golden.replace(",", "")


def test_ac_net_assets_are_the_trust_plus_the_receivable() -> None:
    book = BOOK["net_assets"]
    ebp = cast(
        dict[str, object],
        yaml.safe_load((GOLDEN / "ebp" / "northwind_py2025_slice2.yaml").read_text("utf-8")),
    )
    receivable = next(f for f in seed.FINDINGS if f.ref == "F-05").amount
    assert _usd(ebp["trust"]) == _usd(book["trust"])
    assert _usd(receivable) == _usd(book["receivable"])
    assert _usd(book["trust"]) + _usd(book["receivable"]) == _usd(book["total"])
    assert _usd(ebp["net_assets"]) == _usd(book["total"])


def test_ac_the_checklist_is_97_yes_45_na_0_no() -> None:
    book = BOOK["checklist"]
    assert book["total"] == seed.ITEMS
    assert book["yes"] == seed.ANSWERED_YES
    assert book["na"] == seed.ITEMS - seed.ANSWERED_YES
    assert cast(int, book["yes"]) + cast(int, book["na"]) + cast(int, book["no"]) == book["total"]


def test_ac_review_notes_are_two_open_one_responded_eleven_cleared() -> None:
    book = BOOK["review_notes"]
    states = [n[-1] for n in seed.LIVE_NOTES]
    assert states.count("open") == book["open"]
    assert states.count("responded") == book["responded"]
    assert book["cleared"] == seed.CLEARED_NOTES
    assert len(states) + seed.CLEARED_NOTES == book["total"]


def test_the_tie_out_parts_add_up() -> None:
    book = BOOK["tie_out"]
    assert sum(cast(list[int], book["parts"])) == book["total"]


@pytest.mark.xfail(
    strict=True,
    reason="TASK-6006, DEC-2391: the design's 26-row sign-off matrix isn't seeded",
)
def test_ac_the_sign_off_matrix_is_26() -> None:
    book = BOOK["matrix"]
    assert sum(cast(list[int], book["parts"])) == book["total"]
    assert sum(len(levels) for _paper, levels in seed.SIGN_OFFS) == book["total"]
