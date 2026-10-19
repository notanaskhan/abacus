"""Local database targets refuse hosted databases (F-01-T09)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from abacus.kernel.config import settings
from abacus_tools.local import db_guard


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@127.0.0.1:55432/abacus",
        "postgresql+asyncpg://u:p@localhost/abacus",
        "postgresql://u:p@[::1]:5432/abacus",
        "postgresql+asyncpg://u:p@db:5432/abacus",
        "postgresql+asyncpg://u:p@LOCALHOST/abacus",
    ],
)
def test_a_local_url_is_not_hosted(url: str) -> None:
    assert not db_guard.hosted(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@abacus.cluster-x.us-east-2.rds.amazonaws.com:5432/abacus",
        "postgresql+asyncpg://u:p@10.0.0.5/abacus",
        "postgresql+asyncpg://u:p@localhost.evil.example/abacus",
        "postgresql+asyncpg:///abacus",
        "postgresql://u:p@[not-an-ip/abacus",
    ],
)
def test_anything_else_counts_as_hosted(url: str) -> None:
    assert db_guard.hosted(url)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    settings.cache_clear()
    yield monkeypatch
    settings.cache_clear()


def test_the_local_defaults_pass(
    env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert db_guard.main() == 0
    assert capsys.readouterr().err == ""


def test_a_hosted_url_is_refused_by_name_never_by_value(
    env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env.setenv(
        "ABACUS_MIGRATIONS_DATABASE_URL",
        "postgresql+asyncpg://owner:s3cret@prod.example.com:5432/abacus",
    )
    assert db_guard.main() == 1
    err = capsys.readouterr().err
    assert "ABACUS_MIGRATIONS_DATABASE_URL: never point a local run at a hosted database" in err
    assert "s3cret" not in err
    assert "prod.example.com" not in err
