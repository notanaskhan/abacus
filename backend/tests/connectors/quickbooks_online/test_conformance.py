# ac-test-author: ayushkbhatia
"""A-02-T32 (TASK-1745; ADR-044, ADR-037, ADR-040; A-02 AC-12.1; DEC-835): the QuickBooks Online
connector and its pull pipeline, against the fake (every pull request) and the sandbox (nightly).

Acceptance (the task row): "The suite passes on the fake and on the sandbox, and a drifted fake
marks dependent journeys unverified in the weekly quality report" (the report half is
`test_drift_report.py`).

On each target: the contract surface is the connector port and nothing more; a refresh rotates
and reseals; a pull answers the period asked for, from the provider the pipeline dispatches on,
and normalises into a trial balance `ledger.validate` accepts (the pipeline's own gate); health
reads; anything undeclared is NotSupported; and every request is a read (GET to the API host, a
POST only to the two OAuth paths the registry declares). On the fake alone, the provider's
failure answers map to the short codes.
"""

from __future__ import annotations

import inspect
import json
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.egress import EgressResponse
from abacus.modules.connections.connector import (
    Connector,
    ConnectorError,
    NotSupported,
    Period,
    Unavailable,
)
from abacus.modules.connections.connectors import quickbooks_online as qbo
from abacus.modules.connections.pipeline import QBO_PROVIDER
from abacus.modules.connections.qbo_format import parse_qbo_trial_balance
from abacus.modules.integrations.api import egress_read_posts
from abacus.modules.ledger.api import validate

from . import targets

PORT = frozenset(
    {
        "capabilities",
        "authorise_url",
        "exchange_code",
        "refresh",
        "revoke",
        "pull",
        "changes_since",
        "fetch_attachment",
        "health",
    }
)


async def _ready(target: targets.Target) -> qbo.QuickBooksOnlineConnector:
    connector = target.connector()
    await connector.refresh()  # the sandbox's credentials start expired; the fake's are fresh
    return connector


# --- The contract surface ------------------------------------------------------------------------


async def test_the_connector_is_the_port_and_nothing_more(target: targets.Target) -> None:
    connector = target.connector()
    assert isinstance(connector, Connector)
    public = {
        name
        for name, _member in inspect.getmembers(type(connector), inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == PORT
    capabilities = connector.capabilities()
    assert capabilities.datasets == frozenset({"trial_balance"})
    assert (capabilities.oauth, capabilities.incremental, capabilities.attachments) == (
        True,
        False,
        False,
    )


async def test_undeclared_reads_are_not_supported(target: targets.Target) -> None:
    connector = await _ready(target)
    with pytest.raises(NotSupported):
        await connector.pull("general_ledger", target.period, None)  # type: ignore[arg-type]  # a dataset no connector declares here
    with pytest.raises(NotSupported):
        await connector.changes_since(system_now() - timedelta(days=1))
    with pytest.raises(NotSupported):
        await connector.fetch_attachment("attachment-1")


async def test_authorise_url_asks_only_for_the_read_scope_with_pkce(
    target: targets.Target,
) -> None:
    connector = target.connector()
    url = await connector.authorise_url(
        "state-a02t32", "https://app.example.test/oauth/callback", code_challenge="challenge-1"
    )
    assert url.startswith(qbo.AUTHORISE_URL + "?")
    assert "scope=com.intuit.quickbooks.accounting&" in url
    assert "code_challenge_method=S256" in url
    with pytest.raises(ConnectorError, match="pkce_required"):
        await connector.authorise_url("state-a02t32", "https://app.example.test/cb")


# --- Tokens -------------------------------------------------------------------------------------


async def test_a_refresh_due_rotates_and_hands_the_new_credentials_to_be_resealed(
    target: targets.Target,
) -> None:
    realm = qbo.QboCredentials.opened(target.credentials).realm_id
    due = targets.held(realm, expires_at=system_now() - timedelta(minutes=1))
    if target.name == "sandbox":
        due = target.credentials
    connector = target.connector(due)
    await connector.refresh()
    assert len(target.rotated) == 1
    rotated = qbo.QboCredentials.opened(target.rotated[0])
    assert rotated.realm_id == realm
    assert rotated.access_token != qbo.QboCredentials.opened(due).access_token
    assert rotated.expires_at > system_now()


async def test_a_fresh_token_is_not_refreshed(target: targets.Target) -> None:
    connector = await _ready(target)
    before = len(target.rotated)
    await connector.refresh()  # now fresh: nothing to do
    assert len(target.rotated) == before


# --- The pull and its pipeline ------------------------------------------------------------------


async def test_a_pull_answers_the_period_asked_for_from_the_provider_the_pipeline_reads(
    target: targets.Target,
) -> None:
    connector = await _ready(target)
    payload = await connector.pull("trial_balance", target.period, None)
    assert payload.source == QBO_PROVIDER == qbo.PROVIDER  # the pipeline's QBO dispatch
    assert payload.media_type == "application/json"
    assert payload.request == (
        f"trial_balance {target.period.start.isoformat()}..{target.period.end.isoformat()}"
    )
    header = cast(dict[str, object], json.loads(payload.content)["Header"])
    assert (header["StartPeriod"], header["EndPeriod"]) == (
        target.period.start.isoformat(),
        target.period.end.isoformat(),
    )


async def test_the_pull_normalises_into_a_trial_balance_the_pipeline_accepts(
    target: targets.Target,
) -> None:
    connector = await _ready(target)
    payload = await connector.pull("trial_balance", target.period, None)
    tb = parse_qbo_trial_balance(payload.content)
    problem = validate(tb, period_start=target.period.start, period_end=target.period.end)
    assert problem is None, problem
    assert tb.total_debit == tb.total_credit == tb.declared_debit == tb.declared_credit
    assert all(line.debit >= 0 and line.credit >= 0 for line in tb.lines)
    assert all(line.source_ref == f"qbo:account:{line.account_code}" for line in tb.lines)


async def test_health_reads_the_company(target: targets.Target) -> None:
    connector = await _ready(target)
    assert await connector.health() is True


# --- Read-only ----------------------------------------------------------------------------------


async def test_every_request_is_a_read(target: targets.Target) -> None:
    connector = await _ready(target)
    await connector.pull("trial_balance", target.period, None)
    await connector.health()
    api = qbo.API_HOSTS["sandbox"]
    declared = {f"https://{host}{path}" for host, path in egress_read_posts()}
    assert target.transport.sent
    for method, url in target.transport.sent:
        if method == "POST":
            assert url.split("?")[0] in declared, url
        else:
            assert method in ("GET", "HEAD"), (method, url)
            assert url.startswith(f"https://{api}/v3/company/"), url
    hosts = {url.split("/")[2] for _m, url in target.transport.sent}
    assert qbo.API_HOSTS["production"] not in hosts


# --- The fake alone: provider failures map to short codes ----------------------------------------


class Scripted:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status, self.body = status, body

    async def request(self, method: str, url: str, **_: object) -> EgressResponse:
        if qbo.OAUTH_PATH in url:
            return EgressResponse(self.status, {}, self.body)
        return EgressResponse(self.status, {}, self.body)


@pytest.mark.parametrize(
    ("status", "raised", "code"),
    [
        (401, ConnectorError, "token_expired"),
        (429, Unavailable, "provider_unavailable"),
        (503, Unavailable, "provider_unavailable"),
        (403, ConnectorError, "provider_error"),
        (404, ConnectorError, "provider_error"),
    ],
)
async def test_fake_a_provider_failure_on_a_read_is_a_short_code(
    tmp_path: Path, status: int, raised: type[Exception], code: str
) -> None:
    made = targets.fake(tmp_path, expires_at=system_now() + timedelta(hours=1))
    made.transport.inner = cast(targets.Transport, Scripted(status, b'{"Fault": "x"}'))
    with pytest.raises(raised) as caught:
        await made.connector().pull("trial_balance", made.period, None)
    assert getattr(caught.value, "code", str(caught.value)) == code
    assert b"Fault" not in str(caught.value).encode()  # provider text never leaves


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (400, b'{"error": "invalid_grant"}', "token_expired"),
        (400, b'{"error": "invalid_client"}', "access_denied"),
        (500, b"", "provider_unavailable"),
        (200, b"not json", "provider_error"),
    ],
)
async def test_fake_a_refused_refresh_is_a_short_code(
    tmp_path: Path, status: int, body: bytes, code: str
) -> None:
    made = targets.fake(tmp_path, expires_at=system_now() - timedelta(minutes=1))
    made.transport.inner = cast(targets.Transport, Scripted(status, body))
    with pytest.raises((ConnectorError, Unavailable)) as caught:
        await made.connector().refresh()
    assert getattr(caught.value, "code", str(caught.value)) == code
    assert made.rotated == []  # the old credentials stay sealed


async def test_fake_a_period_with_no_recording_is_a_provider_error(tmp_path: Path) -> None:
    made = targets.fake(tmp_path, expires_at=system_now() + timedelta(hours=1))
    other = Period(made.period.start, made.period.end - timedelta(days=1))
    with pytest.raises(ConnectorError, match="provider_error"):
        await made.connector().pull("trial_balance", other, None)
