"""S28 partials (TASK-3396, DEC-2395): a partner's L4 sign-off on a notice response is what moves
its notice to Approved; any other sign-off is ignored. The move itself, and drafting, Run, send
for signature and mark sent, run against Postgres in `test_n04t21_load.py`."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.modules.notices import sending

TENANT = uuid4()


def _event(target_type: str, level: int, target: UUID) -> OutboxEvent:
    return OutboxEvent(
        event_id=uuid4(),
        tenant_id=TENANT,
        event_type="sign_off.recorded",
        payload={"target_type": target_type, "target_id": str(target), "level": level},
    )


@pytest.fixture
def approved(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    calls: list[UUID] = []

    async def approve(_tenant: TenantContext, response_id: UUID) -> None:
        calls.append(response_id)

    monkeypatch.setattr(sending, "approve_when_signed", approve)
    return calls


async def test_ac_the_partners_sign_off_on_a_response_approves_its_notice(
    approved: list[UUID],
) -> None:
    response_id = uuid4()
    await sending.on_sign_off_recorded(_event("notice_response", 4, response_id))
    assert approved == [response_id]


@pytest.mark.parametrize(
    ("target_type", "level"), [("notice_response", 1), ("notice_response", 2), ("workpaper", 4)]
)
async def test_ac_any_other_sign_off_leaves_the_notice_alone(
    approved: list[UUID], target_type: str, level: int
) -> None:
    await sending.on_sign_off_recorded(_event(target_type, level, uuid4()))
    assert approved == []


def test_ac_the_notices_module_subscribes_to_sign_offs() -> None:
    from abacus.modules.notices import api

    assert api.SUBSCRIPTIONS["sign_off.recorded"] is sending.on_sign_off_recorded
