"""A-04-T41 (TASK-3326; DEC-2323): hardening, from the row. The mutation floor is measured at the
end pass and only then recorded (floors only rise); the p95 budgets need staging and stay open.

Here: I-AGENT-NEVER holds on A-04's decision kinds and acts, from the matrix the codegen reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
HUMAN_ACTS = (
    "materiality.propose",
    "risk.route_for_approval",
    "fraud_minutes.approve",
    "deficiency.propose_severity",
    "soc_report.evaluate",
)


def _matrix(module: str) -> dict[str, dict[str, object]]:
    doc = yaml.safe_load((ROOT / f"docs/architecture/permission-matrix/{module}.yaml").read_text())
    return cast(dict[str, dict[str, object]], doc["actions"])


@pytest.mark.parametrize("action", HUMAN_ACTS)
def test_ac_i_agent_never_on_a04_acts(action: str) -> None:
    rows = _matrix("assurance")
    assert action in rows, action
    assert rows[action].get("agent", "deny") == "deny", action


def test_ac_the_agent_never_decides_or_signs() -> None:
    review = _matrix("review")
    assert review["decision.decide"].get("agent", "deny") == "deny"
    for level in ("prepare", "review", "manager", "partner", "eqr"):
        assert review[f"sign_off.{level}"].get("agent", "deny") == "deny"
