"""DEC-582 (DEC-518 follow-up): each connector reaches only its own hosts. A client built for a
connector, and a sign-in URL checked for one, refuse another connector's host; the union is the
ceiling; module code always names its connector."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from abacus.kernel import egress
from abacus.kernel.egress import (
    EgressClient,
    EgressRefused,
    check_egress,
    check_sign_in_url,
    configure_egress,
)

SRC = Path(egress.__file__).resolve().parents[1]  # src/abacus


@pytest.fixture(autouse=True)
def two_connectors() -> Iterator[None]:
    configure_egress(
        frozenset({"api.ledger-a.test", "login.ledger-a.test", "api.ledger-b.test"}),
        by_connector={
            "ledger_a": frozenset({"api.ledger-a.test", "login.ledger-a.test"}),
            "ledger_b": frozenset({"api.ledger-b.test", "not-in-the-union.test"}),
        },
    )
    yield
    configure_egress(frozenset())


def test_a_connector_reaches_its_own_hosts() -> None:
    assert check_egress("https://api.ledger-a.test/v3/accounts", "ledger_a").host == (
        "api.ledger-a.test"
    )


def test_a_connector_is_refused_another_connectors_host() -> None:
    with pytest.raises(EgressRefused, match=r"api\.ledger-b\.test"):
        check_egress("https://api.ledger-b.test/v1/x", "ledger_a")


def test_an_undeclared_connector_reaches_nothing() -> None:
    with pytest.raises(EgressRefused):
        check_egress("https://api.ledger-a.test/v3/accounts", "ledger_c")


def test_a_connectors_hosts_never_exceed_the_union() -> None:
    with pytest.raises(EgressRefused):
        check_egress("https://not-in-the-union.test/", "ledger_b")


def test_the_sign_in_url_is_held_to_its_connector() -> None:
    url = "https://login.ledger-a.test/oauth2?state=s"
    assert check_sign_in_url(url, "ledger_a") == url
    with pytest.raises(EgressRefused):
        check_sign_in_url(url, "ledger_b")


async def test_a_client_built_for_a_connector_refuses_another_host_before_sending() -> None:
    client = EgressClient("ledger_a")
    try:
        with pytest.raises(EgressRefused):
            await client.request("GET", "https://api.ledger-b.test/v1/x")
    finally:
        await client.close()


def _unnamed_clients(path: Path) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name == "EgressClient" and not node.args and not node.keywords:
            found.append(f"{path.relative_to(SRC)}:{node.lineno}")
        if name == "check_sign_in_url" and len(node.args) + len(node.keywords) < 2:
            found.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return found


@pytest.mark.source_scan
def test_module_code_always_names_its_connector() -> None:
    unnamed = [
        hit for path in sorted((SRC / "modules").rglob("*.py")) for hit in _unnamed_clients(path)
    ]
    assert unnamed == []
