"""CI path filters: a skipped suite is provably irrelevant to the change (F-01-T07)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from abacus_tools.ci import paths

ALL = {"backend": True, "frontend": True, "gallery": True, "agents": True}


@pytest.mark.parametrize(
    ("changed", "backend", "frontend", "gallery", "agents"),
    [
        (["apps/web/src/screens/Board.tsx"], False, True, False, False),
        (["packages/ui/src/Button.tsx", "apps/web/src/router.tsx"], False, True, True, False),
        (
            ["docs/adr/ADR-131-workpapers.md", "work/tasks/TASK-079-x.md"],
            False,
            False,
            False,
            False,
        ),
        (["backend/src/abacus/modules/ledger/README.md"], False, False, False, False),
        (["apps/web/src/x.tsx", "docs/specs/SPEC-037-x.md"], False, True, False, False),
        (["backend/src/abacus/kernel/uow.py"], True, False, False, False),
        (["backend/src/abacus/modules/agents/service.py"], True, False, False, True),
        (["evals/screener/suite.yaml"], True, False, False, True),
        (["backend/src/abacus/ai_gateway/call.py"], True, False, False, True),
        (["packages/api-client/openapi.json"], True, True, False, False),
        (["docs/architecture/permission-matrix/requests.yaml"], True, False, False, False),
        (["docs/product/failure-taxonomy.md"], True, False, False, False),
        (["Makefile"], True, False, False, False),
        ([".github/workflows/ci.yml"], True, False, False, False),
        (["pnpm-lock.yaml"], True, True, True, False),
        ([], False, False, False, False),
        # The gallery's visual run (F-05-T17): library, gallery, harness and manifest.
        (["apps/web/src/gallery/pages.tsx"], False, True, True, False),
        (["apps/web/e2e/visual/parity.spec.ts"], False, True, True, False),
        (["apps/web/playwright.config.ts"], False, True, True, False),
        (["docs/design/parity-manifest.json"], True, False, True, False),
        (["backend/src/abacus_tools/parity/crop_handoff.py"], True, False, True, False),
    ],
)
def test_changes_are_classified(
    changed: list[str], backend: bool, frontend: bool, gallery: bool, agents: bool
) -> None:
    assert paths.classify(changed) == {
        "backend": backend,
        "frontend": frontend,
        "gallery": gallery,
        "agents": agents,
    }


def test_unknown_changes_run_everything() -> None:
    assert paths.classify(None) == ALL


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        # F-04-T28: the pull request's fixture journeys run when what they walk changes.
        (["apps/web/src/screens/CLI-01/index.tsx"], True),
        (["apps/web/src/fixtures/seed/clients.ts"], True),
        (["apps/web/e2e/journeys/J02-client-onboarding.spec.ts"], True),
        (["apps/web/e2e/harness/adapters.ts"], True),
        (["apps/web/portal.html"], True),
        (["packages/ui/src/Button.tsx"], True),
        (["pnpm-lock.yaml"], True),
        (["backend/src/abacus/kernel/uow.py"], False),
        (["apps/web/e2e/visual/parity.spec.ts"], False),
        (["docs/adr/ADR-131-workpapers.md", ".github/workflows/e2e.yml"], False),
        ([], False),
        (None, True),
    ],
)
def test_t28_fixture_journeys_run_when_what_they_walk_changes(
    changed: list[str] | None, expected: bool
) -> None:
    assert paths.journeys(changed) is expected


@pytest.mark.parametrize("base", ["", "0" * 40])
def test_a_missing_base_is_unknown(base: str) -> None:
    assert paths.changed(base, "HEAD") is None


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    out = subprocess.run([git, *args], cwd=repo, capture_output=True, text=True, check=True)
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("x\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_diff_lists_the_changed_paths(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "apps" / "web").mkdir(parents=True)
    (repo / "apps" / "web" / "a.tsx").write_text("x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "change")
    assert paths.changed(base, "HEAD") == ["apps/web/a.tsx"]


def test_a_base_git_does_not_know_is_unknown(repo: Path) -> None:
    assert paths.changed("f" * 40, "HEAD") is None


def test_main_prints_github_outputs(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert paths.main(["", "HEAD"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "backend=true",
        "frontend=true",
        "gallery=true",
        "agents=true",
        "journeys=true",
    ]


def test_main_needs_two_arguments() -> None:
    assert paths.main(["HEAD"]) == 2
