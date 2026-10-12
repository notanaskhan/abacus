"""SPEC-031 (TASK-060): guidance defaults and the client's estimate."""

from __future__ import annotations

from abacus.modules.requests.guidance import (
    KIND_DEFAULTS,
    Guidance,
    after_kind_change,
    estimate_minutes,
    for_new_item,
)


def test_ac2_template_text_wins_over_the_kind_default() -> None:
    made = for_new_item(Guidance("Ours", None, True, "large"), "bank_statement")
    assert made == Guidance("Ours", None, True, "large", "template")


def test_ac2_without_template_text_the_kind_default_applies() -> None:
    made = for_new_item(Guidance(blocks_fieldwork=True), "ar_aging")
    assert made.why == KIND_DEFAULTS["ar_aging"].why
    assert made.blocks_fieldwork
    assert made.effort == "small"
    assert made.source == "kind_default"


def test_ac2_with_neither_the_fields_are_empty() -> None:
    assert for_new_item(None, None) == Guidance()


def test_every_document_kind_has_copy_within_the_limit() -> None:
    assert set(KIND_DEFAULTS) == {"bank_statement", "ar_aging", "ap_aging", "schedule"}
    for g in KIND_DEFAULTS.values():
        assert (
            g.why and g.good_looks_like and len(g.why) <= 1000 and len(g.good_looks_like) <= 1000
        )


def test_ac2_kind_copy_follows_the_kind_but_firm_and_template_text_stand() -> None:
    current = for_new_item(None, "bank_statement")
    assert after_kind_change(current, "schedule") == KIND_DEFAULTS["schedule"]
    assert after_kind_change(current, None) == Guidance()
    assert after_kind_change(Guidance("x", source="firm"), "schedule") is None
    assert after_kind_change(Guidance("x", source="template"), "schedule") is None


def test_ac6_estimate_counts_an_unestimated_item_as_medium() -> None:
    assert estimate_minutes(["small", "large", None]) == 15 + 120 + 45
    assert estimate_minutes([]) == 0
