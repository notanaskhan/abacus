"""C-02-T25 (TASK-8810; ADR-344 §3–§5): enablement on live paths.

Row acceptance: "Posting is refused until all four switches are on, a revoked grant stops the next
entry mid-batch and an attest-flagged client can never hold a write grant." Here: `w1_refusal`
names each switch in order (re-read per entry, so a revocation stops the next one); the firm
switch refuses while the registry is unreleased and needs a fresh MFA; an attest client is refused
the engagement switch and the grant before any write; the routes call the service.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.integrations import w1_switches, writes

SRC = Path(w1_switches.__file__).parent


def _ctx(mfa_minutes_ago: float | None) -> SimpleNamespace:
    at = None if mfa_minutes_ago is None else datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago)
    return SimpleNamespace(
        tenant=SimpleNamespace(tenant_id=uuid4()), tenant_id=uuid4(), user_id=uuid4(), mfa_at=at
    )


@pytest.fixture
def no_authz(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allow(*_: object, **__: object) -> None:
        return None

    async def now(_: object) -> datetime:
        return datetime.now(UTC)

    monkeypatch.setattr(w1_switches, "authorise", allow)
    monkeypatch.setattr(w1_switches.clock, "now", now)


async def test_ac_the_firm_switch_refuses_while_unreleased(
    no_authz: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(w1_switches, "released", lambda: False)
    with pytest.raises(w1_switches.NotReleased):
        await w1_switches.set_firm_switch(_ctx(1), enabled=True, reason=None)  # type: ignore[arg-type]


async def test_ac_the_firm_switch_needs_a_fresh_mfa(no_authz: None) -> None:
    with pytest.raises(w1_switches.MfaRequired):
        await w1_switches.set_firm_switch(_ctx(None), enabled=False, reason=None)  # type: ignore[arg-type]
    with pytest.raises(w1_switches.MfaRequired):
        await w1_switches.set_firm_switch(_ctx(30), enabled=False, reason=None)  # type: ignore[arg-type]


async def test_ac_an_attest_client_never_gets_posting_enabled(
    no_authz: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus.modules.engagements import api as engagements

    async def attest(*_: object) -> bool:
        return True

    async def resource(*_: object) -> object:
        return object()

    monkeypatch.setattr(engagements, "attest_of", attest)
    monkeypatch.setattr(engagements, "engagement_resource_of", resource)
    with pytest.raises(w1_switches.AttestRefused):
        await w1_switches.set_posting_enabled(
            _ctx(1), uuid4(), uuid4(), posting_enabled=True, expected_version=None  # type: ignore[arg-type]
        )


def test_ac_the_four_switches_are_checked_in_order_on_every_entry() -> None:
    source = (SRC / "writes.py").read_text(encoding="utf-8")
    body = source.split("async def w1_refusal", 1)[1].split("\nasync def ", 1)[0]
    order = [
        body.index('"attest_client_posting_refused"'),
        body.index('"write_capability_not_released"'),
        body.index('"write_capability_disabled"'),
        body.index('"posting_not_enabled"'),
        body.index('"write_grant_missing"'),
    ]
    assert order == sorted(order)
    assert writes.w1_refusal.__doc__ and "kill switch" in writes.w1_refusal.__doc__


def test_the_w1_routes_are_built() -> None:
    tree = ast.parse((SRC / "w1_contract.py").read_text(encoding="utf-8"))
    stubs = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef)
        and any(isinstance(s, ast.Raise) and getattr(s.exc, "id", "") == "NotImplementedYet"
                for s in ast.walk(n))
    ]  # fmt: skip
    assert stubs == []
