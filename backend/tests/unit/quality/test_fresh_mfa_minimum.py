"""PROTECTED (P-08-T21 security review; Q-02 AC-42): the minimum set of actions that always need a
second factor verified in the last 15 minutes. The register and the generated overlay can be
edited together (deleting an entry with its matrix condition regenerates cleanly), so this list
is fixed here, by hand: resets, unlocks, exports, holds and retention, walls, the AI policy and the
data boundary, reveals, the independence conclusion and security-role changes. Shrinking it is a
deliberate, reviewed change to this file."""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from abacus.modules.identity.authz.matrix import RULES

REGISTER = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "fresh-mfa-actions.yaml"
MINIMUM: Final = frozenset(
    {
        # Walls (ADR-026)
        "wall.create",
        "wall.remove",
        "wall.approve",
        # AI policy and the data boundary
        "autonomy_policy.update",
        "firm_agents.pause",
        "firm.ai_client_data",
        # Exports
        "export.create",
        "run_trace.export",
        "firm_export.request",
        "firm_export.approve",
        "firm_export.download",
        # Legal holds and retention
        "legal_hold.place",
        "legal_hold.lift",
        "retention_policy.update",
        # The independence conclusion
        "acceptance.record",
        # Reveals
        "tin.reveal",
        "pii.reveal",
        # A client's portal access: unlock and second-factor reset
        "contact.unlock",
        "contact.mfa_reset",
        # Security-role changes
        "security_role.assign",
    }
)


def _listed() -> set[str]:
    data = cast(dict[str, object], yaml.safe_load(REGISTER.read_text(encoding="utf-8")))
    return {e["action"] for e in cast(list[dict[str, str]], data["actions"])}


@pytest.mark.parametrize("action", sorted(MINIMUM))
def test_the_minimum_set_is_listed_and_needs_a_fresh_second_factor(action: str) -> None:
    assert action in _listed(), f"{action} left the fresh-MFA register"
    assert action in RULES, f"{action} left the permission matrix"
    assert RULES[action].mfa_recent, f"{action} lost mfa_recent: required"


def test_the_minimum_set_is_not_smaller_than_this_review_left_it() -> None:
    assert len(MINIMUM) == 20
