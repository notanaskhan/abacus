"""A-07-T25 close (S31; TASK-6227; DEC-2822): a checklist item may carry its blocker sentence,
the firm's words AUD-19 shows while the item is open; the seed's template carries the handoff's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from abacus.modules.methodology.assurance_checklists import ChecklistItemIn

TEMPLATES = (
    Path(__file__).resolve().parents[3]
    / "src/abacus_tools/synthetic/scenarios/brightwater_hale/files/a07_templates.yaml"
)


def test_an_item_carries_an_optional_blocker() -> None:
    item = ChecklistItemIn(
        key="rep_letter", text="Representation letter signed", blocker="Not yet signed"
    )
    assert item.blocker == "Not yet signed"
    assert ChecklistItemIn(key="sum", text="SUM concluded").blocker is None
    with pytest.raises(ValidationError):
        ChecklistItemIn(key="sum", text="SUM concluded", blocker="x" * 301)


def test_the_seed_template_validates_with_its_blockers() -> None:
    raw = yaml.safe_load(TEMPLATES.read_text())
    items = [ChecklistItemIn(**i) for i in raw["completion_ebp"]]
    blockers = {i.key: i.blocker for i in items if i.blocker}
    assert blockers["rep_letter"] == "Representation letter not yet signed"
    assert blockers["tcwg_260"] == "AU-C 260 completion communication not yet sent"
