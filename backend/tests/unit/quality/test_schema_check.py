"""AC-20: schema_check passes only while there are no migrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import schema_check as sc

REPO = Path(__file__).resolve().parents[4]

MESSAGE = (
    "schema_check is not implemented: SPEC-000 must add the tenant and row-level security "
    "schema check with its first migration"
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def test_ac20_nested_migration_fails(tmp_path: Path) -> None:
    nested = tmp_path / "branch" / "deeper"
    nested.mkdir(parents=True)
    (nested / "0001_initial.py").write_text("x = 1\n", encoding="utf-8")
    assert sc.check(tmp_path) == [MESSAGE]


def test_ac20_nested_init_only_passes(tmp_path: Path) -> None:
    nested = tmp_path / "branch"
    nested.mkdir()
    (nested / "__init__.py").write_text("", encoding="utf-8")
    assert sc.check(tmp_path) == []


def test_ac20_migrations_path_is_backend_migrations_versions() -> None:
    assert sc.MIGRATIONS == REPO / "backend" / "migrations" / "versions"


def test_ac20_orm_empty_backend_passes(tmp_path: Path) -> None:
    assert sc.check_orm(tmp_path) == []


def test_ac20_orm_unrelated_sources_pass(tmp_path: Path) -> None:
    for rel in (
        "src/abacus/modules/ledger/service.py",
        "src/abacus_tools/models.py",
        "tests/models.py",
        "src/abacus/modules/ledger/models_helpers.py",
    ):
        _write(tmp_path, rel, "x = 1\n")
    assert sc.check_orm(tmp_path) == []


@pytest.mark.parametrize(
    "rel",
    [
        "alembic.ini",
        "src/abacus/modules/ledger/models.py",
        "src/abacus/kernel/models.py",
        "src/abacus/modules/ledger/models/__init__.py",
        "src/abacus/modules/ledger/adapters/models/user.py",
    ],
)
def test_ac20_orm_models_or_alembic_fail_with_the_contract_message(
    tmp_path: Path, rel: str
) -> None:
    _write(tmp_path, rel, "x = 1\n")
    assert sc.check_orm(tmp_path) == [MESSAGE]


def test_ac20_orm_models_directory_alone_fails(tmp_path: Path) -> None:
    (tmp_path / "src" / "abacus" / "modules" / "ledger" / "models").mkdir(parents=True)
    assert sc.check_orm(tmp_path) == [MESSAGE]


def test_ac20_main_reports_the_union_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_check(_migrations: Path) -> list[str]:
        return [MESSAGE]

    def fake_orm(_backend: Path) -> list[str]:
        return [MESSAGE]

    monkeypatch.setattr(sc, "check", fake_check)
    monkeypatch.setattr(sc, "check_orm", fake_orm)
    assert sc.main() == 1
    assert capsys.readouterr().out == MESSAGE + "\n"


def test_ac20_main_fails_when_only_the_orm_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty: list[str] = []

    def fake_check(_migrations: Path) -> list[str]:
        return empty

    def fake_orm(_backend: Path) -> list[str]:
        return [MESSAGE]

    monkeypatch.setattr(sc, "check", fake_check)
    monkeypatch.setattr(sc, "check_orm", fake_orm)
    assert sc.main() == 1
    assert capsys.readouterr().out == MESSAGE + "\n"


def test_ac20_main_exits_1_and_prints_the_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:

    def fake_check(_migrations: Path) -> list[str]:
        return [MESSAGE]

    def fake_orm(_backend: Path) -> list[str]:
        return []

    monkeypatch.setattr(sc, "check", fake_check)
    monkeypatch.setattr(sc, "check_orm", fake_orm)
    assert sc.main() == 1
    assert capsys.readouterr().out == MESSAGE + "\n"


def test_ac20_main_exits_0_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    empty: list[str] = []

    def fake_check(_migrations: Path) -> list[str]:
        return empty

    def fake_orm(_backend: Path) -> list[str]:
        return empty

    monkeypatch.setattr(sc, "check", fake_check)
    monkeypatch.setattr(sc, "check_orm", fake_orm)
    assert sc.main() == 0
