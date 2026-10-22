"""P-04-T02: the review grammar's status words are in the registry and generated.

Stored codes match the CHECK lists in docs/plan/epics/P-04.md section 4 (ADR-160, ADR-161);
words the sources compute (a sign-off slot, a field value pill, the checkpoint "Current" tag) are
derived and never stored.
"""

from __future__ import annotations

from typing import cast

import pytest

from abacus.kernel import _statuses
from abacus_tools.codegen import status_vocabulary as subject

STORED_BY_P04 = {
    "review_note": ("open", "responded", "cleared", "closed", "withdrawn"),
    "decision_card": ("awaiting_role", "decided", "superseded"),
    "checkpoint": ("proposed", "approved", "rejected", "saved"),
    "issue": ("open", "in_progress", "resolved", "verified", "reopened", "not_applicable"),
    "issue_audit_route": (
        "under_evaluation",
        "converted_to_misstatement",
        "converted_to_deficiency",
    ),
    "suggestion": ("pending", "adopted", "edited", "dismissed", "superseded", "expired"),
    "proposal": ("pending", "approved", "approved_with_edits", "rejected", "superseded"),
}

DERIVED_ONLY = {
    "sign_off_slot": {"signed", "stale"},
    "field_value": {"updated", "edited", "estimate", "unsupported"},
}


def _registry() -> dict[str, dict[str, dict[str, object]]]:
    objects = subject.parse(subject.SOURCE.read_text(encoding="utf-8"))
    return {o.name: {c.code: c.fields for c in o.codes} for o in objects}


@pytest.mark.parametrize(("obj", "codes"), sorted(STORED_BY_P04.items()))
def test_t02_stored_codes_match_the_p04_check_lists(obj: str, codes: tuple[str, ...]) -> None:
    assert _statuses.STORED[obj] == codes


def test_t02_the_issue_check_is_the_issue_and_audit_route_codes() -> None:
    union = set(_statuses.STORED["issue"]) | set(_statuses.STORED["issue_audit_route"])
    assert len(union) == 9


def test_t02_checkpoint_current_is_a_derived_tag() -> None:
    current = _registry()["checkpoint"]["current"]
    assert current["derived"] is True and current["variant"] == "tag"
    assert "current" not in {c.value for c in _statuses.CheckpointStatus}


@pytest.mark.parametrize(("obj", "codes"), sorted(DERIVED_ONLY.items()))
def test_t02_computed_review_words_are_never_stored(obj: str, codes: set[str]) -> None:
    entries = _registry()[obj]
    assert set(entries) == codes
    assert all(e["derived"] is True for e in entries.values())
    assert _statuses.STORED[obj] == ()


@pytest.mark.parametrize(
    ("obj", "code", "label", "variant"),
    [
        ("sign_off_slot", "stale", "Changed after sign-off", "amber"),
        ("decision_card", "decided", "Decided", "green"),
        ("decision_card", "superseded", "Superseded by v{n}", "soon"),
        ("checkpoint", "rejected", "Rejected", "red-tint"),
        ("field_value", "unsupported", "Unsupported", "red-tint"),
        ("proposal", "pending", "Ready for review", "state"),
        ("proposal", "rejected", "Rejected", "red-tint"),
    ],
)
def test_t02_handoff_words_and_variants(obj: str, code: str, label: str, variant: str) -> None:
    entry = _registry()[obj][code]
    assert (entry["label"], entry["variant"]) == (label, variant)


def test_t02_no_approval_is_attributed_to_the_agent() -> None:
    for obj in ("proposal", "suggestion", "decision_card", "sign_off_slot"):
        for entry in _registry()[obj].values():
            words = [str(entry["label"])]
            labels = cast("dict[str, object]", entry.get("context_labels") or {})
            words += [str(v) for v in labels.values()]
            assert not any("Agent" in w for w in words), (obj, words)


def test_t02_the_ui_registry_carries_every_review_object() -> None:
    generated = subject.TS_TARGET.read_text(encoding="utf-8")
    for obj in (*STORED_BY_P04, *DERIVED_ONLY):
        assert f'"{obj}": {{' in generated, obj
