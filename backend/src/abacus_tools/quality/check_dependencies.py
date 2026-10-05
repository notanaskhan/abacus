"""Dependency allowlist check (AGENTS.md rule 12, ADR-083 stage 1). PROTECTED.

Run: python -m abacus_tools.quality.check_dependencies

Every direct dependency in any pyproject.toml, requirements*.txt and package.json must be
`approved` in docs/architecture/dependency-allowlist.yaml, in a section that covers how it is
used, and must come from the package registry. Mechanisms that change where or which packages are
installed (sources, indexes, overrides, patches, catalogs) are refused outright. Transitive
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
SKIPPED_DIRS = frozenset({"node_modules", "dist"})
_PY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_NPM_NON_REGISTRY = re.compile(r"^(?:npm:|git|github:|https?:|file:|link:)|^[^#]*/")
REGISTRY = "must be installed from the package registry, not a URL, path, git repository or alias"
NOT_WORKSPACE = "is not a workspace package"
SOURCE_CHANGE = "is not allowed: it changes where or which dependencies are installed"
UV_FORBIDDEN = (
    "sources",
    "index",
    "override-dependencies",
    "constraint-dependencies",
    "dev-dependencies",
)
NPM_FORBIDDEN = ("overrides", "resolutions", "bundleDependencies", "bundledDependencies")
PNPM_FORBIDDEN = ("overrides", "patchedDependencies")
WORKSPACE_FORBIDDEN = ("overrides", "patchedDependencies", "catalog", "catalogs")


@dataclass(frozen=True)
class Dependency:
    manifest: str
    name: str
    runtime: bool
    registry: bool = True


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


def _files(repo: Path, pattern: str) -> Iterator[Path]:
    for path in sorted(repo.rglob(pattern)):
        parts = path.relative_to(repo).parts[:-1]
        if not any(p in SKIPPED_DIRS or p.startswith(".") for p in parts):
            yield path


def _python_spec(rel: str, spec: object, runtime: bool) -> Iterator[Dependency]:
    if not isinstance(spec, str) or not (m := _PY_NAME.match(spec)):
        return
    direct = "@" in spec.split(";", 1)[0]
    yield Dependency(rel, _pep503(m.group(1)), runtime, registry=not direct)


def _python_dependencies(repo: Path, problems: set[str]) -> Iterator[Dependency]:
    for path in _files(repo, "pyproject.toml"):
        rel = path.relative_to(repo).as_posix()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        project = cast(dict[str, object], data.get("project", {}))
        for spec in cast(list[object], project.get("dependencies", [])):
            yield from _python_spec(rel, spec, runtime=True)
        optional = cast(dict[str, list[object]], project.get("optional-dependencies", {}))
        for specs in optional.values():
            for spec in specs:
                yield from _python_spec(rel, spec, runtime=True)
        for specs in cast(dict[str, list[object]], data.get("dependency-groups", {})).values():
            for spec in specs:
                yield from _python_spec(rel, spec, runtime=False)
        build = cast(dict[str, object], data.get("build-system", {}))
        for spec in cast(list[object], build.get("requires", [])):
            yield from _python_spec(rel, spec, runtime=False)
        tool = cast(dict[str, object], data.get("tool", {}))
        uv = cast(dict[str, object], tool.get("uv", {}))
        for key in UV_FORBIDDEN:
            if key in uv:
                problems.add(f"{rel}: tool.uv.{key} {SOURCE_CHANGE}")
    for path in _files(repo, "requirements*.txt"):
        rel = path.relative_to(repo).as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            spec = line.split("#", 1)[0].strip()
            if spec.startswith("-"):
                problems.add(f"{rel}: {spec.split()[0]} {SOURCE_CHANGE}")
            elif spec:
                yield from _python_spec(rel, spec, runtime=True)


def _npm_dependencies(repo: Path, problems: set[str]) -> Iterator[Dependency]:
    manifests = list(_files(repo, "package.json"))
    datas = {
        p: cast(dict[str, object], json.loads(p.read_text(encoding="utf-8"))) for p in manifests
    }
    workspace_names = {str(d.get("name")) for d in datas.values() if d.get("name")}
    for path, data in datas.items():
        rel = path.relative_to(repo).as_posix()
        for key in NPM_FORBIDDEN:
            if key in data:
                problems.add(f"{rel}: {key} {SOURCE_CHANGE}")
        pnpm = cast(dict[str, object], data.get("pnpm", {}))
        for key in PNPM_FORBIDDEN:
            if key in pnpm:
                problems.add(f"{rel}: pnpm.{key} {SOURCE_CHANGE}")
        for field, runtime in (
            ("dependencies", True),
            ("peerDependencies", True),
            ("optionalDependencies", True),
            ("devDependencies", False),
        ):
            for name, version in cast(dict[str, object], data.get(field, {})).items():
                spec = str(version)
                if spec.startswith("workspace:"):
                    if name not in workspace_names:
                        problems.add(f"{rel}: {name} {NOT_WORKSPACE}")
                    continue
                registry = not _NPM_NON_REGISTRY.search(spec)
                yield Dependency(rel, name, runtime, registry)
    workspace = repo / "pnpm-workspace.yaml"
    if workspace.is_file():
        loaded: object = yaml.safe_load(workspace.read_text(encoding="utf-8"))
        keys = cast(dict[str, object], loaded) if isinstance(loaded, dict) else {}
        for key in WORKSPACE_FORBIDDEN:
            if key in keys:
                problems.add(f"pnpm-workspace.yaml: {key} {SOURCE_CHANGE}")


def _status(name: str, entries: dict[str, str], normalise: bool) -> str | None:
    keys = {(_pep503(k) if normalise else k): v for k, v in entries.items()}
    if name in keys:
        return keys[name]
    return next((v for k, v in keys.items() if fnmatchcase(name, k)), None)


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
        ("python", _python_dependencies(repo, problems), True),
        ("typescript", _npm_dependencies(repo, problems), False),
    ):
        runtime = _section(allowlist, language, "runtime")
        dev = _section(allowlist, language, "dev")
        for dep in deps:
            if not dep.registry:
                problems.add(f"{dep.manifest}: {dep.name} {REGISTRY}")
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
