"""AC-9, AC-20: the fake connector passes the conformance suite and its own contract
(TASK-010a interface contract, "Connector contract and fake connector")."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.modules.connections.api import (
    CONNECTORS,
    Connector,
    ConnectorError,
    FakeConnector,
    NotSupported,
    Period,
    RunFailed,
    Unavailable,
    connector_for,
    fixture_path,
    is_retryable,
)
from abacus.modules.connections.fake import DEMO_CREDENTIALS
from abacus.modules.connections.models import Connection
from abacus.modules.identity.api import Forbidden
from abacus.modules.ledger.api import NormaliseError, Unvalidated
from abacus.modules.requests.api import ItemNotFulfillable
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import write_fault, write_raw, write_trial_balance

from .conformance import (
    CONTRACT_METHODS,
    Check,
    Harness,
    HarnessFactory,
    conformance_params,
    run_check,
)

PERIOD = Period(date(2025, 1, 1), date(2025, 12, 31))


def fake_harness(scratch: Path) -> Harness:
    connection_id = uuid.uuid4()
    entity = generate(7).client_entities[0]
    tb = entity.trial_balances[-1]
    path = write_trial_balance(
        scratch, connection_id, tb, period_start=entity.period_start, entity_name=entity.name
    )
    return Harness(
        FakeConnector(connection_id, scratch),
        {"trial_balance": (Period(entity.period_start, tb.as_of), path.read_bytes())},
    )


@pytest.mark.parametrize(("factory", "check"), conformance_params({"fake": fake_harness}))
async def test_ac20_fake_connector_passes_the_conformance_suite(
    factory: HarnessFactory, check: Check, tmp_path: Path
) -> None:
    await run_check(check, factory, tmp_path)


def test_ac20_connector_is_abstract_in_every_contract_method() -> None:
    assert Connector.__abstractmethods__ == CONTRACT_METHODS
    with pytest.raises(TypeError):
        Connector()  # pyright: ignore[reportAbstractUsage] -- proving it cannot be built


def test_ac20_errors_are_typed_and_carry_a_code() -> None:
    assert ConnectorError("x").code == "x"
    assert issubclass(Unavailable, ConnectorError)
    assert issubclass(NotSupported, ConnectorError)
    assert Unavailable("provider_unavailable").code == "provider_unavailable"


def test_ac9_fixture_path_is_under_the_directory_and_connection(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    path = fixture_path(tmp_path, connection_id, "trial_balance", PERIOD)
    assert path.parent == tmp_path / str(connection_id)
    assert path.name.startswith("trial_balance-")
    assert PERIOD.start.isoformat() in path.name
    assert PERIOD.end.isoformat() in path.name


async def test_ac9_the_fake_returns_the_fixture_file_byte_for_byte(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    content = b'{"anything": "the provider sent"}\n  '
    write_raw(tmp_path, connection_id, PERIOD, content)
    raw = await FakeConnector(connection_id, tmp_path).pull("trial_balance", PERIOD, None)
    assert raw.content == content


async def test_ac9_the_fake_reads_the_path_fixture_path_names(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    path = fixture_path(tmp_path, connection_id, "trial_balance", PERIOD)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"[1, 2, 3]")
    raw = await FakeConnector(connection_id, tmp_path).pull("trial_balance", PERIOD, None)
    assert raw.content == b"[1, 2, 3]"


async def test_ac9_the_fake_keeps_connections_apart(tmp_path: Path) -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    write_raw(tmp_path, mine, PERIOD, b"{}")
    with pytest.raises(ConnectorError) as raised:
        await FakeConnector(other, tmp_path).pull("trial_balance", PERIOD, None)
    assert raised.value.code == "no_data"


async def test_ac9_a_period_with_no_fixture_is_no_data(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    write_raw(tmp_path, connection_id, PERIOD, b"{}")
    other = Period(date(2024, 1, 1), date(2024, 12, 31))
    with pytest.raises(ConnectorError) as raised:
        await FakeConnector(connection_id, tmp_path).pull("trial_balance", other, None)
    assert raised.value.code == "no_data"
    assert not isinstance(raised.value, Unavailable)


async def test_ac11_a_fault_fixture_is_unavailable(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    write_fault(tmp_path, connection_id, PERIOD)
    with pytest.raises(Unavailable) as raised:
        await FakeConnector(connection_id, tmp_path).pull("trial_balance", PERIOD, None)
    assert raised.value.code == "provider_unavailable"


@pytest.mark.parametrize(
    "content",
    [b"not json at all", b"\xff\xfe\x00 bad utf-8", b'{"fault": "other"}', b"[]", b""],
    ids=["text", "bytes", "other-fault", "array", "empty"],
)
async def test_ac11_malformed_bytes_are_returned_as_they_are(
    tmp_path: Path, content: bytes
) -> None:
    connection_id = uuid.uuid4()
    write_raw(tmp_path, connection_id, PERIOD, content)
    raw = await FakeConnector(connection_id, tmp_path).pull("trial_balance", PERIOD, None)
    assert raw.content == content


async def test_ac20_health_is_true_only_when_the_directory_exists(tmp_path: Path) -> None:
    connection_id = uuid.uuid4()
    assert await FakeConnector(connection_id, tmp_path).health() is True
    assert await FakeConnector(connection_id, tmp_path / "missing").health() is False
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")
    assert await FakeConnector(connection_id, a_file).health() is False


def test_ac20_the_fake_declares_a_trial_balance_only_read_connector() -> None:
    capabilities = FakeConnector(uuid.uuid4(), Path("unused")).capabilities()
    assert capabilities.datasets == frozenset({"trial_balance"})
    # SPEC-020 (TASK-036 D2): the demo sign-in.
    assert capabilities.oauth is True


@pytest.mark.parametrize(
    "code",
    ["Bad Code", "x" * 51, "", "1abc", "with-dash", "café", "Provider said: <script>", "A"],
)
def test_ac20_a_code_that_is_not_a_safe_slug_becomes_provider_error(code: str) -> None:
    assert ConnectorError(code).code == "provider_error"
    assert str(ConnectorError(code)) == "provider_error"


@pytest.mark.parametrize("code", ["no_data", "a", "x" * 50, "provider_unavailable"])
def test_ac20_a_safe_slug_code_is_kept(code: str) -> None:
    assert ConnectorError(code).code == code


def test_ac20_only_unavailable_is_retryable() -> None:
    assert Unavailable("provider_unavailable").retryable is True
    assert ConnectorError("no_data").retryable is False
    assert NotSupported("oauth").retryable is False


def test_ac20_is_retryable_follows_the_contract() -> None:
    assert is_retryable(Unavailable("provider_unavailable")) is True
    assert is_retryable(ConnectorError("no_data")) is False
    assert is_retryable(NotSupported("oauth")) is False
    for terminal in (
        RunFailed("failed", "no_data"),
        NotFound("sync_run"),
        Forbidden("evidence.upload", "role"),
        Unvalidated("unbalanced"),
        NormaliseError("malformed_payload"),
        ItemNotFulfillable("ready_for_review"),
    ):
        assert is_retryable(terminal) is False
    for transient in (RuntimeError("db"), OSError("net"), TimeoutError(), ValueError("x")):
        assert is_retryable(transient) is True


def _connection(provider: str) -> Connection:
    return Connection(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        client_entity_id=uuid.uuid4(),
        provider=provider,
        status="active",
        scopes=[],
        expires_at=None,
        created_by="test-seed",
        created_at=datetime.now(UTC),
    )


def test_ac20_the_registry_knows_the_fake_provider() -> None:
    assert "fake" in CONNECTORS


def test_ac20_an_unknown_provider_has_no_connector() -> None:
    with pytest.raises(ConnectorError) as raised:
        connector_for(_connection("quickbooks"))
    assert raised.value.code == "unknown_provider"


def test_ac20_the_fake_connector_is_built_from_the_directory_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path))
    settings.cache_clear()
    try:
        assert isinstance(connector_for(_connection("fake")), FakeConnector)
    finally:
        monkeypatch.undo()
        settings.cache_clear()


def test_ac20_the_fake_connector_without_a_directory_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABACUS_FAKE_CONNECTOR_DIR", raising=False)
    settings.cache_clear()
    try:
        with pytest.raises(ConnectorError) as raised:
            connector_for(_connection("fake"))
        assert raised.value.code == "connector_unavailable"
    finally:
        settings.cache_clear()


async def test_spec020_ac2_the_fake_demo_sign_in_returns_to_the_redirect_with_the_state() -> None:
    fake = FakeConnector(uuid.uuid4(), Path("unused"))
    url = await fake.authorise_url("s-1_x", "https://app.example.test/client/connect/callback")
    assert url == "https://app.example.test/client/connect/callback?state=s-1_x&code=demo"
    assert await fake.exchange_code("demo", "https://app.example.test/cb") == DEMO_CREDENTIALS


@pytest.mark.parametrize("code", ["", "Demo", "demo2"])
async def test_spec020_ac2_the_fake_refuses_any_other_code(code: str) -> None:
    with pytest.raises(ConnectorError) as raised:
        await FakeConnector(uuid.uuid4(), Path("unused")).exchange_code(code, "https://x.test/cb")
    assert raised.value.code == "access_denied"


async def test_spec020_ac2_the_fake_refuses_a_state_it_would_have_to_escape() -> None:
    with pytest.raises(ConnectorError):
        await FakeConnector(uuid.uuid4(), Path("unused")).authorise_url("a&b=c", "https://x.test")
