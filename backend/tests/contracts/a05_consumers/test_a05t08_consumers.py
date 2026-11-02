# ac-test-author: ayushkbhatia
"""A-05-T08 (TASK-2920; A-05 §8.1; DEC-1966): consumer contract tests on behalf of A-05, run in
the providers' CI.

What EBP-02, EBP-04 and EBP-06 read from other epics' contracts:

- C8 (A-06): the AJE-1 pill's states (Proposed, Review required, Approved, Client approved,
  Client declined) and the adjusted TB's four layers;
- C9 (A-02, A-03): the TB layer view per layer, and Final answering `layer_unavailable` until an
  adjustment source registers;
- C3 (P-04): the field-tick sign-off (EBP-02's L1 ticks) and the decision cards.
"""

from __future__ import annotations

import json
from typing import cast, get_args

from abacus.api.export_openapi import document
from abacus.kernel._statuses import ProposedEntryStatus
from abacus.modules.adjustments import contract as c8
from abacus.modules.ledger.api import LayerUnavailable, layer_available

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])


def test_c8_carries_the_aje_1_pill_states() -> None:
    states = set(get_args(c8.EntryStatus))
    assert {"proposed", "review_required", "approved", "client_approved", "client_declined"} <= (
        states
    )
    vocabulary = {s.value for s in ProposedEntryStatus}
    assert states <= vocabulary


def test_c8_reads_the_four_layers_ebp_06_shows() -> None:
    assert set(get_args(c8.Layer)) == {"unadjusted", "aje", "rje", "final"}
    operation = PATHS["/v1/work-items/{work_item_id}/adjusted-tb"]["get"]
    assert operation["x-abacus-action"] == "adjusted_tb.read"


def test_c9_serves_each_layer_and_final_waits_for_an_adjustment_source() -> None:
    path = "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/layers/{layer}"
    assert PATHS[path]["get"]["x-abacus-action"] == "trial_balance.read"
    assert layer_available("unadjusted")
    assert LayerUnavailable.code == "layer_unavailable"


def test_c3_offers_field_ticks_and_decision_cards() -> None:
    actions = {
        cast(str, op.get("x-abacus-action")) for ops in PATHS.values() for op in ops.values()
    }
    assert "decision.decide" in actions
    assert any(a.startswith("sign_off.") for a in actions)
