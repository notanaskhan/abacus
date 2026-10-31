"""Render P-11-T12's golden fixtures once and print their hashes (TASK-2514; SPEC-520 AC-6,
AC-20). Run inside the backend image: `python tests/golden_render/render_fixtures.py`. Prints
`<name> <pdf sha256> <docx sha256> <pages>` per fixture; `two_containers.sh` runs it in two fresh
containers, compares, and records `p11t12.sha256` with `RECORD_GOLDEN=1`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.golden_render.p11t12_fixtures import FIXTURES

from abacus.modules.reporting.render.core import render, render_docx


def main() -> int:
    for fixture in FIXTURES:
        pdf = render(fixture.input())
        docx = render_docx(fixture.input())
        sys.stdout.write(f"{fixture.name} {pdf.render_hash} {docx.render_hash} {pdf.page_count}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
