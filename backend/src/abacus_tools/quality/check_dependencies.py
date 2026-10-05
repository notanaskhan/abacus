"""Dependency allowlist check (AGENTS.md rule 12, ADR-083 stage 1). PROTECTED.

Run: python -m abacus_tools.quality.check_dependencies

Every direct dependency in backend/pyproject.toml and every package.json must be `approved` in
docs/architecture/dependency-allowlist.yaml, in a section that covers how it is used. Transitive
dependencies are pinned by the lockfiles and audited in stage 3.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
ALLOWLIST = Path("docs/architecture/dependency-allowlist.yaml")
PYPROJECT = Path("backend/pyproject.toml")
SKIPPED_DIRS = frozenset({"node_modules", "dist"})
_PY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass(frozen=True)
class Dependency:
    manifest: str
    name: str
    runtime: bool


def _pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _section(allowlist: Mapping[str, object], language: str, kind: str) -> dict[str, str]:
    lang = allowlist.get(language)
    if not isinstance(lang, dict):
        return {}
    entries = cast(dict[str, object], lang).get(kind)
    if not isinstance(entries, dict):
        return {}
    return {str(k): str(v) for k, v in cast(dict[object, object], entries).items()}


def _python_dependencies(repo: Path) -> Iterator[Dependency]:
    path = repo / PYPROJECT
    if not path.is_file():
        return
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rel = PYPROJECT.as_posix()
    project = cast(dict[str, object], data.get("project", {}))
    for spec in cast(list[str], project.get("dependencies", [])):
        if m := _PY_NAME.match(spec):
            yield Dependency(rel, _pep503(m.group(1)), runtime=True)
    groups = cast(dict[str, list[object]], data.get("dependency-groups", {}))
    for specs in groups.values():
        for spec in specs:
            if isinstance(spec, str) and (m := _PY_NAME.match(spec)):
                yield Dependency(rel, _pep503(m.group(1)), runtime=False)


def _package_manifests(repo: Path) -> Iterator[Path]:
    for path in sorted(repo.rglob("package.json")):
        parts = path.relative_to(repo).parts[:-1]
        if not any(p in SKIPPED_DIRS or p.startswith(".") for p in parts):
            yield path


def _npm_dependencies(repo: Path) -> Iterator[Dependency]:
    for path in _package_manifests(repo):
        rel = path.relative_to(repo).as_posix()
        data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        for field, runtime in (
            ("dependencies", True),
            ("peerDependencies", True),
            ("optionalDependencies", True),
            ("devDependencies", False),
        ):
            for name, version in cast(dict[str, object], data.get(field, {})).items():
                if not str(version).startswith("workspace:"):
                    yield Dependency(rel, name, runtime)


def _status(name: str, entries: dict[str, str], normalise: bool) -> str | None:
    for key, status in entries.items():
        pattern = _pep503(key) if normalise else key
        if fnmatchcase(name, pattern):
            return status
    return None


def _verdict(
    dep: Dependency, runtime: dict[str, str], dev: dict[str, str], py: bool
) -> str | None:
    in_runtime = _status(dep.name, runtime, py)
    in_dev = _status(dep.name, dev, py)
    if dep.runtime:
        if in_runtime == "approved":
            return None
        if in_runtime is None and in_dev == "approved":
            return "is approved only as a dev dependency"
        status = in_runtime
    else:
        if "approved" in (in_runtime, in_dev):
            return None
        status = in_dev or in_runtime
    if status is None:
        return "is not in the dependency allowlist"
    return "is pending in the dependency allowlist, not approved"


def check(repo: Path = REPO) -> list[str]:
    loaded: object = yaml.safe_load((repo / ALLOWLIST).read_text(encoding="utf-8"))
    allowlist = cast(dict[str, object], loaded) if isinstance(loaded, dict) else {}
    problems: set[str] = set()
    for language, deps, py in (
        ("python", _python_dependencies(repo), True),
        ("typescript", _npm_dependencies(repo), False),
    ):
        runtime = _section(allowlist, language, "runtime")
        dev = _section(allowlist, language, "dev")
        for dep in deps:
            verdict = _verdict(dep, runtime, dev, py)
            if verdict:
                problems.add(f"{dep.manifest}: {dep.name} {verdict}")
    return sorted(problems)


def main() -> int:
    problems = check()
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} dependency allowlist violation(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
