"""SPEC-025 AC-2 (roll-forward): a copied request keeps last year's client visibility. A new item
defaults to visible, so an item internal last year must be set back to internal. Found by
P-06-T07; before the fix, every rolled-forward request became client-visible."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests import roll_forward as rf


class _Tx:
    session = object()

    def record(self, *_: object, **__: object) -> None: ...

    def emit(self, *_: object, **__: object) -> None: ...


def _prior(visible: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        description="Bank statements",
        audit_area="cash",
        retrievability_tier="A",
        dataset=None,
        tier_source=None,
        tier_rule=None,
        document_kind=None,
        document_kind_source=None,
        why=None,
        good_looks_like=None,
        blocks_fieldwork=False,
        effort=None,
        guidance_source=None,
        guidance_approved_by=None,
        client_visible=visible,
        status="open",
    )


async def test_spec025_a_rolled_forward_request_keeps_last_years_visibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown, internal = _prior(True), _prior(False)
    created: list[uuid.UUID] = []
    visibility: dict[uuid.UUID, bool | None] = {}

    async def items(*_: object) -> list[SimpleNamespace]:
        return [shown, internal]

    async def request_list(*_: object) -> tuple[uuid.UUID, bool]:
        return uuid.uuid4(), False

    async def insert(_: object, *, item_id: uuid.UUID, **__: object) -> None:
        created.append(item_id)

    async def set_fields(_: object, item_id: uuid.UUID, *, client_visible: bool | None) -> None:
        visibility[item_id] = client_visible

    monkeypatch.setattr(rf, "items_to_roll_forward", items)
    monkeypatch.setattr(rf, "request_list_for", request_list)
    monkeypatch.setattr(rf, "insert_request_item", insert)
    monkeypatch.setattr(rf, "set_client_fields", set_fields)
    tenant = uuid.uuid4()
    person = uuid.uuid4()
    ctx = AuthContext(
        tenant=TenantContext(tenant, "human", str(person)),
        user_id=person,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=None,
    )
    copied = await rf.copy_items(
        cast(UnitOfWork, _Tx()), ctx, uuid.uuid4(), uuid.uuid4(), [shown.id, internal.id], []
    )
    assert copied == 2
    assert [visibility[i] for i in created] == [True, False]
