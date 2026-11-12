"""P-10-T56 (TASK-7425; DEC-4414): "No P-10 flag expires before its renewal, and the capacity
ledger records P-10 actuals." Read from the registry, the renewal calendar, the ledger and the
contract register."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from abacus_tools import runtime_v2_flip as flip

REPO = Path(__file__).resolve().parents[4]
CALENDAR = (REPO / "docs/plan/status/flag-renewals-2027.md").read_text(encoding="utf-8")
LEDGER = (REPO / "docs/product/capacity-ledger.md").read_text(encoding="utf-8")
REGISTER = (REPO / "docs/contracts/README.md").read_text(encoding="utf-8")
SECTION = CALENDAR.split("## The P-10 runtime v2 flags (P-10-T56)")[1]


def _due(flag: str) -> date:
    row = next(line for line in SECTION.splitlines() if line.startswith(f"| `{flag}` |"))
    found = re.search(r"\*\*\w{3} (\w{3} \d{1,2}, \d{4})\*\*", row)
    assert found, row
    return datetime.strptime(found.group(1), "%b %d, %Y").date()


@pytest.mark.parametrize("flag", flip.FLAGS_ON)
def test_each_p10_flag_is_renewed_before_it_expires(flag: str) -> None:
    expires = flip.registry_expiry()[flag]
    assert f"| `{flag}` | ayushkbhatia | {expires.isoformat()} |" in SECTION
    assert _due(flag) < expires
    assert "Tue Apr 25, 2028" in SECTION  # the plan's own renewal, a week before M17


def test_each_p10_flag_names_the_m17_journeys() -> None:
    text = (REPO / "docs/architecture/feature-flags/agents.yaml").read_text(encoding="utf-8")
    for flag in flip.FLAGS_ON:
        entry = text.split(f"  - name: {flag}\n")[1].split("  - name:")[0]
        assert "journeys: [j11-workbench, j23-audit-partner-morning]" in entry


def test_the_ledger_records_p10_actuals_that_add_up() -> None:
    section = LEDGER.split("## P-10 Agent runtime v2 and real time")[1].split("\n## ")[0]
    rows = re.findall(
        r"^\| (done|partial[^|]*|deferred|not started) \| (\d+) \| ([\d.]+) \|", section, re.M
    )
    assert sum(int(n) for _, n, _ in rows) == 58
    assert sum(float(te) for _, _, te in rows) == pytest.approx(55.75)


def test_the_register_records_c6_v2_and_c17_live() -> None:
    c6 = next(line for line in REGISTER.splitlines() if line.startswith("| C6 |"))
    c17 = next(line for line in REGISTER.splitlines() if line.startswith("| C17 |"))
    assert "v2 frozen" in c6 and "P-10-T56" in c6
    assert "live" in c17 and "P-10-T56" in c17
