"""AC-20: the dependency gate rejects unlisted, pending and wrongly sectioned dependencies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools.quality import check_dependencies as cd

REPO = Path(__file__).resolve().parents[4]

PYPROJECT = "backend/pyproject.toml"
WEB = "apps/web/package.json"

Allow = dict[str, dict[str, dict[str, str]]]


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _allowlist(
    *,
    py_runtime: dict[str, str] | None = None,
    py_dev: dict[str, str] | None = None,
    ts_runtime: dict[str, str] | None = None,
    ts_dev: dict[str, str] | None = None,
) -> Allow:
    return {
        "python": {"runtime": py_runtime or {}, "dev": py_dev or {}},
        "typescript": {"runtime": ts_runtime or {}, "dev": ts_dev or {}},
    }


def _repo(
    root: Path,
    allow: Allow,
    *,
    runtime: list[str] | None = None,
    dev: list[str] | None = None,
    packages: dict[str, dict[str, object]] | None = None,
    extra_toml: str = "",
    files: dict[str, str] | None = None,
) -> Path:
    """A minimal repo; JSON is valid YAML and its string arrays are valid TOML."""
    _write(root, "docs/architecture/dependency-allowlist.yaml", json.dumps(allow, indent=2))
    toml = '[project]\nname = "x"\nversion = "0"\n'
    toml += "dependencies = " + json.dumps(runtime or []) + "\n"
    toml += "\n[dependency-groups]\ndev = " + json.dumps(dev or []) + "\n"
    _write(root, PYPROJECT, toml + extra_toml)
    for rel, text in (files or {}).items():
        _write(root, rel, text)
    for rel, sections in (packages or {}).items():
        _write(root, rel, json.dumps({"name": "pkg", **sections}))
    return root


# --- clean ------------------------------------------------------------------------------------


def test_ac20_clean_manifests_pass(tmp_path: Path) -> None:
    allow = _allowlist(
        py_runtime={"fastapi": "approved"},
        py_dev={"pytest": "approved"},
        ts_runtime={"react": "approved"},
        ts_dev={"vitest": "approved"},
    )
    _repo(
        tmp_path,
        allow,
        runtime=["fastapi>=0.110"],
        dev=["pytest>=8"],
        packages={WEB: {"dependencies": {"react": "^19"}, "devDependencies": {"vitest": "^3"}}},
    )
    assert cd.check(tmp_path) == []


def test_ac20_no_dependencies_pass(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist())
    assert cd.check(tmp_path) == []


# --- python -----------------------------------------------------------------------------------


def test_ac20_unlisted_python_runtime_dependency_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(), runtime=["left-pad>=1"])
    assert cd.check(tmp_path) == [f"{PYPROJECT}: left-pad is not in the dependency allowlist"]


def test_ac20_unlisted_python_dev_dependency_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(), dev=["left-pad>=1"])
    assert cd.check(tmp_path) == [f"{PYPROJECT}: left-pad is not in the dependency allowlist"]


def test_ac20_pending_python_runtime_dependency_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"workos": "pending"}), runtime=["workos"])
    assert cd.check(tmp_path) == [
        f"{PYPROJECT}: workos is pending in the dependency allowlist, not approved"
    ]


def test_ac20_pending_python_dev_dependency_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_dev={"mutmut": "pending"}), dev=["mutmut"])
    assert cd.check(tmp_path) == [
        f"{PYPROJECT}: mutmut is pending in the dependency allowlist, not approved"
    ]


def test_ac20_runtime_dependency_listed_only_as_dev_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_dev={"pytest": "approved"}), runtime=["pytest"])
    assert cd.check(tmp_path) == [f"{PYPROJECT}: pytest is approved only as a dev dependency"]


def test_ac20_dev_dependency_approved_as_runtime_is_allowed(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"httpx": "approved"}), dev=["httpx"])
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    "requirement",
    [
        "Types_PyYAML>=6",
        "types-pyyaml",
        "TYPES.PYYAML==6.0.12",
        "types__pyyaml~=6.0",
        "Types-PyYAML",
    ],
)
def test_ac20_python_names_are_pep_503_normalised(tmp_path: Path, requirement: str) -> None:
    _repo(tmp_path, _allowlist(py_dev={"types-pyyaml": "approved"}), dev=[requirement])
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    "requirement",
    [
        "uvicorn[standard]>=0.30",
        "uvicorn[standard,extra]==0.30.*",
        "uvicorn>=0.30; python_version >= '3.12'",
        'uvicorn[standard]>=0.30 ; sys_platform == "linux"',
        "uvicorn (>=0.30)",
        "uvicorn",
    ],
)
def test_ac20_extras_versions_and_markers_are_stripped(tmp_path: Path, requirement: str) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"uvicorn": "approved"}), runtime=[requirement])
    assert cd.check(tmp_path) == []


def test_ac20_dotted_and_underscored_names_collapse_to_one_hyphen(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"a-b-c": "approved"}), runtime=["A_.-B__C>=1"])
    assert cd.check(tmp_path) == []


def test_ac20_normalised_name_not_in_allowlist_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"left-pad": "approved"}), runtime=["right_pad>=1"])
    [message] = cd.check(tmp_path)
    assert message.startswith(f"{PYPROJECT}: ")
    assert message.endswith(" is not in the dependency allowlist")


# --- npm --------------------------------------------------------------------------------------

RUNTIME_SECTIONS = ["dependencies", "peerDependencies", "optionalDependencies"]


@pytest.mark.parametrize("section", RUNTIME_SECTIONS)
def test_ac20_unlisted_npm_runtime_dependency_is_reported(tmp_path: Path, section: str) -> None:
    _repo(tmp_path, _allowlist(), packages={WEB: {section: {"left-pad": "^1"}}})
    assert cd.check(tmp_path) == [f"{WEB}: left-pad is not in the dependency allowlist"]


def test_ac20_unlisted_npm_dev_dependency_is_reported(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(), packages={WEB: {"devDependencies": {"left-pad": "^1"}}})
    assert cd.check(tmp_path) == [f"{WEB}: left-pad is not in the dependency allowlist"]


@pytest.mark.parametrize("section", RUNTIME_SECTIONS)
def test_ac20_pending_npm_runtime_dependency_is_reported(tmp_path: Path, section: str) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"left-pad": "pending"}),
        packages={WEB: {section: {"left-pad": "^1"}}},
    )
    assert cd.check(tmp_path) == [
        f"{WEB}: left-pad is pending in the dependency allowlist, not approved"
    ]


def test_ac20_pending_npm_dev_dependency_is_reported(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_dev={"jsdom": "pending"}),
        packages={WEB: {"devDependencies": {"jsdom": "^26"}}},
    )
    assert cd.check(tmp_path) == [
        f"{WEB}: jsdom is pending in the dependency allowlist, not approved"
    ]


@pytest.mark.parametrize("section", RUNTIME_SECTIONS)
def test_ac20_npm_runtime_dependency_listed_only_as_dev_is_reported(
    tmp_path: Path, section: str
) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_dev={"vitest": "approved"}),
        packages={WEB: {section: {"vitest": "^3"}}},
    )
    assert cd.check(tmp_path) == [f"{WEB}: vitest is approved only as a dev dependency"]


@pytest.mark.parametrize(
    ("ts_runtime", "ts_dev"),
    [({}, {"vitest": "approved"}), ({"vitest": "approved"}, {})],
    ids=["dev-listing", "runtime-listing"],
)
def test_ac20_npm_dev_dependency_may_be_listed_under_either_section(
    tmp_path: Path, ts_runtime: dict[str, str], ts_dev: dict[str, str]
) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime=ts_runtime, ts_dev=ts_dev),
        packages={WEB: {"devDependencies": {"vitest": "^3"}}},
    )
    assert cd.check(tmp_path) == []


def test_ac20_scoped_glob_matches_scope_members(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@radix-ui/*": "approved"}),
        packages={
            WEB: {"dependencies": {"@radix-ui/react-dialog": "^1", "@radix-ui/react-slot": "^1"}}
        },
    )
    assert cd.check(tmp_path) == []


def test_ac20_scoped_glob_does_not_match_other_scopes(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@radix-ui/*": "approved"}),
        packages={WEB: {"dependencies": {"@other/react-dialog": "^1"}}},
    )
    assert cd.check(tmp_path) == [f"{WEB}: @other/react-dialog is not in the dependency allowlist"]


def test_ac20_pending_glob_is_reported(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@scope/*": "pending"}),
        packages={WEB: {"dependencies": {"@scope/thing": "^1"}}},
    )
    assert cd.check(tmp_path) == [
        f"{WEB}: @scope/thing is pending in the dependency allowlist, not approved"
    ]


def test_ac20_exact_scoped_name_is_matched(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@tanstack/react-query": "approved"}),
        packages={WEB: {"dependencies": {"@tanstack/react-query": "^5"}}},
    )
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize("version", ["workspace:*", "workspace:^", "workspace:../api-client"])
def test_ac20_workspace_dependencies_are_skipped(tmp_path: Path, version: str) -> None:
    _repo(
        tmp_path,
        _allowlist(),
        packages={
            WEB: {"dependencies": {"@abacus/client": version}},
            "packages/client/package.json": {"name": "@abacus/client"},
        },
    )
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    "rel",
    [
        "node_modules/left-pad/package.json",
        "apps/web/node_modules/left-pad/package.json",
        "apps/web/dist/package.json",
        "dist/package.json",
        ".git/hooks/package.json",
        "apps/.cache/package.json",
        ".venv/lib/package.json",
    ],
)
def test_ac20_ignored_directories_are_not_scanned(tmp_path: Path, rel: str) -> None:
    _repo(tmp_path, _allowlist(), packages={rel: {"dependencies": {"left-pad": "^1"}}})
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize("rel", ["package.json", "packages/api-client/package.json", WEB])
def test_ac20_every_package_json_is_scanned(tmp_path: Path, rel: str) -> None:
    _repo(tmp_path, _allowlist(), packages={rel: {"dependencies": {"left-pad": "^1"}}})
    assert cd.check(tmp_path) == [f"{rel}: left-pad is not in the dependency allowlist"]


# --- ordering and combination -----------------------------------------------------------------


def test_ac20_messages_are_sorted_and_cover_every_manifest(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(
            py_runtime={"pend-py": "pending"},
            py_dev={"dev-only": "approved"},
            ts_runtime={"pend-ts": "pending"},
        ),
        runtime=["zzz-unlisted", "dev-only", "pend-py"],
        packages={
            WEB: {"dependencies": {"pend-ts": "^1", "aaa-unlisted": "^1"}},
            "packages/api-client/package.json": {"dependencies": {"mmm-unlisted": "^1"}},
        },
    )
    result = cd.check(tmp_path)
    assert result == sorted(result)
    assert result == [
        "apps/web/package.json: aaa-unlisted is not in the dependency allowlist",
        "apps/web/package.json: pend-ts is pending in the dependency allowlist, not approved",
        "backend/pyproject.toml: dev-only is approved only as a dev dependency",
        "backend/pyproject.toml: pend-py is pending in the dependency allowlist, not approved",
        "backend/pyproject.toml: zzz-unlisted is not in the dependency allowlist",
        "packages/api-client/package.json: mmm-unlisted is not in the dependency allowlist",
    ]


# --- main and the real repository -------------------------------------------------------------


def test_ac20_main_prints_messages_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    messages = ["a: x is bad", "b: y is bad"]

    def fake_check(*_args: object, **_kwargs: object) -> list[str]:
        return messages

    monkeypatch.setattr(cd, "check", fake_check)
    assert cd.main() == 1
    assert capsys.readouterr().out == "a: x is bad\nb: y is bad\n"


def test_ac20_main_exits_0_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    empty: list[str] = []

    def fake_check(*_args: object, **_kwargs: object) -> list[str]:
        return empty

    monkeypatch.setattr(cd, "check", fake_check)
    assert cd.main() == 0


def test_ac20_repository_dependencies_are_allowlisted() -> None:
    # Deliberately depends on live repo state: this is the AC-20 claim itself, and duplicates
    # the dependency step of `make check-fast`.
    assert cd.check(REPO) == []


# --- Contract revision 1 ----------------------------------------------------------------------

NOT_FROM_REGISTRY = (
    "must be installed from the package registry, not a URL, path, git repository or alias"
)
CHANGES_INSTALL = "it changes where or which dependencies are installed"


# optional dependencies, build requirements, other manifests


def test_ac20_unlisted_optional_dependency_is_reported(tmp_path: Path) -> None:
    extra = '\n[project.optional-dependencies]\nextra = ["left-pad>=1"]\n'
    _repo(tmp_path, _allowlist(), extra_toml=extra)
    assert cd.check(tmp_path) == [f"{PYPROJECT}: left-pad is not in the dependency allowlist"]


def test_ac20_optional_dependency_is_a_runtime_dependency(tmp_path: Path) -> None:
    extra = '\n[project.optional-dependencies]\nextra = ["pytest>=8"]\n'
    _repo(tmp_path, _allowlist(py_dev={"pytest": "approved"}), extra_toml=extra)
    assert cd.check(tmp_path) == [f"{PYPROJECT}: pytest is approved only as a dev dependency"]


def test_ac20_approved_optional_dependency_passes(tmp_path: Path) -> None:
    extra = '\n[project.optional-dependencies]\nextra = ["httpx>=0.27"]\n'
    _repo(tmp_path, _allowlist(py_runtime={"httpx": "approved"}), extra_toml=extra)
    assert cd.check(tmp_path) == []


def test_ac20_unlisted_build_requirement_is_reported(tmp_path: Path) -> None:
    extra = '\n[build-system]\nrequires = ["hatchling>=1"]\nbuild-backend = "hatchling.build"\n'
    _repo(tmp_path, _allowlist(), extra_toml=extra)
    assert cd.check(tmp_path) == [f"{PYPROJECT}: hatchling is not in the dependency allowlist"]


@pytest.mark.parametrize("section", ["py_dev", "py_runtime"])
def test_ac20_build_requirement_may_be_dev_or_runtime(tmp_path: Path, section: str) -> None:
    extra = '\n[build-system]\nrequires = ["hatchling>=1"]\nbuild-backend = "hatchling.build"\n'
    allow = _allowlist(**{section: {"hatchling": "approved"}})
    _repo(tmp_path, allow, extra_toml=extra)
    assert cd.check(tmp_path) == []


def test_ac20_other_pyproject_is_read_as_runtime(tmp_path: Path) -> None:
    other = 'dependencies = ["left-pad"]\n'
    toml = '[project]\nname = "y"\nversion = "0"\n' + other
    _repo(tmp_path, _allowlist(), files={"tools/y/pyproject.toml": toml})
    assert cd.check(tmp_path) == [
        "tools/y/pyproject.toml: left-pad is not in the dependency allowlist"
    ]


def test_ac20_other_pyproject_dev_only_listing_is_reported(tmp_path: Path) -> None:
    toml = '[project]\nname = "y"\nversion = "0"\ndependencies = ["pytest"]\n'
    _repo(
        tmp_path,
        _allowlist(py_dev={"pytest": "approved"}),
        files={"tools/y/pyproject.toml": toml},
    )
    assert cd.check(tmp_path) == [
        "tools/y/pyproject.toml: pytest is approved only as a dev dependency"
    ]


@pytest.mark.parametrize(
    "rel", ["requirements.txt", "requirements-dev.txt", "tools/requirements-docs.txt"]
)
def test_ac20_requirements_files_are_runtime(tmp_path: Path, rel: str) -> None:
    text = "# pinned\n\nleft-pad>=1\npytest==8.0\n"
    _repo(tmp_path, _allowlist(py_dev={"pytest": "approved"}), files={rel: text})
    assert cd.check(tmp_path) == [
        f"{rel}: left-pad is not in the dependency allowlist",
        f"{rel}: pytest is approved only as a dev dependency",
    ]


def test_ac20_approved_requirements_file_passes(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(py_runtime={"httpx": "approved"}),
        files={"requirements.txt": "httpx>=0.27\n"},
    )
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    "rel",
    [
        "node_modules/x/requirements.txt",
        "node_modules/x/pyproject.toml",
        "apps/web/dist/requirements.txt",
        "dist/pyproject.toml",
        ".venv/requirements.txt",
        "tools/.cache/pyproject.toml",
    ],
)
def test_ac20_ignored_directories_hide_python_manifests(tmp_path: Path, rel: str) -> None:
    text = 'dependencies = ["left-pad"]\n' if rel.endswith(".toml") else "left-pad\n"
    toml_or_txt = (
        '[project]\nname = "y"\nversion = "0"\n' + text if rel.endswith(".toml") else text
    )
    _repo(tmp_path, _allowlist(), files={rel: toml_or_txt})
    assert cd.check(tmp_path) == []


# exact keys beat globs


def test_ac20_exact_pending_key_beats_approved_glob(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@scope/*": "approved", "@scope/bad": "pending"}),
        packages={WEB: {"dependencies": {"@scope/bad": "^1", "@scope/good": "^1"}}},
    )
    assert cd.check(tmp_path) == [
        f"{WEB}: @scope/bad is pending in the dependency allowlist, not approved"
    ]


def test_ac20_exact_approved_key_beats_pending_glob(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"@scope/*": "pending", "@scope/good": "approved"}),
        packages={WEB: {"dependencies": {"@scope/good": "^1"}}},
    )
    assert cd.check(tmp_path) == []


# registry-only sources


@pytest.mark.parametrize(
    "requirement",
    [
        "left-pad @ https://example.org/left_pad-1.0.whl",
        "left-pad@https://example.org/left_pad-1.0.whl",
        "left-pad @ git+https://example.org/left-pad.git",
        "left-pad[extra] @ file:///opt/left-pad",
        "left-pad @ ./vendor/left-pad",
    ],
)
def test_ac20_python_url_requirement_is_reported(tmp_path: Path, requirement: str) -> None:
    _repo(tmp_path, _allowlist(py_runtime={"left-pad": "approved"}), runtime=[requirement])
    assert cd.check(tmp_path) == [f"{PYPROJECT}: left-pad {NOT_FROM_REGISTRY}"]


@pytest.mark.parametrize(
    "version",
    [
        "npm:other@1",
        "git+ssh://example.org/a.git",
        "git://example.org/a.git",
        "github:org/repo",
        "http://example.org/a.tgz",
        "https://example.org/a.tgz",
        "file:../a",
        "link:../a",
        "org/repo",
        "org/repo#main",
    ],
)
def test_ac20_npm_non_registry_version_is_reported(tmp_path: Path, version: str) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"left-pad": "approved"}),
        packages={WEB: {"dependencies": {"left-pad": version}}},
    )
    assert cd.check(tmp_path) == [f"{WEB}: left-pad {NOT_FROM_REGISTRY}"]


@pytest.mark.parametrize("version", ["^1.2.3", "~1", "latest", "1.x", "*", ">=1 <2", "1.0.0"])
def test_ac20_npm_registry_version_passes(tmp_path: Path, version: str) -> None:
    _repo(
        tmp_path,
        _allowlist(ts_runtime={"left-pad": "approved"}),
        packages={WEB: {"dependencies": {"left-pad": version}}},
    )
    assert cd.check(tmp_path) == []


# workspace packages


def test_ac20_workspace_dependency_on_unknown_package_is_reported(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(),
        packages={WEB: {"dependencies": {"@abacus/missing": "workspace:*"}}},
    )
    assert cd.check(tmp_path) == [f"{WEB}: @abacus/missing is not a workspace package"]


def test_ac20_workspace_dependency_on_known_package_passes(tmp_path: Path) -> None:
    _repo(
        tmp_path,
        _allowlist(),
        packages={
            WEB: {"devDependencies": {"@abacus/api-client": "workspace:*"}},
            "packages/api-client/package.json": {"name": "@abacus/api-client"},
        },
    )
    assert cd.check(tmp_path) == []


# install-redirecting settings


@pytest.mark.parametrize(
    ("toml", "key"),
    [
        ('[tool.uv.sources]\nleft-pad = { path = "../left-pad" }\n', "tool.uv.sources"),
        ('[[tool.uv.index]]\nname = "x"\nurl = "https://example.org/simple"\n', "tool.uv.index"),
        ('[tool.uv]\noverride-dependencies = ["left-pad>=1"]\n', "tool.uv.override-dependencies"),
        (
            '[tool.uv]\nconstraint-dependencies = ["left-pad>=1"]\n',
            "tool.uv.constraint-dependencies",
        ),
        ('[tool.uv]\ndev-dependencies = ["left-pad>=1"]\n', "tool.uv.dev-dependencies"),
    ],
)
def test_ac20_pyproject_install_redirect_is_reported(tmp_path: Path, toml: str, key: str) -> None:
    _repo(tmp_path, _allowlist(), extra_toml="\n" + toml)
    assert f"{PYPROJECT}: {key} is not allowed: {CHANGES_INSTALL}" in cd.check(tmp_path)


def test_ac20_pyproject_plain_tool_tables_pass(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(), extra_toml="\n[tool.uv]\npackage = false\n")
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    ("sections", "key"),
    [
        ({"pnpm": {"overrides": {"left-pad": "1.0.0"}}}, "pnpm.overrides"),
        (
            {"pnpm": {"patchedDependencies": {"left-pad@1.0.0": "p.patch"}}},
            "pnpm.patchedDependencies",
        ),
        ({"overrides": {"left-pad": "1.0.0"}}, "overrides"),
        ({"resolutions": {"left-pad": "1.0.0"}}, "resolutions"),
        ({"bundleDependencies": ["left-pad"]}, "bundleDependencies"),
        ({"bundledDependencies": ["left-pad"]}, "bundledDependencies"),
    ],
)
def test_ac20_package_json_install_redirect_is_reported(
    tmp_path: Path, sections: dict[str, object], key: str
) -> None:
    _repo(tmp_path, _allowlist(), packages={WEB: sections})
    assert cd.check(tmp_path) == [f"{WEB}: {key} is not allowed: {CHANGES_INSTALL}"]


@pytest.mark.parametrize("key", ["overrides", "patchedDependencies", "catalog", "catalogs"])
def test_ac20_pnpm_workspace_install_redirect_is_reported(tmp_path: Path, key: str) -> None:
    text = json.dumps({"packages": ["apps/*"], key: {"left-pad": "1.0.0"}})
    _repo(tmp_path, _allowlist(), files={"pnpm-workspace.yaml": text})
    assert cd.check(tmp_path) == [f"pnpm-workspace.yaml: {key} is not allowed: {CHANGES_INSTALL}"]


def test_ac20_plain_pnpm_workspace_passes(tmp_path: Path) -> None:
    text = json.dumps({"packages": ["apps/*", "packages/*"]})
    _repo(tmp_path, _allowlist(), files={"pnpm-workspace.yaml": text})
    assert cd.check(tmp_path) == []


# --- Container images (TASK-004) --------------------------------------------------------------

COMPOSE = "docker-compose.yml"
COMPOSE_NAMES = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
DIGEST = "sha256:" + "ab" * 32
OTHER_DIGEST = "sha256:" + "09" * 32
PG = "pgvector/pgvector"
PINNED_PG = f"{PG}:pg17@{DIGEST}"
BUILD_REFUSED = "builds an image; build steps are not allowed in compose files"
ALLOWLIST_PATH = "docs/architecture/dependency-allowlist.yaml"


def _pin_message(rel: str, image: str) -> str:
    return f"{rel}: {image} must be pinned by digest (name:tag@sha256:...)"


def _unlisted(rel: str, name: str) -> str:
    return f"{rel}: {name} is not in the dependency allowlist"


def _pending(rel: str, name: str) -> str:
    return f"{rel}: {name} is pending in the dependency allowlist, not approved"


def _stack(
    root: Path,
    containers: dict[str, str],
    services: dict[str, dict[str, object]] | None = None,
    *,
    rel: str = COMPOSE,
) -> Path:
    """A repo whose allowlist has a `containers:` section and one compose file."""
    _repo(root, _allowlist())
    allow: dict[str, object] = {**_allowlist(), "containers": containers}
    _write(root, ALLOWLIST_PATH, json.dumps(allow, indent=2))
    if services is not None:
        _write(root, rel, json.dumps({"services": services}))
    return root


def _one(image: str) -> dict[str, dict[str, object]]:
    return {"db": {"image": image}}


def test_ac20_pinned_approved_image_passes(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(PINNED_PG))
    assert cd.check(tmp_path) == []


def test_ac20_compose_file_written_as_yaml_text_is_read(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"})
    text = f"services:\n  db:\n    image: {PG}:pg17@{DIGEST}\n    ports:\n      - '5432:5432'\n"
    _write(tmp_path, COMPOSE, text)
    assert cd.check(tmp_path) == []


def test_ac20_unpinned_image_in_yaml_text_is_reported(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"})
    _write(tmp_path, COMPOSE, f"services:\n  db:\n    image: {PG}:pg17\n")
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, f"{PG}:pg17")]


def test_ac20_no_compose_file_passes(tmp_path: Path) -> None:
    _stack(tmp_path, {})
    assert cd.check(tmp_path) == []


def test_ac20_compose_without_images_passes(tmp_path: Path) -> None:
    _stack(tmp_path, {}, {})
    assert cd.check(tmp_path) == []


def test_ac20_allowlist_without_containers_section_reports_image_as_unlisted(
    tmp_path: Path,
) -> None:
    _repo(tmp_path, _allowlist())
    _write(tmp_path, COMPOSE, json.dumps({"services": _one(PINNED_PG)}))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, PG)]


# pinned by digest


@pytest.mark.parametrize(
    "image",
    [
        f"{PG}:pg17",
        f"{PG}:latest",
        PG,
        f"{PG}@sha256",
        f"{PG}@sha256:",
        f"{PG}@{DIGEST[7:]}",
        f"{PG}:pg17@md5:{'ab' * 16}",
        f"{PG}:pg17@sha512:{'ab' * 32}",
    ],
    ids=["tag-only", "latest", "bare-name", "no-hex", "empty-hex", "no-algo", "md5", "sha512"],
)
def test_ac20_image_without_sha256_digest_is_reported(tmp_path: Path, image: str) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(image))
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, image)]


@pytest.mark.parametrize(
    "digest",
    ["sha256:" + "AB" * 32, "sha256:" + "aB" * 32, "sha256:" + "ab" * 31 + "AB"],
    ids=["upper", "mixed", "one-upper-pair"],
)
def test_ac20_uppercase_hex_digest_is_reported(tmp_path: Path, digest: str) -> None:
    image = f"{PG}:pg17@{digest}"
    _stack(tmp_path, {PG: "approved"}, _one(image))
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, image)]


@pytest.mark.parametrize("hex_length", [0, 1, 12, 40, 63, 65, 128])
def test_ac20_digest_of_wrong_length_is_reported(tmp_path: Path, hex_length: int) -> None:
    image = f"{PG}:pg17@sha256:" + ("a1" * 64)[:hex_length]
    _stack(tmp_path, {PG: "approved"}, _one(image))
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, image)]


def test_ac20_non_hex_digest_is_reported(tmp_path: Path) -> None:
    image = f"{PG}:pg17@sha256:" + "g" * 64
    _stack(tmp_path, {PG: "approved"}, _one(image))
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, image)]


def test_ac20_digest_without_tag_is_allowed(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(f"{PG}@{DIGEST}"))
    assert cd.check(tmp_path) == []


def test_ac20_registry_host_and_nested_path_name_is_matched_without_tag_and_digest(
    tmp_path: Path,
) -> None:
    name = "ghcr.io/org/team/img"
    _stack(tmp_path, {name: "approved"}, _one(f"{name}:1.2.3@{DIGEST}"))
    assert cd.check(tmp_path) == []


def test_ac20_tag_does_not_change_the_approved_name(tmp_path: Path) -> None:
    _stack(
        tmp_path,
        {PG: "approved"},
        {"a": {"image": f"{PG}:pg16@{DIGEST}"}, "b": {"image": f"{PG}:pg17@{OTHER_DIGEST}"}},
    )
    assert cd.check(tmp_path) == []


def test_ac20_allowlist_key_with_tag_does_not_approve_the_name(tmp_path: Path) -> None:
    _stack(tmp_path, {f"{PG}:pg17": "approved"}, _one(PINNED_PG))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, PG)]


# approved, pending, unlisted


def test_ac20_unlisted_image_is_reported_by_name(tmp_path: Path) -> None:
    _stack(tmp_path, {}, _one(PINNED_PG))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, PG)]


def test_ac20_image_listed_under_another_name_is_unlisted(tmp_path: Path) -> None:
    _stack(tmp_path, {"versity/versitygw": "approved"}, _one(PINNED_PG))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, PG)]


def test_ac20_pending_image_is_reported_by_name(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "pending"}, _one(PINNED_PG))
    assert cd.check(tmp_path) == [_pending(COMPOSE, PG)]


def test_ac20_unpinned_approved_image_reports_only_the_pin_failure(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(f"{PG}:pg17"))
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, f"{PG}:pg17")]


@pytest.mark.parametrize("status", ["pending", None])
def test_ac20_unpinned_image_that_is_not_approved_still_reports_the_pin_failure(
    tmp_path: Path, status: str | None
) -> None:
    image = f"{PG}:pg17"
    _stack(tmp_path, {} if status is None else {PG: status}, _one(image))
    assert _pin_message(COMPOSE, image) in cd.check(tmp_path)


def test_ac20_container_allowlist_is_independent_of_package_sections(tmp_path: Path) -> None:
    _repo(tmp_path, _allowlist(py_runtime={PG: "approved"}, ts_runtime={PG: "approved"}))
    _write(tmp_path, COMPOSE, json.dumps({"services": _one(PINNED_PG)}))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, PG)]


def test_ac20_package_allowlist_is_independent_of_container_section(tmp_path: Path) -> None:
    _stack(tmp_path, {"fastapi": "approved"})
    _write(
        tmp_path, PYPROJECT, '[project]\nname = "x"\nversion = "0"\ndependencies = ["fastapi"]\n'
    )
    assert cd.check(tmp_path) == [_unlisted(PYPROJECT, "fastapi")]


# glob keys and exact-beats-glob


def test_ac20_container_glob_matches_names_in_its_namespace(tmp_path: Path) -> None:
    _stack(
        tmp_path,
        {"ghcr.io/org/*": "approved"},
        {
            "a": {"image": f"ghcr.io/org/one:1@{DIGEST}"},
            "b": {"image": f"ghcr.io/org/two@{OTHER_DIGEST}"},
        },
    )
    assert cd.check(tmp_path) == []


def test_ac20_container_glob_does_not_match_other_namespaces(tmp_path: Path) -> None:
    _stack(tmp_path, {"ghcr.io/org/*": "approved"}, _one(f"ghcr.io/other/one:1@{DIGEST}"))
    assert cd.check(tmp_path) == [_unlisted(COMPOSE, "ghcr.io/other/one")]


def test_ac20_pending_container_glob_is_reported(tmp_path: Path) -> None:
    _stack(tmp_path, {"ghcr.io/org/*": "pending"}, _one(f"ghcr.io/org/one:1@{DIGEST}"))
    assert cd.check(tmp_path) == [_pending(COMPOSE, "ghcr.io/org/one")]


def test_ac20_exact_pending_container_key_beats_approved_glob(tmp_path: Path) -> None:
    _stack(
        tmp_path,
        {"ghcr.io/org/*": "approved", "ghcr.io/org/bad": "pending"},
        {
            "bad": {"image": f"ghcr.io/org/bad:1@{DIGEST}"},
            "good": {"image": f"ghcr.io/org/good:1@{DIGEST}"},
        },
    )
    assert cd.check(tmp_path) == [_pending(COMPOSE, "ghcr.io/org/bad")]


def test_ac20_exact_approved_container_key_beats_pending_glob(tmp_path: Path) -> None:
    _stack(
        tmp_path,
        {"ghcr.io/org/*": "pending", "ghcr.io/org/good": "approved"},
        _one(f"ghcr.io/org/good:1@{DIGEST}"),
    )
    assert cd.check(tmp_path) == []


# build steps


def test_ac20_build_without_image_is_refused(tmp_path: Path) -> None:
    _stack(tmp_path, {}, {"api": {"build": "./api"}})
    assert cd.check(tmp_path) == [
        f"{COMPOSE}: service api builds an image; build steps are not allowed in compose files"
    ]


def test_ac20_build_mapping_without_image_is_refused(tmp_path: Path) -> None:
    _stack(tmp_path, {}, {"worker": {"build": {"context": ".", "dockerfile": "Dockerfile"}}})
    assert cd.check(tmp_path) == [
        f"{COMPOSE}: service worker builds an image; build steps are not allowed in compose files"
    ]


def test_ac20_build_without_image_is_refused_even_when_images_are_approved(
    tmp_path: Path,
) -> None:
    _stack(tmp_path, {PG: "approved"}, {"db": {"image": PINNED_PG}, "api": {"build": "."}})
    assert cd.check(tmp_path) == [
        f"{COMPOSE}: service api builds an image; build steps are not allowed in compose files"
    ]


def test_ac20_each_build_service_is_reported_in_order(tmp_path: Path) -> None:
    _stack(tmp_path, {}, {"zeta": {"build": "."}, "alpha": {"build": "."}})
    suffix = "builds an image; build steps are not allowed in compose files"
    assert cd.check(tmp_path) == [
        f"{COMPOSE}: service alpha {suffix}",
        f"{COMPOSE}: service zeta {suffix}",
    ]


def test_ac20_build_with_image_is_checked_as_an_image(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"}, {"db": {"image": PINNED_PG, "build": "."}})
    assert cd.check(tmp_path) == []


def test_ac20_build_with_unpinned_image_reports_the_pin_failure(tmp_path: Path) -> None:
    _stack(tmp_path, {PG: "approved"}, {"db": {"image": f"{PG}:pg17", "build": "."}})
    assert cd.check(tmp_path) == [_pin_message(COMPOSE, f"{PG}:pg17")]


# compose filenames and locations


@pytest.mark.parametrize("name", COMPOSE_NAMES)
def test_ac20_every_compose_filename_is_scanned(tmp_path: Path, name: str) -> None:
    _stack(tmp_path, {}, _one(PINNED_PG), rel=name)
    assert cd.check(tmp_path) == [_unlisted(name, PG)]


@pytest.mark.parametrize("name", COMPOSE_NAMES)
def test_ac20_approved_image_passes_in_every_compose_filename(tmp_path: Path, name: str) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(PINNED_PG), rel=name)
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize("name", COMPOSE_NAMES)
def test_ac20_unpinned_image_is_reported_in_every_compose_filename(
    tmp_path: Path, name: str
) -> None:
    _stack(tmp_path, {PG: "approved"}, _one(f"{PG}:pg17"), rel=name)
    assert cd.check(tmp_path) == [_pin_message(name, f"{PG}:pg17")]


@pytest.mark.parametrize("name", COMPOSE_NAMES)
def test_ac20_build_is_refused_in_every_compose_filename(tmp_path: Path, name: str) -> None:
    _stack(tmp_path, {}, {"api": {"build": "."}}, rel=name)
    assert cd.check(tmp_path) == [
        f"{name}: service api builds an image; build steps are not allowed in compose files"
    ]


@pytest.mark.parametrize(
    "rel",
    ["deploy/docker-compose.yml", "infra/local/compose.yaml", "a/b/c/docker-compose.yaml"],
)
def test_ac20_compose_files_in_subdirectories_are_scanned(tmp_path: Path, rel: str) -> None:
    _stack(tmp_path, {}, _one(PINNED_PG), rel=rel)
    assert cd.check(tmp_path) == [_unlisted(rel, PG)]


@pytest.mark.parametrize(
    "rel",
    [
        "docker-compose.override.yml",
        "docker-compose.dev.yaml",
        "compose.override.yml",
        "docker-compose.yml.bak",
        "mycompose.yml",
        "compose.json",
    ],
)
def test_ac20_other_filenames_are_not_compose_files(tmp_path: Path, rel: str) -> None:
    _stack(tmp_path, {}, _one(PINNED_PG), rel=rel)
    assert cd.check(tmp_path) == []


@pytest.mark.parametrize(
    "rel",
    [
        "node_modules/x/docker-compose.yml",
        "apps/web/node_modules/compose.yaml",
        "apps/web/dist/docker-compose.yaml",
        "dist/compose.yml",
        ".git/docker-compose.yml",
        ".venv/compose.yml",
        "apps/.cache/compose.yaml",
        ".github/docker-compose.yml",
    ],
)
def test_ac20_ignored_directories_hide_compose_files(tmp_path: Path, rel: str) -> None:
    _stack(tmp_path, {}, {"db": {"image": PG}, "api": {"build": "."}}, rel=rel)
    assert cd.check(tmp_path) == []


# ordering and combination


def test_ac20_container_messages_are_sorted_and_cover_every_compose_file(tmp_path: Path) -> None:
    _stack(
        tmp_path,
        {PG: "approved", "versity/versitygw": "pending"},
        {
            "zz": {"image": f"zzz/unlisted:1@{DIGEST}"},
            "mid": {"image": f"{PG}:pg17"},
            "s3": {"image": f"versity/versitygw:rel@{DIGEST}"},
            "api": {"build": "."},
        },
    )
    _write(
        tmp_path,
        "deploy/compose.yaml",
        json.dumps({"services": {"x": {"image": f"aaa/unlisted@{DIGEST}"}}}),
    )
    result = cd.check(tmp_path)
    assert result == sorted(result)
    assert result == sorted(
        [
            _unlisted("deploy/compose.yaml", "aaa/unlisted"),
            f"{COMPOSE}: service api {BUILD_REFUSED}",
            _pending(COMPOSE, "versity/versitygw"),
            _pin_message(COMPOSE, f"{PG}:pg17"),
            _unlisted(COMPOSE, "zzz/unlisted"),
        ]
    )


def test_ac20_container_and_package_messages_are_combined_and_sorted(tmp_path: Path) -> None:
    _stack(tmp_path, {}, _one(PINNED_PG))
    _write(tmp_path, PYPROJECT, '[project]\nname = "x"\nversion = "0"\ndependencies = ["zzz"]\n')
    result = cd.check(tmp_path)
    assert result == sorted(result)
    assert result == sorted([_unlisted(PYPROJECT, "zzz"), _unlisted(COMPOSE, PG)])


def test_ac20_same_image_in_two_services_is_reported_for_each_occurrence(
    tmp_path: Path,
) -> None:
    _stack(tmp_path, {}, {"a": {"image": PINNED_PG}, "b": {"image": PINNED_PG}})
    result = cd.check(tmp_path)
    assert result
    assert set(result) == {_unlisted(COMPOSE, PG)}
