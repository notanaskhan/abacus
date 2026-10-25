"""Q-03-T029 (Q-03 §3.9 I2; ADR-099; DEC-366): no high or critical finding is older than its SLA.
A registered finding is skipped by pip-audit and Trivy only while it is inside its SLA (critical 7
days, high 30); past it, the scanners and the SLA check fail."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from abacus_tools.quality import supply_chain
from abacus_tools.quality.supply_chain import RegisterInvalid, ignores, overdue, parse, weakened

REGISTER = """
findings:
  - id: GHSA-aaaa-bbbb-cccc
    source: pip-audit
    severity: critical
    package: example==1.0
    first_seen: 2027-01-04
  - id: CVE-2027-0001
    source: trivy-image
    severity: high
    package: openssl
    first_seen: 2027-01-04
  - id: CVE-2027-0002
    source: trivy-fs
    severity: high
    first_seen: 2026-11-01
    closed: 2026-11-20
"""


def test_t029_the_committed_register_parses_and_nothing_is_past_sla() -> None:
    findings = parse(supply_chain.REGISTER.read_text(encoding="utf-8"))
    assert overdue(findings, date(2026, 10, 25)) == []
    assert supply_chain.main(["check"]) == 0


def test_t029_slas_are_seven_days_for_critical_and_thirty_for_high() -> None:
    critical, high, _closed = parse(REGISTER)
    assert critical.due == date(2027, 1, 11)
    assert high.due == date(2027, 2, 3)


def test_t029_a_finding_is_ignored_only_inside_its_sla() -> None:
    findings = parse(REGISTER)
    assert ignores(findings, "pip-audit", date(2027, 1, 11)) == ["GHSA-aaaa-bbbb-cccc"]
    assert ignores(findings, "pip-audit", date(2027, 1, 12)) == []
    assert ignores(findings, "trivy", date(2027, 2, 3)) == ["CVE-2027-0001"]
    assert ignores(findings, "trivy", date(2027, 2, 4)) == []
    # Ignored while open, never after it is closed: if it comes back, the scanner fails again.
    assert ignores(findings, "trivy", date(2026, 11, 10)) == ["CVE-2027-0002"]
    assert ignores(findings, "trivy", date(2026, 11, 25)) == []


def test_t029_the_check_fails_on_an_open_finding_past_its_sla(tmp_path: Path) -> None:
    findings = parse(REGISTER)
    assert overdue(findings, date(2027, 1, 11)) == []
    late = overdue(findings, date(2027, 1, 12))
    assert len(late) == 1 and late[0].startswith("GHSA-aaaa-bbbb-cccc (pip-audit, critical")
    register = tmp_path / "register.yaml"
    register.write_text(REGISTER, encoding="utf-8")
    assert supply_chain.main(["check", "--register", str(register), "--as-of", "2027-03-01"]) == 1
    assert supply_chain.main(["check", "--register", str(register), "--as-of", "2027-01-05"]) == 0


def test_t029_ignore_lists_in_each_scanners_form(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register = tmp_path / "register.yaml"
    register.write_text(REGISTER, encoding="utf-8")
    common = ["--register", str(register), "--as-of", "2027-01-05"]
    assert supply_chain.main(["ignores", "--tool", "pip-audit", *common]) == 0
    assert capsys.readouterr().out.strip() == "--ignore-vuln GHSA-aaaa-bbbb-cccc"
    out = tmp_path / "trivyignore"
    assert supply_chain.main(["ignores", "--tool", "trivy", *common, "--out", str(out)]) == 0
    assert out.read_text() == "CVE-2027-0001\n"


@pytest.mark.parametrize(
    "text",
    [
        "findings: {}\n",
        "findings:\n  - {id: X1, source: pypi, severity: high, first_seen: 2027-01-01}\n",
        "findings:\n  - {id: X1, source: bandit, severity: medium, first_seen: 2027-01-01}\n",
        "findings:\n  - {id: X1, source: bandit, severity: high, first_seen: soon}\n",
        "findings:\n  - {id: 'x y', source: bandit, severity: high, first_seen: 2027-01-01}\n",
        "findings:\n  - {id: X1, source: bandit, severity: high, first_seen: 2027-01-02,"
        " closed: 2027-01-01}\n",
        "findings:\n  - {id: X1, source: bandit, severity: high, first_seen: 2027-01-01}\n"
        "  - {id: X1, source: bandit, severity: high, first_seen: 2027-01-01}\n",
    ],
)
def test_t029_a_malformed_register_is_refused(text: str) -> None:
    with pytest.raises(RegisterInvalid):
        parse(text)


def test_t029_a_change_may_not_loosen_the_base_register(tmp_path: Path) -> None:
    base = parse(REGISTER)
    assert weakened(base, base) == []
    later = parse(
        REGISTER.replace(
            "first_seen: 2027-01-04\n  - id: CVE-2027-0001",
            "first_seen: 2027-02-04\n  - id: CVE-2027-0001",
        )
    )
    assert weakened(base, later) == [
        "GHSA-aaaa-bbbb-cccc (pip-audit): first seen moved from 2027-01-04 to 2027-02-04"
    ]
    lower = parse(REGISTER.replace("severity: critical", "severity: high"))
    assert weakened(base, lower) == [
        "GHSA-aaaa-bbbb-cccc (pip-audit): severity lowered from critical to high"
    ]
    removed = parse(REGISTER.split("  - id: CVE-2027-0001")[0])
    assert "CVE-2027-0001 (trivy-image) was removed" in weakened(base, removed)
    reopened = parse(REGISTER.replace("    closed: 2026-11-20\n", ""))
    assert weakened(base, reopened) == ["CVE-2027-0002 (trivy-fs): reopened without a new entry"]
    closed = parse(
        REGISTER.replace(
            "first_seen: 2027-01-04\n  - id: CVE-2027-0001",
            "first_seen: 2027-01-04\n    closed: 2027-01-06\n  - id: CVE-2027-0001",
        )
    )
    assert weakened(base, closed) == []
    base_file, head_file = tmp_path / "base.yaml", tmp_path / "head.yaml"
    base_file.write_text(REGISTER, encoding="utf-8")
    head_file.write_text(
        REGISTER.replace("severity: critical", "severity: high"), encoding="utf-8"
    )
    common = ["check", "--as-of", "2027-01-05", "--register", str(head_file)]
    assert supply_chain.main([*common, "--base-register", str(base_file)]) == 1
    assert supply_chain.main(common) == 0
