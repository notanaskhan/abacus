"""C-02-T21 (S51 partials, TASK-8735; DEC-5728): before anyone writes it, the package commentary is
filled by code from the close's accepted flux explanations, in line order, with no draft."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from abacus.modules.closes import flux, package_service


async def test_ac_accepted_lines_fill_the_drafted_commentary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def accepted(
        _tenant: object, _close: object
    ) -> list[tuple[str, Decimal, Decimal | None, str]]:
        return [
            ("Payroll expense", Decimal("4210.00"), Decimal("12.4"), "Two new baristas."),
            ("Rent", Decimal("-1500.00"), None, "July's rent was prepaid in June."),
        ]

    monkeypatch.setattr(flux, "accepted_flux", accepted)
    text = await package_service.drafted_commentary(object(), uuid4())  # type: ignore[arg-type]  # a stand-in
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("- Payroll expense:") and lines[0].endswith("Two new baristas.")
    assert "(12.4%)" in lines[0] and "%" not in lines[1]


async def test_ac_no_accepted_line_no_commentary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none(
        _tenant: object, _close: object
    ) -> list[tuple[str, Decimal, Decimal | None, str]]:
        return []

    monkeypatch.setattr(flux, "accepted_flux", none)
    assert await package_service.drafted_commentary(object(), uuid4()) == ""  # type: ignore[arg-type]  # a stand-in
