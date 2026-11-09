"""A-07-T30 (TASK-6507; A-07 F6; SPEC-644; DEC-3107): the in-app release transaction (G8).

Row acceptance: "Margaret Okonkwo's 10:07 AM release records G8 once under replay, a render
failure records nothing, and agent, system and stale-MFA calls are refused."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from temporalio.exceptions import ApplicationError

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.assurance import release as rel
from abacus.modules.assurance import release_workflow as wf
from abacus.modules.assurance.record_auth import RecordNeedsMfa
from abacus.modules.engagements.api import GateFact
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.reporting.api import ApprovalRef, RenderOutcome

pytestmark = pytest.mark.asyncio
WORK_ITEM, ENGAGEMENT, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
MARGARET = uuid.uuid4()


def _ctx(kind: ActorKind = "human", *, mfa_minutes_ago: int = 1) -> AuthContext:
    tenant = TenantContext(uuid.uuid4(), kind, str(MARGARET))
    return AuthContext(
        tenant,
        MARGARET,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago),
    )


def _snap(**over: object) -> rel.ReleaseSnapshot:
    base: dict[str, Any] = {  # Any: the dataclass's mixed field types
        "work_item_id": WORK_ITEM,
        "engagement_id": ENGAGEMENT,
        "gates": (
            rel.GateCard("G5", True, True, ()),
            rel.GateCard("G6", True, True, ()),
            rel.GateCard("G7", True, True, ()),
        ),
        "also_required": tuple(rel.AlsoRequired(k, True) for k in rel.ALSO_REQUIRED_KEYS),
        "report_id": uuid.uuid4(),
        "report_version_id": VERSION,
        "report_version_hash": "a" * 64,
        "report_status": "approved",
        "report_approved": True,
        "report_date": date(2026, 10, 9),
        "city": "Chicago",
    }
    base.update(over)
    return rel.ReleaseSnapshot(**base)


# --- the gate snapshot ---------------------------------------------------------------------------


def test_the_gate_hash_is_deterministic_and_moves_with_any_gate() -> None:
    assert _snap().sha256 == _snap().sha256
    blocked = _snap(
        gates=(
            rel.GateCard("G5", True, True, ()),
            rel.GateCard("G6", True, True, ()),
            rel.GateCard("G7", False, True, ("rep_letter_not_signed",)),
        )
    )
    assert blocked.sha256 != _snap().sha256
    assert blocked.blockers == ("G7",)  # AUD-24 b: "Blocked by G7 · representation letter"


def test_an_unapproved_report_or_an_unmet_item_blocks() -> None:
    assert _snap(report_approved=False).blockers == ("report_not_approved",)
    unmet = tuple(rel.AlsoRequired(k, k != "governance_260") for k in rel.ALSO_REQUIRED_KEYS)
    assert _snap(also_required=unmet).blockers == ("also_required:governance_260",)


async def test_a_missing_or_failing_provider_is_unmet(monkeypatch: pytest.MonkeyPatch) -> None:
    async def item(_t: TenantContext, _w: uuid.UUID) -> object:
        return SimpleNamespace(engagement_id=ENGAGEMENT)

    async def met(_t: TenantContext, _e: uuid.UUID) -> GateFact:
        return GateFact(met=True)

    async def boom(_t: TenantContext, _e: uuid.UUID) -> GateFact:
        raise RuntimeError("provider down")

    from abacus.modules.assurance import gates

    monkeypatch.setattr(rel, "assurance_item", item)
    monkeypatch.setattr(gates, "g5_facts", met)
    monkeypatch.setattr(gates, "in_app_g6", met)
    monkeypatch.setattr(gates, "in_app_g7", boom)
    monkeypatch.setattr(rel, "_ALSO_REQUIRED", {})

    @asynccontextmanager
    async def session(_t: TenantContext) -> AsyncIterator[object]:
        async def execute(*_a: object, **_k: object) -> object:
            return SimpleNamespace(first=lambda: None)

        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(rel, "tenant_session", session)
    snap = await rel.snapshot(TenantContext(uuid.uuid4(), "system", "t"), WORK_ITEM)
    assert ("G7", False) in {(g.gate, g.met) for g in snap.gates}
    assert all(not a.met for a in snap.also_required)  # no provider registered: fail closed
    assert "report_not_approved" in snap.blockers


# --- who may release -----------------------------------------------------------------------------


@dataclass
class _Tx:
    recorded: list[str] = field(default_factory=list[str])

    def record(self, action: str, **_k: object) -> None:
        self.recorded.append(action)


def _no_db(monkeypatch: pytest.MonkeyPatch, tx: _Tx) -> None:
    async def item(_t: TenantContext, _w: uuid.UUID) -> object:
        return SimpleNamespace(engagement_id=ENGAGEMENT)

    async def ref(_tx: object, _e: uuid.UUID) -> object:
        from abacus.modules.identity.api import Resource

        return SimpleNamespace(resource=lambda: Resource(uuid.uuid4(), engagement_id=ENGAGEMENT))

    @asynccontextmanager
    async def unit(_t: TenantContext) -> AsyncIterator[_Tx]:
        yield tx

    monkeypatch.setattr(rel, "assurance_item", item)
    monkeypatch.setattr(rel, "lock_ref", ref)
    monkeypatch.setattr(rel, "uow", unit)


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_agent_and_system_calls_are_refused_before_anything_is_written(
    monkeypatch: pytest.MonkeyPatch, kind: ActorKind
) -> None:
    tx = _Tx()
    _no_db(monkeypatch, tx)
    with pytest.raises(Forbidden):
        await rel.request_release(_ctx(kind), WORK_ITEM, _snap().sha256, "key-1")
    assert tx.recorded == []


async def test_a_stale_second_factor_is_refused_with_mfa_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tx = _Tx()
    _no_db(monkeypatch, tx)

    async def allowed(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(rel, "authorise_record", allowed)
    with pytest.raises(RecordNeedsMfa):
        await rel.request_release(_ctx(mfa_minutes_ago=40), WORK_ITEM, _snap().sha256, "key-1")
    assert tx.recorded == []


def _passes(monkeypatch: pytest.MonkeyPatch, snap: rel.ReleaseSnapshot) -> None:
    async def allowed(*_a: object, **_k: object) -> None:
        return None

    async def in_app(_t: TenantContext) -> str:
        return "in_app"

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return snap

    async def locked(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(rel, "authorise_record", allowed)
    monkeypatch.setattr(rel, "release_mode", in_app)
    monkeypatch.setattr(rel, "snapshot", current)
    monkeypatch.setattr(rel, "lock_assurance_item", locked)


async def test_unmet_gates_answer_409_gates_not_met(monkeypatch: pytest.MonkeyPatch) -> None:
    tx = _Tx()
    _no_db(monkeypatch, tx)
    _passes(monkeypatch, _snap(report_approved=False))

    async def none(_t: TenantContext, _w: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(rel, "released", none)
    with pytest.raises(rel.GatesNotMet):
        await rel.request_release(_ctx(), WORK_ITEM, _snap().sha256, "key-1")


async def test_a_changed_gate_since_the_dialog_answers_content_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tx = _Tx()
    _no_db(monkeypatch, tx)
    _passes(monkeypatch, _snap())

    async def none(_t: TenantContext, _w: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(rel, "released", none)
    with pytest.raises(rel.ContentChanged):
        await rel.request_release(_ctx(), WORK_ITEM, "0" * 64, "key-1")


def _done(key: str) -> rel.ReleasedFacts:
    return rel.ReleasedFacts(
        uuid.uuid4(),
        MARGARET,
        datetime(2026, 10, 9, 15, 7, tzinfo=UTC),  # 10:07 AM CDT
        date(2026, 10, 9),
        (uuid.uuid4(),),
        key,
        uuid.uuid4(),
    )


async def test_a_replay_with_the_same_key_answers_the_one_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tx = _Tx()
    _no_db(monkeypatch, tx)
    _passes(monkeypatch, _snap())
    done = _done("key-1")

    async def stored(_t: TenantContext, _w: uuid.UUID) -> rel.ReleasedFacts:
        return done

    monkeypatch.setattr(rel, "released", stored)
    assert await rel.request_release(_ctx(), WORK_ITEM, _snap().sha256, "key-1") is done
    assert tx.recorded == ["report.release_replayed"]
    with pytest.raises(rel.AlreadyReleased):
        await rel.request_release(_ctx(), WORK_ITEM, _snap().sha256, "key-2")


def test_the_documentation_clock_is_60_days_from_release() -> None:
    # AUD-24 d: "Archive in 60 days · by Dec 8, 2026" for the Oct 9 release.
    assert _done("k").documentation_completion_date == date(2026, 12, 8)


# --- the final render's approval and failures ----------------------------------------------------


async def test_c11_sees_no_approval_outside_the_consumed_grant() -> None:
    ref = ApprovalRef("report_release", uuid.uuid4(), "b" * 64)
    assert await rel.report_release_approval(ref) is None


def _request() -> rel.ReleaseRequest:
    return rel.ReleaseRequest(
        str(uuid.uuid4()),
        str(WORK_ITEM),
        str(ENGAGEMENT),
        str(uuid.uuid4()),
        str(MARGARET),
        str(VERSION),
        str(uuid.uuid4()),
        "b" * 64,
        _snap().sha256,
        "key-1",
    )


async def test_a_failed_render_ends_the_run_and_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failed(_r: rel.ReleaseRequest, _n: int) -> RenderOutcome:
        return RenderOutcome("failed", failure_code="render_error")

    recorded: list[object] = []

    async def record(*a: object, **_k: object) -> uuid.UUID:
        recorded.append(a)
        return uuid.uuid4()

    monkeypatch.setattr(rel, "final_render", failed)
    monkeypatch.setattr(rel, "record_in_app_release", record)
    with pytest.raises(ApplicationError) as raised:
        await wf.final_render_activity(_request(), 2)
    assert raised.value.type == "RenderFailed" and raised.value.non_retryable
    assert recorded == []


async def test_a_pending_render_is_retried_not_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def running(_r: rel.ReleaseRequest, _n: int) -> RenderOutcome:
        return RenderOutcome("running")

    monkeypatch.setattr(rel, "final_render", running)
    with pytest.raises(ApplicationError) as raised:
        await wf.final_render_activity(_request(), 2)
    assert raised.value.type == "RenderPending" and not raised.value.non_retryable


async def test_a_refused_grant_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refused(_r: rel.ReleaseRequest) -> int:
        raise rel.ReleaseRefused("grant_refused")

    monkeypatch.setattr(rel, "consume_and_render", refused)
    with pytest.raises(ApplicationError) as raised:
        await wf.consume_and_render_activity(_request())
    assert raised.value.type == "ReleaseRefused" and raised.value.non_retryable


def test_the_grant_digest_binds_version_draft_and_gates() -> None:
    a = rel.grant_digest(WORK_ITEM, VERSION, "b" * 64, "c" * 64)
    assert a != rel.grant_digest(WORK_ITEM, VERSION, "b" * 64, "d" * 64)
    assert a != rel.grant_digest(WORK_ITEM, uuid.uuid4(), "b" * 64, "c" * 64)
