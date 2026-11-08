"""Generate the AgentBlocks v1 JSON Schema for clients (P-09-T03; ADR-230; SPEC-648 AC-6).

Run: python -m abacus_tools.codegen.agent_blocks_schema [--check]

`packages/api-client/schemas/agent-blocks.v1.json` is `AgentBlocks.model_json_schema()` in
validation mode, keys sorted, so a client (P-10's SSE source, a mobile reader, an eval grader) can
validate a payload with the same closed set of parts the server enforces. The server stays the
authority: `agents.blocks.validate_blocks` adds the copy lint, number provenance and references,
which a JSON Schema cannot express. The file drifts from the model only through this generator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from abacus.modules.agents.blocks import AgentBlocks

ROOT = Path(__file__).resolve().parents[4]
TARGET = ROOT / "packages" / "api-client" / "schemas" / "agent-blocks.v1.json"


def render() -> str:
    schema = AgentBlocks.model_json_schema(mode="validation")
    schema["$id"] = "https://accrued.app/schemas/agent-blocks.v1.json"
    schema["title"] = "AgentBlocks v1"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.name} is out of date with agents.blocks.AgentBlocks")
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
