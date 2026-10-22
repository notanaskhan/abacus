"""F-04-T08: independent acceptance tests (ADR-078) for the business clock, database business
time and the tenant demo clock, written from F-04 stories F-04.2, F-04.4, F-04.5 and F-04.6,
not from the code. The Postgres halves (F-04.3, effective_at grants, the demo-clock service
end to end) are in tests/integration/test_business_clock.py."""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from abacus.kernel import clock
from abacus.kernel.db import TenantContext
from abacus.modules.identity import firm_settings

SRC = Path(__file__).parents[2] / "src" / "abacus"
MIGRATION = Path(__file__).parents[2] / "migrations/versions/0085_business_clock.py"
TENANT = TenantContext(uuid.uuid4(), "human", "probe")
DEMO = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


# --- F-04.2: fail closed in production ----------------------------------------------------------


def test_f04_2_startup_fails_in_production_with_a_demo_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        clock, "settings", lambda: SimpleNamespace(environment="production", demo_clock="demo")
    )
    with pytest.raises(clock.ClockMisconfigured):
        clock.check_startup()


async def test_f04_2_production_never_consults_the_tenant_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[TenantContext] = []

    async def provider(tenant: TenantContext) -> datetime | None:
        asked.append(tenant)
        return DEMO

    monkeypatch.setattr(clock, "_tenant_clock", [provider])
    monkeypatch.setattr(
        clock, "settings", lambda: SimpleNamespace(environment="production", demo_clock="")
    )
    real = await clock.now(TENANT)
    assert asked == []
    assert abs(real - datetime.now(UTC)) < timedelta(seconds=5)


async def test_f04_2_outside_production_the_provider_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def provider(_: TenantContext) -> datetime | None:
        return DEMO

    monkeypatch.setattr(clock, "_tenant_clock", [provider])
    monkeypatch.setattr(
        clock, "settings", lambda: SimpleNamespace(environment="staging", demo_clock="")
    )
    assert await clock.now(TENANT) == DEMO


# --- F-04.4: security time never shifts ---------------------------------------------------------


async def test_f04_4_system_now_ignores_every_demo_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def provider(_: TenantContext) -> datetime | None:
        return DEMO

    monkeypatch.setattr(clock, "_tenant_clock", [provider])
    with clock.frozen(DEMO):
        assert await clock.now(TENANT) == DEMO
        assert abs(clock.system_now() - datetime.now(UTC)) < timedelta(seconds=5)


def _calls(path: Path, names: set[str]) -> list[int]:
    """Lines in `path` that call `clock.now(...)`/`now(...)` imported from kernel.clock."""
    tree = ast.parse(path.read_text())
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in names
                and isinstance(func.value, ast.Name)
                and func.value.id == "clock"
            ):
                lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    "path",
    [
        "modules/identity/authz/__init__.py",  # MFA recency
        "modules/connections/connect.py",  # OAuth state TTL
        "modules/evidence/storage.py",  # Object Lock retain-until
        "ai_gateway/budgets.py",  # USD budget windows
    ],
)
def test_f04_4_security_windows_never_read_business_time(path: str) -> None:
    assert _calls(SRC / path, {"now", "today"}) == [], path


def test_f04_4_the_demo_clock_offset_is_measured_on_system_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
    row = firm_settings.DemoClockRow("offset", DEMO, real)
    monkeypatch.setattr(clock, "system_now", lambda: real + timedelta(hours=1))
    assert firm_settings._business(row) == DEMO + timedelta(hours=1)  # pyright: ignore[reportPrivateUsage]  # the rule, tested directly


# --- F-04.5: audit truth and business time ------------------------------------------------------


def test_f04_5_occurred_at_and_the_security_columns_stay_system_time() -> None:
    source = MIGRATION.read_text()
    switched = source[source.index("SWITCHED") : source.index("def upgrade")]
    for kept in (
        '("audit_events", "occurred_at"',
        '("outbox", "occurred_at"',
        '("eval_runs"',
        '("support_sessions"',
        '("invitation_tokens"',
        '("staff_invitation_tokens"',
        '("connection_states"',
        '("budgets"',
        '("usage_records"',
    ):
        assert kept not in switched, kept
    assert "effective_at SET DEFAULT abacus_now()" in source


def test_f04_5_abacus_now_checks_the_firm_is_synthetic() -> None:
    source = MIGRATION.read_text()
    body = source[source.index("CREATE FUNCTION abacus_now()") :]
    body = body[: body.index('$$\n        """')]
    assert "SECURITY INVOKER" in body
    assert "f.synthetic" in body
    assert "current_setting('app.now', true)" in body
    assert "clock_timestamp()" in body


# --- F-04.6: Temporal determinism ---------------------------------------------------------------


def test_f04_6_workflow_code_never_reads_the_business_clock() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*workflow*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "abacus.kernel.clock":
                offenders.append(str(path.relative_to(SRC)))
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "abacus.kernel"
                and any(alias.name == "clock" for alias in node.names)
            ):
                offenders.append(str(path.relative_to(SRC)))
    assert offenders == []
