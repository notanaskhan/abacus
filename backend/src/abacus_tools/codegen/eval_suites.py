"""Generate `abacus.ai_gateway._eval_suites` from the agent specs and their evaluation suites
(SPEC-005 AC-13; TASK-020 review): for each agent with a suite, its prompt reference and the
suite's version, and each other mode's prompt (N-01-T22). The gateway can't read `evals/`
(ADR-101), so it reads this constant to key eligibility on the agent's own prompt and current
suite. A test fails when they drift.

Run: python -m abacus_tools.codegen.eval_suites [--check]
"""

from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path
from typing import cast

import yaml

from abacus.modules.agents.api import AGENTS

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
TARGET = BACKEND / "src" / "abacus" / "ai_gateway" / "_eval_suites.py"
_HEADER = '''"""GENERATED from the agent specs and evals/*/suite.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.eval_suites
"""

'''


EXTRA_MODES: dict[str, dict[str, str]] = {
    "decisions.recommender": {
        "decisions.recommend.convention_706d@v1": "evals/tax_recommender_modes",
        "decisions.recommend.section_754@v1": "evals/tax_recommender_modes",
    }
}


def render() -> str:
    suites: dict[str, tuple[str, int]] = {}
    # N-01-T22 (DEC-1282): an agent's other modes, each prompt on the same suite and version.
    modes: dict[str, dict[str, int]] = {}
    for agent_id, spec in sorted(AGENTS.items()):
        path = REPO / spec.evaluation_suite / "suite.yaml"
        if path.exists():  # only the version is read: each agent's suite has its own shape
            raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
            version = int(cast(int, raw["version"]))
            suites[agent_id] = (spec.prompt, version)
            if spec.modes:
                modes[agent_id] = {m.prompt: version for m in spec.modes.values()}
    # T-05-T47 (DEC-4713): spec v2 capabilities with a suite (tax.account_mapper,
    # tax.agreement_reader, tax.memo_drafter, ...), keyed the same way.
    from abacus.modules.agents.api import SPECS_V2

    for agent_id, raw_spec in sorted(SPECS_V2.items()):
        suite_dir = raw_spec.get("evaluation_suite")
        if agent_id in suites or not isinstance(suite_dir, str):
            continue
        path = REPO / suite_dir / "suite.yaml"
        if path.exists():
            raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
            suites[agent_id] = (str(raw_spec["prompt"]), int(cast(int, raw["version"])))
    # T-05-T47: the recommender's tax modes (T-05-T49) run on their own suite.
    for agent_id, prompts in EXTRA_MODES.items():
        for prompt, suite_dir in prompts.items():
            path = REPO / suite_dir / "suite.yaml"
            if path.exists():
                raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
                modes.setdefault(agent_id, {})[prompt] = int(cast(int, raw["version"]))
    body = pprint.pformat(suites, indent=4, width=99, sort_dicts=True)
    mode_body = pprint.pformat(modes, indent=4, width=99, sort_dicts=True)
    return (
        f"{_HEADER}# fmt: off\nEVAL_SUITES: dict[str, tuple[str, int]] = {body}\n"
        f"EVAL_SUITE_MODES: dict[str, dict[str, int]] = {mode_body}\n# fmt: on\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.relative_to(BACKEND)} is out of date with the agent specs and suites")
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
