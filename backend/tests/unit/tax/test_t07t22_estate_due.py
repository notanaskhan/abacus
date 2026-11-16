"""T-07-T22 (AC-14.1): Thornbury's due chip reads Nov 2, 2026 and May 3, 2027 (DOD Feb 2, 2026 +
9 months; + 6 months rolled from Sunday May 2, 2027 under §7503) with no published 706 rule."""

from __future__ import annotations

from datetime import date

import pytest

import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- import order: the module first
from abacus.modules.tax import estate_service


@pytest.mark.asyncio
async def test_ac141_the_due_chip(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_rule(*_: object, **__: object) -> object:
        raise LookupError("due_date_rules:706")

    monkeypatch.setattr(estate_service, "due_dates_for", no_rule)
    chip = await estate_service.due_chip(2026, date(2026, 2, 2))
    assert (chip.due_on, chip.extension_to) == (date(2026, 11, 2), date(2027, 5, 3))
    assert chip.form_8971_due_on == date(2026, 12, 2)
