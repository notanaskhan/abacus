"""N-01-T11 (TASK-1746; DEC-836) against Postgres: E0 with `--slice firm_inbox` loads the docs@
mailbox through the intake service and foots from the rows: 17 threads, 18 messages, 23
attachments waiting, 4 threads unmatched (their files `new`), Varga's file ignored, W0's three
filed files not loaded, the Intake team with Grace Holloway on it, and the export's per-thread
waiting counts."""

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
from abacus_tools.synthetic.scenarios.brightwater_hale import firm_inbox, loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
BUCKET: Final = "n01t11-evidence"


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
    configure_key_service(LocalKeyService(b"n01t11-scenario-master-key-0123456789ab"))
    storage.configure_storage(client, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


async def test_ac_e0_with_the_slice_foots_from_the_rows(
    migrated_db: MigratedDatabase, wired: None
) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    await loader.load(migrated_db.superuser_dsn, "E0", slices=(firm_inbox.SLICE,), wait=False)
    tenant = loader.TENANT

    async def count(sql: str) -> int:
        return int(str(await seed.value(sql, tenant)))

    assert await count("SELECT count(*) FROM inbox_threads WHERE tenant_id = $1") == 17
    assert await count("SELECT count(*) FROM inbound_messages WHERE tenant_id = $1") == 18
    assert (
        await count(
            "SELECT count(*) FROM inbox_attachments WHERE tenant_id = $1 AND status = 'waiting'"
        )
        == 23
    )
    assert (
        await count(
            "SELECT count(*) FROM inbox_threads WHERE tenant_id = $1 AND client_id IS NULL"
        )
        == 4
    )
    assert (
        await count(
            "SELECT count(*) FROM inbox_attachments WHERE tenant_id = $1 AND status = 'new'"
        )
        == 4
    )
    assert (
        await count(
            "SELECT count(*) FROM inbox_attachments WHERE tenant_id = $1 AND status = 'ignored'"
        )
        == 1
    )
    assert (
        await count(
            "SELECT count(*) FROM inbox_attachments WHERE tenant_id = $1 AND status = 'filed'"
        )
        == 0
    )

    # Per thread, as the export has it (one sender per thread; a thread keeps its first subject).
    rows = await seed.rows(
        "SELECT t.sender_display, count(a.id) FILTER (WHERE a.status = 'waiting') AS waiting "
        "FROM inbox_threads t LEFT JOIN inbox_attachments a ON a.thread_id = t.id "
        "WHERE t.tenant_id = $1 GROUP BY t.id, t.sender_display",
        tenant,
    )
    loaded = sorted((str(r["sender_display"]), int(r["waiting"])) for r in rows)
    exported = json.loads(firm_inbox.EXPORT.read_text("utf-8"))["inbox"]["threads"]
    assert loaded == sorted((str(t["sender"]), int(t["waiting"])) for t in exported)

    # The Intake team, with Grace Holloway on it.
    team = await seed.rows(
        "SELECT t.kind, r.user_id FROM teams t JOIN team_rosters r ON r.team_id = t.id "
        "WHERE t.tenant_id = $1 AND t.name = 'Intake'",
        tenant,
    )
    assert [(r["kind"], r["user_id"]) for r in team] == [
        ("intake", loader.user_id_of(loader._SEATS["GH"]))  # pyright: ignore[reportPrivateUsage]  # the loader's own seat map
    ]
