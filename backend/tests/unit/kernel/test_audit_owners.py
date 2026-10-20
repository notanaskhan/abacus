"""DEC-121: the registry the audit explorer reads to place an event's target with its engagement.
A kind has one owner; registering the same owner again is harmless."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import pytest

from abacus.kernel import audit_owners
from abacus.kernel.db import TenantContext


async def _owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    return {}


async def _other(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    return {}


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit_owners, "_ENGAGEMENT", {})
    monkeypatch.setattr(audit_owners, "_ENTITY", {})


def test_a_registered_kind_is_listed_under_its_owner_type() -> None:
    audit_owners.register_engagement_owners(["thing"], _owners)
    audit_owners.register_entity_owners({"snapshot"}, _other)
    assert audit_owners.engagement_owners() == {"thing": _owners}
    assert audit_owners.entity_owners() == {"snapshot": _other}


def test_registering_the_same_owner_again_is_harmless() -> None:
    audit_owners.register_engagement_owners(["thing"], _owners)
    audit_owners.register_engagement_owners(["thing"], _owners)
    assert list(audit_owners.engagement_owners()) == ["thing"]


def test_a_second_owner_for_a_kind_is_refused() -> None:
    audit_owners.register_engagement_owners(["thing"], _owners)
    with pytest.raises(RuntimeError, match="already has an owner"):
        audit_owners.register_engagement_owners(["thing"], _other)
    with pytest.raises(RuntimeError, match="already has an owner"):
        audit_owners.register_entity_owners(["thing"], _owners)


def test_the_lists_are_copies() -> None:
    audit_owners.engagement_owners()["x"] = _owners
    assert audit_owners.engagement_owners() == {}
