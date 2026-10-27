"""Q-03-T026 (ADR-079; DEC-365; Q-03 C1): the mutation driver plans the nightly and weekly runs
over the red scopes, narrows mutmut's config on the runner, and publishes survivors per module."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from abacus_tools.quality import mutation
from abacus_tools.quality.mutation import (
    ScopeResult,
    changed_red_files,
    narrow,
    red_files,
    scope_of,
    shards,
    tally,
    under_floor,
    unmeasured,
)


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("src/abacus/modules/identity/authz/__init__.py", "identity/authz"),
        ("src/abacus/kernel/db/session.py", "kernel/db"),
        ("src/abacus/kernel/uow/__init__.py", "kernel/uow"),
        ("src/abacus/kernel/crypto/cursor.py", "kernel/crypto"),
        ("src/abacus/modules/evidence/citations/display.py", "evidence"),
        ("src/abacus/ai_gateway/gateway.py", "ai_gateway"),
        ("src/abacus/modules/audit_trail/service.py", "audit_trail"),
        ("src/abacus/modules/ledger/compute/tieout.py", "compute"),
        ("src/abacus/modules/identity/people.py", None),
        ("src/abacus/kernel/_flags.py", None),
        ("src/abacus/modules/identity/authz/_matrix.py", None),
        ("src/abacus/kernel/db/README.md", None),
    ],
)
def test_t026_scopes_are_the_red_modules_and_compute_packages(
    path: str, scope: str | None
) -> None:
    assert scope_of(path) == scope


def test_t026_the_committed_mutmut_config_names_every_scope() -> None:
    config = tomllib.loads(mutation.PYPROJECT.read_text(encoding="utf-8"))["tool"]["mutmut"]
    only = config["only_mutate"]
    for globs in mutation.SCOPES.values():
        for glob in globs:
            assert glob.removesuffix(".py") in only, glob
    assert config["pytest_add_cli_args_test_selection"] == [
        "tests/unit",
        "tests/property",
        "tests/acceptance",
    ]
    for generated in mutation.GENERATED:
        assert f"*/{generated}" in config["do_not_mutate"]


def test_t026_nightly_takes_only_red_files_that_still_exist(tmp_path: Path) -> None:
    for rel in ("src/abacus/kernel/db/a.py", "src/abacus/modules/identity/people.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x = 1\n")
    changed = [
        "backend/src/abacus/kernel/db/a.py",
        "backend/src/abacus/kernel/db/a.py",
        "backend/src/abacus/kernel/db/deleted.py",
        "backend/src/abacus/modules/identity/people.py",
        "apps/web/src/main.ts",
    ]
    assert changed_red_files(changed, tmp_path) == ["src/abacus/kernel/db/a.py"]


def test_t026_weekly_shards_cover_every_red_file_once_and_balance_lines() -> None:
    files = red_files()
    assert files, "the red scopes are not empty"
    weight = {f: (mutation.BACKEND / f).read_text(encoding="utf-8").count("\n") for f in files}
    parts = shards(files, mutation.WEEKLY_SHARDS, weight)
    flat = [f for part in parts for f in part]
    assert sorted(flat) == files and len(flat) == len(set(flat))
    loads = [sum(weight[f] for f in part) for part in parts]
    # Greedy balance: no shard carries more than the lightest plus the largest single file.
    assert max(loads) - min(loads) <= max(weight.values())


def test_t026_shards_need_at_least_one() -> None:
    with pytest.raises(ValueError):
        shards(["a.py"], 0, {})


def test_t026_narrow_replaces_only_the_only_mutate_list() -> None:
    text = mutation.PYPROJECT.read_text(encoding="utf-8")
    narrowed = narrow(text, ["src/abacus/kernel/db/session.py"])
    config = tomllib.loads(narrowed)
    assert config["tool"]["mutmut"]["only_mutate"] == ["src/abacus/kernel/db/session.py"]
    original = tomllib.loads(text)
    assert config["project"] == original["project"]
    assert {k: v for k, v in config["tool"]["mutmut"].items() if k != "only_mutate"} == {
        k: v for k, v in original["tool"]["mutmut"].items() if k != "only_mutate"
    }


def test_t026_prepare_links_the_repository_entries_into_backend(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    (backend / "src").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "AGENTS.md").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()  # backend already has one: left alone
    assert mutation.prepare(backend) == ["AGENTS.md", "docs"]
    assert (backend / "docs").resolve() == (tmp_path / "docs").resolve()
    assert not (backend / ".git").exists()


def _meta(codes: dict[str, int | None]) -> dict[str, object]:
    return {"exit_code_by_key": codes, "durations_by_key": {}}


@pytest.mark.source_scan
def test_t026_survivors_are_published_per_module(tmp_path: Path) -> None:
    mutants = tmp_path / "mutants"
    metas = {
        "src/abacus/kernel/db/session.py": _meta(
            {"a__mutmut_1": 1, "a__mutmut_2": 0, "a__mutmut_3": 36, "a__mutmut_4": None}
        ),
        "src/abacus/modules/evidence/viewer.py": _meta({"v__mutmut_1": 33, "v__mutmut_2": 3}),
        "src/abacus/modules/identity/people.py": _meta({"p__mutmut_1": 0}),
    }
    for source, meta in metas.items():
        path = mutants / f"{source}.meta"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta))
    results = tally(mutation.read_metas(mutants))
    assert set(results) == {"kernel/db", "evidence"}
    db = results["kernel/db"]
    assert (db.killed, db.timeout, db.survived, db.not_run) == (1, 1, 1, 1)
    assert db.survivors == ["a__mutmut_2"] and db.score == pytest.approx(66.7)
    assert results["evidence"].survivors == ["v__mutmut_1"]
    report = mutation.markdown(results, {"kernel/db": 0}, "Nightly")
    assert "| kernel/db | 66.7% | 0% | 1 | 1 | 1 | 0 | 1 |" in report
    assert "`a__mutmut_2`" in report

    out_json, out_md = tmp_path / "s.json", tmp_path / "s.md"
    code = mutation.main(
        [
            "summarise",
            "--mutants",
            str(mutants),
            "--json",
            str(out_json),
            "--markdown",
            str(out_md),
        ]
    )
    assert code == 0  # publishing alone never fails
    assert json.loads(out_json.read_text())["kernel/db"]["survivors"] == ["a__mutmut_2"]


def test_t026_a_scope_under_its_floor_fails_the_weekly_run() -> None:
    results = {"evidence": ScopeResult(killed=7, survived=3), "kernel/db": ScopeResult()}
    assert under_floor(results, {"evidence": 75, "kernel/db": 90}) == [
        "evidence: 70.0% is under its floor of 75%"
    ]
    assert under_floor(results, {"evidence": 70}) == []


def test_t026_a_floored_scope_with_no_results_fails_the_weekly_run() -> None:
    files = ["src/abacus/kernel/db/session.py", "src/abacus/modules/evidence/viewer.py"]
    results = {"kernel/db": ScopeResult(killed=3)}
    # evidence has files but no mutant ran (excluded through do_not_mutate, say): it fails.
    assert unmeasured(results, {"kernel/db": 0, "evidence": 0}, files) == [
        "evidence: no mutant ran (floor 0%); the scope went unmeasured"
    ]
    # compute has no package yet: nothing to measure, nothing fails, unless it carries a floor.
    assert unmeasured(results, {"compute": 0}, files) == []
    assert unmeasured(results, {"compute": 50}, files) == [
        "compute: no mutant ran (floor 50%); the scope went unmeasured"
    ]
    # A floor for a scope SCOPES no longer names fails too.
    assert unmeasured(results, {"retired": 0}, files) == [
        "retired: has a floor but is not a mutation scope (SCOPES)"
    ]


@pytest.mark.source_scan
def test_t026_the_weekly_floors_check_fails_on_an_unmeasured_red_scope(tmp_path: Path) -> None:
    mutants = tmp_path / "mutants"
    meta = mutants / "src/abacus/kernel/db/session.py.meta"
    meta.parent.mkdir(parents=True)
    meta.write_text(json.dumps(_meta({"a__mutmut_1": 1})))
    common = ["summarise", "--mutants", str(mutants), "--json", str(tmp_path / "s.json")]
    common += ["--markdown", str(tmp_path / "s.md")]
    assert mutation.main(common) == 0
    assert mutation.main([*common, "--enforce-floors"]) == 1  # identity/authz and others ran none
