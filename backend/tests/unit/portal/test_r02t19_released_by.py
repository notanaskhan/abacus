"""R-02-T19 (TASK-6620; POR-08 a): an approval item names who in the firm released it, and when.

The send record's person (`actor_id`) and time come through the provider as
`released_by_user_id` and `released_at`; the portal answers the person's display name, never the
id, and nothing when the provider has no send record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from abacus.modules.engagements.api import ApprovalItem, user_of
from abacus.modules.portal import approvals_contract as contract

PRIYA = uuid4()
AT = datetime(2026, 9, 14, 21, 25, tzinfo=UTC)


def _item(by: UUID | None) -> ApprovalItem:
    return ApprovalItem(
        kind="fs_draft",
        item_id=uuid4(),
        scope_kind="work_item",
        scope_id=uuid4(),
        sent_to_client=True,
        title="Financial statements · draft 3",
        state="waiting",
        seen_hash="a" * 64,
        released_by_user_id=by,
        released_at=AT if by is not None else None,
    )


def test_the_send_records_person_reads_as_a_user_id() -> None:
    assert user_of(str(PRIYA)) == PRIYA
    assert user_of(None) is None
    assert user_of("system:portal") is None  # a system actor is no person


def test_the_detail_names_the_person_never_the_id() -> None:
    out = contract._detail(_item(PRIYA), ("ask",), {PRIYA: "Priya Raman"})  # pyright: ignore[reportPrivateUsage] -- the mapper
    assert (out.released_by, out.released_at) == ("Priya Raman", AT)
    assert str(PRIYA) not in out.model_dump_json()


def test_no_send_record_answers_nothing() -> None:
    out = contract._detail(_item(None))  # pyright: ignore[reportPrivateUsage] -- the mapper
    assert (out.released_by, out.released_at) == (None, None)
