"""AC-20: LOG-001 in the banned-pattern gate (TASK-013 interface contract, "LOG-001"; ADR-022,
ADR-031).

Outside `kernel/logging.py`, product code imports neither stdlib `logging` nor `structlog`, and
never passes a caught exception as text (`str(e)`, `repr(e)`, an f-string with it) in a log
method's keyword. Expectations come from the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

SERVICE = "src/abacus/modules/engagements/service.py"
KERNEL = "src/abacus/kernel/uow/relay.py"
KERNEL_LOGGING = "src/abacus/kernel/logging.py"
TOOL_FILE = "src/abacus_tools/synthetic/x.py"
TEST_FILE = "tests/unit/x/test_y.py"
RULE = "LOG-001"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _count(root: Path, rel: str, source: str) -> int:
    _write(root, rel, source)
    return len([v for v in bp.scan(root) if v.rule_id == RULE and v.path == rel])


def _caught(call: str) -> str:
    return (
        "from abacus.kernel.logging import get_logger\n"
        "log = get_logger(__name__)\n"
        "def f():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        f"        {call}\n"
    )


IMPORTS = [
    "import logging\n",
    "import logging.handlers\n",
    "import logging as stdlib_logging\n",
    "from logging import getLogger\n",
    "from logging.config import dictConfig\n",
    "import structlog\n",
    "import structlog.stdlib\n",
    "from structlog import get_logger\n",
    "from structlog.processors import JSONRenderer\n",
    "import os, logging\n",
]


@pytest.mark.parametrize("source", IMPORTS)
@pytest.mark.parametrize("rel", [SERVICE, KERNEL])
def test_ac20_log001_flags_stdlib_logging_and_structlog_imports(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _count(tmp_path, rel, source) == 1


def test_ac20_log001_flags_a_logging_import_inside_a_function(tmp_path: Path) -> None:
    assert _count(tmp_path, SERVICE, "def f():\n    import logging\n    return logging\n") == 1


@pytest.mark.parametrize(
    "source",
    [
        "from abacus.kernel.logging import get_logger\n",
        "from abacus.kernel import logging as kernel_logging\n",
        "import os\n",
        "import loggingfoo\n",
    ],
)
def test_ac20_log001_passes_the_helper_and_other_imports(tmp_path: Path, source: str) -> None:
    assert _count(tmp_path, SERVICE, source) == 0


@pytest.mark.parametrize("method", ["debug", "info", "warning", "error"])
@pytest.mark.parametrize(
    "value",
    ["str(e)", "repr(e)", 'f"failed: {e}"', 'f"{e!r}"', 'f"{e}"', 'f"{type(e)} {e}"'],
)
def test_ac20_log001_flags_a_caught_exception_as_text_in_a_log_field(
    tmp_path: Path, method: str, value: str
) -> None:
    assert _count(tmp_path, SERVICE, _caught(f'log.{method}("x", detail={value})')) == 1


def test_ac20_log001_flags_each_offending_call(tmp_path: Path) -> None:
    source = _caught('log.error("x", detail=str(e))\n        log.warning("y", detail=repr(e))')
    assert _count(tmp_path, SERVICE, source) == 2


@pytest.mark.parametrize(
    "call",
    [
        'log.error("x", error=e)',
        'log.error("x", error=type(e).__name__)',
        'log.info("x", n=str(count))',
        'log.info("x", n=str(other))',
        'log.info("x", n=repr(other))',
        'log.info("x", n=f"{other}")',
        'log.info("x")',
        "raise RuntimeError(str(e))",
        "text = str(e)",
    ],
)
def test_ac20_log001_passes_the_exception_as_a_value_and_str_of_other_names(
    tmp_path: Path, call: str
) -> None:
    assert _count(tmp_path, SERVICE, _caught(call)) == 0


def test_ac20_log001_str_of_a_name_not_bound_by_except_is_allowed(tmp_path: Path) -> None:
    source = (
        "from abacus.kernel.logging import get_logger\n"
        "log = get_logger(__name__)\n"
        "def f(e):\n"
        '    log.error("x", detail=str(e))\n'
    )
    assert _count(tmp_path, SERVICE, source) == 0


@pytest.mark.parametrize("rel", [KERNEL_LOGGING, TOOL_FILE, TEST_FILE])
def test_ac20_log001_does_not_apply_to_the_helper_tools_or_tests(tmp_path: Path, rel: str) -> None:
    assert _count(tmp_path, rel, "import logging\nimport structlog\n") == 0


def test_ac20_log001_does_not_exempt_the_rest_of_the_kernel(tmp_path: Path) -> None:
    assert _count(tmp_path, "src/abacus/kernel/telemetry.py", "import logging\n") == 1


def test_ac20_log001_findings_name_the_rule_and_the_adr(tmp_path: Path) -> None:
    _write(tmp_path, SERVICE, "import logging\n")
    [found] = [v for v in bp.scan(tmp_path) if v.rule_id == RULE]
    assert found.path == SERVICE
    assert found.line == 1
    assert "ADR-022" in found.adr
