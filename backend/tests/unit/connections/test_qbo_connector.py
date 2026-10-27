"""A-02-T26 (TASK-1612; DEC-70, DEC-709): the QuickBooks Online read connector.

"Against recorded synthetic sandbox responses the connector yields a balanced snapshot through
the existing pipeline, and the interception harness proves it sends no write-shaped request"
(A-02-T26 acceptance). The provider is replaced by a recording client that answers recorded,
synthetic responses (no real company data); the connector passes the conformance suite; every
request it sends is a GET or HEAD, or a POST to one of the two OAuth paths the registry declares
as reads; the kernel's egress client refuses any other POST; the report normalises to a balanced
trial balance, through the pipeline's own normaliser dispatch.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.egress import EgressClient, EgressRefused, EgressResponse, configure_egress
from abacus.modules.connections.connector import ConnectorError, Period
from abacus.modules.connections.connectors import quickbooks_online as qbo
from abacus.modules.connections.qbo_format import parse_qbo_trial_balance
from abacus.modules.integrations.api import egress_allowlist, egress_read_posts
from abacus.modules.ledger.api import NormaliseError

from .conformance import Check, Harness, HarnessFactory, conformance_params, run_check

FIXTURE = Path(__file__).parent / "fixtures" / "qbo_trial_balance_synthetic.json"
PERIOD = Period(date(2026, 1, 1), date(2026, 8, 31))
REALM = "9341453052194873"
APP = qbo.QboApp("synthetic-client-id", "synthetic-client-secret", "sandbox")


ROTATED = "rt-2"


def _tokens(refresh: str = ROTATED) -> bytes:
    return json.dumps(
        {"access_token": "at-2", "refresh_token": refresh, "expires_in": 3600}
    ).encode()


@dataclass
class Recorder:
    """Stands in for `kernel.egress.EgressClient`: records every request, answers recorded
    synthetic responses."""

    sent: list[tuple[str, str]] = field(default_factory=lambda: list[tuple[str, str]]())
    report: bytes = field(default_factory=FIXTURE.read_bytes)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> EgressResponse:
        self.sent.append((method.upper(), url))
        if qbo.OAUTH_PATH in url:
            return EgressResponse(200, {}, _tokens())
        if qbo.REVOKE_PATH in url:
            return EgressResponse(200, {}, b"")
        if "/reports/TrialBalance" in url:
            return EgressResponse(200, {}, self.report)
        if "/companyinfo/" in url:
            return EgressResponse(200, {}, b'{"CompanyInfo": {"Id": "1"}}')
        return EgressResponse(404, {}, b"")


def _held(expires_in: timedelta = timedelta(hours=1)) -> bytes:
    return qbo.QboCredentials("at-1", "rt-1", REALM, system_now() + expires_in).sealed_form()


def _connector(
    recorder: Recorder, credentials: bytes | None = None, rotated: list[bytes] | None = None
) -> qbo.QuickBooksOnlineConnector:
    async def on_rotate(blob: bytes) -> None:
        if rotated is not None:
            rotated.append(blob)

    return qbo.QuickBooksOnlineConnector(
        APP, cast(EgressClient, recorder), credentials, on_rotate=on_rotate
    )


def qbo_harness(scratch: Path) -> Harness:
    return Harness(
        _connector(Recorder(), _held()), {"trial_balance": (PERIOD, FIXTURE.read_bytes())}
    )


@pytest.mark.parametrize(
    ("factory", "check"), conformance_params({"quickbooks_online": qbo_harness})
)
async def test_ac20_the_qbo_connector_passes_the_conformance_suite(
    factory: HarnessFactory, check: Check, tmp_path: Path
) -> None:
    await run_check(check, factory, tmp_path)


async def test_a02t26_every_request_is_a_read() -> None:
    recorder = Recorder()
    connector = _connector(recorder)
    url = await connector.authorise_url(
        "state-1", "https://app.example.test/cb", code_challenge="c1"
    )
    assert url.startswith(qbo.AUTHORISE_URL) and "scope=com.intuit.quickbooks.accounting" in url
    blob = await connector.exchange_code(
        f"code-1{qbo.REALM_SEPARATOR}{REALM}", "https://app.example.test/cb", code_verifier="v1"
    )
    assert blob is not None
    await connector.pull("trial_balance", PERIOD, None)
    await connector.health()
    await connector.revoke()
    posts = {(m, u.split("?")[0]) for m, u in recorder.sent if m == "POST"}
    declared = {("POST", f"https://{h}{p}") for h, p in egress_read_posts()}
    assert posts and posts <= declared
    assert {m for m, _u in recorder.sent} <= {"GET", "HEAD", "POST"}
    api = qbo.API_HOSTS["sandbox"]
    assert all(m == "GET" for m, u in recorder.sent if api in u)


async def test_a02t26_the_egress_client_refuses_a_post_to_the_books() -> None:
    configure_egress(egress_allowlist(), egress_read_posts())
    client = EgressClient()
    try:
        with pytest.raises(EgressRefused):
            await client.request(
                "POST", f"https://{qbo.API_HOSTS['sandbox']}/v3/company/{REALM}/journalentry"
            )
        with pytest.raises(EgressRefused):
            await client.request("PUT", f"https://{qbo.OAUTH_HOST}{qbo.OAUTH_PATH}")
    finally:
        await client.close()
        configure_egress(frozenset())


async def test_a02t26_the_authorisation_needs_pkce_and_the_company() -> None:
    connector = _connector(Recorder())
    with pytest.raises(ConnectorError, match="pkce_required"):
        await connector.authorise_url("s", "https://app.example.test/cb")
    with pytest.raises(ConnectorError, match="invalid_realm"):
        await connector.exchange_code("code-1", "https://app.example.test/cb", code_verifier="v")


async def test_a02t26_a_rotated_refresh_token_is_resealed() -> None:
    rotated: list[bytes] = []
    connector = _connector(Recorder(), _held(timedelta(minutes=1)), rotated)
    await connector.refresh()
    assert len(rotated) == 1
    assert qbo.QboCredentials.opened(rotated[0]).refresh_token == ROTATED


async def test_a02t26_a_refused_refresh_is_token_expired() -> None:
    class Refusing(Recorder):
        async def request(self, method: str, url: str, **_: object) -> EgressResponse:
            return EgressResponse(400, {}, b'{"error": "invalid_grant"}')

    connector = _connector(Refusing(), _held(timedelta(minutes=1)))
    with pytest.raises(ConnectorError, match="token_expired"):
        await connector.refresh()


def test_a02t26_the_report_normalises_to_a_balanced_trial_balance() -> None:
    tb = parse_qbo_trial_balance(FIXTURE.read_bytes())
    assert (tb.period_start, tb.period_end, tb.currency) == (PERIOD.start, PERIOD.end, "USD")
    assert len(tb.lines) == 11
    assert tb.total_debit == tb.total_credit == tb.declared_debit == tb.declared_credit
    contra = next(line for line in tb.lines if line.account_code == "40")
    assert (contra.debit, str(contra.credit)) == (0, "4200.00")  # moved by code, not a model


_TOTAL = (
    '{"Summary": {"ColData": [{"value": "TOTAL"}, {"value": "274715.35"}, '
    '{"value": "274715.35"}]}, "type": "Section", "group": "GrandTotal"}'
)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (_TOTAL, '{"ColData": [{"value": "x", "id": "1"}, {"value": ""}, {"value": ""}]}'),
        ('"84210.55"', '"8.4e4"'),
        ('"Operating Checking"', '"Operating \\u202eChecking"'),
    ],
    ids=["no_total", "exponent", "bidi_override"],
)
def test_a02t26_hostile_reports_are_refused(old: str, new: str) -> None:
    text = json.dumps(json.loads(FIXTURE.read_bytes()))
    assert old in text
    with pytest.raises(NormaliseError):
        parse_qbo_trial_balance(text.replace(old, new).encode())


def test_a02t26_the_pipeline_dispatches_qbo_runs_to_this_normaliser() -> None:
    source = (Path(__file__).parents[3] / "src/abacus/modules/connections/pipeline.py").read_text()
    assert "run.source == QBO_PROVIDER" in source
    assert "parse_qbo_trial_balance(content)" in source
