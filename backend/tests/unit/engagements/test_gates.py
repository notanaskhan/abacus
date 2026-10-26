"""C1 (F-03-T19): G1 acceptance, G2 independence, G3 the letter, as the type requires them."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import api as engagements_api
from abacus.modules.engagements import gates as subject

# Importing the module's api registers G1 to G3; run alone, nothing else would.
assert engagements_api.ROUTERS

TENANT = TenantContext(uuid.uuid4(), "system", "test")
E = uuid.uuid4()


class _Session:
    async def __aenter__(self) -> object:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _world(
    monkeypatch: pytest.MonkeyPatch,
    acceptance: object,  # a fake stands in for the acceptance row
    letter: object,  # a fake stands in for the letter row
    needs_letter: bool = True,
) -> None:
    async def latest(*_: object) -> object:
        return acceptance

    async def get_letter(*_: object) -> object:
        return letter

    async def policy(*_: object) -> bool:
        return needs_letter

    def session(*_: object) -> _Session:
        return _Session()

    async def g1(*_: object) -> object:
        # G1 reads the acceptance decision (P-07-T35, DEC-372): SPEC-025's row stands in for it.
        if acceptance is None:
            return None
        return SimpleNamespace(accepted=getattr(acceptance, "decision", None) == "accepted")

    async def no_rows(*_: object) -> None:
        return None  # P-07-T41: no conclusion row, so G2 reads SPEC-025's row

    async def no_breaches(*_: object) -> list[object]:
        return []

    monkeypatch.setattr(subject, "latest_acceptance", latest)
    monkeypatch.setattr(subject, "latest_conclusion", no_rows)
    monkeypatch.setattr(subject, "open_breach_ids", no_breaches)
    monkeypatch.setattr(subject, "g1_decision", g1)
    monkeypatch.setattr(subject, "get_letter", get_letter)
    monkeypatch.setattr(subject, "letter_policy", policy)
    monkeypatch.setattr(subject, "tenant_session", session)


async def test_c1_nothing_recorded_blocks_every_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, None, None)
    views = await subject.engagement_gates(TENANT, E, "fs_audit")
    assert [(v.gate, v.met, v.blockers) for v in views] == [
        ("G1", False, ("acceptance",)),
        ("G2", False, ("independence_conclusion",)),
        ("G3", False, ("engagement_letter",)),
    ]


async def test_c1_all_recorded_meets_every_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    accepted = SimpleNamespace(
        decision="accepted", independence_concluded_at=datetime.now(UTC), legacy_g2=True
    )  # a row from before 0175 (DEC-429)
    _world(monkeypatch, accepted, SimpleNamespace(status="signed"))
    assert all(v.met for v in await subject.engagement_gates(TENANT, E, "review"))


async def test_c1_a_non_attest_type_skips_g2_and_a_firm_without_letters_meets_g3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declined = SimpleNamespace(decision="declined", independence_concluded_at=None, legacy_g2=True)
    _world(monkeypatch, declined, None, needs_letter=False)
    views = await subject.engagement_gates(TENANT, E, "cas_monthly_close")
    assert [(v.gate, v.met, v.blockers) for v in views] == [
        ("G1", False, ("acceptance_declined",)),
        ("G3", True, ()),
    ]
