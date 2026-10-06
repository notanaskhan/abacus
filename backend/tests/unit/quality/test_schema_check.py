"""AC-20: the schema_check contract that needs no database.

The real checks run against Postgres in `tests/integration/test_schema_check_db.py`.
"""

from __future__ import annotations

import inspect

from abacus_tools.quality import schema_check as sc


def test_ac20_check_takes_owner_and_app_dsns_and_returns_a_list() -> None:
    params = list(inspect.signature(sc.check).parameters)
    assert params == ["dsn_owner", "dsn_app"]


def test_ac20_main_takes_no_arguments() -> None:
    assert list(inspect.signature(sc.main).parameters) == []


def test_ac20_the_orm_stop_gap_is_gone() -> None:
    assert not hasattr(sc, "check_orm")


def test_ac20_the_no_migrations_guard_is_gone() -> None:
    assert not hasattr(sc, "MESSAGE")
    assert "not implemented" not in inspect.getsource(sc)
