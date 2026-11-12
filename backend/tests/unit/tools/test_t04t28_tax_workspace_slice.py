"""T-04-T28 (TASK-6806; T-04 §5.3; DEC-3406): the `tax_workspace` slice foots and matches fixture
mode's figures (`apps/web/src/fixtures/seed/tax-workspace.ts`).

Row acceptance: "make seed-demo and fixture mode show identical counts and figures for every
in-scope artboard, and the scenario loads on staging under the demo clock."
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from abacus.modules.integrations.api import engine_field_profile
from abacus.modules.tax.workspace_seed import total
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale import tax_workspace_slice as slice_
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import ordered

FIXTURE = (
    Path(__file__).resolve().parents[4] / "apps/web/src/fixtures/seed/tax-workspace.ts"
).read_text(encoding="utf-8")


def _ts_list(name: str) -> list[Decimal]:
    found = re.search(rf"{name}: \[([^\]]+)\]", FIXTURE)
    assert found is not None, name
    return [Decimal(v.strip().strip('"')) for v in found.group(1).split(",") if v.strip()]


def _ts_value(name: str) -> Decimal:
    found = re.search(rf'{name}: "([0-9.]+)"', FIXTURE)
    assert found is not None, name
    return Decimal(found.group(1))


def test_ridgeline_box_2_foots_and_matches_fixture_mode() -> None:
    shares = [amount for _, amount in slice_.RIDGELINE_STATE_SHARES]
    assert sum(shares) == slice_.RIDGELINE_BOX2 == Decimal("307900")
    assert shares == _ts_list("ridgelineBox2Shares")
    assert _ts_value("ridgelineBox2Total") == slice_.RIDGELINE_BOX2
    assert _ts_value("k1Box5") == slice_.K1_BOX5
    assert _ts_value("it201Line20") == slice_.FIX_AMOUNT  # the value the 18A fix lands


def test_the_state_allocation_section_foots_in_code() -> None:
    allocation = next(s for s in slice_.SCH_E_RIDGELINE.sections if s.key == "state_allocation")
    assert total(allocation.fields) == slice_.RIDGELINE_BOX2


def test_tax_06_counts() -> None:
    open_rows = [i for i in slice_.ISSUES if i[5] is None]
    assert len(open_rows) + 1 == slice_.OPEN_ISSUES == 4  # + the system's Draft K-1 issue
    assert len(slice_.ISSUES) - len(open_rows) == slice_.RESOLVED_ISSUES == 3
    assert len(slice_.ISSUES) + 1 == slice_.RAISED_ISSUES == 7
    kinds = sorted(i[2] for i in open_rows)
    assert kinds == ["missing_information", "missing_information", "review_point"]


def test_every_engine_key_is_in_the_profile() -> None:
    profile = engine_field_profile()
    for sheet in slice_.WORKSHEETS:
        for section in sheet.sections:
            for field in section.fields:
                if field.engine_field_key is not None:
                    assert profile.valid_key(field.engine_field_key), field.engine_field_key
                if field.derivation == "engine":
                    assert field.engine_field_key is not None and field.value is None


def test_events_are_ordered_unique_and_handled() -> None:
    events = ordered(slice_.tax_workspace_events())
    assert {e.kind for e in events} <= set(loader.HANDLERS)
    assert len(events) == 2 + 1 + 6 + 3 + 3  # flags, worksheets, issues, resolved, checkpoints
    assert loader.SLICE_NEEDS[slice_.SLICE] == slice_.NEEDS


def test_no_event_replays_before_the_firm_and_the_return_exist() -> None:
    # TASK-7324: the loader replays by `at`, and the firm, Feld's engagement and its return are
    # created at setup (Sep 1, 8:00 AM). A business time before that rides in `data["at"]`.
    events = ordered(slice_.tax_workspace_events())
    assert min(e.at for e in events) >= slice_.REPLAY_FROM
    issue = next(e for e in events if e.label == "tax-workspace:feld:issue:digital_assets")
    assert issue.data["at"] == "2026-08-25T10:08:00-05:00"
    resolved = next(e for e in events if e.label.endswith("digital_assets:resolved"))
    assert issue.at < resolved.at  # raised before it is resolved, in the business order
    later = next(e for e in events if e.label == "tax-workspace:feld:checkpoint:Manager review")
    assert later.at == later.data["at"] or later.at.isoformat() == later.data["at"]
