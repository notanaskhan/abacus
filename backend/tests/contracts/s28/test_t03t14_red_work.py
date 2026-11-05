"""T-03-T14 (TASK-3332): AC tests of T-03's red work, from the row: "The tests fail if any T-03
write is
allowed to the agent or a portal principal or if an extension ack maps to the wrong return or
jurisdiction."
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.tax.extension_acks import jurisdiction_of

ROOT = Path(__file__).resolve().parents[4]
WRITES = (
    "filing_extension.prepare",
    "filing_extension.approve_payment",
    "filing_extension.mark_filed",
    "filing_extension.flag_likely",
    "filing_extension.confirmation_send",
)


def _tax() -> dict[str, dict[str, object]]:
    doc = yaml.safe_load((ROOT / "docs/architecture/permission-matrix/tax.yaml").read_text())
    return cast(dict[str, dict[str, object]], doc["actions"])


@pytest.mark.parametrize("action", WRITES)
@pytest.mark.parametrize(
    "principal", ["agent", "client_admin", "client_contributor", "third_party"]
)
def test_ac_no_t03_write_for_the_agent_or_a_portal_principal(action: str, principal: str) -> None:
    assert _tax()[action].get(principal, "deny") == "deny", (action, principal)


def test_ac_the_payment_approval_holds_the_reviewer_function() -> None:
    assert "manager_reviewer" in str(_tax()["filing_extension.approve_payment"].get("function_in"))


def test_ac_an_ack_keeps_its_own_jurisdiction() -> None:
    assert jurisdiction_of("federal") == "federal"
    assert jurisdiction_of("NY") == "NY"


def test_ac_the_update_is_keyed_by_return_jurisdiction_and_form() -> None:
    source = (ROOT / "backend/src/abacus/modules/tax/extension_acks.py").read_text()
    assert "WHERE tax_return_id = :r AND jurisdiction = :j AND form = :f" in source


def test_ac_never_an_ero_act() -> None:
    source = (ROOT / "backend/src/abacus/modules/tax/extensions.py").read_text()
    assert "transmit(" not in source
