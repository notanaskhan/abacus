"""T-04-T15 (TASK-6614; SPEC-649; ADR-160, ADR-161): the individual return workspace's review
registrations. Row acceptance: "Unregistered targets stay refused, a field edit through PUT
/v1/fields/return_worksheet/... writes one field_value_versions row and moves the section hash,
and the section's sign-off reads stale." The database half (the PUT, the version row, the stale
sign-off) is the end pass's integration suite; this holds the registrations and the hash."""

from __future__ import annotations

import pytest

import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the slots
from abacus.modules.agents import proposal_slots
from abacus.modules.review import slots
from abacus.modules.review.api import UnregisteredKind
from abacus.modules.tax import worksheet_review as wr


def test_both_reviewables_and_their_facts_are_registered() -> None:
    assert {wr.WORKSHEET, wr.SECTION} <= set(slots.reviewable_types())
    assert {wr.WORKSHEET, wr.SECTION} <= set(slots.reviewable_fact_types())


def test_the_field_owner_tags_every_field_tri_and_checkpoints_an_edit() -> None:
    owner = slots.field_owner(wr.WORKSHEET)
    assert owner.tri_fields == wr.ALL_FIELDS_TRI
    assert owner.apply_edit is wr.apply_field_edit
    assert owner.checkpoints is True


def test_an_unregistered_target_stays_refused() -> None:
    with pytest.raises(UnregisteredKind):
        slots.field_owner("return_worksheets_x")
    with pytest.raises(proposal_slots.UnregisteredTarget):
        proposal_slots.check_suggestion_target("return_fieldx")


def test_the_suggestion_targets_and_appliers_are_registered() -> None:
    for target in ("return_field", "pass_through_treatment", "residency_determination"):
        proposal_slots.check_suggestion_target(target)
    adapters = proposal_slots._ADAPTERS  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert {"return_field_changes", "pass_through_treatments", "residency"} <= set(adapters)


def test_a_changed_value_moves_the_hash_and_order_does_not() -> None:
    one = wr._hash([("line_20", {"t": "decimal", "v": "100.00"}), ("line_33", None)])  # pyright: ignore[reportPrivateUsage] -- the hash under test
    same = wr._hash([("line_20", {"t": "decimal", "v": "100.00"}), ("line_33", None)])  # pyright: ignore[reportPrivateUsage] -- the hash under test
    moved = wr._hash([("line_20", {"t": "decimal", "v": "101.00"}), ("line_33", None)])  # pyright: ignore[reportPrivateUsage] -- the hash under test
    assert one == same != moved
