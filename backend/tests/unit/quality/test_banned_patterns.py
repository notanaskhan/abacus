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


# SIDESTEP-001 (ADR-083): API sidesteps around lint rules.
SIDESTEP_FILES = [TEST_FILE, SERVICE, "src/abacus_tools/synthetic/export.py"]
SIDESTEP_VIOLATIONS: list[tuple[str, str, str]] = [
    (
        "import asyncio\nasync def f():\n    await asyncio.create_subprocess_exec('x')\n",
        "create_subprocess_exec",
        "subprocess.run",
    ),
    (
        "import asyncio\nasync def f():\n    await asyncio.create_subprocess_shell('x')\n",
        "create_subprocess_shell",
        "subprocess.run",
    ),
    (
        "import xml.etree.ElementTree as ET\np = ET.XMLPullParser()\n",
        "XMLPullParser",
        "xml.etree.ElementTree.fromstring",
    ),
    (
        "import xml.etree.ElementTree as ET\ndef f(p: ET.XMLPullParser) -> None:\n    pass\n",
        "XMLPullParser",
        "xml.etree.ElementTree.fromstring",
    ),
    (
        "from asyncio import create_subprocess_exec\n",
        "create_subprocess_exec",
        "subprocess.run",
    ),
    (
        "from asyncio.subprocess import create_subprocess_shell\n",
        "create_subprocess_shell",
        "subprocess.run",
    ),
    (
        "from xml.etree.ElementTree import XMLPullParser\n",
        "XMLPullParser",
        "xml.etree.ElementTree.fromstring",
    ),
]
SIDESTEP_CLEAN = [
    "import subprocess\nsubprocess.run(['x'], check=True)\n",
    "import xml.etree.ElementTree as ET\nroot = ET.fromstring('<a/>')\n",
    "from xml.etree.ElementTree import fromstring\n",
    "import asyncio\nasyncio.run(main())\n",
    "from asyncio import run\n",
    "x = obj.create_subprocess\n",
    "x = obj.XMLParser\n",
]


@pytest.mark.parametrize("rel", SIDESTEP_FILES)
@pytest.mark.parametrize(("body", "name", "plain"), SIDESTEP_VIOLATIONS)
def test_ac20_sidestep_001_flags_sidestep_apis(
    tmp_path: Path, rel: str, body: str, name: str, plain: str
) -> None:
    _write(tmp_path, rel, body)
    [violation] = bp.scan(tmp_path)
    assert violation.rule_id == "SIDESTEP-001"
    assert violation.message.startswith(f"{name}: use ")
    assert plain in violation.message


def test_ac20_sidestep_001_reports_one_finding_per_node(tmp_path: Path) -> None:
    _write(
        tmp_path,
        TEST_FILE,
        "import asyncio\nimport xml.etree.ElementTree as ET\n"
        "a = asyncio.create_subprocess_exec\nb = asyncio.create_subprocess_shell\n"
        "c = ET.XMLPullParser\nd = ET.XMLPullParser\n",
    )
    assert _rule_ids(tmp_path) == ["SIDESTEP-001"] * 4


@pytest.mark.parametrize("rel", SIDESTEP_FILES)
@pytest.mark.parametrize("body", SIDESTEP_CLEAN)
def test_ac20_sidestep_001_allows_plain_apis(tmp_path: Path, rel: str, body: str) -> None:
    _write(tmp_path, rel, body)
    assert _rule_ids(tmp_path) == []


# SIDESTEP-001 additions: process-spawning names (Popen is a different name, so it is clean).
SIDESTEP_SPAWN_NAMES = [
    "subprocess_exec",
    "subprocess_shell",
    "popen",
    "posix_spawn",
    "posix_spawnp",
]
SIDESTEP_SPAWN_CLEAN = [
    "import subprocess\nsubprocess.Popen(['x'])\n",
    "from subprocess import Popen\n",
    "import subprocess\nsubprocess.run(['x'], check=True)\n",
    "x = os.spawn\n",
]


@pytest.mark.parametrize("rel", SIDESTEP_FILES)
@pytest.mark.parametrize("name", SIDESTEP_SPAWN_NAMES)
@pytest.mark.parametrize("form", ["attribute", "import"])
def test_ac20_sidestep_001_flags_spawn_names(
    tmp_path: Path, rel: str, name: str, form: str
) -> None:
    body = f"x = os.{name}\n" if form == "attribute" else f"from os import {name}\n"
    _write(tmp_path, rel, body)
    [violation] = bp.scan(tmp_path)
    assert violation.rule_id == "SIDESTEP-001"
    assert violation.message.startswith(f"{name}: use subprocess.run")


@pytest.mark.parametrize("rel", SIDESTEP_FILES)
@pytest.mark.parametrize("body", SIDESTEP_SPAWN_CLEAN)
def test_ac20_sidestep_001_allows_popen_class_and_run(tmp_path: Path, rel: str, body: str) -> None:
    _write(tmp_path, rel, body)
    assert _rule_ids(tmp_path) == []


# --- TENANT-001: the tenant setting is written only by abacus.kernel.db ------------------------

TENANT_MESSAGE = "tenant and actor settings are written only by abacus.kernel.db"
TENANT_LITERALS = [
    "SET app.tenant_id = 'x'",
    "select set_config('app.tenant_id', :t, false)",
]
TENANT_EXCLUDED = [
    "src/abacus/kernel/db/session.py",
    "src/abacus/kernel/db/migration.py",
    "src/abacus_tools/quality/schema_check.py",
    "src/abacus_tools/quality/banned_patterns.py",
    "tests/integration/test_tenancy.py",
    "tests/integration/test_schema_check_db.py",
    "tests/unit/kernel/test_migration_helpers.py",
    "tests/unit/quality/test_banned_patterns.py",
]


def _tenant_source(literal: str, wrapped: bool) -> str:
    return f"text({literal!r})\n" if wrapped else f"X = {literal!r}\n"


@pytest.mark.parametrize("literal", TENANT_LITERALS)
@pytest.mark.parametrize("rel", [SERVICE, "tests/unit/test_something.py"])
def test_ac20_tenant_001_flags_the_setting_outside_the_kernel(
    tmp_path: Path, rel: str, literal: str
) -> None:
    _write(tmp_path, rel, _tenant_source(literal, wrapped="set_config" in literal))
    tenant = [v for v in bp.scan(tmp_path) if v.rule_id == "TENANT-001"]
    assert [(v.path, v.line, v.message) for v in tenant] == [(rel, 1, TENANT_MESSAGE)]


def test_ac20_tenant_001_reports_one_finding_per_literal(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, 'A = "SET app.tenant_id = 1"\nB = "RESET app.tenant_id"\n')
    tenant = [v for v in bp.scan(tmp_path) if v.rule_id == "TENANT-001"]
    assert [v.line for v in tenant] == [1, 2]


@pytest.mark.parametrize("literal", TENANT_LITERALS)
@pytest.mark.parametrize("rel", TENANT_EXCLUDED)
def test_ac20_tenant_001_allows_the_setting_in_excluded_paths(
    tmp_path: Path, rel: str, literal: str
) -> None:
    _write(tmp_path, rel, _tenant_source(literal, wrapped="set_config" in literal))
    assert "TENANT-001" not in _rule_ids(tmp_path)


def test_ac20_tenant_001_ignores_unrelated_strings(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, 'A = "app.other"\nB = "tenant_id"\n')
    assert "TENANT-001" not in _rule_ids(tmp_path)


# --- UOW-002: tenant_connection is for the kernel, the unit of work and integration tests -------

UOW2_VIOLATING = [
    "from abacus.kernel.db import tenant_connection\n",
    "from abacus.kernel.db.session import tenant_connection\n",
    "from abacus.kernel.db import tenant_connection as tc\n",
    "import abacus.kernel.db\nabacus.kernel.db.tenant_connection(ctx)\n",
    "from abacus.kernel import db\ndb.tenant_connection(ctx)\n",
    "from abacus.kernel.db import tenant_session, tenant_connection\n",
    "from abacus.kernel.db import relay_engine\n",
    "from abacus.kernel.db import configure_relay_engine\n",
    "from abacus.kernel.db.session import relay_engine as engine\n",
    "import abacus.kernel.db\nabacus.kernel.db.configure_relay_engine(url)\n",
    "from abacus.kernel import db\ndb.relay_engine()\n",
]
UOW2_FLAGGED_PATHS = [
    SERVICE,
    "src/abacus/kernel/config.py",
    "src/abacus/kernel/uow_helpers.py",
    "tests/unit/test_something.py",
    "tests/integration_helpers/x.py",
]
UOW2_ALLOWED_PATHS = [
    "src/abacus/kernel/db/session.py",
    "src/abacus/kernel/uow/unit.py",
    "tests/integration/test_unit_of_work.py",
]


@pytest.mark.parametrize("source", UOW2_VIOLATING)
@pytest.mark.parametrize("rel", UOW2_FLAGGED_PATHS)
def test_ac20_uow_002_flags_tenant_connection_outside_its_owners(
    tmp_path: Path, rel: str, source: str
) -> None:
    _write(tmp_path, rel, source)
    found = [v for v in bp.scan(tmp_path) if v.rule_id == "UOW-002"]
    assert found
    assert {v.path for v in found} == {rel}


def test_ac20_uow_002_reports_the_import_line(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "import os\nfrom abacus.kernel.db import tenant_connection\n")
    found = [v for v in bp.scan(tmp_path) if v.rule_id == "UOW-002"]
    assert [v.line for v in found] == [2]


@pytest.mark.parametrize("source", UOW2_VIOLATING)
@pytest.mark.parametrize("rel", UOW2_ALLOWED_PATHS)
def test_ac20_uow_002_allows_the_kernel_the_unit_of_work_and_integration_tests(
    tmp_path: Path, rel: str, source: str
) -> None:
    _write(tmp_path, rel, source)
    assert "UOW-002" not in _rule_ids(tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        "from abacus.kernel.db import tenant_session\n",
        "from abacus.kernel.uow import uow\n",
        "# relay_engine and configure_relay_engine belong to the kernel\n",
        "from abacus.kernel.uow.relay import relay_once\n",
        "# tenant_connection is for the unit of work\n",
        "import abacus.kernel.db\nabacus.kernel.db.tenant_session(ctx)\n",
    ],
)
def test_ac20_uow_002_ignores_clean_code_elsewhere(tmp_path: Path, source: str) -> None:
    _write(tmp_path, SERVICE, source)
    assert "UOW-002" not in _rule_ids(tmp_path)


# --- TENANT-001 also covers the actor settings ---------------------------------------------

ACTOR_LITERALS = [
    "SET app.actor_kind = 'x'",
    "select set_config('app.actor_id', :a, false)",
    "RESET app.actor_",
]


@pytest.mark.parametrize("literal", ACTOR_LITERALS)
@pytest.mark.parametrize("rel", [SERVICE, "tests/unit/test_something.py"])
def test_ac20_tenant_001_flags_the_actor_settings_outside_the_kernel(
    tmp_path: Path, rel: str, literal: str
) -> None:
    _write(tmp_path, rel, _tenant_source(literal, wrapped="set_config" in literal))
    tenant = [v for v in bp.scan(tmp_path) if v.rule_id == "TENANT-001"]
    assert [(v.path, v.line) for v in tenant] == [(rel, 1)]


@pytest.mark.parametrize("literal", ACTOR_LITERALS)
@pytest.mark.parametrize("rel", ["src/abacus/kernel/db/session.py", *TENANT_EXCLUDED[2:]])
def test_ac20_tenant_001_allows_the_actor_settings_in_excluded_paths(
    tmp_path: Path, rel: str, literal: str
) -> None:
    _write(tmp_path, rel, _tenant_source(literal, wrapped="set_config" in literal))
    assert "TENANT-001" not in _rule_ids(tmp_path)


def test_ac20_tenant_001_ignores_other_app_settings_and_similar_strings(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, 'A = "app.other"\nB = "actor_kind"\nC = "app.actors"\n')
    tenant = [v for v in bp.scan(tmp_path) if v.rule_id == "TENANT-001"]
    assert tenant == []


# --- TASK-007 identity rules: UOW-003, AUTH-001, AUTH-002, AUTHZ-001, AUTHZ-002, TENANT-002, ---
# --- ROUTE-001, ROUTE-002, CTX-001 ---------------------------------------------------------------

IDENT = "src/abacus/modules/identity"
OUTSIDE_SRC = ["tests/unit/x/test_y.py", "src/abacus_tools/synthetic/x.py"]
INSIDE_SRC = [SERVICE, "src/abacus/modules/ledger/routes.py", "src/abacus/kernel/logging.py"]


def _found(root: Path, rule_id: str) -> list[str]:
    return [v.path for v in bp.scan(root) if v.rule_id == rule_id]


def _flags(tmp_path: Path, rule_id: str, rel: str, source: str) -> bool:
    _write(tmp_path, rel, source)
    return rel in _found(tmp_path, rule_id)


UOW3_VIOLATING = [
    "from abacus.kernel.db import identity_engine\n",
    "from abacus.kernel.db import configure_identity_engine\n",
    "from abacus.kernel.db.session import identity_engine as engine\n",
    "import abacus.kernel.db\nabacus.kernel.db.identity_engine()\n",
    "from abacus.kernel import db\ndb.configure_identity_engine(url)\n",
    "def f():\n    return identity_engine()\n",
    "x = identity_engine\n",
    "def f(identity_engine):\n    pass\n",
    "def f(identity_database_url):\n    pass\n",
    "x = settings.identity_database_url\n",
    "from abacus.kernel.db import *\n",
    "from abacus.kernel.db.session import *\n",
]
UOW3_CLEAN = [
    "from abacus.kernel.db import tenant_session\n",
    "from abacus.kernel.uow import *\n",
    "from os.path import *\n",
    "x = identity_url\n",
    "# identity_engine is for the repository\n",
    'x = "identity_engine"\n',
]
UOW3_ALLOWED = [
    "src/abacus/kernel/db/session.py",
    "src/abacus/kernel/config.py",
    f"{IDENT}/repository.py",
    "tests/integration/conftest.py",
    "tests/unit/kernel/test_config.py",
    "tests/integration/test_identity.py",
]
UOW3_FLAGGED = [
    SERVICE,
    f"{IDENT}/service.py",
    f"{IDENT}/context.py",
    "src/abacus/kernel/uow/core.py",
    "tests/unit/x/test_y.py",
    "tests/integration/test_tenancy.py",
    "src/abacus_tools/quality/x.py",
]


@pytest.mark.parametrize("source", UOW3_VIOLATING)
@pytest.mark.parametrize("rel", UOW3_FLAGGED)
def test_ac20_uow_003_flags_the_identity_engine_outside_its_owners(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "UOW-003", rel, source)


@pytest.mark.parametrize("source", UOW3_VIOLATING)
@pytest.mark.parametrize("rel", UOW3_ALLOWED)
def test_ac20_uow_003_allows_the_identity_engine_in_its_owners(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "UOW-003", rel, source)


@pytest.mark.parametrize("source", UOW3_CLEAN)
def test_ac20_uow_003_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "UOW-003", SERVICE, source)


def test_ac20_uow_003_reports_the_offending_line(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "import os\nfrom abacus.kernel.db import identity_engine\n")
    assert [(v.line, v.rule_id) for v in bp.scan(tmp_path) if v.rule_id == "UOW-003"] == [
        (2, "UOW-003")
    ]


AUTH1_VIOLATING = [
    "import jwt\n",
    "import jwt.algorithms\n",
    "from jwt import decode\n",
    "from jwt.algorithms import RSAAlgorithm\n",
    "import jose\n",
    "from jose import jwt\n",
    "import josepy\n",
    "import jwcrypto.jwk\n",
    "from authlib.jose import jwt\n",
    "import python_jose\n",
    "import importlib\nimportlib.import_module('jwt')\n",
    "import importlib\nimportlib.import_module('jose.jwt')\n",
    "__import__('jwt')\n",
    "import importlib\nimportlib.import_module('authlib.jose')\n",
]
AUTH1_CLEAN = [
    "import json\n",
    "import jwtx\n",
    "from pyjwt_helpers import decode\n",
    "import importlib\nimportlib.import_module('json')\n",
    "from abacus.modules.identity.api import JwtVerifier\n",
    "x = 'jwt'\n",
    "# import jwt\n",
]
AUTH1_ALLOWED = [f"{IDENT}/tokens.py", "src/abacus_tools/fakes/identity.py"]
AUTH1_FLAGGED = [
    SERVICE,
    f"{IDENT}/service.py",
    f"{IDENT}/routing.py",
    "src/abacus_tools/synthetic/x.py",
    "tests/unit/x/test_y.py",
    "tests/integration/test_identity.py",
]


@pytest.mark.parametrize("source", AUTH1_VIOLATING)
@pytest.mark.parametrize("rel", AUTH1_FLAGGED)
def test_ac20_auth_001_flags_token_libraries_outside_their_two_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "AUTH-001", rel, source)


@pytest.mark.parametrize("source", AUTH1_VIOLATING)
@pytest.mark.parametrize("rel", AUTH1_ALLOWED)
def test_ac20_auth_001_allows_token_libraries_in_their_two_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTH-001", rel, source)


@pytest.mark.parametrize("source", AUTH1_CLEAN)
def test_ac20_auth_001_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "AUTH-001", SERVICE, source)


AUTH2_VIOLATING = [
    'h = request.headers["Authorization"]\n',
    'h = request.headers.get("authorization")\n',
    'x = " authorization "\n',
    'x = "AUTHORIZATION"\n',
    "def f(authorization):\n    pass\n",
    "async def f(authorization: str | None = None):\n    pass\n",
    "from fastapi.security import HTTPBearer\n",
    "from fastapi.security.http import HTTPBearer\n",
    "import fastapi.security\n",
]
AUTH2_CLEAN = [
    'x = "authorization_code"\n',
    'x = "Authorization: Bearer"\n',
    "x = authorize\n",
    "x = Authorization\n",
    "authorization = 1\n",
    "x = obj.authorization\n",
    "from m import authorization\n",
    "from fastapi import Depends\n",
]
AUTH2_ALLOWED = [f"{IDENT}/routing.py", f"{IDENT}/service.py"]


@pytest.mark.parametrize("source", AUTH2_VIOLATING)
@pytest.mark.parametrize("rel", [*INSIDE_SRC, f"{IDENT}/tokens.py", f"{IDENT}/routes.py"])
def test_ac20_auth_002_flags_the_authorization_header_outside_the_request_context(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "AUTH-002", rel, source)


@pytest.mark.parametrize("source", AUTH2_VIOLATING)
@pytest.mark.parametrize("rel", AUTH2_ALLOWED)
def test_ac20_auth_002_allows_the_request_context_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTH-002", rel, source)


@pytest.mark.parametrize("source", AUTH2_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_auth_002_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTH-002", rel, source)


@pytest.mark.parametrize("source", AUTH2_CLEAN)
def test_ac20_auth_002_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "AUTH-002", SERVICE, source)


AUTHZ1_VIOLATING = [
    'def f(m):\n    return m.firm_role == "firm_admin"\n',
    'x = role == "manager"\n',
    'x = firm_role != "reviewer"\n',
    'x = "manager" == y.role\n',
    'x = role in ("senior", "staff")\n',
    'x = user.role in ["manager", "senior"]\n',
    'x = user.role in {"engagement_partner"}\n',
    'x = y.roles == "quality_partner"\n',
    'x = roles == "practice_leader"\n',
    'x = a.role == "firm_admin"\n',
    'match role:\n    case "firm_admin":\n        pass\n',
    'match user.firm_role:\n    case "manager" | "senior":\n        pass\n',
]
AUTHZ1_CLEAN = [
    "x = a == b\n",
    'x = a == "something"\n',
    "x = role\n",
    'x = "manager"\n',
    'x = status == "active"\n',
    "x = role is None\n",
    "x = role is not None\n",
    'x = message.role == "assistant"\n',
    'x = role == "agent"\n',
    'x = role == "system"\n',
    'x = role == "client_admin"\n',
    'x = y == "manager"\n',
    'x = a in ("senior", "staff")\n',
    "x = a == role\n",
    'match r:\n    case "firm_admin":\n        pass\n',
    'match status:\n    case "active":\n        pass\n',
]


@pytest.mark.parametrize("source", AUTHZ1_VIOLATING)
@pytest.mark.parametrize("rel", [*INSIDE_SRC, f"{IDENT}/service.py", f"{IDENT}/routes.py"])
def test_ac20_authz_001_flags_role_comparisons_outside_authz(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "AUTHZ-001", rel, source)


@pytest.mark.parametrize("source", AUTHZ1_VIOLATING)
@pytest.mark.parametrize("rel", [f"{IDENT}/authz/__init__.py", f"{IDENT}/authz/matrix.py"])
def test_ac20_authz_001_allows_role_comparisons_inside_authz(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-001", rel, source)


@pytest.mark.parametrize("source", AUTHZ1_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_authz_001_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-001", rel, source)


@pytest.mark.parametrize("source", AUTHZ1_CLEAN)
def test_ac20_authz_001_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "AUTHZ-001", SERVICE, source)


@pytest.mark.parametrize("name", ["agent", "system", "client_admin", "client_contributor"])
def test_ac20_authz_001_does_not_treat_actor_kinds_or_client_roles_as_matrix_roles(
    tmp_path: Path, name: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-001", SERVICE, f'x = role == "{name}"\n')


@pytest.mark.parametrize(
    "name",
    [
        "firm_admin",
        "practice_leader",
        "quality_partner",
        "engagement_partner",
        "manager",
        "senior",
        "staff",
        "reviewer",
    ],
)
def test_ac20_authz_001_flags_every_firm_and_engagement_role_name(
    tmp_path: Path, name: str
) -> None:
    assert _flags(tmp_path, "AUTHZ-001", SERVICE, f'x = role == "{name}"\n')


AUTHZ2_VIOLATING = [
    "x = ctx.firm_role\n",
    "def f(c):\n    return c.firm_role\n",
    "c.firm_role = None\n",
    "x = a.b.firm_role.value\n",
]
AUTHZ2_CLEAN = ["x = ctx.role_name\n", "firm_role = 1\n", "x = ctx.firm\n", 'x = "firm_role"\n']


@pytest.mark.parametrize("source", AUTHZ2_VIOLATING)
@pytest.mark.parametrize("rel", INSIDE_SRC)
def test_ac20_authz_002_flags_firm_role_reads_outside_identity(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "AUTHZ-002", rel, source)


@pytest.mark.parametrize("source", AUTHZ2_VIOLATING)
@pytest.mark.parametrize(
    "rel", [f"{IDENT}/service.py", f"{IDENT}/authz/__init__.py", f"{IDENT}/routes.py"]
)
def test_ac20_authz_002_allows_firm_role_reads_inside_identity(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-002", rel, source)


@pytest.mark.parametrize("source", AUTHZ2_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_authz_002_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-002", rel, source)


@pytest.mark.parametrize("source", AUTHZ2_CLEAN)
def test_ac20_authz_002_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "AUTHZ-002", SERVICE, source)


TENANT2_VIOLATING = [
    'H = "X-Abacus-Tenant"\n',
    'H = "x-abacus-tenant"\n',
    'h = req.headers.get("X-ABACUS-TENANT")\n',
    'x = "prefix x-abacus-tenant suffix"\n',
    "def f(x_abacus_tenant):\n    pass\n",
    "x = x_abacus_tenant\n",
    "from abacus.modules.identity.service import TENANT_HEADER\n",
    "x = mod.TENANT_HEADER\n",
    "x = TENANT_HEADER\n",
]
TENANT2_CLEAN = ['x = "abacus-tenant"\n', 'x = "tenant"\n', "x = tenant_header\n"]
TENANT2_ALLOWED = [f"{IDENT}/service.py", f"{IDENT}/routing.py"]


@pytest.mark.parametrize("source", TENANT2_VIOLATING)
@pytest.mark.parametrize("rel", [*INSIDE_SRC, f"{IDENT}/routes.py", f"{IDENT}/authz/__init__.py"])
def test_ac20_tenant_002_flags_the_tenant_header_outside_the_request_context(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "TENANT-002", rel, source)


@pytest.mark.parametrize("source", TENANT2_VIOLATING)
@pytest.mark.parametrize("rel", TENANT2_ALLOWED)
def test_ac20_tenant_002_allows_the_request_context_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "TENANT-002", rel, source)


@pytest.mark.parametrize("source", TENANT2_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_tenant_002_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "TENANT-002", rel, source)


@pytest.mark.parametrize("source", TENANT2_CLEAN)
def test_ac20_tenant_002_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "TENANT-002", SERVICE, source)


ROUTE_CLASSES = [
    "APIRouter",
    "APIRoute",
    "APIWebSocketRoute",
    "FastAPI",
    "Starlette",
    "Mount",
    "Route",
    "Router",
    "WebSocketRoute",
    "BaseHTTPMiddleware",
    "StaticFiles",
]
ROUTE_METHODS = [
    "add_api_route",
    "add_route",
    "add_websocket_route",
    "add_api_websocket_route",
    "websocket",
    "mount",
    "include_router",
    "add_middleware",
]
ROUTE1_ALLOWED = [f"{IDENT}/routing.py", "src/abacus/api/app.py"]
ROUTE1_VIOLATING = [
    *[f"from fastapi import {name}\n" for name in ROUTE_CLASSES],
    *[f"from starlette.routing import {name}\n" for name in ROUTE_CLASSES],
    "import fastapi\nx = fastapi.FastAPI()\n",
    "import fastapi\nx = fastapi.APIRouter\n",
    "app.dependency_overrides[f] = g\n",
    "x = app.dependency_overrides\n",
    *[f"app.{name}(x)\n" for name in ROUTE_METHODS],
]
ROUTE1_CLEAN = [
    "from fastapi import Request\n",
    "from fastapi import Depends\n",
    "from fastapi import HTTPException\n",
    "from fastapi.responses import JSONResponse\n",
    "x = mount_point\n",
    "x = websockets\n",
    "x = APIRouterish\n",
    'x = "FastAPI"\n',
    "x = FastAPI\n",
    "x = obj.include_router\n",
    "x = obj.add_middleware\n",
    "from other import FastAPI\n",
]


@pytest.mark.parametrize("source", ROUTE1_VIOLATING)
def test_ac20_route_001_flags_route_bypasses(tmp_path: Path, source: str) -> None:
    assert _flags(tmp_path, "ROUTE-001", SERVICE, source)


@pytest.mark.parametrize("source", ROUTE1_VIOLATING)
@pytest.mark.parametrize("rel", ROUTE1_ALLOWED)
def test_ac20_route_001_allows_the_router_and_app_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "ROUTE-001", rel, source)


@pytest.mark.parametrize("source", ROUTE1_VIOLATING)
@pytest.mark.parametrize("rel", [f"{IDENT}/routes.py", f"{IDENT}/service.py"])
def test_ac20_route_001_flags_other_identity_files_too(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "ROUTE-001", rel, source)


@pytest.mark.parametrize("source", ROUTE1_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_route_001_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "ROUTE-001", rel, source)


@pytest.mark.parametrize("source", ROUTE1_CLEAN)
def test_ac20_route_001_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "ROUTE-001", SERVICE, source)


ROUTE2_VIOLATING = [
    "from m import SELF\n",
    "x = SELF\n",
    "x = api.SELF\n",
    "def f(SELF):\n    pass\n",
]
ROUTE2_CLEAN = ["x = SELFISH\n", "x = self\n", 'x = "SELF"\n', "def f(self):\n    pass\n"]
ROUTE2_ALLOWED = [f"{IDENT}/routing.py", f"{IDENT}/routes.py", f"{IDENT}/api.py"]


@pytest.mark.parametrize("source", ROUTE2_VIOLATING)
@pytest.mark.parametrize("rel", [*INSIDE_SRC, f"{IDENT}/service.py", "src/abacus/api/app.py"])
def test_ac20_route_002_flags_self_outside_the_identity_routes(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "ROUTE-002", rel, source)


@pytest.mark.parametrize("source", ROUTE2_VIOLATING)
@pytest.mark.parametrize("rel", ROUTE2_ALLOWED)
def test_ac20_route_002_allows_self_in_the_identity_route_files(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "ROUTE-002", rel, source)


@pytest.mark.parametrize("source", ROUTE2_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_route_002_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "ROUTE-002", rel, source)


@pytest.mark.parametrize("source", ROUTE2_CLEAN)
def test_ac20_route_002_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "ROUTE-002", SERVICE, source)


CTX_VIOLATING = [
    "x = AuthContext(a, b)\n",
    "x = mod.AuthContext(a)\n",
    "x = AuthContext(**kwargs)\n",
    "x = replace(ctx, firm_role=None)\n",
    "x = dataclasses.replace(ctx, firm_role=None)\n",
    "x = replace(auth_ctx)\n",
    "x = copy(context)\n",
    "x = copy.copy(ctx)\n",
    "x = deepcopy(ctx)\n",
    "x = copy.deepcopy(self.ctx)\n",
    "x = __replace__(ctx, firm_role=None)\n",
    "x = replace(request_context, a=1)\n",
]
CTX_CLEAN = [
    "from abacus.modules.identity.api import AuthContext\n",
    "from abacus.kernel.db import TenantContext\n",
    "def f(ctx: AuthContext) -> TenantContext:\n    return ctx.tenant\n",
    "x = AuthContextual()\n",
    "x = isinstance(a, AuthContext)\n",
    "x = TenantContext(a, 'agent', 'x')\n",
    "x = db.TenantContext(1, 'system', 'x')\n",
    "x = replace(item, a=1)\n",
    "x = copy(items)\n",
    "x = deepcopy(payload)\n",
]
CTX_ALLOWED = [f"{IDENT}/service.py"]


@pytest.mark.parametrize("source", CTX_VIOLATING)
@pytest.mark.parametrize(
    "rel",
    [*INSIDE_SRC, f"{IDENT}/context.py", f"{IDENT}/routing.py", f"{IDENT}/authz/__init__.py"],
)
def test_ac20_ctx_001_flags_hand_built_or_copied_contexts(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "CTX-001", rel, source)


@pytest.mark.parametrize("source", CTX_VIOLATING)
@pytest.mark.parametrize("rel", CTX_ALLOWED)
def test_ac20_ctx_001_allows_the_context_builder(tmp_path: Path, rel: str, source: str) -> None:
    assert not _flags(tmp_path, "CTX-001", rel, source)


@pytest.mark.parametrize("source", CTX_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_ctx_001_applies_only_under_src_abacus(tmp_path: Path, rel: str, source: str) -> None:
    assert not _flags(tmp_path, "CTX-001", rel, source)


@pytest.mark.parametrize("source", CTX_CLEAN)
def test_ac20_ctx_001_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "CTX-001", SERVICE, source)


def test_ac20_ctx_001_no_longer_flags_tenant_context_in_the_kernel_or_elsewhere(
    tmp_path: Path,
) -> None:
    for rel in (SERVICE, "src/abacus/kernel/db/session.py", "src/abacus/modules/agents/x.py"):
        assert not _flags(tmp_path, "CTX-001", rel, "x = TenantContext(a, 'agent', 'b')\n")


AUTHZ3_VIOLATING = [
    "x = Resource.engagement(t, e, archived=False)\n",
    "x = Resource.engagement(t, e, archived=True)\n",
    "x = engagement(t, e, archived=False)\n",
    "x = Resource(t, e, archived=True)\n",
    "x = Resource(t, e, True)\n",
    "x = Resource(t, e, False)\n",
    "x = authz.Resource(t, e, False)\n",
]
AUTHZ3_CLEAN = [
    "x = Resource.engagement(t, e, archived=row.archived)\n",
    "x = Resource.engagement(t, e, archived=archived)\n",
    "x = Resource(t, e, row.archived)\n",
    "x = Resource(t, e)\n",
    "x = Resource.firm(t)\n",
    "x = other(t, e, archived=False)\n",
    "x = other(t, e, True)\n",
]


@pytest.mark.parametrize("source", AUTHZ3_VIOLATING)
@pytest.mark.parametrize("rel", [*INSIDE_SRC, f"{IDENT}/service.py", f"{IDENT}/routes.py"])
def test_ac20_authz_003_flags_a_literal_archived_outside_authz(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "AUTHZ-003", rel, source)


@pytest.mark.parametrize("source", AUTHZ3_VIOLATING)
@pytest.mark.parametrize("rel", [f"{IDENT}/authz/__init__.py", f"{IDENT}/authz/matrix.py"])
def test_ac20_authz_003_allows_literals_inside_authz(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-003", rel, source)


@pytest.mark.parametrize("source", AUTHZ3_VIOLATING)
@pytest.mark.parametrize("rel", OUTSIDE_SRC)
def test_ac20_authz_003_applies_only_under_src_abacus(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "AUTHZ-003", rel, source)


@pytest.mark.parametrize("source", AUTHZ3_CLEAN)
def test_ac20_authz_003_ignores_clean_code(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "AUTHZ-003", SERVICE, source)


@pytest.mark.parametrize(
    ("source", "rule_id"),
    [
        ("from abacus.kernel.db import identity_engine\n", "UOW-003"),
        ("import jwt\n", "AUTH-001"),
        ('x = "Authorization"\n', "AUTH-002"),
        ('x = role == "manager"\n', "AUTHZ-001"),
        ("x = ctx.firm_role\n", "AUTHZ-002"),
        ('x = "X-Abacus-Tenant"\n', "TENANT-002"),
        ("from fastapi import FastAPI\n", "ROUTE-001"),
        ("x = Resource(t, e, True)\n", "AUTHZ-003"),
        ("x = SELF\n", "ROUTE-002"),
        ("x = AuthContext(a)\n", "CTX-001"),
    ],
)
def test_ac20_identity_rules_output_names_path_line_rule_and_an_adr(
    tmp_path: Path, source: str, rule_id: str
) -> None:
    _write(tmp_path, SERVICE, source)
    found = [v for v in bp.scan(tmp_path) if v.rule_id == rule_id]
    assert found
    assert str(found[0]).startswith(f"{SERVICE}:1: {rule_id} ")
    assert str(found[0]).endswith(")")
    assert "ADR-" in str(found[0])
