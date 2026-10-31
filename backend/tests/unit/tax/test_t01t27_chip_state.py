"""T-01-T27 (TASK-2415; T-01 §3.9; tax-engine-bridge §3; DEC-1463): the sync chip is a pure
function.

The row's acceptance: "Every artboard state of TAX-09 is reproduced from seed events by the state
function." Each artboard's data condition (docs/screens/TAX-09.md) is written as the facts its
seed events give, and the seven states are each reached; precedence holds (a waiting import
over an error, an error over an unmarked export, an unmarked export over the last sync).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import get_args

import pytest

from abacus.modules.tax.engine_sync import ChipFacts, SyncState, chip_state

SEP_16 = datetime(2026, 9, 16, 16, 43, tzinfo=UTC)
NOTHING = ChipFacts(
    pending_import=False,
    diagnostics_errors=0,
    export_failed=False,
    unmarked_export=False,
    last_synced_at=None,
    changed_since_sync=False,
    final_approved=False,
)

# TAX-09's artboards, as the facts their seed events give.
ARTBOARDS: dict[str, tuple[ChipFacts, SyncState]] = {
    # a: exported and marked at 11:42 (the motion ends on Synced).
    "a": (replace(NOTHING, final_approved=True, last_synced_at=SEP_16), "synced"),
    # a2: approved at 11:20, nothing exported yet.
    "a2": (replace(NOTHING, final_approved=True), "ready_for_export"),
    # b: blocked on a draft K-1: not approved, never exported.
    "b": (NOTHING, "not_yet_exported"),
    # c: synced before, then box 18A changed three fields.
    "c": (replace(NOTHING, last_synced_at=SEP_16, changed_since_sync=True), "out_of_sync"),
    # d: the diagnostics run came back with errors after an export.
    "d": (
        replace(NOTHING, final_approved=True, last_synced_at=SEP_16, diagnostics_errors=1),
        "failed",
    ),
    # d2: the export failed.
    "d2": (replace(NOTHING, final_approved=True, export_failed=True), "failed"),
    # e: V3 uploaded, five fields waiting on Samuel Ito.
    "e": (replace(NOTHING, pending_import=True), "import_pending_approval"),
}


@pytest.mark.parametrize("artboard", sorted(ARTBOARDS))
def test_ac_every_tax09_artboard_from_its_seed_facts(artboard: str) -> None:
    facts, expected = ARTBOARDS[artboard]
    assert chip_state(facts) == expected


def test_every_state_is_reachable() -> None:
    exporting = replace(NOTHING, final_approved=True, unmarked_export=True)
    reached = {chip_state(f) for f, _ in ARTBOARDS.values()} | {chip_state(exporting)}
    assert reached == set(get_args(SyncState))


def test_precedence() -> None:
    everything = ChipFacts(
        pending_import=True,
        diagnostics_errors=2,
        export_failed=True,
        unmarked_export=True,
        last_synced_at=SEP_16,
        changed_since_sync=True,
        final_approved=True,
    )
    assert chip_state(everything) == "import_pending_approval"
    assert chip_state(replace(everything, pending_import=False)) == "failed"
    no_error = replace(everything, pending_import=False, diagnostics_errors=0, export_failed=False)
    assert chip_state(no_error) == "exporting"
    assert chip_state(replace(no_error, unmarked_export=False)) == "out_of_sync"
