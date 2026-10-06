"""AC-20: the local stack (Postgres with pgvector, write-once storage, Temporal) works, pinned.

The services come from the session fixtures in `conftest.py`; the images come from the repo's
`docker-compose.yml`.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import boto3
import pytest
import yaml
from botocore.client import Config
from botocore.exceptions import ClientError
from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
from temporalio.client import Client
from types_boto3_s3 import S3Client

REPO = Path(__file__).resolve().parents[3]
PINNED_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


# --- docker-compose.yml ------------------------------------------------------------------------


def test_ac20_compose_defines_the_three_services() -> None:
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"db", "s3", "temporal"} <= set(compose["services"])


def test_ac20_every_compose_image_is_pinned_by_digest() -> None:
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    images = {
        name: service["image"]
        for name, service in compose["services"].items()
        if "image" in service
    }
    assert images
    unpinned = {name: image for name, image in images.items() if not PINNED_IMAGE.match(image)}
    assert unpinned == {}


def test_ac20_compose_services_do_not_build_images() -> None:
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    assert [name for name, svc in compose["services"].items() if "build" in svc] == []


# --- Postgres with pgvector --------------------------------------------------------------------


async def test_ac20_postgres_accepts_a_connection(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        assert await conn.fetchval("SELECT 1") == 1
    finally:
        await conn.close()


async def test_ac20_postgres_is_version_17(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        assert await conn.fetchval("SHOW server_version_num") >= "170000"
    finally:
        await conn.close()


async def test_ac20_pgvector_extension_can_be_created(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        name = await conn.fetchval("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        assert name == "vector"
    finally:
        await conn.close()


async def test_ac20_pgvector_value_round_trips(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        async with conn.transaction():
            await conn.execute("CREATE TEMP TABLE ac20_items (v vector(3)) ON COMMIT DROP")
            await conn.execute("INSERT INTO ac20_items (v) VALUES ($1::vector(3))", "[1,2.5,-3]")
            stored = await conn.fetchval("SELECT v::text FROM ac20_items")
        assert stored == "[1,2.5,-3]"
    finally:
        await conn.close()


async def test_ac20_pgvector_rejects_a_value_of_the_wrong_dimension(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        with pytest.raises(asyncpg.PostgresError):
            await conn.fetchval("SELECT $1::vector(3)", "[1,2]")
    finally:
        await conn.close()


async def test_ac20_pgvector_computes_distance(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        distance = await conn.fetchval("SELECT '[0,0,0]'::vector <-> '[3,4,0]'::vector")
        assert distance == pytest.approx(5.0)
    finally:
        await conn.close()


# --- S3-compatible storage with Object Lock ----------------------------------------------------


def _s3(settings: dict[str, str]) -> S3Client:
    # boto3-stubs overloads name every AWS service; only the s3 stub package is installed.
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- see comment above
        "s3",
        endpoint_url=settings["endpoint_url"],
        aws_access_key_id=settings["access_key"],
        aws_secret_access_key=settings["secret_key"],
        region_name=settings["region"],
        config=Config(s3={"addressing_style": "path"}),
    )


def _bucket_name() -> str:
    return f"ac20-{uuid.uuid4().hex[:16]}"


def test_ac20_s3_refuses_to_delete_a_locked_object_version(
    s3_settings: dict[str, str],
) -> None:
    s3 = _s3(s3_settings)
    bucket = _bucket_name()
    s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    version_id = ""
    try:
        put = s3.put_object(
            Bucket=bucket,
            Key="evidence.txt",
            Body=b"immutable",
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=datetime.now(UTC) + timedelta(days=1),
        )
        version_id = put["VersionId"]
        with pytest.raises(ClientError) as raised:
            s3.delete_object(Bucket=bucket, Key="evidence.txt", VersionId=version_id)
        assert raised.value.response.get("Error", {}).get("Code") == "AccessDenied"
        body = s3.get_object(Bucket=bucket, Key="evidence.txt", VersionId=version_id)["Body"]
        assert body.read() == b"immutable"
    finally:
        if version_id:
            s3.delete_object(
                Bucket=bucket,
                Key="evidence.txt",
                VersionId=version_id,
                BypassGovernanceRetention=True,
            )
        s3.delete_bucket(Bucket=bucket)


def test_ac20_s3_object_has_governance_retention_until_tomorrow(
    s3_settings: dict[str, str],
) -> None:
    s3 = _s3(s3_settings)
    bucket = _bucket_name()
    s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    version_id = ""
    try:
        until = datetime.now(UTC) + timedelta(days=1)
        put = s3.put_object(
            Bucket=bucket,
            Key="k",
            Body=b"x",
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=until,
        )
        version_id = put["VersionId"]
        retention = s3.get_object_retention(Bucket=bucket, Key="k", VersionId=version_id)
        held = retention.get("Retention", {})
        assert held.get("Mode") == "GOVERNANCE"
        until = held.get("RetainUntilDate")
        assert until is not None
        assert until > datetime.now(UTC) + timedelta(hours=23)
    finally:
        if version_id:
            s3.delete_object(
                Bucket=bucket, Key="k", VersionId=version_id, BypassGovernanceRetention=True
            )
        s3.delete_bucket(Bucket=bucket)


def test_ac20_s3_bucket_has_object_lock_enabled(s3_settings: dict[str, str]) -> None:
    s3 = _s3(s3_settings)
    bucket = _bucket_name()
    s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    try:
        config = s3.get_object_lock_configuration(Bucket=bucket)
        assert config.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") == "Enabled"
    finally:
        s3.delete_bucket(Bucket=bucket)


def test_ac20_s3_deletes_an_unlocked_object(s3_settings: dict[str, str]) -> None:
    s3 = _s3(s3_settings)
    bucket = _bucket_name()
    s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    put = s3.put_object(Bucket=bucket, Key="k", Body=b"x")
    s3.delete_object(Bucket=bucket, Key="k", VersionId=put["VersionId"])
    s3.delete_bucket(Bucket=bucket)


# --- Temporal ----------------------------------------------------------------------------------


async def test_ac20_temporal_accepts_a_tcp_connection(temporal_target: str) -> None:
    host, _, port = temporal_target.rpartition(":")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=10)
    writer.close()
    await writer.wait_closed()
    assert reader is not None


async def test_ac20_temporal_frontend_reports_system_info(temporal_target: str) -> None:
    client = await Client.connect(temporal_target)
    info = await client.workflow_service.get_system_info(GetSystemInfoRequest())
    assert info.server_version


async def test_ac20_temporal_frontend_reports_serving(temporal_target: str) -> None:
    client = await Client.connect(temporal_target)
    health = await client.service_client.check_health()
    assert health is True
