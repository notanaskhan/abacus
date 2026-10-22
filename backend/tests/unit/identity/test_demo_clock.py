"""F-04-T07 (ADR-143): a demo clock's business time, frozen or running from its anchor, and the
tenant provider's registration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import clock
from abacus.modules.identity import firm_settings
from abacus.modules.identity.repository import DemoClockRow

ANCHOR = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def test_a_frozen_clock_stands_at_its_anchor() -> None:
    row = DemoClockRow("frozen", ANCHOR, datetime(2026, 10, 22, tzinfo=UTC))
    assert firm_settings._business(row) == ANCHOR  # pyright: ignore[reportPrivateUsage]  # the rule, tested directly


def test_an_offset_clock_runs_from_its_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    real = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    row = DemoClockRow("offset", ANCHOR, real)
    monkeypatch.setattr(clock, "system_now", lambda: real + timedelta(minutes=17))
    # F-04 story: Hannah opens AUD-02 seventeen minutes after the reset; it reads 9:41 AM.
    assert firm_settings._business(row) == ANCHOR + timedelta(minutes=17)  # pyright: ignore[reportPrivateUsage]  # the rule, tested directly


def test_identity_registers_the_demo_clock_as_the_tenant_provider() -> None:
    import abacus.modules.identity.api  # registers at import

    assert abacus.modules.identity.api
    assert clock._tenant_clock == [firm_settings.tenant_demo_time]  # pyright: ignore[reportPrivateUsage]  # the slot, read directly
