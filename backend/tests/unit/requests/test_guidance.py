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


def test_ac5_drafted_guidance_reaches_clients_only_when_the_firm_allows() -> None:
    """SPEC-035 AC-5 (TASK-073; ADR-111)."""
    from abacus.modules.requests.guidance import for_client

    assert for_client("drafted", "bank_statement", shown=True) is None  # the item's own
    assert for_client("drafted", "bank_statement", shown=False) == KIND_DEFAULTS["bank_statement"]
    assert for_client("drafted", None, shown=False) == Guidance()  # nothing
    assert for_client("firm", None, shown=False) is None  # only drafted text is held back


def test_ac6_approved_drafted_guidance_stands_when_the_kind_changes() -> None:
    assert after_kind_change(Guidance("x", source="drafted"), "schedule") is None
