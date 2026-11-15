"""T-07-T03 part (TASK-8069; T-07 §4.8; SPEC-656 AC-4.1): the reading's C13 gate and C16 kinds
register, name the right people and carry identifiers only."""

from __future__ import annotations

import uuid

import pytest

import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the gate
from abacus.kernel.classification import restricted_fields, unclassified_fields
from abacus.modules.notifications import catalogue
from abacus.modules.notifications.kinds import AGENT_KINDS, kind_of
from abacus.modules.review import gates
from abacus.modules.tax import instrument_events as ev
from abacus.modules.tax import instrument_gates

TENANT = uuid.uuid4()


def test_the_approval_gate_is_a_sign_off_request_on_the_interpretation_events() -> None:
    source = gates._SOURCES[instrument_gates.SUBJECT]  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert source.kind == "sign_off_request"
    assert source.events == {
        "instrument_interpretation.adopted",
        "instrument_interpretation.approved",
        "instrument_interpretation.reopened",
    }
    assert source.read_action == "instrument.read"


def test_the_two_kinds_are_registered_and_the_reader_offers_no_inline_action() -> None:
    ready, finished = (
        kind_of("instrument_interpretation_ready"),
        kind_of("instrument_read_finished"),
    )
    assert ready is not None and ready.category == "approval"
    assert finished is not None and finished.category == "run" and not finished.inline_actions
    assert "instrument_read_finished" in AGENT_KINDS
    assert catalogue.CATALOGUE["instrument_interpretation.adopted"].kind == ready.code
    assert catalogue.CATALOGUE["instrument_read.finished"].kind == finished.code
    for event in ("instrument_interpretation.adopted", "instrument_read.finished"):
        assert "{subject}" in catalogue.TEMPLATES[event]


async def test_ready_goes_to_the_managers_but_never_the_adopter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engagement, kevin, samuel, rosa = (uuid.uuid4() for _ in range(4))

    async def managers(_tenant: uuid.UUID, e: uuid.UUID) -> list[uuid.UUID]:
        return [kevin, samuel, rosa] if e == engagement else []

    monkeypatch.setattr(catalogue, "engagement_managers", managers)
    recipients = await catalogue.CATALOGUE["instrument_interpretation.adopted"].recipients(
        TENANT, {"engagement_id": str(engagement), "by_user": str(kevin)}
    )
    assert recipients == [samuel, rosa]


async def test_finished_goes_to_the_person_who_started_the_read() -> None:
    who = uuid.uuid4()
    recipients = await catalogue.CATALOGUE["instrument_read.finished"].recipients(
        TENANT, {"user_id": str(who)}
    )
    assert recipients == [who]


def test_the_events_carry_identifiers_and_codes_only() -> None:
    for model in (
        ev.InstrumentInterpretationAdopted,
        ev.InstrumentInterpretationApproved,
        ev.InstrumentInterpretationReopened,
        ev.InstrumentReadFinished,
    ):
        assert unclassified_fields(model) == [], model.__name__
        assert restricted_fields(model) == [], model.__name__
        assert model.event_type.startswith(("instrument_interpretation.", "instrument_read."))
    finished = ev.InstrumentReadFinished(
        run_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        work_item_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        outcome="refused",
        code="consent_required",
    )
    assert set(finished.model_dump()) >= {"run_id", "user_id", "outcome", "code"}


def test_a_gate_whose_read_action_is_not_a_read_is_refused_at_registration() -> None:
    """DEC-5061: C13 filters rows with `visible()`, which takes reads only."""

    async def nothing(*_: object) -> list[gates.OpenGate]:
        return []

    with pytest.raises(ValueError, match="is not a read"):
        gates.register_gate_source(
            gates.GateSource(
                "probe_decision_gate",
                "final_approval",
                "close_plan.publish",
                frozenset({"close_plan.published"}),
                nothing,
            )
        )
