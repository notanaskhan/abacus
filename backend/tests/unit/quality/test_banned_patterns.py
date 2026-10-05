"""AC-20: the banned-pattern gate flags each violation and passes clean code."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

SERVICE = "src/abacus/modules/ledger/service.py"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rule_ids(root: Path) -> list[str]:
    return [v.rule_id for v in bp.scan(root)]


# (rule id, file, violating source, clean source)
CASES: list[tuple[str, str, str, str]] = [
    (
        "UOW-001",
        SERVICE,
        "def f(session):\n    session.commit()\n",
        "def f(tx):\n    tx.commit()\n",
    ),
    (
        "UOW-001",
        SERVICE,
        "def f(self):\n    self.db_session.flush()\n",
        "def f(self):\n    self.cache.flush()\n",
    ),
    (
        "DB-001",
        SERVICE,
        'from sqlalchemy import create_engine\ncreate_engine("postgresql://")\n',
        "from abacus.kernel.db import tenant_session\n",
    ),
    (
        "DB-001",
        SERVICE,
        'import asyncpg\nasyncpg.connect("postgresql://")\n',
        "import asyncpg\n",
    ),
    (
        "SQL-001",
        SERVICE,
        'def f(text, q):\n    text(f"select {q}")\n',
        'def f(text):\n    text("select * from t where id = :id")\n',
    ),
    (
        "SQL-001",
        SERVICE,
        'def f(s, q):\n    s.execute("select " + q)\n',
        'def f(s, stmt):\n    s.execute(stmt, {"id": 1})\n',
    ),
    (
        "SQL-001",
        SERVICE,
        'def f(text, q):\n    text("select %s" % q)\n',
        'def f(text):\n    text("select 1")\n',
    ),
    (
        "SQL-001",
        SERVICE,
        'def f(text, q):\n    text("select {}".format(q))\n',
        'def f(text):\n    text("select 2")\n',
    ),
    (
        "BOUND-001",
        SERVICE,
        "from abacus.modules.evidence.repository import EvidenceRepository\n",
        "from abacus.modules.evidence.api import add_version\n",
    ),
    (
        "BOUND-001",
        SERVICE,
        "from abacus.modules.evidence import service\n",
        "from abacus.modules.evidence import api\n",
    ),
    (
        "BOUND-001",
        SERVICE,
        "import abacus.modules.evidence.models\n",
        "import abacus.modules.evidence.api\n",
    ),
    (
        "BOUND-001",
        SERVICE,
        "from ..evidence import service\n",
        "from . import repository\n",
    ),
    (
        "BOUND-001",
        SERVICE,
        "from abacus.modules.evidence import EvidenceItem\n",
        "from abacus.modules.ledger.repository import LedgerRepository\n",
    ),
    (
        "TYPE-001",
        SERVICE,
        "x = 1  # type: ignore[misc]\n",
        "x = 1  # type: ignore[misc]  # stub missing upstream\n",
    ),
    (
        "TYPE-001",
        SERVICE,
        "x = 1  # pyright: ignore[reportUnknownVariableType]\n",
        "x = 1  # pyright: ignore[reportUnknownVariableType] -- untyped vendor SDK\n",
    ),
    (
        "ANY-001",
        SERVICE,
        "from typing import Any\nx: Any = 1\n",
        "from typing import Any\nx: Any = 1  # vendor JSON, shape unknown\n",
    ),
    (
        "ANY-001",
        SERVICE,
        "import typing\ndef f(a: typing.Any) -> None: ...\n",
        "import typing\ndef f(a: typing.Any) -> None: ...  # plugin hook receives anything\n",
    ),
]
CASE_IDS = [f"{rule}-{n}" for n, (rule, *_rest) in enumerate(CASES)]


@pytest.mark.parametrize(("rule_id", "rel", "bad", "_clean"), CASES, ids=CASE_IDS)
def test_ac20_rule_flags_violation(
    tmp_path: Path, rule_id: str, rel: str, bad: str, _clean: str
) -> None:
    _write(tmp_path, rel, bad)
    assert rule_id in _rule_ids(tmp_path)


@pytest.mark.parametrize(("rule_id", "rel", "_bad", "clean"), CASES, ids=CASE_IDS)
def test_ac20_rule_allows_clean_code(
    tmp_path: Path, rule_id: str, rel: str, _bad: str, clean: str
) -> None:
    _write(tmp_path, rel, clean)
    assert _rule_ids(tmp_path) == []


def test_ac20_layout_flags_unknown_top_level_entry(tmp_path: Path) -> None:
    (tmp_path / "src" / "platform").mkdir(parents=True)
    violations = bp.scan(tmp_path)
    assert [(v.rule_id, v.path) for v in violations] == [("LAYOUT-001", "src/platform")]


def test_ac20_layout_allows_namespaced_roots(tmp_path: Path) -> None:
    for name in ("abacus", "abacus_tools", "__pycache__", "abacus_backend.egg-info"):
        (tmp_path / "src" / name).mkdir(parents=True)
    assert _rule_ids(tmp_path) == []


@pytest.mark.parametrize(
    ("rel", "source"),
    [
        ("src/abacus/kernel/uow/core.py", "def f(session):\n    session.commit()\n"),
        (
            "src/abacus/kernel/db/engine.py",
            'from sqlalchemy import create_engine\ncreate_engine("x")\n',
        ),
        ("tests/unit/ledger/test_repo.py", "from abacus.modules.ledger.repository import Repo\n"),
    ],
)
def test_ac20_exclude_globs_exempt_only_their_paths(tmp_path: Path, rel: str, source: str) -> None:
    _write(tmp_path, rel, source)
    assert _rule_ids(tmp_path) == []


def test_ac20_exclude_glob_does_not_leak_to_sibling_package(tmp_path: Path) -> None:
    _write(
        tmp_path, "src/abacus/kernel/outbox/relay.py", "def f(session):\n    session.commit()\n"
    )
    assert _rule_ids(tmp_path) == ["UOW-001"]


def test_ac20_unparseable_file_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "def f(:\n")
    assert _rule_ids(tmp_path) == ["PARSE-001"]


def test_ac20_violation_output_names_path_line_rule_and_adr(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "\ndef f(session):\n    session.rollback()\n")
    [violation] = bp.scan(tmp_path)
    assert str(violation) == (
        f"{SERVICE}:3: UOW-001 session.rollback() outside the unit of work (ADR-007, ADR-018)"
    )


def test_ac20_main_exits_1_on_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    found = [bp.Violation(SERVICE, 1, "UOW-001", "message", "ADR-007")]
    monkeypatch.setattr(bp, "scan", lambda: found)
    assert bp.main() == 1


def test_ac20_repository_backend_is_clean() -> None:
    assert bp.scan() == []
