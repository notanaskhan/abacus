"""Each worktree gets its own compose project and ports (F-01-T09)."""

from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus_tools.local import worktree_env


def _with_offset(tmp_path: Path, name: str, offset: int) -> Path:
    tree = tmp_path / name
    tree.mkdir()
    (tree / worktree_env.FILE).write_text(worktree_env.contents(f"abacus-{name}", offset))
    return tree


def test_the_primary_checkout_keeps_its_project_and_ports(tmp_path: Path) -> None:
    assert worktree_env.plan(tmp_path, True, []) == (
        "COMPOSE_PROJECT_NAME=abacus\nABACUS_PORT_OFFSET=0\n"
    )


def test_a_worktree_takes_the_next_free_slot(tmp_path: Path) -> None:
    taken = [_with_offset(tmp_path, "one", 10), _with_offset(tmp_path, "three", 30)]
    mine = tmp_path / "AY Eng 01"
    mine.mkdir()
    assert worktree_env.plan(mine, False, [*taken, mine]) == (
        "COMPOSE_PROJECT_NAME=abacus-ay-eng-01\nABACUS_PORT_OFFSET=20\n"
    )


def test_its_own_old_file_does_not_count_as_taken(tmp_path: Path) -> None:
    mine = _with_offset(tmp_path, "mine", 10)
    assert worktree_env.plan(mine, False, [mine]).endswith("ABACUS_PORT_OFFSET=10\n")


def test_every_slot_taken_is_refused() -> None:
    with pytest.raises(RuntimeError, match="every port slot"):
        worktree_env.next_offset(set(range(10, 100, 10)))


@pytest.mark.parametrize(("raw", "offset"), [("", 0), ("0", 0), ("10", 10), ("90", 90)])
def test_the_offset_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, raw: str, offset: int
) -> None:
    monkeypatch.setenv("ABACUS_PORT_OFFSET", raw)
    assert worktree_env.port_offset() == offset


@pytest.mark.parametrize("raw", ["5", "100", "-10", "ten"])
def test_a_bad_offset_is_refused(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("ABACUS_PORT_OFFSET", raw)
    with pytest.raises(ValueError, match="ABACUS_PORT_OFFSET"):
        worktree_env.port_offset()


def test_settings_ignore_the_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_PORT_OFFSET", "10")
    monkeypatch.setenv("ABACUS_DB_PORT", "55442")
    settings.cache_clear()
    try:
        assert settings().environment == "local"
    finally:
        settings.cache_clear()


def test_the_sign_in_fake_serves_and_accepts_only_its_own_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus_tools.fakes import oidc_server

    monkeypatch.setenv("ABACUS_PORT_OFFSET", "10")
    try:
        offset = importlib.reload(oidc_server)
        assert offset.PORT == 9010
        assert {
            "http://localhost:5183/signin/callback",
            "http://127.0.0.1:5183/signin/callback",
            # P-01-T09: the staff session BFF's callback, on the same SPA origins.
            "http://localhost:5183/v1/auth/callback",
            "http://127.0.0.1:5183/v1/auth/callback",
        } == offset.REDIRECT_URIS
    finally:
        monkeypatch.delenv("ABACUS_PORT_OFFSET")
        importlib.reload(oidc_server)


def test_main_writes_the_primary_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    assert worktree_env.main() == 0
    written = (tmp_path / worktree_env.FILE).read_text()
    assert written == "COMPOSE_PROJECT_NAME=abacus\nABACUS_PORT_OFFSET=0\n"
    (tmp_path / worktree_env.FILE).write_text("COMPOSE_PROJECT_NAME=kept\nABACUS_PORT_OFFSET=40\n")
    assert worktree_env.main() == 0
    assert "kept" in (tmp_path / worktree_env.FILE).read_text()
