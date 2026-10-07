"""A throwaway stack (Postgres, Versity S3, Temporal) and a seeded synthetic firm, for tooling that
runs the real platform outside pytest: the replay recorders and the evaluation runner (TASK-020
D2). Containers come from the compose images (`compose_image`) and are removed on exit."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import asyncpg
import httpx
from temporalio.client import Client
from testcontainers.core.container import DockerContainer

from abacus.kernel.db import TenantContext, configure_engine, configure_identity_engine
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.connections.api import Period
from abacus.modules.evidence.storage import configure_storage
from abacus.modules.identity.api import AuthContext
from abacus_tools.quality.schema_check import compose_image, provisioned_database
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.model import TrialBalance

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

_LOCAL_S3 = ("abacus", "abacuslocal")


@dataclass(frozen=True)
class Stack:
    """Throwaway services a recorder runs against: database URLs, S3 client, Temporal target."""

    app_url: str
    identity_url: str
    superuser: str
    s3: S3Client
    target: str


@dataclass(frozen=True)
class Seeded:
    """One firm with one engagement, a senior member, two open items and a fake connection."""

    tenant: uuid.UUID
    user: uuid.UUID
    engagement: uuid.UUID
    items: list[uuid.UUID]
    connection: uuid.UUID

    def context(self) -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant, "human", str(self.user)),
            self.user,
            uuid.UUID(int=2),
            None,
            None,
        )


async def connect(stack: Stack) -> Client:
    """Point the platform at the stack and return a Temporal client using its converter."""
    configure_engine(stack.app_url)
    configure_identity_engine(stack.identity_url)
    configure_storage(stack.s3, "abacus-evidence")
    client = await Client.connect(stack.target, data_converter=data_converter())
    configure_temporal_client(client)
    return client


async def seed(superuser: str) -> Seeded:
    tenant = uuid.UUID(int=1)
    conn = await asyncpg.connect(superuser)
    try:
        await conn.execute("INSERT INTO firms VALUES ($1, 'Recorder firm')", tenant)
        user = await conn.fetchval(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('recorder', 'recorder', 'recorder@example.com', 'Recorder') RETURNING id"
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id) VALUES ($1, $2)", tenant, user
        )
        client_id = await conn.fetchval(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Example client') RETURNING id",
            tenant,
        )
        entity = await conn.fetchval(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Example') "
            "RETURNING id",
            tenant,
            client_id,
        )
        engagement = await conn.fetchval(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, 'FY', $4, $5, $6) RETURNING id",
            tenant,
            client_id,
            entity,
            date(2025, 1, 1),
            date(2025, 12, 31),
            user,
        )
        await conn.execute(
            "INSERT INTO engagement_members VALUES ($1, $2, $3, 'senior')",
            tenant,
            engagement,
            user,
        )
        request_list = await conn.fetchval(
            "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
            tenant,
            engagement,
        )
        items = [
            await conn.fetchval(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) VALUES ($1, $2, $3, 'Trial balance', "
                "'general', $4) RETURNING id",
                tenant,
                engagement,
                request_list,
                user,
            )
            for _ in range(2)
        ]
        connection = await conn.fetchval(
            "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
            "VALUES ($1, $2, 'fake', 'recorder') RETURNING id",
            tenant,
            entity,
        )
    finally:
        await conn.close()
    return Seeded(tenant, user, engagement, items, connection)


def trial_balance() -> TrialBalance:
    return generate(7).client_entities[0].trial_balances[-1]


def period_of(tb: TrialBalance) -> Period:
    return Period(date(2025, 1, 1), tb.as_of)


def _wait(url: str) -> None:
    for _ in range(90):
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError(f"{url} did not become healthy")


def run_with_stack(record: Callable[[Stack], Coroutine[object, object, None]]) -> None:
    """Start throwaway S3, Temporal and Postgres containers and run `record` against them."""
    os.environ["ABACUS_FAKE_CONNECTOR_DIR"] = tempfile.mkdtemp()
    s3_container = (
        DockerContainer(compose_image("s3"))
        .with_env("ROOT_ACCESS_KEY", _LOCAL_S3[0])
        .with_env("ROOT_SECRET_KEY", _LOCAL_S3[1])
        .with_command("--health /health posix --versioning-dir /versions /data")
        .with_tmpfs_mount("/data")
        .with_tmpfs_mount("/versions")
        .with_exposed_ports(7070)
    )
    temporal = (
        DockerContainer(compose_image("temporal"))
        .with_command("server start-dev --ip 0.0.0.0")
        .with_exposed_ports(7233)
    )
    with s3_container, temporal:
        endpoint = (
            f"http://{s3_container.get_container_host_ip()}:{s3_container.get_exposed_port(7070)}"
        )
        _wait(endpoint + "/health")
        target = f"{temporal.get_container_host_ip()}:{temporal.get_exposed_port(7233)}"
        for _ in range(90):
            if temporal.exec(["temporal", "operator", "cluster", "health"]).exit_code == 0:
                break
            time.sleep(1)
        access, password = _LOCAL_S3
        s3 = s3_client(endpoint_url=endpoint, access_key=access, secret_key=password)
        s3.create_bucket(Bucket="abacus-evidence", ObjectLockEnabledForBucket=True)
        with provisioned_database(roundtrip=False) as db:
            asyncio.run(record(Stack(db.app_url, db.identity_url, db.superuser_dsn, s3, target)))
