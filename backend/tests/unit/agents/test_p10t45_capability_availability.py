"""P-10-T45 (TASK-7303; P-10 §4.3; DEC-4303): the reason order, pure.

HTTP and the Stein taxpayer: `tests/integration/agent_tests/test_p10t45_capabilities.py`."""

from __future__ import annotations

from types import SimpleNamespace

import abacus.modules.agents.api  # noqa: F401  # the registries load before the specs
from abacus.modules.agents.capability_availability import first_reason, installable


def _spec(name: str, *classes: str) -> SimpleNamespace:
    return SimpleNamespace(id=name, data_classes=frozenset(classes))


def _reason(spec: SimpleNamespace, **facts: bool) -> str | None:
    base = {
        "paused": False,
        "policy_off": False,
        "excluded": False,
        "consent": True,
        "may_start": True,
        "on_engagement": True,
    }
    return first_reason(spec, **{**base, **facts})  # type: ignore[arg-type]  # a stand-in spec


def test_a_tax_capability_without_both_consents_reads_consent_7216() -> None:
    drafter = _spec("tax.return_drafter", "tri", "confidential")
    assert _reason(drafter, consent=False) == "consent_7216"
    assert _reason(_spec("issues.fix_runner", "confidential"), consent=False) is None


def test_the_first_reason_wins_in_order() -> None:
    drafter = _spec("tax.return_drafter", "tri")
    assert _reason(drafter, paused=True, consent=False) == "paused"
    assert _reason(drafter, policy_off=True, excluded=True) == "ai_policy_off"
    assert _reason(drafter, excluded=True, consent=False) == "ai_excluded"
    assert _reason(drafter, may_start=False) == "not_on_team"
    assert _reason(drafter, consent=False, on_engagement=False) is None  # firm facts only


def test_a_test_only_capability_never_appears_for_a_real_firm() -> None:
    specs = [_spec("runtime.conformance"), _spec("tax.return_drafter", "tri")]
    assert [s.id for s in installable(specs, synthetic=False)] == ["tax.return_drafter"]  # type: ignore[arg-type]
    assert len(installable(specs, synthetic=True)) == 2  # type: ignore[arg-type]
