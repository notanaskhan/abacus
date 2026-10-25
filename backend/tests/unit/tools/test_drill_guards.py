"""Security review (S8 wave B, HIGH 1): `abacus_tools.drill verify` swaps only the host of the
production owner and app URLs, so the host is the one thing that decides where the production
database password goes. It must be the drill's own restore (`abacus-drill-<run id>`, an RDS
endpoint in a US region), and every connection must verify the server against the RDS CA bundle
(`ABACUS_DATABASE_CA_FILE`), refused before anything connects."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus_tools import drill
from abacus_tools.release import OPS_COMMANDS

GOOD_HOST = "abacus-drill-18734512345.c9akciq32xyz.us-east-2.rds.amazonaws.com"


@pytest.mark.parametrize(
    "host",
    [
        GOOD_HOST,
        "abacus-drill-1.abcdefghijkl.us-west-2.rds.amazonaws.com",
    ],
)
def test_the_drill_instance_endpoint_is_accepted(host: str) -> None:
    assert drill.check_restored_host(host) == host


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.test",
        "localhost",
        "10.20.3.4",
        "abacus-production.c9akciq32xyz.us-east-2.rds.amazonaws.com",  # the source itself
        f"{GOOD_HOST}.evil.example.test",
        "abacus-drill-12.c9akciq32xyz.eu-west-1.rds.amazonaws.com",  # not a US region
        "abacus-drill-abc.c9akciq32xyz.us-east-2.rds.amazonaws.com",  # not a run id
        "x.abacus-drill-12.c9akciq32xyz.us-east-2.rds.amazonaws.com",
        "ABACUS-DRILL-12.C9AKCIQ32XYZ.US-EAST-2.RDS.AMAZONAWS.COM:5432",
        "",
    ],
)
def test_any_other_host_is_refused(host: str) -> None:
    with pytest.raises(drill.Refused):
        drill.check_restored_host(host)


@pytest.fixture
def no_connections(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Any attempt to connect is recorded and fails the test."""
    tried: list[str] = []

    async def refuse(*args: object, **kwargs: object) -> drill.DrillReport:
        tried.append("verify")
        raise AssertionError("the drill connected before its guards passed")

    monkeypatch.setattr(drill, "verify", refuse)
    yield tried
    settings.cache_clear()


def _argv(host: str) -> list[str]:
    return [
        "verify",
        "--env",
        "production",
        "--restored-host",
        host,
        "--restore-point",
        "2026-12-08T03:14:00Z",
        "--replica-bucket",
        "abacus-production-evidence-replica",
    ]


def test_a_foreign_host_is_refused_before_anything_connects(
    no_connections: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert drill.main(_argv("evil.example.test")) == 2
    assert no_connections == []
    assert "abacus-drill-" in capsys.readouterr().err


def test_the_rds_ca_bundle_is_required_before_anything_connects(
    no_connections: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ABACUS_DATABASE_CA_FILE", raising=False)
    settings.cache_clear()
    assert drill.main(_argv(GOOD_HOST)) == 2
    monkeypatch.setenv("ABACUS_DATABASE_CA_FILE", str(tmp_path / "missing.pem"))
    settings.cache_clear()
    assert drill.main(_argv(GOOD_HOST)) == 2
    assert no_connections == []


def test_drill_verify_is_not_an_ops_request_command() -> None:
    """It runs only from drill.yml, which builds the host from the restore it just made."""
    assert not any(command.startswith("abacus_tools.drill") for command in OPS_COMMANDS)
