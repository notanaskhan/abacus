"""Scope guards (F-02-T08; DEC-19): excluded identifiers, single audit and banned terms.

Run: python -m abacus_tools.quality.scope_guards [--write]

Reads docs/architecture/scope-guards.yaml. Scans, as whole identifiers (never substrings):
- Python under backend/src (string constants, names, enum members, Literal values) and the
  migrations, for excluded identifiers and `single_audit`, and its string constants for banned
  terms;
- the permission matrix, feature flags and status registry, for excluded identifiers;
- prompts, and seed scenarios and fixtures when they exist, for both; eval suites for excluded
  identifiers only (their cases are adversarial data, not product text).
Tests are not scanned: they assert the absence. `--write` regenerates
packages/ui/scope-guards.gen.json (checked for drift without it).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
SOURCE = REPO / "docs" / "architecture" / "scope-guards.yaml"
GENERATED = REPO / "packages" / "ui" / "scope-guards.gen.json"


@dataclass(frozen=True)
class Guards:
    nav: tuple[str, ...]
    excluded: dict[str, str]  # identifier -> group
    single_audit_allowed: frozenset[str]
    terms: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def load(text: str | None = None) -> Guards:
    raw = cast(dict[str, object], yaml.safe_load(text if text is not None else SOURCE.read_text()))
    groups = cast(dict[str, list[str]], raw["excluded_identifiers"])
    single = cast(dict[str, object], raw["single_audit"])
    return Guards(
        tuple(cast(list[str], raw["nav"])),
        {ident: group for group, idents in groups.items() for ident in idents},
        frozenset(cast(list[str], single.get("allowed_in") or [])),
        tuple(cast(list[dict[str, str]], raw["banned_terms"])),
    )


def excluded_in(text: str, guards: Guards, rel: str) -> Iterator[str]:
    """Whole identifiers only: `cui` never matches "security", `gri` never "agricultural"."""
    lowered = text.lower().replace("-", "_")
    for ident, group in guards.excluded.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(ident)}(?![a-z0-9])", lowered):
            yield f"excluded identifier {ident!r} ({group})"
    if "single_audit" in lowered and rel not in guards.single_audit_allowed:
        yield "`single_audit` outside the catalogue allowlist (D9)"


def terms_in(text: str, guards: Guards) -> Iterator[str]:
    for entry in guards.terms:
        if entry["term"] in text:
            yield f"banned term {entry['term']!r} ({entry['rule']}): use {entry['use']}"


def _python_strings(source: str) -> Iterator[tuple[int, str]]:
    """String constants and identifiers, not comments: a comment may name what's excluded."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                yield node.lineno, node.value
        elif isinstance(node, ast.Name):
            yield node.lineno, node.id
        elif isinstance(node, ast.Attribute):
            yield node.lineno, node.attr


def _files(roots: Iterable[Path], suffixes: tuple[str, ...]) -> Iterator[Path]:
    for root in roots:
        if root.is_file():
            yield root
        elif root.is_dir():
            yield from (p for p in sorted(root.rglob("*")) if p.suffix in suffixes and p.is_file())


def scan(guards: Guards | None = None) -> list[Finding]:
    g = guards or load()
    findings: list[Finding] = []
    python = [BACKEND / "src" / "abacus", BACKEND / "migrations"]
    for path in _files(python, (".py",)):
        rel = str(path.relative_to(REPO))
        for line, text in _python_strings(path.read_text()):
            for message in excluded_in(text, g, rel):
                findings.append(Finding(rel, line, message))
            for message in terms_in(text, g):
                findings.append(Finding(rel, line, message))
    data = [
        REPO / "docs" / "architecture" / "permission-matrix",
        REPO / "docs" / "architecture" / "feature-flags",
        REPO / "docs" / "product" / "status-vocabulary.yaml",
        REPO / "evals",
        REPO / "scenarios",
        REPO / "apps" / "web" / "src" / "fixtures",
        BACKEND / "src" / "abacus" / "ai_gateway" / "prompts",
    ]
    for path in _files(data, (".yaml", ".yml", ".txt", ".json", ".md", ".ts")):
        rel = str(path.relative_to(REPO))
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            messages = [*excluded_in(line, g, rel)]
            # Terms apply to product text: prompts and seed, not eval cases or the registry.
            if not rel.startswith("evals/") and not rel.endswith("status-vocabulary.yaml"):
                messages += [*terms_in(line, g)]
            findings += [Finding(rel, number, m) for m in messages]
    return findings


def generated(guards: Guards | None = None) -> str:
    g = guards or load()
    return json.dumps({"nav": list(g.nav), "bannedTerms": list(g.terms)}, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scope_guards")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    text = generated()
    if args.write:
        GENERATED.parent.mkdir(parents=True, exist_ok=True)
        GENERATED.write_text(text)
    status = 0
    if not GENERATED.exists() or GENERATED.read_text() != text:
        print("packages/ui/scope-guards.gen.json is stale: run with --write", file=sys.stderr)
        status = 1
    for finding in scan():
        print(finding, file=sys.stderr)
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
