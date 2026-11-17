"""A-09-T30 (TASK-8409; A-09 §5; AUD-02 h): the Group band's rows register in order and answer
nothing with the capability off, so every live screen renders as before."""

from __future__ import annotations

import importlib
import uuid

import pytest

from abacus.modules.assurance import group_hosts as gh
from abacus.modules.assurance.sections import registered_sections


def test_the_group_band_rows_in_order() -> None:
    importlib.import_module("abacus.modules.assurance.api")  # registers at import

    group = [s for s in registered_sections() if s.band == "group"]
    assert [s.key for s in group] == [k for k, _, _ in gh.GROUP_SECTIONS]
    assert [s.route for s in group] == ["AUD-32", "AUD-34", "AUD-35"]


@pytest.mark.asyncio
async def test_capability_off_answers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.platform import api as platform

    async def off(*_: object) -> bool:
        return False

    monkeypatch.setattr(platform, "group_audit_on", off)
    tenant = object()
    for provider in gh._PROVIDERS.values():  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        assert await provider(tenant, uuid.uuid4()) is None  # type: ignore[arg-type] -- unused
    assert await gh.component_auditor_tags(tenant, [uuid.uuid4()]) == {}  # type: ignore[arg-type] -- a stand-in tenant, unused when off


@pytest.mark.parametrize(
    ("ties", "levels", "chip"),
    [
        (True, (1, 2), "Balanced · 50,760,000"),
        (False, (1, 2), None),  # it does not tie: no chip
        (True, (2,), None),  # no whole-group level yet
    ],
)
async def test_aud02h_the_tie_chip_is_the_engines_whole_group_total(
    monkeypatch: pytest.MonkeyPatch, ties: bool, levels: tuple[int, ...], chip: str | None
) -> None:
    """S48 rest (AUD-02 h): "Balanced · 50,760,000" from level 1's tie and total assets."""
    from decimal import Decimal
    from types import SimpleNamespace

    from abacus.modules.assurance import group_tb

    async def levels_for(*_: object) -> tuple[list[SimpleNamespace], int, int]:
        found = [
            SimpleNamespace(level=n, ties=ties, total_assets=Decimal("50760000.00"))
            for n in levels
        ]
        return found, 0, 0

    monkeypatch.setattr(group_tb, "levels_for", levels_for)
    assert await gh._tie_chip(object(), object()) == chip  # type: ignore[arg-type] -- stand-ins; the engine is faked


async def test_aud02h_no_chip_when_the_engine_cannot_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.assurance import group_tb

    async def missing(*_: object) -> object:
        raise RuntimeError("a TB is missing")

    monkeypatch.setattr(group_tb, "levels_for", missing)
    assert await gh._tie_chip(object(), object()) is None  # type: ignore[arg-type] -- stand-ins; the engine is faked
