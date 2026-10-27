"""P-04-T27 acceptance (TASK-1463; DEC-606): C3 services v1 is frozen.

"The register marks C3 services v1 frozen by Fri Apr 16, 2027, and removing a field fails the
snapshot diff."
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import cast

from abacus_tools import contracts

Schema = dict[str, object]
ROOT = Path(__file__).resolve().parents[4]


def _frozen() -> dict[str, Schema]:
    path = contracts.CONTRACTS / "review_grammar" / "v1.json"
    return cast(dict[str, Schema], json.loads(path.read_text()))


def test_ac_c3_v1_is_frozen_and_today_breaks_nothing() -> None:
    assert [p.stem for p in contracts.snapshots()["review_grammar"]] == ["v1"]
    frozen = _frozen()
    assert set(frozen) == set(contracts.MODELS["review_grammar"])
    assert {"AgentProposalOut", "AgentSuggestionOut", "DecisionCardOut", "SignOffOut"} <= set(
        frozen
    )
    assert contracts.breaking(frozen, contracts.current("review_grammar")) == []


def test_ac_removing_a_field_fails_the_snapshot_diff() -> None:
    frozen = _frozen()
    now = copy.deepcopy(contracts.current("review_grammar"))
    proposal = cast(dict[str, Schema], now["AgentProposalOut"]["properties"])
    del proposal["allowed_actions"]
    assert contracts.breaking(frozen, now) == [
        "AgentProposalOut.allowed_actions: removed or renamed"
    ]
    status = now["ProposalStatus"]
    status["enum"] = [m for m in cast(list[str], status["enum"]) if m != "rejected"]
    assert "ProposalStatus: enum member 'rejected' removed" in contracts.breaking(frozen, now)


def test_ac_the_register_marks_c3_services_v1_frozen() -> None:
    register = (ROOT / "docs" / "contracts" / "README.md").read_text()
    row = next(line for line in register.splitlines() if line.startswith("| C3 |"))
    assert "frozen" in row
    found = re.search(r"services v1 \*\*frozen (\d{4}-\d{2}-\d{2})\*\*", row)
    assert found is not None and found.group(1) <= "2027-04-16"
