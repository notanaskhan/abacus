"""W-01-T09 (SPEC-659 §4; red): the Connect fakes and the port conformance suite.

Every Connect port (each fake mode, and any port a later task registers) passes the same rules:
the port's members only, egress hosts in the grammar, a consent URL on an egress host carrying the
state and the S256 challenge, a deterministic exchange that refuses a declined grant, scripted
health outcomes in the known set, and a revoke that confirms. Fakes bind only to synthetic firms
where `integrations_fake_adapters` is set; production refuses the setting (`test_config.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import get_args
from urllib.parse import parse_qs, urlparse

import pytest

from abacus.kernel import config
from abacus.modules.integrations import adapters, connect_ports, fakes
from abacus.modules.integrations.ports import (
    HEALTH_OUTCOMES,
    ConnectMode,
    ConnectRefused,
)

MODES: tuple[ConnectMode, ...] = get_args(ConnectMode)


@pytest.fixture
def fakes_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    monkeypatch.setenv("ABACUS_INTEGRATIONS_FAKE_ADAPTERS", "true")
    config.settings.cache_clear()
    yield
    config.settings.cache_clear()
    fakes.reset_scripts()


@pytest.mark.parametrize("mode", MODES)
def test_every_fake_port_passes_the_port_rules(mode: ConnectMode) -> None:
    port = connect_ports.check_port(fakes.fake_port("box", mode))
    assert port.mode == mode


@pytest.mark.parametrize("mode", MODES)
def test_the_consent_url_carries_the_state_and_the_s256_challenge(mode: ConnectMode) -> None:
    port = fakes.fake_port("box", mode)
    url = urlparse(
        port.authorise_url(
            state="s" * 32, code_challenge="c" * 43, redirect_uri="https://x.test/cb"
        )
    )
    query = parse_qs(url.query)
    assert url.scheme == "https" and url.hostname in port.egress_hosts()
    assert query["state"] == ["s" * 32] and query["code_challenge"] == ["c" * 43]
    assert query["code_challenge_method"] == ["S256"]


async def test_the_exchange_is_deterministic_and_a_declined_grant_is_refused() -> None:
    port = fakes.fake_port("box", "personal")
    first = await port.exchange_code(code="abc", code_verifier="v" * 43, redirect_uri="r")
    again = await port.exchange_code(code="abc", code_verifier="v" * 43, redirect_uri="r")
    assert first.secret == again.secret and first.renews_at is not None
    with pytest.raises(ConnectRefused):
        await port.exchange_code(code=fakes.DECLINED, code_verifier="v" * 43, redirect_uri="r")
    app = await fakes.fake_port("qbo", "firm_app").exchange_code(
        code="abc", code_verifier="v" * 43, redirect_uri="r"
    )
    assert app.renews_at is None  # a firm app has no token of its own to renew


@pytest.mark.usefixtures("fakes_on")
async def test_health_follows_its_script_and_the_last_outcome_repeats() -> None:
    port = fakes.fake_port("cch", "token")
    assert await port.check_health(b"t") == "ok"
    fakes.script_health("cch", ["transient", "token_expired"])
    seen = [await port.check_health(b"t") for _ in range(3)]
    assert seen == ["transient", "token_expired", "token_expired"]
    assert set(seen) <= set(HEALTH_OUTCOMES)
    assert await port.check_health(None) == "unauthorised"  # no secret: the grant is gone
    assert await fakes.fake_port("qbo", "firm_app").check_health(None) == "ok"
    with pytest.raises(ValueError):
        fakes.script_health("cch", ["sideways"])  # type: ignore[list-item] -- not an outcome


async def test_revoke_confirms() -> None:
    assert await fakes.fake_port("box", "personal").revoke(b"t") is True


def test_the_fake_read_adapter_passes_the_read_registry_rules() -> None:
    adapters.register_adapter(fakes.fake_read_adapter("probe_fake"))
    try:
        assert adapters.registered_adapter("probe_fake") is not None
    finally:
        adapters.unregister_adapter("probe_fake")


def test_fakes_are_off_by_default() -> None:
    config.settings.cache_clear()
    assert not fakes.fakes_allowed()
    assert adapters.adapter_for("karbon", synthetic=True) is None
    assert connect_ports.port_for("karbon", "token", synthetic=True) is None


@pytest.mark.usefixtures("fakes_on")
def test_fakes_bind_only_to_a_synthetic_firm() -> None:
    assert fakes.fakes_allowed()
    assert adapters.adapter_for("karbon", synthetic=True) is not None
    assert adapters.adapter_for("karbon", synthetic=False) is None
    assert connect_ports.port_for("karbon", "token", synthetic=True) is not None
    assert connect_ports.port_for("karbon", "token", synthetic=False) is None


class _Leaky(fakes.FakePort):
    def post(self) -> None:  # a public method outside the port
        return None


def test_a_port_with_anything_public_outside_the_port_is_refused() -> None:
    with pytest.raises(connect_ports.PortRefused):
        connect_ports.check_port(_Leaky("box", "token"))


def test_a_registered_port_answers_only_its_own_mode() -> None:
    connect_ports.register_port(fakes.fake_port("probe_real", "token"))
    try:
        assert connect_ports.port_for("probe_real", "token", synthetic=False) is not None
        assert connect_ports.port_for("probe_real", "personal", synthetic=False) is None
        with pytest.raises(connect_ports.PortRefused):
            connect_ports.register_port(fakes.fake_port("probe_real", "token"))
    finally:
        connect_ports.unregister_port("probe_real")
