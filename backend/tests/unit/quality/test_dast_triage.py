"""Q-03-T004 (QD-9; DEC-366): the DAST triage counts ZAP's alerts by risk and prints nothing but
counts, since the repository's logs are public."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools.quality import dast

REPORT: dict[str, object] = {
    "site": [
        {
            "@name": "https://staging.example.test",
            "alerts": [
                {"pluginid": "40012", "name": "Cross Site Scripting (Reflected)", "riskcode": "3"},
                {
                    "pluginid": "10038",
                    "name": "Content Security Policy Header Not Set",
                    "riskcode": "2",
                },
                {"pluginid": "10021", "name": "X-Content-Type-Options Missing", "riskcode": "1"},
                {"pluginid": "10109", "name": "Modern Web Application", "riskcode": "0"},
            ],
        },
        {"@name": "https://portal.staging.example.test", "alerts": []},
    ]
}


def test_t004_alerts_are_counted_by_risk() -> None:
    assert dast.counts(REPORT) == {"high": 1, "medium": 1, "low": 1, "informational": 1}
    assert dast.counts({}) == {"high": 0, "medium": 0, "low": 0, "informational": 0}


def test_t004_an_unknown_risk_is_an_error() -> None:
    with pytest.raises(ValueError):
        dast.counts({"site": [{"alerts": [{"riskcode": "9"}]}]})


def test_t004_only_counts_leave_the_tool(tmp_path: Path) -> None:
    report = tmp_path / "zap-report.json"
    report.write_text(json.dumps(REPORT), encoding="utf-8")
    summary, output = tmp_path / "summary.md", tmp_path / "output"
    assert dast.main([str(report), "--summary", str(summary), "--github-output", str(output)]) == 0
    assert output.read_text() == "high=1\nmedium=1\n"
    text = summary.read_text()
    assert "| high | 1 |" in text and "SEV3" in text
    for leak in ("Cross Site", "staging.example.test", "40012", "Content Security"):
        assert leak not in text
