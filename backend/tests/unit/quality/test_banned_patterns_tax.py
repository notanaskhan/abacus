"""T-01-T07 (SPEC-501 AC-13, AC-14; R-04; T-01 §4.9): NEVER-ERO-001 and TAXAPPROVE-001, and the
egress allowlist holding no IRS or state revenue host."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from abacus.modules.integrations import _capabilities as caps
from abacus_tools.quality import banned_patterns as bp

MODULE = "src/abacus/modules/tax/filing.py"
APPROVAL = "src/abacus/modules/tax/approval.py"


def _count(root: Path, rule: str, rel: str, source: str) -> int:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return len([v for v in bp.scan(root) if v.rule_id == rule and v.path == rel])


@pytest.mark.parametrize(
    "source",
    [
        'CHANNEL = "MeF"\n',
        'PATH = "submit via A2A"\n',
        "def send_efin(x: int) -> int:\n    return x\n",
        "etin_value = 1\n",
        'LABEL = "IRIS TCC"\n',
    ],
)
def test_ac14_never_ero_refuses_transmitter_identifiers(tmp_path: Path, source: str) -> None:
    assert _count(tmp_path, "NEVER-ERO-001", MODULE, source) >= 1


def test_ac14_never_ero_leaves_ordinary_words_alone(tmp_path: Path) -> None:
    source = 'TITLE = "Transmission record"\ndef meeting_notes() -> str:\n    return "efficient"\n'
    assert _count(tmp_path, "NEVER-ERO-001", MODULE, source) == 0


def test_ac14_only_approval_py_records_a_final_approval(tmp_path: Path) -> None:
    source = 'def go(record) -> None:\n    record(kind="final_approval")\n'
    assert _count(tmp_path, "TAXAPPROVE-001", MODULE, source) == 1
    assert _count(tmp_path, "TAXAPPROVE-001", APPROVAL, source) == 0


def test_ac14_no_egress_host_is_an_irs_or_state_revenue_host() -> None:
    hosts = [
        str(h) for c in caps.READ_CONNECTORS for h in cast(tuple[str, ...], c["egress_hosts"])
    ]
    for host in hosts:
        assert not host.endswith("irs.gov"), host
        assert ".tax." not in f".{host}." and "revenue" not in host, host


def test_ac13_the_tax_engine_write_is_a_file_bridge_never_enabled() -> None:
    w2 = [w for w in caps.WRITES if w["shape"] == "W2"]
    assert [w["key"] for w in w2] == ["tax_engine_file_bridge"]
    assert all(w["enabled"] is False for w in w2)
