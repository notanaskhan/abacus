"""AC-20: schema_check passes only while there are no migrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import schema_check as sc

MESSAGE = (
    "schema_check is not implemented: SPEC-000 must add the tenant and row-level security "
    "schema check with its first migration"
)


def test_ac20_missing_directory_passes(tmp_path: Path) -> None:
    assert sc.check(tmp_path / "migrations" / "versions") == []


def test_ac20_empty_directory_passes(tmp_path: Path) -> None:
    assert sc.check(tmp_path) == []


def test_ac20_only_init_passes(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    assert sc.check(tmp_path) == []


def test_ac20_non_python_files_are_not_migrations(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("notes\n", encoding="utf-8")
    assert sc.check(tmp_path) == []


@pytest.mark.parametrize("with_init", [True, False])
def test_ac20_a_migration_fails_with_the_contract_message(tmp_path: Path, with_init: bool) -> None:
    if with_init:
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "0001_initial.py").write_text("revision = '0001'\n", encoding="utf-8")
    assert sc.check(tmp_path) == [MESSAGE]


def test_ac20_several_migrations_yield_one_message(tmp_path: Path) -> None:
    for name in ("0001_a.py", "0002_b.py", "0003_c.py"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    assert sc.check(tmp_path) == [MESSAGE]


def test_ac20_main_exits_1_and_prints_the_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:

    def fake_check(_migrations: Path) -> list[str]:
        return [MESSAGE]

    monkeypatch.setattr(sc, "check", fake_check)
    assert sc.main() == 1
    assert capsys.readouterr().out == MESSAGE + "\n"


def test_ac20_main_exits_0_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    empty: list[str] = []

    def fake_check(_migrations: Path) -> list[str]:
        return empty

    monkeypatch.setattr(sc, "check", fake_check)
    assert sc.main() == 0
