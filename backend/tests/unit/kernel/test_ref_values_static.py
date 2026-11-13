"""An audit `Ref` carries identifiers, integers and SHA-256 fingerprints only (kernel
`_ref_value`), and the kernel refuses anything else at runtime, inside the unit of work, as a
500. Unit tests with fakes never reach that check, so text slipped through twice (S34's S2
finding; A-07's EQR, rep-letter, release and subsequent-events records, found by A-07-T41).
This scan fails on the shapes that are always text: a string literal that is not a fingerprint,
and a date's `.isoformat()`. A value the scan can't type is the runtime check's.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"
FINGERPRINT = re.compile(r"[0-9a-f]{64}")


def _text_values(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Ref":
            continue
        for kw in node.keywords:
            value = kw.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if not FINGERPRINT.fullmatch(value.value):
                    found.append((node.lineno, f"{kw.arg}={value.value!r}"))
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "isoformat"
            ):
                found.append((node.lineno, f"{kw.arg}=….isoformat()"))
    return found


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_no_ref_carries_text() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{line} {what}"
        for path in sorted(SRC.rglob("*.py"))
        for line, what in _text_values(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert offenders == []


def test_the_scan_finds_both_shapes() -> None:
    sample = ast.parse(
        "Ref(status='open')\nRef(on=day.isoformat())\nRef(h='" + "a" * 64 + "', n=1)\n"
    )
    assert [what for _, what in _text_values(sample)] == ["status='open'", "on=….isoformat()"]
