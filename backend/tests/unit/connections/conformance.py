"""The connector conformance suite (ADR-037, ADR-040; TASK-010a interface contract).

Every connector must pass it. A connector's test module supplies a `HarnessFactory` (a function
from a scratch directory to a `Harness`) and parametrises one test over `conformance_params`:

    @pytest.mark.parametrize(("factory", "check"), conformance_params({"fake": fake_harness}))
    async def test_ac20_connector_conformance(factory, check, tmp_path):
        await run_check(check, factory, tmp_path)

It lives under `tests/unit/connections/` because `make check` collects `tests/unit`, not a
top-level `tests/connectors`.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, get_args

import pytest

from abacus.modules.connections.api import (
    Capabilities,
    Connector,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
)

WRITE_VERBS = ("create", "update", "delete", "write", "post", "put", "patch", "upload", "send")
CONTRACT_METHODS = frozenset(
    {
        "capabilities",
        "authorise_url",
        "exchange_code",
        "refresh",
        "pull",
        "changes_since",
        "fetch_attachment",
        "health",
    }
)
UNDECLARED = cast(Dataset, "dataset-no-connector-declares")


@dataclass(frozen=True)
class Harness:
    """A connector under test and what its provider would send for each declared dataset."""

    connector: Connector
    responses: Mapping[Dataset, tuple[Period, bytes]]  # dataset -> (period, the provider's bytes)


HarnessFactory = Callable[[Path], Harness]
Check = Callable[[Harness], Awaitable[None]]


async def check_is_a_concrete_connector(harness: Harness) -> None:
    assert isinstance(harness.connector, Connector)
    assert not inspect.isabstract(type(harness.connector))
    assert isinstance(type(harness.connector).provider, str)


async def check_capabilities_are_declared(harness: Harness) -> None:
    capabilities = harness.connector.capabilities()
    assert isinstance(capabilities, Capabilities)
    assert isinstance(capabilities.datasets, frozenset)
    assert all(name in get_args(Dataset) for name in capabilities.datasets)
    for flag in (capabilities.oauth, capabilities.incremental, capabilities.attachments):
        assert isinstance(flag, bool)


async def check_every_declared_dataset_is_pullable_byte_for_byte(harness: Harness) -> None:
    declared = harness.connector.capabilities().datasets
    assert set(harness.responses) >= declared, "the harness must cover every declared dataset"
    for dataset in sorted(declared):
        period, provider_bytes = harness.responses[dataset]
        raw = await harness.connector.pull(dataset, period, None)
        assert isinstance(raw, RawPayload)
        assert isinstance(raw.content, bytes)
        assert raw.content == provider_bytes
        assert isinstance(raw.media_type, str)
        assert isinstance(raw.source, str)
        assert isinstance(raw.pulled_at, datetime)
        assert isinstance(raw.request, str)
        assert raw.request  # what was read: the access log needs it (ADR-040)
        assert raw.next_cursor is None or isinstance(raw.next_cursor, str)


async def check_pull_is_deterministic_for_the_same_period_and_cursor(harness: Harness) -> None:
    for dataset in sorted(harness.connector.capabilities().datasets):
        period, _ = harness.responses[dataset]
        first = await harness.connector.pull(dataset, period, None)
        second = await harness.connector.pull(dataset, period, None)
        assert first.content == second.content
        assert first.media_type == second.media_type
        assert first.source == second.source
        assert first.request == second.request


async def check_pulled_at_is_the_time_of_the_pull(harness: Harness) -> None:
    for dataset in sorted(harness.connector.capabilities().datasets):
        period, _ = harness.responses[dataset]
        before = datetime.now(UTC)
        raw = await harness.connector.pull(dataset, period, None)
        after = datetime.now(UTC)
        assert raw.pulled_at.tzinfo is not None
        assert before <= raw.pulled_at <= after


async def check_an_undeclared_dataset_is_not_supported(harness: Harness) -> None:
    assert UNDECLARED not in harness.connector.capabilities().datasets
    period = next(iter(harness.responses.values()))[0]
    with pytest.raises(NotSupported):
        await harness.connector.pull(UNDECLARED, period, None)


async def check_oauth_methods_raise_not_supported_when_oauth_is_not_declared(
    harness: Harness,
) -> None:
    if harness.connector.capabilities().oauth:
        return  # a connector that declares OAuth is exercised by its own tests
    with pytest.raises(NotSupported):
        await harness.connector.authorise_url("test-state", "https://app.example.test/callback")
    with pytest.raises(NotSupported):
        await harness.connector.exchange_code("test-code", "https://app.example.test/callback")


async def check_refresh_without_oauth_is_a_no_op_or_not_supported(harness: Harness) -> None:
    """Contract ambiguity: `refresh` is listed with the OAuth methods in ADR-037 but the contract
    names only the other two. Either is accepted; anything else is not."""
    if harness.connector.capabilities().oauth:
        return
    try:
        await harness.connector.refresh()
    except NotSupported:
        return


async def check_undeclared_optional_operations_raise_not_supported(harness: Harness) -> None:
    capabilities = harness.connector.capabilities()
    if not capabilities.incremental:
        with pytest.raises(NotSupported):
            await harness.connector.changes_since(datetime(2026, 1, 1, tzinfo=UTC))
    if not capabilities.attachments:
        with pytest.raises(NotSupported):
            await harness.connector.fetch_attachment("test-attachment-ref")


async def check_health_is_a_bool(harness: Harness) -> None:
    assert isinstance(await harness.connector.health(), bool)


async def check_no_method_is_write_shaped(harness: Harness) -> None:
    """CONN-001 at run time: connectors only read (ADR-040)."""
    names = {
        name
        for name, member in inspect.getmembers(type(harness.connector))
        if callable(member) and not (name.startswith("__") and name.endswith("__"))
    }
    assert {name for name in names if name.lstrip("_").startswith(WRITE_VERBS)} == set()
    public = {name for name in names if not name.startswith("_")}
    assert public >= CONTRACT_METHODS


ALL_CHECKS: tuple[Check, ...] = (
    check_is_a_concrete_connector,
    check_capabilities_are_declared,
    check_every_declared_dataset_is_pullable_byte_for_byte,
    check_pull_is_deterministic_for_the_same_period_and_cursor,
    check_pulled_at_is_the_time_of_the_pull,
    check_an_undeclared_dataset_is_not_supported,
    check_oauth_methods_raise_not_supported_when_oauth_is_not_declared,
    check_refresh_without_oauth_is_a_no_op_or_not_supported,
    check_undeclared_optional_operations_raise_not_supported,
    check_health_is_a_bool,
    check_no_method_is_write_shaped,
)


def conformance_params(
    factories: Mapping[str, HarnessFactory],
) -> list[object]:
    """`pytest.param(factory, check)` for every factory and check, with readable IDs."""
    return [
        pytest.param(factory, check, id=f"{name}-{check.__name__.removeprefix('check_')}")
        for name, factory in factories.items()
        for check in ALL_CHECKS
    ]


async def run_check(check: Check, factory: HarnessFactory, scratch: Path) -> None:
    await check(factory(scratch))
