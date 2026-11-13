"""T-05-T45 (TASK-7708; T-05 §5.3; DEC-4711): the entity returns' slice part 1. The seeded cells
are the goldens' and the handoff's and foot (TB to 0, Σ K-1 = K, every partner rolls forward, the
M-2 to 6,866,200 while Item L reads 6,860,000); the recorder refuses a firm that is not synthetic;
the slice orders facts before structures, sign-offs and runs."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.tax import entity_seed
from abacus.modules.tax.entity_sections import tie_outs
from abacus_tools.synthetic.scenarios.brightwater_hale import entity_slice as e
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

D = Decimal


def _values() -> dict[str, dict[str, object]]:
    return {a: {"v": v} for a, v in e.ridgeline_cells()}


def test_the_trial_balance_foots_and_schedule_k_equals_the_k1s() -> None:
    found = {t.key: t for t in tie_outs(_values())}
    assert found["tb_foots"].state == "tie"
    assert found["k1_sum_k"].state == "tie"
    assert found["capital_rollforward"].state == "tie"


def test_item_l_is_off_6200_against_the_m2_as_drafted() -> None:
    found = {t.key: t for t in tie_outs(_values())}["item_l_m2"]
    assert (found.state, found.difference) == ("off", D(-6200))


def test_two_periods_of_628100_and_the_transfer_of_5_points() -> None:
    cells = dict(e.ridgeline_cells())
    assert (cells["04!D2"], cells["04!D3"]) == ("628100", "628100")
    on, src, dst, points, price = e.TRANSFER
    assert (on.isoformat(), src, dst, points, price) == (
        "2025-06-30",
        "Pell Street Ventures LLC",
        "Pell Street II LLC",
        D(5),
        D(360000),
    )


def test_the_slice_replays_facts_then_structures_signoffs_and_runs() -> None:
    events = [ev for ev in slice_events(e.SLICE) if not ev.label.startswith("flag:")]
    kinds = [ev.kind for ev in sorted(events, key=lambda ev: ev.at)]
    assert kinds.index("tax.entity_seeded") < kinds.index("tax.allocation_drafted")
    assert kinds.count("review.allocation_signed") == 4
    assert kinds.count("agents.entity_run_recorded") == 2
    assert all(ev.data.get("at") for ev in events)


def test_the_recorder_refuses_a_firm_that_is_not_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def not_synthetic(tenant: object) -> bool:
        return False

    monkeypatch.setattr(entity_seed, "is_synthetic_firm", not_synthetic)
    ctx: Any = type("C", (), {"tenant": object(), "tenant_id": uuid.uuid4()})()
    with pytest.raises(NotFound):
        asyncio.run(
            entity_seed.record_synthetic_entity(
                ctx, uuid.uuid4(), entity_seed.SeedEntity("a", "531110", "accrual", "gaap", [])
            )
        )
