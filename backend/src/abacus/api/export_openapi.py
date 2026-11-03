"""Print the OpenAPI document (ADR-013): `make generate` builds `packages/api-client` from it.

Run: python -m abacus.api.export_openapi > ../packages/api-client/openapi.json
Deterministic (sorted keys, fixed indentation), so the drift check compares like with like.
Built once per process: the routes are fixed at import, and each build (the app and its schema)
takes seconds, which 60-odd contract suites paid in turn until the CI job ran out of time
(TASK-2928).
"""

from __future__ import annotations

import json
import sys
from functools import cache

from abacus.api.app import create_app


@cache
def document() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    sys.stdout.write(document())
    return 0


if __name__ == "__main__":
    sys.exit(main())
