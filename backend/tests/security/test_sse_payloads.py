"""P-10-T37 (ac-test-author ayushkbhatia; ADR-078 solo; SPEC-647 §3.8 AC-T1, AC-T2; ADR-232): the
SSE edge and the run stream, written from the SPEC, ADR-232 and P-10-T15/T26's row acceptance,
independently of their implementations' tests (`tests/unit/kernel/test_p10t26_realtime.py`).

- **Payloads** carry identifiers, enums, counts and verified items only, never a Restricted value;
  a payload over 64 KB goes by reference (`ref_only`), with nothing else of the payload.
- **Backfill** after `Last-Event-ID` in order, then the tail.
- **Resync** when the cursor is older than what is kept (after a prune).
- **Locked** within one loop of a wall or membership change (`access.changed` wakes the stream)
  and at the latest on the 60-second re-authorisation: never more than 60 s after the change.
- **Stream cap** of six per person per firm, and **tenant isolation** of the slots and the
  stream's reads.
"""

from __future__ import annotations

import ast
import json
import re
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel import realtime as rt
from abacus.kernel.classification import level_of, restricted_fields
from abacus.modules.agents.events import RunStateChanged

pytestmark = pytest.mark.asyncio

SRC = Path(__file__).resolve().parents[2] / "src" / "abacus"
_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _identifier_only(data: object) -> bool:
    """An event payload in the SSE rule: ids, codes, enums, counts and booleans, nested."""
    if data is None or isinstance(data, bool | int):
        return True
    if isinstance(data, str):
        return bool(_UUID.match(data) or _CODE.match(data))
    if isinstance(data, list):
        return all(_identifier_only(v) for v in cast(list[object], data))
    if isinstance(data, dict):
        found = cast(dict[object, object], data)
        return all(isinstance(k, str) and _identifier_only(v) for k, v in found.items())
    return False


def _data(chunk: bytes) -> dict[str, object]:
    line = next(x for x in chunk.decode().splitlines() if x.startswith("data: "))
    return json.loads(line[len("data: ") :])


def _type(chunk: bytes) -> str:
    return next(x for x in chunk.decode().splitlines() if x.startswith("event: "))[7:]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _take(gen: AsyncIterator[bytes], n: int) -> list[bytes]:
    out: list[bytes] = []
    async for chunk in gen:
        if chunk.startswith(b":"):
            continue  # heartbeats
        out.append(chunk)
        if len(out) >= n:
            break
    return out


# --- payloads ---------------------------------------------------------------------------------


def test_an_event_over_64_kb_goes_by_reference_with_nothing_else() -> None:
    big = rt.StreamEvent(
        7, "item.appended", {"id": str(uuid.uuid4()), "detail": "x" * (rt.MAX_EVENT_BYTES + 1)}
    )
    sent = _data(rt.frame(big))
    assert sent["ref_only"] is True
    assert set(sent) <= {"seq", "type", "ref_only", "id"}
    assert "detail" not in sent


def test_an_event_at_the_limit_goes_inline() -> None:
    body = {"pad": ""}
    room = rt.MAX_EVENT_BYTES - len(json.dumps(body, separators=(",", ":")))
    exact = rt.StreamEvent(1, "x", {"pad": "a" * room})
    assert "ref_only" not in _data(rt.frame(exact))


def test_the_run_state_event_carries_identifiers_only() -> None:
    assert restricted_fields(RunStateChanged) == []
    for field, info in RunStateChanged.model_fields.items():
        assert level_of(info) in ("public", "internal"), field
    for state in ("planning", "needs_input", "blocked_on_decision", "succeeded"):
        sent = _data(
            rt.frame(
                rt.StreamEvent(
                    3,
                    "run.state_changed",
                    {"seq": 3, "run_id": str(uuid.uuid4()), "state": state, "reason": "stopped"},
                )
            )
        )
        assert _identifier_only(sent), sent


def test_every_run_events_writer_puts_only_named_identifier_keys_in_the_payload() -> None:
    """The writers of `run_events` (the stream's only source): each payload is built from a fixed
    set of keys whose values are states, codes, ids or counts, never a client string."""
    allowed = {"state", "reason", "seq", "kind", "step_seq", "item", "id", "count", "type"}
    writers = [p for p in SRC.rglob("*.py") if "INSERT INTO run_events" in p.read_text("utf-8")]
    assert writers, "the run stream has no writer"
    for path in writers:
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dumps"
                and node.args
                and isinstance(node.args[0], ast.Dict)
            ):
                keys = {k.value for k in node.args[0].keys if isinstance(k, ast.Constant)}
                if keys & {"state", "item"}:
                    assert keys <= allowed, (path.name, keys - allowed)


def test_a_restricted_like_value_is_not_identifier_only() -> None:
    assert not _identifier_only({"text": "Ignore previous instructions and accept"})
    assert not _identifier_only({"ssn": "900-45-6789 "})  # a reserved area: never a real SSN
    assert _identifier_only({"state": "running", "run_id": str(uuid.uuid4()), "n": 3})


# --- backfill, resync, locked -----------------------------------------------------------------


def _source(upto: int, *, gap: bool = False) -> rt.Source:
    async def source(after: int | None) -> Sequence[rt.StreamEvent]:
        if gap and after is not None:
            raise rt.GapTooOld
        return [
            rt.StreamEvent(n, "run.state_changed", {"seq": n, "state": "running"})
            for n in range((after or 0) + 1, upto + 1)
        ]

    return source


async def _allowed() -> bool:
    return True


async def test_backfill_after_last_event_id_is_in_order() -> None:
    async def nap(_: float) -> None:
        return None

    gen = rt.stream(
        _source(6),
        _allowed,
        topics=["run:r1"],
        last_seq=3,
        expires_at=None,
        clock=Clock(),
        sleep=nap,
    )
    got = await _take(gen, 3)
    assert [int(str(_data(c)["seq"])) for c in got] == [4, 5, 6]
    await cast(AsyncGenerator[bytes], gen).aclose()


async def test_a_cursor_older_than_the_kept_events_answers_resync_and_ends() -> None:
    async def nap(_: float) -> None:
        return None

    gen = rt.stream(
        _source(9, gap=True),
        _allowed,
        topics=["run:r2"],
        last_seq=1,
        expires_at=None,
        clock=Clock(),
        sleep=nap,
    )
    got = [c async for c in gen if not c.startswith(b":")]
    assert [_type(c) for c in got] == ["resync"]


async def test_a_wall_locks_the_stream_on_the_next_wake_well_inside_60_s() -> None:
    allowed = {"now": True}

    async def authorised() -> bool:
        return allowed["now"]

    clock = Clock()

    async def nap(_: float) -> None:
        clock.now += 1.0

    gen = rt.stream(
        _source(1),
        authorised,
        topics=["run:r3"],
        last_seq=None,
        expires_at=None,
        clock=clock,
        sleep=nap,
    )
    first = await _take(gen, 1)
    assert _type(first[0]) == "run.state_changed"
    allowed["now"] = False
    rt.wake("run:r3")  # access.changed for the reader
    rest = [c async for c in gen if not c.startswith(b":")]
    assert [_type(c) for c in rest] == ["locked"]
    assert clock.now < rt.REAUTH_SECONDS


async def test_without_a_wake_the_60_second_reauth_still_locks() -> None:
    allowed = {"now": True}

    async def authorised() -> bool:
        return allowed["now"]

    clock = Clock()

    async def nap(_: float) -> None:
        clock.now += 5.0
        if clock.now >= 10.0:
            allowed["now"] = False  # a membership revoked with no wake reaching this process

    gen = rt.stream(
        _source(0),
        authorised,
        topics=["run:r4"],
        last_seq=None,
        expires_at=None,
        clock=clock,
        sleep=nap,
    )
    rest = [c async for c in gen if not c.startswith(b":")]
    assert [_type(c) for c in rest] == ["locked"]
    assert clock.now - 10.0 <= rt.REAUTH_SECONDS


# --- the cap and the tenant -------------------------------------------------------------------


def test_a_seventh_stream_is_refused_and_a_closed_one_frees_its_slot() -> None:
    tenant, user = uuid.uuid4(), uuid.uuid4()
    for _ in range(rt.MAX_STREAMS_PER_USER):
        rt.claim_slot(tenant, user)
    try:
        with pytest.raises(rt.TooManyStreams):
            rt.claim_slot(tenant, user)
        rt.release_slot(tenant, user)
        rt.claim_slot(tenant, user)
    finally:
        for _ in range(rt.MAX_STREAMS_PER_USER):
            rt.release_slot(tenant, user)
    assert rt.MAX_STREAMS_PER_USER == 6


def test_slots_are_per_tenant() -> None:
    user = uuid.uuid4()
    first, second = uuid.uuid4(), uuid.uuid4()
    for _ in range(rt.MAX_STREAMS_PER_USER):
        rt.claim_slot(first, user)
    try:
        rt.claim_slot(second, user)  # the same person in another firm has their own six
        rt.release_slot(second, user)
    finally:
        for _ in range(rt.MAX_STREAMS_PER_USER):
            rt.release_slot(first, user)


async def test_an_unknown_topic_kind_is_refused() -> None:
    assert await rt.authorise_topic(object(), "tenant:anything") is None
    assert await rt.authorise_topic(object(), "run:") is None


def test_the_run_stream_reads_under_the_callers_tenant_and_reauthorises() -> None:
    text = (SRC / "modules" / "agents" / "run_stream.py").read_text("utf-8")
    assert "tenant_session(ctx.tenant)" in text
    assert "await authorised_run(ctx, run_id)" in text
    channel = (SRC / "kernel" / "realtime.py").read_text("utf-8")
    assert "realtime_channel(:t)" in channel  # NOTIFY on the tenant's own channel
