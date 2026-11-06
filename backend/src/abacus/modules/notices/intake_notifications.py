"""The C16 producers for an intake and a new notice (N-04-T07; N-04 §4.6): `notice_intake_ready`
to the intake's owner, `notice_created` to the assignee and anyone the person chose to notify.
Identifiers only; the text is rendered client-side and names no amount."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from abacus.modules.notifications.api import register_kind_source


async def _intake_owner(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    del tenant_id
    return [UUID(str(payload["owner_id"]))]


async def _assignee_and_notified(tenant_id: UUID, payload: dict[str, object]) -> list[UUID]:
    del tenant_id
    notified = cast("Sequence[object]", payload.get("notify_user_ids") or ())
    people = {UUID(str(u)) for u in notified}
    if payload.get("assignee_id") is not None:
        people.add(UUID(str(payload["assignee_id"])))
    return sorted(people)


def register_kinds() -> None:
    register_kind_source(
        "notice_intake_ready",
        "notice_intake.ready",
        _intake_owner,
        ("notice_intake", "intake_id"),
        engagement_key=None,
    )
    register_kind_source(
        "notice_created",
        "notice.created",
        _assignee_and_notified,
        ("notice", "work_item_id"),
        engagement_key=None,
    )
