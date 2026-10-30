"""T-01-T11 (TASK-2212; SPEC-501 AC-21, AC-22; ADR-167; ADR P-12): the matrix condition
`consent(<purpose>)` and the agent-spec rule for `data_classes: [tri]`.

- The condition parses a closed list of §7216 purposes and refuses anything else.
- It is a resource condition: it binds every actor, and holds only when every data subject of
  the target holds every listed purpose; no subjects, or unknown facts, fail closed.
- The generated security cases cover it (consented allow; not consented and no subjects deny).
- An agent spec declaring `tri` loads only while the `use` and `ai_disclosure` checks exist.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import spec as agent_spec
from abacus.modules.identity import authz
from abacus.modules.identity.api import AuthContext, Resource, TargetFacts
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import CONSENT_PURPOSES, RULES
from abacus_tools.codegen.security_tests import CONSENT_VARIANTS, condition_cases

# The matrix parser, driven directly.
_parse = matrix._rule  # pyright: ignore[reportPrivateUsage] -- the parser, driven directly
ROW = {"engagement_partner": "allow", "agent": "task_scope", "consent": "use,ai_disclosure"}


def test_ac21_the_condition_takes_only_the_section_7216_purposes() -> None:
    rule = _parse("probe.read", ROW)
    assert rule.consent == frozenset({"use", "ai_disclosure"})
    assert set(CONSENT_PURPOSES) >= rule.consent
    with pytest.raises(ValueError):
        _parse("probe.read", {**ROW, "consent": "use,marketing"})


@pytest.mark.parametrize("person", [True, False])
@pytest.mark.parametrize(
    ("held", "holds"),
    [
        (frozenset({"use", "ai_disclosure"}), True),
        (frozenset({"use", "ai_disclosure", "offshore_disclosure"}), True),
        (frozenset({"use"}), False),
        (frozenset[str](), False),
        (None, False),  # no subjects or unknown: fail closed
    ],
)
def test_ac21_every_subject_must_hold_every_purpose_for_every_actor(
    person: bool, held: frozenset[str] | None, holds: bool
) -> None:
    rule = _parse("probe.read", ROW)
    assert conditions_hold(rule, ConditionFacts(consents=held), person=person) is holds


async def test_ac21_the_facts_are_read_for_every_subject_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subjects = frozenset({uuid.uuid4(), uuid.uuid4()})
    signed = {(next(iter(subjects)), "use")}
    asked: list[tuple[uuid.UUID, str]] = []

    async def given(_tenant: object, entity: uuid.UUID, purpose: str, _at: object) -> bool:
        asked.append((entity, purpose))
        return (entity, purpose) in signed or purpose == "ai_disclosure"

    monkeypatch.setattr(authz, "consent_given", given)
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", "u"), uuid.uuid4(), uuid.uuid4(), None, None
    )
    resource = replace(Resource.firm(ctx.tenant_id), target=TargetFacts(consent_subjects=subjects))
    held = await authz._consents_held(ctx, resource, frozenset({"use", "ai_disclosure"}))  # pyright: ignore[reportPrivateUsage] -- the fact resolver
    assert held == frozenset({"ai_disclosure"})  # one subject lacks `use`
    assert len(asked) == 4
    empty = replace(resource, target=TargetFacts())
    assert await authz._consents_held(ctx, empty, frozenset({"use"})) is None  # pyright: ignore[reportPrivateUsage] -- the fact resolver


def test_ac21_the_generated_cases_cover_the_condition() -> None:
    rules = {**RULES, "probe.read": _parse("probe.read", ROW)}
    cases = [c for c in condition_cases(rules) if c[0] == "probe.read"]
    assert {(variant, want) for _, _, variant, want in cases} == set(CONSENT_VARIANTS)
    assert {role for _, role, _, _ in cases} == {"engagement_partner"}


def test_ac22_a_tri_spec_needs_the_consent_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = next(iter(agent_spec.AGENTS.values()))
    tri = probe.model_copy(update={"data_classes": frozenset({"tri"})})

    def only_use(purpose: str) -> bool:
        return purpose == "use"

    def both(_purpose: str) -> bool:
        return True

    monkeypatch.setattr(agent_spec, "consent_registered", only_use)
    with pytest.raises(ValueError, match="data_classes tri"):
        agent_spec.validate_data_classes(tri)
    monkeypatch.setattr(agent_spec, "consent_registered", both)
    agent_spec.validate_data_classes(tri)
    agent_spec.validate_data_classes(probe)  # no `tri`: nothing to check
