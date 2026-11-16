"""The Connect fakes (W-01-T09; SPEC-659 §4; red): a firm token, a personal OAuth app, a firm app
and a file bridge, with scripted health outcomes.

They bind to synthetic firms only, and only where `integrations_fake_adapters` is set (the
config refuses it in production, so the API and the worker do not boot with it there). The
synthetic tenant on staging uses them so every listed tile has an adapter (WB-10's 38 Available)
and WB-11 e and f (Connecting, Needs reauth) can be shown without a real provider.

- **Read:** `fake_read_adapter(key)`, a read-only `IntegrationAdapter` that declares no read
  method (nothing to read: the demo's data is seeded, never fetched).
- **Connect:** `fake_port(key, mode)`. The consent URL is on `auth.fake.accrued.test` with the
  state and the S256 challenge; `exchange_code` grants an opaque token derived from the code (so
  tests are deterministic) and refuses the code `declined` (`ConnectRefused`, AC-12's
  `connect_declined`); `revoke` always confirms.
- **Health:** each key answers `ok` unless a script says otherwise (`script_health`), one
  outcome per check, the last repeating: the Aug 17 replay scripts `token_expired` for CCH.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Final, Literal
from urllib.parse import urlencode

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.modules.integrations.ports import (
    HEALTH_OUTCOMES,
    ConnectMode,
    ConnectRefused,
    HealthOutcome,
    TokenGrant,
)

HOST: Final = "auth.fake.accrued.test"
DECLINED: Final = "declined"
TOKEN_DAYS: Final = 90
_SCRIPTS: dict[str, list[HealthOutcome]] = {}


def fakes_allowed() -> bool:
    """Never in production (the config refuses the setting there, and this checks again)."""
    s = settings()
    return s.integrations_fake_adapters and s.environment != "production"


def script_health(key: str, outcomes: list[HealthOutcome]) -> None:
    """The outcomes `key`'s fake answers, in order, the last repeating (tests and the replay)."""
    if not outcomes or any(o not in HEALTH_OUTCOMES for o in outcomes):
        raise ValueError("a script is one or more known outcomes")
    _SCRIPTS[key] = list(outcomes)


def reset_scripts() -> None:
    _SCRIPTS.clear()


class FakeReadAdapter:
    """A read-only adapter with nothing to read (the demo's data is seeded)."""

    read_methods: tuple[str, ...] = ()

    def __init__(self, key: str) -> None:
        self._key = key

    @property
    def key(self) -> str:
        return self._key

    @property
    def category(self) -> Literal["grc"]:
        return "grc"  # a v1 read category; never a portal card (the fake is workbench-only)

    @property
    def connector_provider(self) -> str | None:
        return None

    def read_scopes(self) -> tuple[str, ...]:
        return ("fake.read",)

    def egress_hosts(self) -> tuple[str, ...]:
        return (HOST,)


class FakePort:
    """A scripted Connect port for one key and mode."""

    def __init__(self, key: str, mode: ConnectMode) -> None:
        self._key = key
        self._mode: ConnectMode = mode

    @property
    def key(self) -> str:
        return self._key

    @property
    def mode(self) -> ConnectMode:
        return self._mode

    def egress_hosts(self) -> tuple[str, ...]:
        return (HOST,)

    def authorise_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": f"fake-{self._key}",
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://{HOST}/{self._key}/authorize?{query}"

    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenGrant:
        if code == DECLINED:
            raise ConnectRefused("the person declined")
        digest = hashlib.sha256(f"{self._key}:{code}:{code_verifier}".encode()).hexdigest()
        renews: datetime | None = (
            None if self._mode == "firm_app" else system_now() + timedelta(days=TOKEN_DAYS)
        )
        return TokenGrant(f"fake-token:{digest}".encode(), renews, ("fake.read",))

    async def check_health(self, secret: bytes | None) -> HealthOutcome:
        if secret is None and self._mode != "firm_app":
            return "unauthorised"
        script = _SCRIPTS.get(self._key)
        if not script:
            return "ok"
        return script.pop(0) if len(script) > 1 else script[0]

    async def revoke(self, secret: bytes) -> bool:
        return True


def fake_read_adapter(key: str) -> FakeReadAdapter:
    return FakeReadAdapter(key)


def fake_port(key: str, mode: ConnectMode) -> FakePort:
    return FakePort(key, mode)
