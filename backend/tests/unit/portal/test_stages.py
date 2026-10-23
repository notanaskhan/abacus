"""P-08-T12: the client stage projection (POR-02; DEC-209). Every registry code maps; no firm word
leaks; the golden rows from the screen contract project as drawn."""

from __future__ import annotations

from enum import StrEnum
from typing import get_args

import pytest

from abacus.kernel._statuses import AuditEngagementStatus, CloseStatus, ReturnStatus
from abacus.modules.portal import stages
from abacus.modules.portal.contract import PillCode, StageCode

OBJECTS: dict[stages.Kind, type[StrEnum]] = {
    "return_1040": ReturnStatus,
    "return_entity": ReturnStatus,
    "close": CloseStatus,
    "audit": AuditEngagementStatus,
    "soc2": AuditEngagementStatus,
}
CASES = [(kind, code.value) for kind, enum in OBJECTS.items() for code in enum]


def test_every_kind_has_a_registry_object() -> None:
    assert set(OBJECTS) == set(get_args(stages.Kind)) == set(stages.STAGES)


@pytest.mark.parametrize(("kind", "code"), CASES)
def test_every_registry_code_maps_to_one_stage_or_done(kind: stages.Kind, code: str) -> None:
    assert code in stages.MAPS[kind]
    view = stages.client_view(kind, code)
    if view is None:
        return
    states = [s.state for s in view.stages]
    assert states.count("current") == 1
    at = states.index("current")
    assert all(s == "done" for s in states[:at])
    assert all(s == "upcoming" for s in states[at + 1 :])
    assert [s.code for s in view.stages] == list(stages.STAGES[kind])
    assert view.variant == "state"  # never red to the client (POR-02)


@pytest.mark.parametrize("kind", list(stages.MAPS))
def test_maps_hold_no_codes_outside_the_registry(kind: stages.Kind) -> None:
    assert set(stages.MAPS[kind]) == {c.value for c in OBJECTS[kind]}


def test_projections_only_use_contract_codes() -> None:
    stage_codes, pill_codes = set(get_args(StageCode)), set(get_args(PillCode))
    for order in stages.STAGES.values():
        assert set(order) <= stage_codes
    for table in stages.MAPS.values():
        for found in table.values():
            if found is not None:
                assert found[0] in stage_codes and found[1] in pill_codes


def test_golden_feld_1040_in_review_is_at_review() -> None:
    view = stages.client_view("return_1040", ReturnStatus.IN_REVIEW)
    assert view is not None
    assert [(s.code, s.state) for s in view.stages] == [
        ("gather_documents", "done"),
        ("prepare", "done"),
        ("review", "current"),
        ("sign_form_8879", "upcoming"),
        ("file", "upcoming"),
    ]
    assert view.pill == "reviewing_return"


def test_golden_action_required_reads_as_review_not_a_problem() -> None:
    assert stages.client_view("return_1040", ReturnStatus.ACTION_REQUIRED) == stages.client_view(
        "return_1040", ReturnStatus.IN_REVIEW
    )


def test_golden_granite_peak_audit_is_at_statements_review() -> None:
    view = stages.client_view("audit", AuditEngagementStatus.COMPLETION)
    assert view is not None
    assert [s.code for s in view.stages if s.state == "current"] == ["statements_review"]
    assert view.pill == "finishing_audit"


def test_golden_soc2_fieldwork_is_testing_with_description_done() -> None:
    view = stages.client_view("soc2", AuditEngagementStatus.FIELDWORK)
    assert view is not None
    assert dict((s.code, s.state) for s in view.stages)["system_description"] == "done"
    assert view.pill == "testing_under_way"


def test_golden_close_in_progress_is_reconciling() -> None:
    view = stages.client_view("close", CloseStatus.IN_PROGRESS)
    assert view is not None and view.pill == "reconciling_accounts"
    assert [s.code for s in view.stages if s.state == "current"] == ["reconcile"]


def test_entity_returns_have_no_8879_stage() -> None:
    view = stages.client_view("return_entity", ReturnStatus.APPROVED)
    assert view is not None
    assert "sign_form_8879" not in [s.code for s in view.stages]
    assert [s.code for s in view.stages if s.state == "current"] == ["file"]


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("return_1040", ReturnStatus.ACCEPTED),
        ("close", CloseStatus.DELIVERED),
        ("close", CloseStatus.LOCKED),
        ("audit", AuditEngagementStatus.RELEASED),
        ("soc2", AuditEngagementStatus.ARCHIVED),
    ],
)
def test_finished_items_have_no_card(kind: stages.Kind, code: str) -> None:
    assert stages.client_view(kind, code) is None


def test_filed_and_accepted_is_the_success_pill() -> None:
    view = stages.filed_and_accepted()
    assert view.pill == "filed_and_accepted" and view.variant == "success"


def test_an_unknown_code_is_a_caller_bug() -> None:
    with pytest.raises(stages.UnknownStatus):
        stages.client_view("close", "in_review_manager")
