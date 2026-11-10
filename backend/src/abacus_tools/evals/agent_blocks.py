"""The AgentBlocks conformance suite's runner (P-09-T15; TASK-6520; DEC-3120).

`python -m abacus_tools.evals --agent agent_blocks` (and `make evals-blocks-fast`): every case of
`evals/agent_blocks/suite.yaml` through the gateway's own output check
(`ai_gateway.output_checks.run_output_check("agent_blocks", …)`), `repeats` times. Deterministic
and code-only: no model, no stack, no cost. The suite passes only at `required_pass_rate` (1.0)
overall and per category; the report goes to `--out` with CI's HMAC-SHA256 signature
(`ABACUS_EVAL_SIGNING_KEY`) when the key is set, so `publish` accepts it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, cast
from uuid import UUID

import yaml

from abacus.ai_gateway.output_checks import run_output_check
from abacus.modules.agents.api import BlocksTurn, Fact
from abacus_tools.evals.summary import SIGNING_KEY_ENV

AGENT: Final = "agent_blocks"
SUITE: Final = Path(__file__).resolve().parents[4] / "evals" / "agent_blocks" / "suite.yaml"


def load(path: Path = SUITE) -> dict[str, Any]:  # ANY-001: the YAML suite
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))  # ANY-001: YAML


def payload(case: dict[str, Any]) -> object:  # ANY-001: a YAML case
    if "raw" in case:
        return case["raw"]
    if "badge" in case:
        obj, code = case["badge"]
        return {"parts": [{"kind": "badge", "object": obj, "code": code}]}
    if "cite" in case:
        cite = {"kind": "cite", "citation_id": case["cite"], "n": 1}
        return {"parts": [{"kind": "cite_list", "cites": [cite]}]}
    segments: list[dict[str, str]] = [{"kind": "text", "text": case["text"]}]
    if "fact" in case:
        segments.append({"kind": "fact", "fact_id": case["fact"]})
    return {"parts": [{"kind": "p", "segments": segments}]}


def run_suite(data: dict[str, Any]) -> dict[str, object]:  # ANY-001: the YAML suite
    facts = {k: Fact(id=k, **v) for k, v in data["facts"].items()}
    cites = {UUID(c) for c in data["citations"]}
    hits: dict[str, list[bool]] = defaultdict(list)
    misses: list[str] = []
    for _ in range(int(data["repeats"])):
        for case in data["cases"]:
            failure = run_output_check("agent_blocks", BlocksTurn(payload(case), facts, cites))
            outcome = "pass" if failure is None else failure.code
            ok = outcome == case["expect"]
            hits[str(case["category"])].append(ok)
            if not ok:
                misses.append(str(case["id"]))
    rates = {cat: sum(v) / len(v) for cat, v in sorted(hits.items())}
    overall = sum(sum(v) for v in hits.values()) / sum(len(v) for v in hits.values())
    required = float(data["required_pass_rate"])
    return {
        "suite": data["suite"],
        "version": data["version"],
        "cases": len(data["cases"]),
        "repeats": int(data["repeats"]),
        "pass_rate": overall,
        "by_category": rates,
        "failed_cases": sorted(set(misses)),
        "status": "passed"
        if overall >= required and all(r >= required for r in rates.values())
        else "failed",
    }


def signed(report: dict[str, object]) -> dict[str, object]:
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return report
    body = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {**report, "signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest()}


def main(out: Path) -> int:
    report = signed(run_suite(load()))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{AGENT}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "signature"}, indent=2))
    return 0 if report["status"] == "passed" else 1
