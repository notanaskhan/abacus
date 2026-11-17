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
    assert await gh.group_tags(tenant, [uuid.uuid4()]) == {}  # type: ignore[arg-type] -- a stand-in tenant, unused when off
    assert await gh.component_auditor_tags(tenant, [uuid.uuid4()]) == {}  # type: ignore[arg-type] -- a stand-in tenant, unused when off
