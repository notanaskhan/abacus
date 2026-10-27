"""P-04-T06 acceptance: "An unregistered target, decision kind, gate kind or field owner is
refused or answers 503 in tests." The review and agents slots fail closed."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import ServiceUnavailable
from abacus.modules.agents.api import (
    UnregisteredTarget,
    apply_proposal,
    check_suggestion_target,
    register_proposal_adapter,
    register_suggestion_target,
)
from abacus.modules.review.api import (
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    FieldOwner,
    UnregisteredKind,
    decision_kind,
    field_owner,
    gate_met,
    register_decision_kind,
    register_field_owner,
    register_gate_kind,
    run_fix,
)

TENANT = TenantContext(uuid.uuid4(), "human", "probe")
pytestmark = pytest.mark.asyncio


async def _options(_tenant: TenantContext, _subject: CardSubject) -> ComputedCard:
    # P-04-T23: a kind's provider computes the card's options (code, never a model).
    return ComputedCard((CardOption("overall_1_0", "1.0%"), CardOption("overall_1_5", "1.5%")))


async def _raises(_tenant: TenantContext, _engagement: uuid.UUID) -> bool:
    raise RuntimeError("owner down")


async def _value(_tenant: TenantContext, _target: uuid.UUID, _field: str) -> dict[str, object]:
    return {"t": "decimal", "v": "168100"}


async def test_unregistered_kinds_are_refused() -> None:
    with pytest.raises(UnregisteredKind):
        decision_kind("probe_unregistered")
    with pytest.raises(UnregisteredKind):
        field_owner("probe_unregistered")
    with pytest.raises(UnregisteredKind):
        await gate_met(TENANT, "probe_unregistered", uuid.uuid4())
    with pytest.raises(UnregisteredTarget):
        check_suggestion_target("probe_unregistered")


async def test_missing_runners_and_adapters_answer_503() -> None:
    with pytest.raises(ServiceUnavailable):
        await run_fix(TENANT, "probe_unregistered", uuid.uuid4())
    with pytest.raises(ServiceUnavailable):
        await apply_proposal(TENANT, "probe_unregistered", uuid.uuid4())


async def test_a_failing_gate_owner_leaves_the_gate_unmet() -> None:
    register_gate_kind("probe_gate", _raises)
    assert await gate_met(TENANT, "probe_gate", uuid.uuid4()) is False


async def test_registration_is_once_and_validated() -> None:
    register_decision_kind(DecisionKind("probe_materiality", "engagement_partner", _options))
    register_decision_kind(DecisionKind("probe_materiality", "engagement_partner", _options))
    assert decision_kind("probe_materiality").reserved_role == "engagement_partner"
    with pytest.raises(ValueError, match="already registered"):
        register_decision_kind(DecisionKind("probe_materiality", "manager", _options))
    with pytest.raises(ValueError, match="reserved role"):
        register_decision_kind(DecisionKind("probe_other", "staff", _options))
    register_field_owner(FieldOwner("probe_workpaper", _value, frozenset({"ssn_last4"})))
    assert field_owner("probe_workpaper").tri_fields == {"ssn_last4"}
    register_suggestion_target("probe_workpaper")
    check_suggestion_target("probe_workpaper")
    with pytest.raises(ValueError, match="snake_case"):
        register_proposal_adapter("Probe-Kind", _raises)  # type: ignore[arg-type]  # shape only
