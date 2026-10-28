"""Seed contamination and canonical-name lint (F-04-T09; F-04.13, DF-35; lint L10).

Run: python -m abacus_tools.quality.seed_contamination

The Brightwater Hale seed comes from the shared context block and blueprint §9, never from the
design kits' sample data, and its canonical names are spelled one way. This scans the scenario
package (`abacus_tools/synthetic/scenarios/`), the TS seed and scenarios (`apps/web/src/fixtures/`,
including the F-06 tax seed in `fixtures/seed/tax/`), the tier-3 gallery specimens
(`apps/web/src/gallery/specimens/`) and the journey specs (`apps/web/e2e/journeys/`) and fails on:

- kit sample data (F-04.13; ch. 04 §9 "Never port kit sample data"): Elena Ruiz, "Ridgeview
  Partners", the Whitcombes' Schedule E, the kit's inbox address, "17% (4 / 24)", "86 of the 119
  returns", 21 integrations, the Austin office, 126 engagements, the 13-task close run;
- variant spellings of the canonical constants (handoff `gaps.md` §4): "Claire & Jonah Feld",
  and the legal names without their comma ("Ridgeline Property Partners LP" and the like).

Thomas Whitcombe (the EQR partner) and the short forms "Granite Peak" and "Copperleaf" in running
text are canonical and pass. Test files are not scanned: they name the patterns to prove the
lint catches them.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND: Final = Path(__file__).resolve().parents[3]
REPO: Final = BACKEND.parent

ROOTS: Final = (
    BACKEND / "src" / "abacus_tools" / "synthetic" / "scenarios",
    REPO / "apps" / "web" / "src" / "fixtures",
    REPO / "apps" / "web" / "src" / "gallery" / "specimens",  # F-06-T02: the tier-3 specimens
    REPO / "apps" / "web" / "e2e" / "journeys",
)
SUFFIXES: Final = (".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md", ".txt")


@dataclass(frozen=True)
class Rule:
    kind: str  # "kit sample data" or "variant spelling"
    pattern: re.Pattern[str]
    use: str  # what to write instead


def _rule(kind: str, pattern: str, use: str) -> Rule:
    return Rule(kind, re.compile(pattern), use)


RULES: Final[tuple[Rule, ...]] = (
    # Kit sample data (F-04.13). Each is a figure or name the kits invented for their specimens.
    _rule("kit sample data", r"\bElena Ruiz\b", "a seed person (blueprint §9.2)"),
    _rule("kit sample data", r"\bRidgeview Partners\b", "Ridgeline Property Partners, LP"),
    _rule("kit sample data", r"\bWhitcombes'?(?:\s+Schedule E)?", "the Feld household"),
    _rule("kit sample data", r"brightwater-hale@inbox\.accrued\.app", "the synthetic sink"),
    _rule("kit sample data", r"17%\s*\(\s*4\s*/\s*24\s*\)", "Northwind PBC 11 of 24"),
    _rule("kit sample data", r"\b86 of the 119 returns\b", "224 TY2025 returns"),
    _rule("kit sample data", r"\b119 returns\b", "224 TY2025 returns"),
    _rule("kit sample data", r"\b21 integrations\b", "53 integrations"),
    _rule("kit sample data", r"\bAustin\b", "Chicago HQ, Denver or New York"),
    _rule("kit sample data", r"\b126 engagements\b", "counts derived from the seed"),
    _rule("kit sample data", r"\b13-task close run\b", "the Copperleaf close (9 of 21)"),
    # Variant spellings of the canonical constants (gaps.md §4): the seed order and legal names.
    _rule("variant spelling", r"\bClaire (?:&|and) Jonah Feld\b", "Jonah & Claire Feld"),
    _rule("variant spelling", r"\bJonah and Claire Feld\b", "Jonah & Claire Feld"),
    # A legal name with its comma or full stop dropped.
    _rule(
        "variant spelling",
        r"\bRidgeline Property Partners(?: LP\b|, L\.P\.)",
        "Ridgeline Property Partners, LP",
    ),
    _rule(
        "variant spelling",
        r"\bHarborview Dental Properties(?: LP\b|, L\.P\.)",
        "Harborview Dental Properties, LP",
    ),
    _rule(
        "variant spelling",
        r"\bCopperleaf Coffee Roasters(?: Inc\b|, Inc\b(?!\.))",
        "Copperleaf Coffee Roasters, Inc.",
    ),
    _rule(
        "variant spelling",
        r"\bGranite Peak Outdoor Supply(?: Inc\b|, Inc\b(?!\.))",
        "Granite Peak Outdoor Supply, Inc.",
    ),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def findings_in(text: str) -> Iterator[str]:
    """Every rule that matches `text`, as a message naming the fix."""
    for rule in RULES:
        found = rule.pattern.search(text)
        if found is not None:
            yield f"{rule.kind} {found.group(0)!r}: use {rule.use}"


def _is_test(path: Path) -> bool:
    """Unit tests name the patterns on purpose; journey specs are scanned (they carry names)."""
    name = path.name
    return name.startswith("test_") or ".test." in name or "__tests__" in path.parts


def files(roots: Iterable[Path] = ROOTS) -> Iterator[Path]:
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SUFFIXES and not _is_test(path):
                yield path


def scan(roots: Iterable[Path] = ROOTS) -> list[Finding]:
    out: list[Finding] = []
    for path in files(roots):
        rel = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            out.extend(Finding(rel, number, message) for message in findings_in(line))
    return out


def main() -> int:
    found = scan()
    for finding in found:
        print(finding, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
