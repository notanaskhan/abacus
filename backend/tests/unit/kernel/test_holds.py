"""Q-02 AC-37 (Q-02-T29): the hold-check slot fails closed. With no check registered nothing is
erasable, a held version is never among the erasable ones, and a second, different check is
refused."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence

import pytest

from abacus.kernel import holds
from abacus.kernel.db import TenantContext

TENANT = TenantContext(uuid.uuid4(), "system", "probe")
HELD, FREE = uuid.uuid4(), uuid.uuid4()


async def _check(tenant: TenantContext, version_ids: Sequence[uuid.UUID]) -> frozenset[uuid.UUID]:
    return frozenset(v for v in version_ids if v == HELD)


async def _other(tenant: TenantContext, version_ids: Sequence[uuid.UUID]) -> frozenset[uuid.UUID]:
    return frozenset()


@pytest.fixture(autouse=True)
def restore() -> Iterator[None]:
    before = holds.hold_check()
    holds.reset_hold_check()
    yield
    holds.reset_hold_check()
    if before is not None:
        holds.register_hold_check(before)


async def test_ac37_without_a_check_the_caller_erases_nothing() -> None:
    with pytest.raises(holds.HoldCheckMissing):
        await holds.erasable_versions(TENANT, [FREE])
    with pytest.raises(holds.HoldCheckMissing):
        await holds.held_versions(TENANT, [])


async def test_ac37_a_held_version_is_never_erasable() -> None:
    holds.register_hold_check(_check)
    assert await holds.erasable_versions(TENANT, [HELD, FREE]) == [FREE]
    assert await holds.held_versions(TENANT, [HELD, FREE]) == frozenset({HELD})
    assert await holds.held_versions(TENANT, []) == frozenset()


def test_one_check_only() -> None:
    holds.register_hold_check(_check)
    holds.register_hold_check(_check)  # the same one again (a reloaded api.py) is fine
    with pytest.raises(ValueError, match="already registered"):
        holds.register_hold_check(_other)


def test_evidence_registers_its_check_on_import() -> None:
    from abacus.modules.evidence import holds as evidence_holds

    holds.register_hold_check(evidence_holds.holds_covering)
    assert holds.hold_check() is evidence_holds.holds_covering
