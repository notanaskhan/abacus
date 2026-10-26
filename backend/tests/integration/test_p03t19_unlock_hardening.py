"""P-03-T19 security review fixes (DEC-425): M1, both unlock routes share one attempt budget per
person per version, and the older upload route refuses calls outside a person's own request;
L1, two people unlocking the same version at once yield one derivation and one 409.

Over HTTP with the wiring and world of the T21 independent suite (imported, not edited), so the
upload route sees a real request item and its upload.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import suppress

import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.unlock import UNLOCK_LIMIT, unlock_upload
from abacus.modules.identity.api import Forbidden
from abacus_tools.synthetic.documents import password_pdf

from . import test_p03t21_pii_masking_independent as t21
from .backfill.support import Person

BUCKET = "p03t19-unlock-hardening"  # this module's own: the T21 module makes and keeps its own


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> S3Client:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    # The other xdist worker may have made it for this module already.
    with suppress(client.exceptions.BucketAlreadyOwnedByYou):
        client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    return client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(t21.MASTER))
    storage.configure_storage(raw, BUCKET)
    forget_flags()
    yield
    forget_flags()
    storage.reset_storage()
    reset_key_service()


# The T21 suite's wiring, as this file's own fixtures (pytest finds them by name).
engines = t21.engines
idp = t21.idp
http = t21.http
net = t21.net
seed = t21.seed
world = t21.world
OPENS_WITH = t21.OPENS_WITH
World = t21.World


async def _upload_unlock(
    world: World, item: uuid.UUID, version: uuid.UUID, password: str
) -> httpx.Response:
    return await world.net.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/request-items/{item}/uploads/"
        f"{version}/unlock",
        world.client,
        body={"password": password},
    )


async def test_m1_the_upload_route_counts_failures_in_the_same_budget(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    for _ in range(UNLOCK_LIMIT):
        wrong = await _upload_unlock(world, upload.item, upload.version, "not-it")
        assert wrong.status_code == 422, wrong.text
    limited = await _upload_unlock(world, upload.item, upload.version, OPENS_WITH)
    assert limited.status_code == 429, limited.text
    assert limited.json()["detail"] == "unlock_rate_limited"
    failed = await world.count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_version.unlock_failed'",
        world.tenant_id,
    )
    assert failed == UNLOCK_LIMIT


async def test_m1_failures_on_one_route_count_on_the_other(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    # The client's budget is per person: the viewer route refuses clients outright, so spend the
    # client's on the upload route and check the viewer route for a person separately.
    for _ in range(UNLOCK_LIMIT):
        await world.unlock(upload.version, "not-it", world.samuel)
    viewer = await world.unlock(upload.version, OPENS_WITH, world.samuel)
    assert viewer.status_code == 429, viewer.text
    # Samuel is staff: the upload route is his too, and it shares his spent budget.
    staff = await world.net.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/request-items/{upload.item}/uploads/"
        f"{upload.version}/unlock",
        world.samuel,
        body={"password": OPENS_WITH},
    )
    assert staff.status_code == 429, staff.text


async def test_m1_the_upload_route_refuses_a_call_outside_a_request(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    with pytest.raises(Forbidden):
        await unlock_upload(
            t21._person(world.client),  # pyright: ignore[reportPrivateUsage] -- the suite's context
            world.site.engagement_id,
            upload.item,
            upload.version,
            OPENS_WITH,
        )


async def test_l1_two_people_unlocking_at_once_make_one_derivation(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    other: Person = await world.seed.person(world.tenant_id)
    await world.seed.member(world.site, other, "staff")
    first, second = await asyncio.gather(
        world.unlock(upload.version, OPENS_WITH, world.samuel),
        world.unlock(upload.version, OPENS_WITH, other),
    )
    answers = sorted([first.status_code, second.status_code])
    assert answers == [200, 409], (first.text, second.text)
    loser = first if first.status_code == 409 else second
    assert loser.json()["detail"] == "not_password_protected"
    derivations = await world.count(
        "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1", world.tenant_id
    )
    assert derivations == 1
