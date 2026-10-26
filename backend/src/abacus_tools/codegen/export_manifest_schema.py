"""Generate the engagement export manifest's JSON schema (A-01-T17; SPEC-344; ADR-036).

Run: python -m abacus_tools.codegen.export_manifest_schema [--check]

ADR-036 asks for a versioned schema with tests. The source is the Pydantic model
`abacus.modules.evidence.export_manifest.EngagementExportManifest`; the target,
`docs/contracts/schemas/engagement-export-manifest-v1.schema.json`, is what a firm's own tools
read to check a package. `--check` (in `make check-generated`) reports a stale file. A v2 format
adds a second model and a second file; the v1 file is never rewritten for v2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from abacus.modules.evidence.api import EXPORT_SCHEMA_FILE, export_manifest_json_schema

BACKEND = Path(__file__).resolve().parents[3]
TARGET = BACKEND.parent / "docs" / "contracts" / "schemas" / EXPORT_SCHEMA_FILE


def render() -> str:
    return (
        json.dumps(export_manifest_json_schema(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the schema is out of date")
    args = parser.parse_args(argv)
    body = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != body:
            print(f"{TARGET.name} is out of date: run python -m {__spec__.name}")
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
