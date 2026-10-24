"""The audits cockpit's registration slots (A-01-T02; SPEC-330 AC-7): a section needs a state
provider, a taken key refuses a different registration, rows come back in rail order, tags
respect their classification and segments their entitlement."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from uuid import UUID

import pytest

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext
from abacus.modules.assurance import sections
from abacus.modules.assurance.sections import IndexTag, SectionState


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(sections, "_SECTIONS", {})
    monkeypatch.setattr(sections, "_TAGS", {})
    monkeypatch.setattr(sections, "_SEGMENTS", {})
    yield


async def _tb(_tenant: TenantContext, _work_item: UUID) -> SectionState | None:
    return SectionState(AuditSectionStatus.DRAFT_READY, "sub_line", "Complete · 9:26 AM")


async def _other(_tenant: TenantContext, _work_item: UUID) -> SectionState | None:
    return None


async def _tags(_tenant: TenantContext, _ids: Sequence[UUID]) -> Mapping[UUID, Sequence[IndexTag]]:
    return {}


async def _more_tags(
    _tenant: TenantContext, _ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    return {}


def test_ac7_a_section_without_a_state_provider_is_refused() -> None:
    with pytest.raises(ValueError, match="state provider"):
        sections.register_audit_section("trial_balance", "planning", 10, "AUD-06", None)
    assert sections.registered_sections() == ()


def test_ac7_a_taken_key_refuses_a_different_registration_but_takes_itself_again() -> None:
    sections.register_audit_section("trial_balance", "planning", 10, "AUD-06", _tb)
    sections.register_audit_section("trial_balance", "planning", 10, "AUD-06", _tb)
    with pytest.raises(ValueError, match="already registered"):
        sections.register_audit_section("trial_balance", "planning", 10, "AUD-06", _other)
    with pytest.raises(ValueError, match="already registered"):
        sections.register_audit_section("trial_balance", "fieldwork", 10, "AUD-06", _tb)


def test_ac7_an_unknown_band_is_refused() -> None:
    with pytest.raises(ValueError, match="band"):
        sections.register_audit_section("x", "nowhere", 1, "AUD-06", _tb)  # pyright: ignore[reportArgumentType] -- the refusal under test


def test_ac7_rows_come_back_in_rail_order() -> None:
    sections.register_audit_section("testing", "fieldwork", 20, "AUD-12", _other)
    sections.register_audit_section("materiality", "planning", 20, "AUD-07", _other)
    sections.register_audit_section("trial_balance", "planning", 10, "AUD-06", _tb)
    sections.register_audit_section("source_documents", "overview", 40, "AUD-03", _other)
    keys = [s.key for s in sections.registered_sections()]
    assert keys == ["source_documents", "trial_balance", "materiality", "testing"]


def test_ac7_metadata_only_roles_see_only_metadata_tags() -> None:
    sections.register_index_tag("letter_sent", _tags, "metadata")
    sections.register_index_tag("materiality_pending", _more_tags, "content")
    assert [t.name for t in sections.registered_index_tags(metadata_only=True)] == ["letter_sent"]
    assert [t.name for t in sections.registered_index_tags(metadata_only=False)] == [
        "letter_sent",
        "materiality_pending",
    ]
    with pytest.raises(ValueError, match="already registered"):
        sections.register_index_tag("letter_sent", _tags, "content")


def test_ac7_segments_follow_their_entitlement_in_segmented_order() -> None:
    sections.register_audit_segment("soc", "soc")
    sections.register_audit_segment("ebp", None)
    sections.register_audit_segment("fs", None)
    assert [s.family for s in sections.registered_segments(frozenset())] == ["fs", "ebp"]
    assert [s.family for s in sections.registered_segments(frozenset({"soc"}))] == [
        "fs",
        "ebp",
        "soc",
    ]
    with pytest.raises(ValueError, match="already registered"):
        sections.register_audit_segment("soc", "attest")
