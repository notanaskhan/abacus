"""P-06-T18 (ADR-162 §5): envelope v2 with a detached key. The object carries no key; the wrapped
data key lives apart, and without it nothing opens. The binding, the tenant and the key ID are
bound, so an object can't be opened as another version, tenant or key."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace

import pytest

from abacus.kernel.crypto import (
    DecryptionError,
    LocalKeyService,
    configure_key_service,
    open_detached,
    open_sealed,
    reset_key_service,
    seal_detached,
    seal_under,
)

MASTER = b"unit-test-master-key-detached-0123456789"
TENANT = uuid.UUID(int=7)
OTHER = uuid.UUID(int=8)


@pytest.fixture(autouse=True)
def local_service() -> Iterator[None]:
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    yield
    reset_key_service()


async def test_t18_a_detached_object_round_trips_through_its_key() -> None:
    sealed, key = await seal_detached(TENANT, b"statement", "o:v1:fp")
    assert sealed[:4] == b"ABE2"
    assert key.wrapped not in sealed
    assert await open_detached(TENANT, sealed, "o:v1:fp", key) == b"statement"


async def test_t18_the_binding_tenant_and_key_are_bound() -> None:
    sealed, key = await seal_detached(TENANT, b"statement", "o:v1:fp")
    with pytest.raises(DecryptionError):
        await open_detached(TENANT, sealed, "o:v2:fp", key)
    with pytest.raises(DecryptionError):
        await open_detached(OTHER, sealed, "o:v1:fp", key)
    with pytest.raises(DecryptionError):
        await open_detached(TENANT, sealed, "o:v1:fp", replace(key, key_id="local:other"))
    _, another = await seal_detached(TENANT, b"other", "o:v1:fp")
    with pytest.raises(DecryptionError):
        await open_detached(TENANT, sealed, "o:v1:fp", another)


async def test_t18_derived_objects_share_the_versions_key() -> None:
    _, key = await seal_detached(TENANT, b"statement", "o:v1:fp")
    page = await seal_under(TENANT, b"png bytes", "d:v1:pagefp", key)
    assert await open_detached(TENANT, page, "d:v1:pagefp", key) == b"png bytes"


async def test_t18_v1_and_v2_envelopes_are_not_confused() -> None:
    sealed, key = await seal_detached(TENANT, b"statement", "fp")
    with pytest.raises(DecryptionError):
        await open_sealed(TENANT, sealed, "fp")
    with pytest.raises(DecryptionError):
        await open_detached(TENANT, b"ABE1" + bytes(64), "fp", key)
    with pytest.raises(DecryptionError):
        await open_detached(TENANT, b"ABE2" + bytes(8), "fp", key)
