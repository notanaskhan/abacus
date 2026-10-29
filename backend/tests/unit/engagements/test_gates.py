"""C1 (F-03-T19): G1 acceptance, G2 independence, G3 the letter, as the type requires them."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import api as engagements_api
from abacus.modules.engagements import gates as subject
from abacus.modules.engagements import slots

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
    acceptance: object,  # a fake stands in for CLI-07's decision
    letter: object,  # a fake stands in for the letter row
) -> None:

    async def get_letter(*_: object) -> object:
        return letter

    def session(*_: object) -> _Session:
        return _Session()

    async def g1(*_: object) -> object:
        # G1 reads CLI-07's decision alone (DEC-372; DEC-906).
        if acceptance is None:
            return None
        return SimpleNamespace(accepted=getattr(acceptance, "decision", None) == "accepted")

    async def conclusion(*_: object) -> object:
        # G2 reads CLI-08's conclusion alone (DEC-428; DEC-906).
        if getattr(acceptance, "concluded", False):
            return SimpleNamespace(option="independent")
        return None

    async def no_breaches(*_: object) -> list[object]:
        return []

    monkeypatch.setattr(subject, "latest_conclusion", conclusion)
    monkeypatch.setattr(subject, "open_breach_ids", no_breaches)
    monkeypatch.setattr(subject, "g1_decision", g1)
    monkeypatch.setattr(subject, "get_letter", get_letter)
    monkeypatch.setattr(subject, "tenant_session", session)
    # C1's own providers: once signatures has replaced the interim G3 (N-02-T09, DEC-820) in this
    # process, the registry would read envelopes; this suite is about P-07's three.
    monkeypatch.setattr(
        slots,
        "_GATES",
        {"G1": subject._acceptance, "G2": subject._independence, "G3": subject.recorded_letter},  # pyright: ignore[reportPrivateUsage] -- the module's own providers
    )


async def test_c1_nothing_recorded_blocks_every_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, None, None)
    views = await subject.engagement_gates(TENANT, E, "fs_audit")
    assert [(v.gate, v.met, v.blockers) for v in views] == [
        ("G1", False, ("acceptance",)),
        ("G2", False, ("independence_conclusion",)),
        ("G3", False, ("engagement_letter",)),
    ]


async def test_c1_all_recorded_meets_every_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    accepted = SimpleNamespace(decision="accepted", concluded=True)
    _world(monkeypatch, accepted, SimpleNamespace(status="signed"))
    assert all(v.met for v in await subject.engagement_gates(TENANT, E, "review"))


async def test_c1_a_non_attest_type_skips_g2_and_a_letter_not_required_this_year_meets_g3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # G3 is strict whatever the firm's letter policy (DEC-39 (b), ED-010): the exception is
    # recorded for the engagement.
    declined = SimpleNamespace(decision="declined", concluded=False)
    _world(monkeypatch, declined, SimpleNamespace(status="not_required_this_year"))
    views = await subject.engagement_gates(TENANT, E, "cas_monthly_close")
    assert [(v.gate, v.met, v.blockers) for v in views] == [
        ("G1", False, ("acceptance_declined",)),
        ("G3", True, ()),
    ]
