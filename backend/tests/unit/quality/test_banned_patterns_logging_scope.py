"""AC-20: LOG-001 scope after contract revision 1 (TASK-013): which receivers count, literal
event names, any non-bare use of the caught exception, and dynamic imports of logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

SERVICE = "src/abacus/modules/engagements/service.py"
RULE = "LOG-001"


def _count(root: Path, source: str, rel: str = SERVICE) -> int:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return len([v for v in bp.scan(root) if v.rule_id == RULE and v.path == rel])


def _caught(call: str) -> str:
    return f"def f(log):\n    try:\n        pass\n    except ValueError as e:\n        {call}\n"


@pytest.mark.parametrize(
    "receiver", ["log", "_log", "logger", "self.log", "self._log", "a.b.logger"]
)
def test_ac20_log001_checks_calls_on_log_receivers(tmp_path: Path, receiver: str) -> None:
    assert _count(tmp_path, _caught(f'{receiver}.error("x", detail=str(e))')) == 1


@pytest.mark.parametrize("receiver", ["printer", "self.client", "audit", "console", "records"])
def test_ac20_log001_ignores_calls_on_other_receivers(tmp_path: Path, receiver: str) -> None:
    assert _count(tmp_path, _caught(f'{receiver}.error("x", detail=str(e))')) == 0


@pytest.mark.parametrize("method", ["debug", "info", "warning", "error"])
@pytest.mark.parametrize(
    "source",
    ["log.{m}(name)", 'log.{m}(f"x")', 'log.{m}("a" + "b")', "log.{m}(make())", "log.{m}(EVENT)"],
)
def test_ac20_log001_requires_a_literal_event_name(
    tmp_path: Path, method: str, source: str
) -> None:
    assert _count(tmp_path, f"def f(log, name):\n    {source.format(m=method)}\n") == 1


@pytest.mark.parametrize("method", ["debug", "info", "warning", "error"])
def test_ac20_log001_passes_a_literal_event_name(tmp_path: Path, method: str) -> None:
    assert _count(tmp_path, f'def f(log):\n    log.{method}("thing.done", n=1)\n') == 0


def test_ac20_log001_a_call_with_no_event_argument_is_not_flagged(tmp_path: Path) -> None:
    assert _count(tmp_path, "def f(log):\n    log.info()\n") == 0


@pytest.mark.parametrize(
    "value",
    [
        "str(e)",
        "repr(e)",
        "e.args",
        "e.__class__",
        "format(e)",
        'f"{e}"',
        "[e]",
        '{"k": e}',
        "(e,)",
        "e.errno",
        "getattr(e, 'x')",
        "e or None",
        "len(e.args)",
    ],
)
def test_ac20_log001_flags_any_non_bare_use_of_the_caught_exception(
    tmp_path: Path, value: str
) -> None:
    assert _count(tmp_path, _caught(f'log.error("x", detail={value})')) == 1


@pytest.mark.parametrize("value", ["e", "type(e)", "type(e).__name__", "other", "str(other)"])
def test_ac20_log001_allows_the_bare_name_and_type_of_it(tmp_path: Path, value: str) -> None:
    assert _count(tmp_path, _caught(f'log.error("x", detail={value})')) == 0


def test_ac20_log001_flags_a_log_call_nested_deeper_in_the_except_block(
    tmp_path: Path,
) -> None:
    source = (
        "def f(log, items):\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        "        for item in items:\n"
        "            if item:\n"
        '                log.error("x", detail=str(e))\n'
    )
    assert _count(tmp_path, source) == 1


def test_ac20_log001_does_not_flag_the_same_name_outside_the_except_block(
    tmp_path: Path,
) -> None:
    source = (
        "def f(log, e):\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        "        pass\n"
        '    log.error("x", detail=str(e))\n'
    )
    assert _count(tmp_path, source) == 0


def test_ac20_log001_does_not_flag_another_handlers_name_in_a_different_block(
    tmp_path: Path,
) -> None:
    source = (
        "def f(log, other):\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        "        pass\n"
        "    try:\n"
        "        pass\n"
        "    except KeyError:\n"
        '        log.error("x", detail=str(other))\n'
    )
    assert _count(tmp_path, source) == 0


@pytest.mark.parametrize(
    "source",
    [
        '__import__("logging")\n',
        '__import__("structlog")\n',
        '__import__("logging.handlers")\n',
        'import importlib\nimportlib.import_module("logging")\n',
        'import importlib\nimportlib.import_module("structlog.stdlib")\n',
        'from importlib import import_module\nimport_module("logging")\n',
    ],
)
def test_ac20_log001_flags_dynamic_imports_of_logging_and_structlog(
    tmp_path: Path, source: str
) -> None:
    assert _count(tmp_path, source) == 1


@pytest.mark.parametrize(
    "source",
    [
        '__import__("os")\n',
        'import importlib\nimportlib.import_module("json")\n',
        'import importlib\nimportlib.import_module("loggingfoo")\n',
    ],
)
def test_ac20_log001_passes_dynamic_imports_of_other_modules(tmp_path: Path, source: str) -> None:
    assert _count(tmp_path, source) == 0


@pytest.mark.parametrize(
    "rel", ["src/abacus/kernel/logging.py", "src/abacus_tools/x.py", "tests/unit/x/test_y.py"]
)
def test_ac20_log001_dynamic_imports_are_allowed_in_the_helper_tools_and_tests(
    tmp_path: Path, rel: str
) -> None:
    assert _count(tmp_path, '__import__("logging")\n', rel) == 0
