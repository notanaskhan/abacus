"""Session fixtures for integration tests: the same images `docker compose` runs (ADR-077).

Images are read from the repo's `docker-compose.yml`, the single source of truth, and started with
testcontainers once per test session. Credentials are fixed local values.
"""

from __future__ import annotations

import socket
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import yaml
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer

REPO = Path(__file__).resolve().parents[3]
S3_ACCESS = "abacus"
S3_SECRET = "abacuslocal"


def compose_image(service: str) -> str:
    loaded = cast(dict[str, object], yaml.safe_load((REPO / "docker-compose.yml").read_text()))
    services = cast(dict[str, dict[str, object]], loaded["services"])
    return str(services[service]["image"])


def _wait(check: object, what: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if callable(check) and check():
                return
        except OSError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{what} did not become ready within {timeout:.0f}s")


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    with PostgresContainer(
        compose_image("db"), username="postgres", password="postgres", dbname="abacus", driver=None
    ) as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def s3_settings() -> Iterator[dict[str, str]]:
    container = (
        DockerContainer(compose_image("s3"))
        .with_env("ROOT_ACCESS_KEY", S3_ACCESS)
        .with_env("ROOT_SECRET_KEY", S3_SECRET)
        .with_command("--health /health posix --versioning-dir /versions /data")
        .with_tmpfs_mount("/data")
        .with_tmpfs_mount("/versions")
        .with_exposed_ports(7070)
    )
    with container:
        endpoint = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(7070)}"

        def healthy() -> bool:
            with urllib.request.urlopen(f"{endpoint}/health", timeout=2) as response:
                return response.status == 200

        _wait(healthy, "S3 gateway")
        yield {
            "endpoint_url": endpoint,
            "access_key": S3_ACCESS,
            "secret_key": S3_SECRET,
            "region": "us-east-1",
        }


@pytest.fixture(scope="session")
def temporal_target() -> Iterator[str]:
    container = (
        DockerContainer(compose_image("temporal"))
        .with_command("server start-dev --ip 0.0.0.0")
        .with_exposed_ports(7233)
    )
    with container:
        host, port = container.get_container_host_ip(), int(container.get_exposed_port(7233))

        def healthy() -> bool:
            with socket.create_connection((host, port), timeout=2):
                pass
            result = container.exec(["temporal", "operator", "cluster", "health"])
            return result.exit_code == 0

        _wait(healthy, "Temporal")
        yield f"{host}:{port}"
