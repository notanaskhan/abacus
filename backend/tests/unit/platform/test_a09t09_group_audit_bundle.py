"""A-09-T09 (TASK-8090; A-09 §0, §4.8; DEC-5069): S46 protected bundle #2.

The four flags are in the registry, default off, live at most 90 days and expire outside every
release window; `/v1/me/capabilities` carries `group_audit` only with the entitlement and both
rollout flags; the entitlement is a reviewed module (a non-synthetic firm holds it only after the
consolidation golden-review memo); the six C16 kinds are catalogued with their text.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.modules.notifications import catalogue, kinds
from abacus.modules.platform import capabilities as caps
from abacus.modules.platform import entitlements
from abacus_tools import release_windows
from abacus_tools.codegen import feature_flags as registry

NAMES = (
    "ledger.consolidation",
    "assurance.group_audit",
    "prompt.ledger.tb_mapper",
    "prompt.consolidation.elimination_proposer",
)
KINDS = (
    "consolidation.finalized",
    "eliminations.proposed",
    "component_instructions.acknowledged",
    "component_question.asked",
    "component_deliverable.uploaded",
    "component_deliverable.late",
)


def _entries() -> dict[str, registry.Entry]:
    return {e.name: e for e in registry.parse(registry.source())}


def test_the_four_flags_are_registered_default_off() -> None:
    found = _entries()
    for name in NAMES:
        assert name in found and name in _flags.FLAGS
    assert _flags.LEDGER_CONSOLIDATION.default == "false"
    assert _flags.ASSURANCE_GROUP_AUDIT.default == "false"
    assert _flags.PROMPT_LEDGER_TB_MAPPER.default == "off"
    assert _flags.PROMPT_CONSOLIDATION_ELIMINATION_PROPOSER.default == "off"


def test_they_expire_within_90_days_and_outside_every_release_window() -> None:
    found = _entries()
    mine = [found[n] for n in NAMES]
    cal = release_windows.load()
    assert registry.window_conflicts(mine, cal) == []
    for e in mine:
        assert registry.window_of(e.expires, cal) is None
    assert {e.expires for e in mine} == {date(2027, 2, 12)}  # created 2026-11-15: 89 days


def test_a_registry_expiry_inside_a_window_is_refused() -> None:
    cal = release_windows.load()
    window = cal.windows[0]
    inside = registry.Entry(
        "ledger.consolidation",
        "notanaskhan",
        window.span.start + timedelta(days=3),
        "boolean",
        (),
        "false",
    )
    assert registry.window_conflicts([inside], cal)


@pytest.mark.parametrize(
    ("entitled", "consolidation", "group_audit", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
async def test_the_capability_is_the_entitlement_and_both_flags(
    monkeypatch: pytest.MonkeyPatch,
    entitled: bool,
    consolidation: bool,
    group_audit: bool,
    expected: bool,
) -> None:
    async def entitlement(_tenant: TenantContext, module: str) -> object | None:
        assert module == "group_audit"
        return object() if entitled else None

    async def flag_enabled(_tenant: TenantContext, f: object) -> bool:
        return consolidation if f is _flags.LEDGER_CONSOLIDATION else group_audit

    monkeypatch.setattr(caps, "entitlement", entitlement)
    monkeypatch.setattr(caps, "flag_enabled", flag_enabled)
    assert await caps.group_audit_on(TenantContext(uuid4(), "human", "probe")) is expected


def test_the_entitlement_waits_on_the_golden_review_for_a_real_firm() -> None:
    assert "group_audit" in entitlements.REVIEWED_MODULES
    assert caps.GROUP_AUDIT == "group_audit"


def test_the_six_kinds_are_catalogued_with_text_and_a_notification_kind() -> None:
    codes = set(kinds.registered())
    for event in KINDS:
        kind = catalogue.CATALOGUE[event]
        assert kind.kind == event.replace(".", "_") and kind.kind in codes
        assert "{engagement}" in catalogue.TEMPLATES[event]
