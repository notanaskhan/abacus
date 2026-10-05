"""AC-20: the banned-pattern gate flags each violation and passes clean code."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

SERVICE = "src/abacus/modules/ledger/service.py"
LEDGER_INIT = "src/abacus/modules/ledger/__init__.py"
NESTED = "src/abacus/modules/ledger/adapters/sql.py"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rule_ids(root: Path) -> list[str]:
    return [v.rule_id for v in bp.scan(root)]


# (rule id, file, violating source, clean source). Each violating source yields exactly one
# finding; each clean source yields none.
CASES: list[tuple[str, str, str, str]] = [
    # UOW-001
    (
        "UOW-001",
        SERVICE,
        "def f(session):\n    session.commit()\n",
        "def f(uow, ctx, event):\n    with uow(ctx) as tx:\n        tx.record(event)\n",
    ),
    (
        "UOW-001",
        SERVICE,
        "def f(self):\n    self.db_session.flush()\n",
        "def f(self):\n    self.log_handler.flush()\n",
    ),
    ("UOW-001", SERVICE, "def f(db):\n    db.rollback()\n", "def f(db):\n    db.close()\n"),
    ("UOW-001", SERVICE, "def f(conn):\n    conn.commit()\n", "def f(conn):\n    conn.cursor()\n"),
    # DB-001
    (
        "DB-001",
        SERVICE,
        'from sqlalchemy import create_engine\ncreate_engine("postgresql://")\n',
        "from abacus.kernel.db import tenant_session\n",
    ),
    (
        "DB-001",
        SERVICE,
        'from sqlalchemy.ext.asyncio import create_async_engine\ncreate_async_engine("x")\n',
        "from sqlalchemy.ext.asyncio import AsyncSession\n",
    ),
    ("DB-001", SERVICE, 'import asyncpg\nasyncpg.connect("x")\n', "import asyncpg\n"),
    ("DB-001", SERVICE, 'import asyncpg\nasyncpg.create_pool("x")\n', "import asyncpg\n"),
    ("DB-001", SERVICE, 'import psycopg\npsycopg.connect("x")\n', "import psycopg\n"),
    # SQL-001
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
        "SQL-001",
        SERVICE,
        'def f(c, q):\n    c.exec_driver_sql(f"select {q}")\n',
        'def f(c):\n    c.exec_driver_sql("select 1")\n',
    ),
    # BOUND-001
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
    ("BOUND-001", SERVICE, "from ..evidence import service\n", "from . import repository\n"),
    (
        "BOUND-001",
        SERVICE,
        "from abacus.modules.evidence import EvidenceItem\n",
        "from abacus.modules.ledger.repository import LedgerRepository\n",
    ),
    (
        "BOUND-001",
        SERVICE,
        "from abacus.modules import evidence\n",
        "from abacus.modules import ledger\n",
    ),
    ("BOUND-001", SERVICE, "from .. import evidence\n", "from .. import ledger\n"),
    ("BOUND-001", SERVICE, "from abacus import modules\n", "from abacus import kernel\n"),
    ("BOUND-001", SERVICE, "import abacus.modules\n", "import abacus.kernel\n"),
    ("BOUND-001", LEDGER_INIT, "from ..evidence import service\n", "from . import service\n"),
    (
        "BOUND-001",
        NESTED,
        "from ...evidence.repository import Repo\n",
        "from ..repository import LedgerRepository\n",
    ),
    # TYPE-001
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
    ("TYPE-001", SERVICE, "x = 1  # type: ignore\n", "x = 1  # type: ignore  # stub gap\n"),
    # ANY-001
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
    (
        "ANY-001",
        SERVICE,
        "from typing import (\n    Any,\n)\nx: Any = 1  # pyright: ignore[reportX] -- r\n",
        "from typing import (\n    Any,\n)\nx: Any = 1  # payload validated downstream\n",
    ),
    # SUPPRESS-001
    (
        "SUPPRESS-001",
        SERVICE,
        "import os  # noqa: TID251\n",
        "import os  # noqa: F401\n",
    ),
    ("SUPPRESS-001", SERVICE, "x = eval('1')  # noqa: S307\n", "x = int('1')  # noqa: E501\n"),
    ("SUPPRESS-001", SERVICE, "x = 1  # nosec\n", "x = 1  # nosecure is not a marker\n"),
    # PROVIDER-001
    (
        "PROVIDER-001",
        SERVICE,
        'URL = "https://api.anthropic.com/v1/messages"\n',
        'URL = "https://example.com/v1/messages"\n',
    ),
    (
        "PROVIDER-001",
        SERVICE,
        'def f(boto3):\n    boto3.client("bedrock-runtime")\n',
        'def f(boto3):\n    boto3.client("s3")\n',
    ),
]
CASE_IDS = [f"{rule}-{n}" for n, (rule, *_rest) in enumerate(CASES)]


@pytest.mark.parametrize(("rule_id", "rel", "bad", "_clean"), CASES, ids=CASE_IDS)
def test_ac20_rule_flags_violation(
    tmp_path: Path, rule_id: str, rel: str, bad: str, _clean: str
) -> None:
    _write(tmp_path, rel, bad)
    assert _rule_ids(tmp_path) == [rule_id]


@pytest.mark.parametrize(("rule_id", "rel", "_bad", "clean"), CASES, ids=CASE_IDS)
def test_ac20_rule_allows_clean_code(
    tmp_path: Path, rule_id: str, rel: str, _bad: str, clean: str
) -> None:
    _write(tmp_path, rel, clean)
    assert _rule_ids(tmp_path) == []


def test_ac20_violation_reports_the_offending_line(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, '"""Doc."""\n\nimport abacus.modules.evidence.models\n')
    assert [(v.rule_id, v.line) for v in bp.scan(tmp_path)] == [("BOUND-001", 3)]


def test_ac20_tests_directory_is_scanned(tmp_path: Path) -> None:
    _write(
        tmp_path, "tests/unit/ledger/test_service.py", "def f(session):\n    session.commit()\n"
    )
    assert [(v.rule_id, v.path) for v in bp.scan(tmp_path)] == [
        ("UOW-001", "tests/unit/ledger/test_service.py")
    ]


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
        ("src/abacus/ai_gateway/providers.py", 'URL = "https://api.anthropic.com/v1"\n'),
    ],
)
def test_ac20_exclude_globs_exempt_only_their_paths(tmp_path: Path, rel: str, source: str) -> None:
    _write(tmp_path, rel, source)
    assert _rule_ids(tmp_path) == []


@pytest.mark.parametrize(
    ("rel", "source", "rule_id"),
    [
        (
            "src/abacus/kernel/outbox/relay.py",
            "def f(session):\n    session.commit()\n",
            "UOW-001",
        ),
        (
            "src/abacus/kernel/dbx/engine.py",
            'from x import create_engine\ncreate_engine("x")\n',
            "DB-001",
        ),
        (
            "src/abacus/modules/agents/gateway.py",
            'URL = "https://api.openai.com/v1"\n',
            "PROVIDER-001",
        ),
    ],
)
def test_ac20_exclude_glob_does_not_leak_to_sibling_package(
    tmp_path: Path, rel: str, source: str, rule_id: str
) -> None:
    _write(tmp_path, rel, source)
    assert _rule_ids(tmp_path) == [rule_id]


def test_ac20_unparseable_file_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "def f(:\n")
    assert _rule_ids(tmp_path) == ["PARSE-001"]


def test_ac20_violation_output_names_path_line_rule_and_adr(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "\ndef f(session):\n    session.rollback()\n")
    [violation] = bp.scan(tmp_path)
    assert str(violation) == (
        f"{SERVICE}:3: UOW-001 session.rollback() outside the unit of work (ADR-007, ADR-018)"
    )


def test_ac20_main_prints_violations_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    found = [bp.Violation(SERVICE, 1, "UOW-001", "message", "ADR-007")]
    monkeypatch.setattr(bp, "scan", lambda: found)
    assert bp.main() == 1
    assert capsys.readouterr().out == f"{SERVICE}:1: UOW-001 message (ADR-007)\n"


def test_ac20_main_exits_0_when_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty: list[bp.Violation] = []
    monkeypatch.setattr(bp, "scan", lambda: empty)
    assert bp.main() == 0
    assert capsys.readouterr().out == ""


def test_ac20_repository_backend_is_clean() -> None:
    # Deliberately depends on live repo state: this is the AC-20 claim itself, and duplicates
    # the banned-pattern step of `make check-fast`.
    assert bp.scan() == []


# --- SKIP-001 (ADR-079) -----------------------------------------------------------------------

TEST_FILE = "tests/unit/x/test_y.py"


def _test_source(body: str) -> str:
    return "import pytest\n\n" + body


# Each source yields exactly one SKIP-001 finding.
SKIP_VIOLATIONS: list[str] = [
    "@pytest.mark.skip\ndef test_a() -> None:\n    pass\n",
    "@pytest.mark.skip()\ndef test_a() -> None:\n    pass\n",
    '@pytest.mark.skip(reason="flaky")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip("flaky")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="issue 123")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="#abc")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="#")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="github.com/acme/abacus/pull/12")\n'
    "def test_a() -> None:\n    pass\n",
    '@pytest.mark.skipif(True, reason="no db")\ndef test_a() -> None:\n    pass\n',
    "@pytest.mark.skipif(True)\ndef test_a() -> None:\n    pass\n",
    "@pytest.mark.skipif\ndef test_a() -> None:\n    pass\n",
    "@pytest.mark.xfail\ndef test_a() -> None:\n    pass\n",
    "@pytest.mark.xfail()\ndef test_a() -> None:\n    pass\n",
    '@pytest.mark.xfail(reason="later")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.xfail(strict=True, reason="later")\ndef test_a() -> None:\n    pass\n',
    'def test_a() -> None:\n    pytest.skip("not ready")\n',
    "def test_a() -> None:\n    pytest.skip()\n",
    'def test_a() -> None:\n    pytest.skip(reason="not ready")\n',
    'def test_a() -> None:\n    pytest.xfail("later")\n',
    "def test_a() -> None:\n    pytest.xfail()\n",
    'def test_a() -> None:\n    pytest.importorskip("numpy")\n',
    'def test_a() -> None:\n    pytest.importorskip("numpy", reason="optional")\n',
    'class TestA:\n    @pytest.mark.skip(reason="flaky")\n    def test_a(self) -> None:\n'
    "        pass\n",
]

# Each source is accepted: a reason carrying an issue reference.
SKIP_ALLOWED: list[str] = [
    '@pytest.mark.skip(reason="see #123")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="#123")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip("flaky, tracked in #45")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.skip(reason="https://github.com/acme/abacus/issues/45")\n'
    "def test_a() -> None:\n    pass\n",
    '@pytest.mark.skipif(True, reason="needs db, #7")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.xfail(reason="#9")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.xfail(strict=True, reason="bug #9")\ndef test_a() -> None:\n    pass\n',
    '@pytest.mark.xfail(reason="https://github.com/acme/abacus/issues/9")\n'
    "def test_a() -> None:\n    pass\n",
    'def test_a() -> None:\n    pytest.skip("#12 flaky")\n',
    'def test_a() -> None:\n    pytest.skip(reason="https://github.com/acme/abacus/issues/12")\n',
    'def test_a() -> None:\n    pytest.xfail("#3")\n',
    'def test_a() -> None:\n    pytest.importorskip("numpy", reason="#5")\n',
    # unrelated decorators and calls
    "@pytest.mark.slow\ndef test_a() -> None:\n    pass\n",
    '@pytest.mark.parametrize("x", [1, 2])\ndef test_a(x: int) -> None:\n    pass\n',
    "@pytest.mark.skipped\ndef test_a() -> None:\n    pass\n",
    'def test_a(other) -> None:\n    other.skip("x")\n',
    "def test_a() -> None:\n    assert True\n",
]


@pytest.mark.parametrize("body", SKIP_VIOLATIONS)
def test_ac20_skip_001_flags_violation(tmp_path: Path, body: str) -> None:
    _write(tmp_path, TEST_FILE, _test_source(body))
    assert _rule_ids(tmp_path) == ["SKIP-001"]


@pytest.mark.parametrize("body", SKIP_ALLOWED)
def test_ac20_skip_001_allows_issue_reference_and_unrelated_code(
    tmp_path: Path, body: str
) -> None:
    _write(tmp_path, TEST_FILE, _test_source(body))
    assert _rule_ids(tmp_path) == []


def test_ac20_skip_001_reports_one_finding_per_offending_node(tmp_path: Path) -> None:
    body = (
        '@pytest.mark.skip(reason="flaky")\n'
        '@pytest.mark.xfail(reason="later")\n'
        "def test_a() -> None:\n"
        '    pytest.skip("x")\n'
        '    pytest.importorskip("numpy")\n'
        '    pytest.skip("#1")\n'
    )
    _write(tmp_path, TEST_FILE, _test_source(body))
    assert _rule_ids(tmp_path) == ["SKIP-001"] * 4


def test_ac20_skip_001_reports_the_offending_line(tmp_path: Path) -> None:
    body = 'def test_a() -> None:\n    assert True\n    pytest.skip("later")\n'
    _write(tmp_path, TEST_FILE, _test_source(body))
    assert [(v.rule_id, v.line) for v in bp.scan(tmp_path)] == [("SKIP-001", 5)]


def test_ac20_skip_001_output_names_path_rule_and_adr(tmp_path: Path) -> None:
    _write(tmp_path, TEST_FILE, _test_source('def test_a() -> None:\n    pytest.skip("later")\n'))
    [violation] = bp.scan(tmp_path)
    assert str(violation).startswith(f"{TEST_FILE}:4: SKIP-001 ")
    assert str(violation).endswith("(ADR-079)")


# --- SKIP-001: aliasing ---------------------------------------------------------------------

ALIAS_MESSAGE = "pytest aliased; use pytest.mark/pytest.skip directly so skips stay checkable"

SKIP_ALIASED: list[str] = [
    "from pytest import mark\n",
    "from pytest import skip\n",
    "from pytest import xfail\n",
    "from pytest import importorskip\n",
    "from pytest import mark as m\n",
    "from pytest import skip as s\n",
    "import pytest as pt\n",
    "import pytest as _pytest\n",
    "m = pytest.mark\n",
    "def f() -> None:\n    m = pytest.mark\n",
]

SKIP_NOT_ALIASED: list[str] = [
    "from pytest import fixture\n",
    "from pytest import raises\n",
    "import pytest as pytest\n",
    "mark = other.mark\n",
    "m = pytest.fixture\n",
]


@pytest.mark.parametrize("body", SKIP_ALIASED)
@pytest.mark.parametrize("rel", [TEST_FILE, "src/abacus/modules/ledger/helpers.py"])
def test_ac20_skip_001_flags_pytest_aliasing(tmp_path: Path, body: str, rel: str) -> None:
    _write(tmp_path, rel, _test_source(body))
    assert _rule_ids(tmp_path) == ["SKIP-001"]


def test_ac20_skip_001_alias_message_is_exact(tmp_path: Path) -> None:
    _write(tmp_path, TEST_FILE, "from pytest import mark\n")
    [violation] = bp.scan(tmp_path)
    assert violation.message == ALIAS_MESSAGE
    assert violation.line == 1


@pytest.mark.parametrize("body", SKIP_NOT_ALIASED)
def test_ac20_skip_001_allows_non_aliasing_imports(tmp_path: Path, body: str) -> None:
    _write(tmp_path, TEST_FILE, _test_source(body))
    assert _rule_ids(tmp_path) == []
