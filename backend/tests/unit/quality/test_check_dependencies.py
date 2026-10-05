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
    packages: dict[str, dict[str, dict[str, str]]] | None = None,
) -> Path:
    """A minimal repo; JSON is valid YAML and its string arrays are valid TOML."""
    _write(root, "docs/architecture/dependency-allowlist.yaml", json.dumps(allow, indent=2))
    toml = '[project]\nname = "x"\nversion = "0"\n'
    toml += "dependencies = " + json.dumps(runtime or []) + "\n"
    toml += "\n[dependency-groups]\ndev = " + json.dumps(dev or []) + "\n"
    _write(root, PYPROJECT, toml)
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
    _repo(tmp_path, _allowlist(), packages={WEB: {"dependencies": {"@abacus/client": version}}})
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
