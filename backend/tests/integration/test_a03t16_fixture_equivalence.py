"""A-03-T16 AC-1, the export half (TASK-2719; DEC-1770; F-04.21; ADR-085): the committed AUD-11 and
AUD-31 fixture JSON at `2026-09-24T10:20` is what `make seed-demo --slice sampling` + the API
answer, byte for byte, once the server's own ids and the hashes made from them are stand-ins.
Re-export with `make fixtures SNAPSHOT=2026-09-24T10:20`; `seed/sampling.exported.test.ts` holds
fixture mode to the files.

The load gets its own database and bucket: the census and predecessor uploads are evidence."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Final

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import configure_engine
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic import fixture_export
from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, SCENARIO_VERSION

from .conftest import MigratedDatabase

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
SNAPSHOT: Final = fixture_export.SAMPLING_SNAPSHOT
BUCKET: Final = "a03t16-fixture-export"


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture
def wired(s3_settings: dict[str, str]) -> Iterator[None]:
    client: S3Client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    settings.cache_clear()
    reset_key_service()
    configure_key_service(LocalKeyService(b"a03t16-fixture-export-master-key-012345"))
    storage.configure_storage(client, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


async def test_ac1_the_committed_aud11_and_aud31_fixtures_equal_seed_demo_through_the_api(
    own_db: Database, wired: None
) -> None:
    await fixture_export.load(SNAPSHOT, own_db.superuser_dsn, own_db.app_url)
    found = await fixture_export.server_ids(SNAPSHOT, own_db.superuser_dsn)
    captured = await fixture_export.capture(
        SNAPSHOT, app_url=own_db.app_url, identity_url=own_db.identity_url, found=found
    )
    rendered = fixture_export.render(SNAPSHOT, captured, found)
    files = fixture_export.exported_files(fixture_export.EXPORTED, SNAPSHOT)
    committed = {p.name: p.read_text(encoding="utf-8") for p in files}
    hint = f"run `make fixtures SNAPSHOT={SNAPSHOT}`"
    assert sorted(committed) == sorted(rendered), hint
    for name, text in rendered.items():
        assert committed[name] == text, f"{name} differs: {hint}"


def test_every_sampling_fixture_names_its_scenario_snapshot_slice_and_persona() -> None:
    profile = fixture_export.PROFILES[SNAPSHOT]
    files = fixture_export.exported_files(fixture_export.EXPORTED, SNAPSHOT)
    assert len(files) == len(profile.reads)
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["scenario"] == {
            "version": SCENARIO_VERSION,
            "hash": SCENARIO_HASH,
            "snapshot": SNAPSHOT,
            "slices": ["sampling"],
        }, path.name
        assert doc["persona"] and doc["request"].startswith("GET /v1/"), path.name


def test_the_reads_are_aud11_a_and_f_and_aud31_f_as_their_viewers() -> None:
    reads = fixture_export.PROFILES[SNAPSHOT].reads
    assert [(r.name, r.persona) for r in reads] == [
        ("northwind-sample-sets", "marcus-delaney"),
        ("northwind-participants", "marcus-delaney"),
        ("northwind-participants-v2-items", "marcus-delaney"),
        ("northwind-participants-v2-population", "marcus-delaney"),
        ("granite-sample-sets", "simone-baptiste"),
        ("granite-disbursements", "simone-baptiste"),
        ("granite-disbursements-v1-items", "simone-baptiste"),
        ("granite-disbursements-v1-population", "simone-baptiste"),
        ("granite-mapping-sets", "caleb-dunn"),
        ("granite-mapping", "caleb-dunn"),
    ]
