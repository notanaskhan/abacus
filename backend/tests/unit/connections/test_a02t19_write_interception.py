"""A-02-T19 (TASK-1419; ADR-078 independent AC suite): the write-interception harness extension
and the outbound host allowlist, from ADR-040 ("a test fails if any connector issues a non-read
request"; "worker outbound traffic is restricted to approved provider hosts"), ADR-150 ("the
write-interception harness fails on any undeclared outbound non-GET request") and A-02 AC-12.2.

The harness (`write_interception.py`) is shown to fail on each seeded violation (a write-shaped
method, an undeclared host, plain HTTP, a client built around the kernel's) and to pass a declared
read; the kernel's egress client is shown to keep undeclared hosts and redirects off the network;
and the connectors main ships reach nothing at all.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import httpx
import pytest

from abacus.kernel.egress import EgressClient, EgressRefused, configure_egress
from abacus.modules.connections.api import CONNECTORS, NETWORKLESS_PROVIDERS, FakeConnector, Period
from abacus.modules.integrations.api import egress_allowlist, registry
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import write_trial_balance

from .write_interception import Interceptor, WriteIntercepted, intercept

HOST: Final = "api.probe-t19.example"
DECLARED: Final = frozenset({HOST})
READ_POST_PATH: Final = "/oauth2/v1/tokens/bearer"


@pytest.fixture
def egress() -> Iterator[EgressClient]:
    """The kernel's egress client, configured as start-up would for one declared host."""
    configure_egress(DECLARED)
    yield EgressClient()
    configure_egress(frozenset())


async def test_ac12_2_a_declared_read_passes_the_harness(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with intercept(monkeypatch, DECLARED) as harness:
        response = await egress.request("GET", f"https://{HOST}/v3/reports/TrialBalance")
        await egress.close()
    assert response.status_code == 200
    assert [(c.method, c.host) for c in harness.calls] == [("GET", HOST)]
    harness.assert_read_only()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_ac12_2_a_write_shaped_request_fails_the_harness(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """The seeded violation: a connector sending a write to its own declared host."""
    with intercept(monkeypatch, DECLARED) as harness:
        await egress.request(method, f"https://{HOST}/v3/company/1/journalentry")
        await egress.close()
    with pytest.raises(WriteIntercepted, match="write-shaped"):
        harness.assert_read_only()


async def test_ac12_2_only_an_allowlisted_provider_read_post_passes(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = frozenset({(HOST, READ_POST_PATH)})
    with intercept(monkeypatch, DECLARED, read_posts=allowed) as harness:
        await egress.request("POST", f"https://{HOST}{READ_POST_PATH}", data={"grant_type": "x"})
    harness.assert_read_only()
    with intercept(monkeypatch, DECLARED, read_posts=allowed) as harness:
        await egress.request("POST", f"https://{HOST}/v3/company/1/bill")
        await egress.close()
    with pytest.raises(WriteIntercepted, match="write-shaped"):
        harness.assert_read_only()


async def test_ac12_2_an_undeclared_host_never_leaves_the_process(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with intercept(monkeypatch, DECLARED) as harness:
        for url in (
            "https://evil.example/collect",
            f"http://{HOST}/v3/reports",  # the declared host over plain HTTP
            f"https://{HOST}.evil.example/",
        ):
            with pytest.raises(EgressRefused):
                await egress.request("GET", url)
        await egress.close()
    assert harness.calls == []


async def test_ac12_2_a_redirect_off_the_allowlist_is_not_followed(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def bounce(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    with intercept(monkeypatch, DECLARED, responder=bounce) as harness:
        response = await egress.request("GET", f"https://{HOST}/v3/reports")
        await egress.close()
    assert response.status_code == 302
    assert [c.host for c in harness.calls] == [HOST]
    harness.assert_read_only()


async def test_ac12_2_a_client_built_around_the_kernel_is_caught_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seeded violation: an undeclared host (and plain HTTP) through a hand-built client."""
    with intercept(monkeypatch, DECLARED) as harness:
        async with httpx.AsyncClient() as raw:
            await raw.get("https://undeclared.example/v1/accounts")
        with httpx.Client() as sync:
            sync.get(f"http://{HOST}/v3/reports")
    with pytest.raises(WriteIntercepted) as caught:
        harness.assert_read_only()
    assert "undeclared host" in str(caught.value) and "not HTTPS" in str(caught.value)


def test_ac12_2_the_harness_judges_each_rule_on_its_own() -> None:
    harness = Interceptor(DECLARED)
    for method, url in (
        ("GET", f"https://{HOST}/v3/reports"),
        ("HEAD", f"https://{HOST}/v3/reports"),
    ):
        harness.answer(httpx.Request(method, url))
    assert harness.violations() == []
    harness.answer(httpx.Request("DELETE", f"https://{HOST}/v3/account/7"))
    assert harness.violations() == [f"write-shaped request: DELETE https://{HOST}/v3/account/7"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1419 (ED-156): kernel.egress.EgressClient.request sends any HTTP method to an "
        "allowlisted host; ADR-040's enforcement says connector HTTP clients expose only GET "
        "(and provider read POSTs explicitly allowlisted)"
    ),
)
@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
async def test_adr040_the_connectors_client_refuses_write_methods_before_sending(
    egress: EgressClient, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    with intercept(monkeypatch, DECLARED) as harness:
        try:
            with pytest.raises(EgressRefused):
                await egress.request(method, f"https://{HOST}/v3/company/1/journalentry")
        finally:
            await egress.close()
    assert harness.calls == []


# --- the connectors main ships ----------------------------------------------------------------


def test_ac12_2_every_shipped_connector_reaches_no_host_or_a_declared_one() -> None:
    declared = {r.adapter_key for r in registry().read_connectors}
    networked = set(CONNECTORS) - NETWORKLESS_PROVIDERS
    assert networked <= declared
    assert egress_allowlist() == frozenset(
        h for r in registry().read_connectors for h in r.egress_hosts
    )


async def test_ac12_2_the_demo_ledger_pull_sends_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection_id = uuid.uuid4()
    entity = generate(7).client_entities[0]
    tb = entity.trial_balances[-1]
    write_trial_balance(
        tmp_path, connection_id, tb, period_start=entity.period_start, entity_name=entity.name
    )
    connector = FakeConnector(connection_id, tmp_path)
    with intercept(monkeypatch, egress_allowlist()) as harness:
        raw = await connector.pull("trial_balance", Period(entity.period_start, tb.as_of), None)
    assert raw.content
    assert harness.calls == []
    harness.assert_read_only()
