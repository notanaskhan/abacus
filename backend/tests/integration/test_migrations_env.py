"""AC-20: Alembic environment behaviour (TASK-005 Design section 4 and contract revision 1).

Each test provisions its own database (compose image, `bootstrap.sql` applied, at head) and
writes temporary revisions after head into a version location of its own (`tmp_path`), which
Alembic reads beside `backend/migrations/versions/`. Never into the real directory: a migration
to head running at the same time (another pytest-xdist worker's `migrated_db`, `check-heads`)
would pick them up (DEC-335).
"""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError

from abacus_tools.quality.schema_check import provisioned_database

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "migrations" / "versions"


def _config(x: list[str] | None = None, extra: Path | None = None) -> Config:
    config = Config(
        str(BACKEND / "alembic.ini"),
        cmd_opts=argparse.Namespace(x=x) if x is not None else None,
    )
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    if extra is not None:  # alembic.ini's path_separator is `os`
        config.set_main_option("version_locations", os.pathsep.join([str(VERSIONS), str(extra)]))
    return config


def _migrate(owner_url: str, revision: str, extra: Path) -> None:
    """`schema_check.migrate` (the same `-x url` upgrade), with `extra` as a version location."""
    command.upgrade(_config([f"url={owner_url}"], extra), revision)


def _head() -> str:
    head = ScriptDirectory.from_config(_config()).get_current_head()
    assert head is not None
    return head


def _revision(rev: str, down: str, upgrade_sql: list[str]) -> str:
    lines = [
        '"""temporary test revision"""',
        "from alembic import op",
        "",
        f'revision = "{rev}"',
        f'down_revision = "{down}"',
        "branch_labels = None",
        "depends_on = None",
        "",
        "",
        "def upgrade() -> None:",
        *[f"    op.execute({sql!r})" for sql in upgrade_sql],
        "    pass",
        "",
        "",
        "def downgrade() -> None:",
        "    pass",
        "",
    ]
    return "\n".join(lines)


@contextmanager
def _temporary_revisions(
    directory: Path, *revisions: tuple[str, list[str]]
) -> Generator[list[str]]:
    """Write a linear chain of revisions after head into `directory`; remove them afterwards."""
    written: list[Path] = []
    ids: list[str] = []
    try:
        down = _head()
        for rev, sql in revisions:
            path = directory / f"{rev}.py"
            source = _revision(rev, down, sql)
            compile(source, str(path), "exec")
            upgrade_body = source.split("def upgrade()")[1].split("def downgrade()")[0]
            assert all(f"op.execute({statement!r})" in upgrade_body for statement in sql)
            path.write_text(source, encoding="utf-8")
            written.append(path)
            ids.append(rev)
            down = rev
        yield ids
    finally:
        for path in written:
            path.unlink(missing_ok=True)
            for pyc in (directory / "__pycache__").glob(f"{path.stem}.*"):
                pyc.unlink(missing_ok=True)


async def _fetch(dsn: str, sql: str) -> list[tuple[object, ...]]:
    conn = await asyncpg.connect(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        return [tuple(row) for row in await conn.fetch(sql)]
    finally:
        await conn.close()


def _rows(dsn: str, sql: str) -> list[tuple[object, ...]]:
    return asyncio.run(_fetch(dsn, sql))


def test_ac20_each_migration_runs_in_its_own_transaction(tmp_path: Path) -> None:
    with (
        provisioned_database(roundtrip=False) as database,
        _temporary_revisions(
            tmp_path,
            ("tmp_env_a", ["CREATE TABLE tmp_env_a (id int)"]),
            ("tmp_env_b", ["CREATE TABLE tmp_env_b (id int)", "SELECT 1/0"]),
        ),
    ):
        with pytest.raises(DBAPIError):
            _migrate(database.owner_url, "tmp_env_b", tmp_path)
        assert _rows(database.owner_url, "SELECT version_num FROM alembic_version") == [
            ("tmp_env_a",)
        ]
        tables = _rows(
            database.owner_url,
            "SELECT tablename FROM pg_tables WHERE tablename LIKE 'tmp_env_%' ORDER BY 1",
        )
        assert tables == [("tmp_env_a",)]


def test_ac20_timeouts_are_set_inside_a_migration(tmp_path: Path) -> None:
    capture = (
        "CREATE TABLE tmp_env_timeouts AS SELECT current_setting('lock_timeout') AS lt, "
        "current_setting('statement_timeout') AS st"
    )
    with (
        provisioned_database(roundtrip=False) as database,
        _temporary_revisions(tmp_path, ("tmp_env_timeouts", [capture])),
    ):
        _migrate(database.owner_url, "tmp_env_timeouts", tmp_path)
        assert _rows(database.owner_url, "SELECT lt, st FROM tmp_env_timeouts") == [("5s", "1min")]


def test_ac20_migrations_connect_as_abacus_owner(tmp_path: Path) -> None:
    capture = "CREATE TABLE tmp_env_who AS SELECT current_user::text AS u"
    with (
        provisioned_database(roundtrip=False) as database,
        _temporary_revisions(tmp_path, ("tmp_env_who", [capture])),
    ):
        _migrate(database.owner_url, "tmp_env_who", tmp_path)
        assert _rows(database.owner_url, "SELECT u FROM tmp_env_who") == [("abacus_owner",)]


def test_ac20_x_url_argument_is_honoured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with (
        provisioned_database(roundtrip=False) as database,
        _temporary_revisions(tmp_path, ("tmp_env_x", ["CREATE TABLE tmp_env_x (id int)"])),
    ):
        unreachable = "postgresql+asyncpg://nobody@127.0.0.1:1/nowhere"
        monkeypatch.setenv("ABACUS_MIGRATIONS_DATABASE_URL", unreachable)
        command.upgrade(_config([f"url={database.owner_url}"], tmp_path), "tmp_env_x")
        tables = _rows(
            database.owner_url, "SELECT tablename FROM pg_tables WHERE tablename = 'tmp_env_x'"
        )
        assert tables == [("tmp_env_x",)]


def test_ac20_offline_mode_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [k for k in os.environ if k.startswith("ABACUS_")]:
        monkeypatch.delenv(key)
    with pytest.raises(RuntimeError):
        command.upgrade(_config(), "head", sql=True)
