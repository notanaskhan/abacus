"""T-04-T29 (TASK-6828): the invalidations that carry the return workspace's counts to a second
tab, the two new events' identifier-only payloads, and the section id on worksheet fields."""

from __future__ import annotations

import uuid

from abacus.kernel import realtime
from abacus.modules.notifications.realtime import register
from abacus.modules.review.events import IssueStatusChanged
from abacus.modules.tax.review_tree import DocumentApprovalChanged
from abacus.modules.tax.workspace_contract import WorksheetSectionOut

WORKSPACE_EVENTS = {
    "document_approval.changed": ("document_approval", "approval_id"),
    "issue.status_changed": ("issue", "issue_id"),
    "checkpoint.recorded": ("checkpoint", "checkpoint_id"),
    "checkpoint.approved": ("checkpoint", "checkpoint_id"),
    "checkpoint.rejected": ("checkpoint", "checkpoint_id"),
    "sign_off.recorded": ("sign_off", "sign_off_id"),
}


def test_each_workspace_event_invalidates_the_engagement_and_the_return() -> None:
    register()
    for event_type, (ref_type, ref_field) in WORKSPACE_EVENTS.items():
        found = realtime.invalidation_of(event_type)
        assert found is not None, event_type
        assert (found.ref_type, found.ref_field) == (ref_type, ref_field)
        assert found.topic_fields == (
            ("engagement", "engagement_id"),
            ("work_item", "work_item_id"),
        )


def test_a_field_value_is_not_an_invalidation() -> None:
    # A bulk import writes thousands of field versions; none of them moves a count.
    register()
    assert realtime.invalidation_of("field.value_recorded") is None


def test_the_new_events_carry_identifiers_and_codes_only() -> None:
    approval = DocumentApprovalChanged(
        approval_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        work_item_id=uuid.uuid4(),
        kind="approve",
    )
    assert approval.event_type == "document_approval.changed"
    assert set(approval.model_dump()) - {"event_id"} == {
        "approval_id",
        "engagement_id",
        "work_item_id",
        "kind",
    }
    moved = IssueStatusChanged(issue_id=uuid.uuid4(), engagement_id=None, status="resolved")
    assert moved.event_type == "issue.status_changed"
    assert set(moved.model_dump()) - {"event_id"} == {"issue_id", "engagement_id", "status"}


def test_a_section_names_its_sign_off_target() -> None:
    section = uuid.uuid4()
    out = WorksheetSectionOut(key="income", title="Income", fields=[], section_id=section)
    assert out.model_dump(mode="json")["section_id"] == str(section)
    assert WorksheetSectionOut(key="k", title="t", fields=[]).section_id is None
