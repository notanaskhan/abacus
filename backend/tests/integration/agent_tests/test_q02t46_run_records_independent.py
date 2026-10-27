# ac-test-author: ayushkbhatia
"""Q-02-T46 (TASK-1455): independent AC tests (ADR-078) for run records and the C6 v1 reads,
Q-02 AC-44 and AC-45 (SPEC-341 story 12; ADR-169).

AC-44: a completed specialist run yields one durable record (capability, spec and prompt
versions with the prompt SHA-256, model, route, region, register version, boundary basis, input
hashes, records read as identifiers, citations as locators and fingerprints, outcome, initiator,
`record_sha256`), content-free, and a run completed 90 days earlier still yields it through
`GET /v1/agent-runs/{run_id}/record` after its raw trace is gone; its `record_sha256` is the one
the `agent_run_record.persisted` audit event carries (ADR-169 §3, so it joins the hash chain).
AC-45: the run reads give the legacy state map (`completed` -> `succeeded`) and
`run_record_sha256`, only to people who can read the engagement; another firm gets 404. The C6 v1
summary of ADR-169 §4 (`state`, `state_reason`, `outcome`, `stage`, `record_sha256`,
`record_persisted_at` on the run summary and the engagement list) is Q-02-T45, not built: its
consumer test is written from ADR-169 §4 and expected to fail until T45 lands.

Boundary: a real screener run through `agents.api` (`create_screening_run`, `screen`, the fake
model's stock answer), persisted by the activity registered as `agents.persist_run_record` in
`agents.api.ACTIVITIES` (ADR-169's activity), then `create_app()` over HTTP with the business
clock frozen 90 days on. The raw trace (the gateway's `usage_records`, ADR-032's ~30 days) is
deleted behind the product's back to stand for its pruning. Expectations: ADR-169 §3 and §4,
`docs/contracts/agent-runs.md` §3 and §6, DEC-396 (the run view's `run_record_sha256` is a
read-time fingerprint of the live run row, a different value from the record's own
`record_sha256`; both names keep their meaning, which supersedes AC-45's single name).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from temporalio.testing import ActivityEnvironment

from abacus.kernel.clock import frozen, system_now
from abacus.modules.agents.api import ACTIVITIES as AGENT_ACTIVITIES
from abacus.modules.agents.api import create_screening_run, load_agent_context, screen
from abacus.modules.agents.workflow_types import RunInput
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, World, retrieve
from .walls_support import Net

Json = dict[str, object]
HEX64: Final = re.compile(r"^[0-9a-f]{64}$")
PERSIST: Final = "agents.persist_run_record"  # ADR-169 §3's activity
CONTENT_KEYS: Final = ("model_text", "prompt_text", "quote", "text", "content")


def _persist_activity() -> Callable[[RunInput], Awaitable[None]]:
    for candidate in AGENT_ACTIVITIES:
        definition = getattr(candidate, "__temporal_activity_definition", None)
        if getattr(definition, "name", None) == PERSIST:
            return cast("Callable[[RunInput], Awaitable[None]]", candidate)
    raise AssertionError(f"{PERSIST} is not registered in agents.api.ACTIVITIES")


async def _completed_run(world: World) -> uuid.UUID:
    """A screener run that completed on a retrieved trial balance, its record persisted."""
    version = (await retrieve(world)).evidence_version_id
    run_id = await create_screening_run(
        world.tenant_id, version, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    await screen(await load_agent_context(world.tenant_id, run_id))
    await ActivityEnvironment().run(
        _persist_activity(), RunInput(str(world.tenant_id), str(run_id))
    )
    return run_id


async def _untriggered(seed: Seeder, sql: str, *args: object) -> None:
    """A change behind the product's back: one superuser transaction with triggers off."""
    async with seed.held() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        await conn.execute(sql, *args)


async def _prune_trace(seed: Seeder, run_id: uuid.UUID) -> None:
    """ADR-032: the raw model trace expires after about 30 days."""
    await _untriggered(seed, "DELETE FROM usage_records WHERE agent_run_id = $1", run_id)


async def _persisted_digest(seed: Seeder, run_id: uuid.UUID) -> str:
    rows = await seed.rows(
        "SELECT actor_kind, after_ref::text AS after FROM audit_events "
        "WHERE action = 'agent_run_record.persisted' AND target_id = $1",
        str(run_id),
    )
    assert len(rows) == 1, rows
    assert rows[0]["actor_kind"] == "system"
    found = re.findall(r"[0-9a-f]{64}", str(rows[0]["after"]))
    assert len(found) == 1, rows[0]["after"]
    return found[0]


# --- probe ---------------------------------------------------------------------------------------


def record_problems(
    record: Mapping[str, object], *, audited: str, world: World, run_id: uuid.UUID
) -> list[str]:
    """What a record read gets wrong against ADR-169 §3 and its audited fingerprint (AC-44)."""
    found: list[str] = []
    if record.get("run_id") != str(run_id):
        found.append("run_id is not the run's")
    if record.get("engagement_id") != str(world.engagement_id):
        found.append("engagement_id is not the run's")
    if record.get("initiator_user_id") != str(world.requester.user_id):
        found.append("initiator is not the person the run acted for")
    if record.get("record_sha256") != audited:
        found.append("record_sha256 is not the fingerprint the audit chain carries")
    for field in ("capability", "spec_version", "prompt_ref", "model", "route", "region"):
        if not isinstance(record.get(field), str) or not record.get(field):
            found.append(f"{field} missing")
    if not HEX64.match(str(record.get("prompt_sha256"))):
        found.append("prompt_sha256 is not a SHA-256")
    if record.get("stage") not in ("shadow", "live"):
        found.append(f"stage {record.get('stage')!r}")
    hashes = record.get("input_hashes")
    if not isinstance(hashes, dict) or not cast(Json, hashes).get("context"):
        found.append("input_hashes has no context hash")
    if not record.get("records_read"):
        found.append("records_read is empty")
    if not record.get("citations"):
        found.append("citations are empty")
    outcome = record.get("outcome")
    if not isinstance(outcome, dict) or cast(Json, outcome).get("state") != "succeeded":
        found.append(f"outcome {outcome!r}")
    started, completed = record.get("started_at"), record.get("completed_at")
    if not started or not completed:
        found.append("started_at or completed_at missing")
    elif datetime.fromisoformat(str(started)) > datetime.fromisoformat(str(completed)):
        found.append("completed before it started")
    for key in CONTENT_KEYS:
        if key in record:
            found.append(f"content field {key!r} in a content-free record")
    for citation in cast(list[Json], record.get("citations") or []):
        if any(key in citation for key in CONTENT_KEYS):
            found.append("a citation carries quoted words")
    return found


# --- AC-44: the durable record ------------------------------------------------------------------


@pytest.mark.usefixtures("fake_model")
async def test_ac44_a_run_completed_90_days_ago_still_yields_its_record(
    seed: Seeder,
    world: World,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
) -> None:
    run_id = await _completed_run(world)
    net = Net(seed, http, idp)
    first = await net.call("GET", f"/v1/agent-runs/{run_id}/record", world.requester)
    assert first.status_code == 200, first.text
    await _prune_trace(seed, run_id)
    with frozen(system_now() + timedelta(days=90)):
        later = await net.call("GET", f"/v1/agent-runs/{run_id}/record", world.requester)
    assert later.status_code == 200, later.text
    record = cast(Json, later.json())
    audited = await _persisted_digest(seed, run_id)
    assert record_problems(record, audited=audited, world=world, run_id=run_id) == []
    # The record is the same record: written once, never changed.
    unchanged = {k: v for k, v in cast(Json, first.json()).items() if k != "persisted_at"}
    assert {k: v for k, v in record.items() if k != "persisted_at"} == unchanged


@pytest.mark.usefixtures("fake_model")
async def test_ac44_one_record_per_run_and_persisting_again_writes_nothing(
    seed: Seeder, world: World
) -> None:
    run_id = await _completed_run(world)
    await ActivityEnvironment().run(
        _persist_activity(), RunInput(str(world.tenant_id), str(run_id))
    )
    count = await seed.value("SELECT count(*) FROM agent_run_records WHERE run_id = $1", run_id)
    assert count == 1
    audits = await seed.value(
        "SELECT count(*) FROM audit_events WHERE action = 'agent_run_record.persisted' "
        "AND target_id = $1",
        str(run_id),
    )
    assert audits == 1


@pytest.mark.usefixtures("fake_model")
async def test_ac44_another_firm_reads_no_record(
    seed: Seeder, world: World, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    run_id = await _completed_run(world)
    net = Net(seed, http, idp)
    outsider = await net.person(await seed.firm(), "firm_admin")
    for path in (f"/v1/agent-runs/{run_id}/record", f"/v1/agent-runs/{run_id}"):
        response = await net.call("GET", path, outsider)
        assert response.status_code == 404, (path, response.text)


# --- AC-45: the run reads (C6) -------------------------------------------------------------------


@pytest.mark.usefixtures("fake_model")
async def test_ac45_the_run_reads_give_the_legacy_map_and_run_record_sha256(
    seed: Seeder, world: World, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    run_id = await _completed_run(world)
    net = Net(seed, http, idp)
    view = await net.call("GET", f"/v1/agent-runs/{run_id}", world.requester)
    assert view.status_code == 200, view.text
    body = cast(Json, view.json())
    assert cast(Json, body["run"])["state"] == "succeeded"  # completed -> succeeded
    assert HEX64.match(str(body["run_record_sha256"]))
    listed = await net.call(
        "GET", f"/v1/engagements/{world.engagement_id}/agent-runs?state=recent", world.requester
    )
    assert listed.status_code == 200, listed.text
    runs = [r for r in cast(list[Json], listed.json()) if r["id"] == str(run_id)]
    assert len(runs) == 1 and runs[0]["state"] == "succeeded"


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1455: waits on Q-02-T45/T47 (Q-02-T45: the C6 v1 run summary of ADR-169 §4)",
)
@pytest.mark.usefixtures("fake_model")
async def test_ac45_c6_v1_the_run_summary_carries_the_record_fingerprint(
    seed: Seeder, world: World, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    run_id = await _completed_run(world)
    net = Net(seed, http, idp)
    audited = await _persisted_digest(seed, run_id)
    view = await net.call("GET", f"/v1/agent-runs/{run_id}", world.requester)
    assert view.status_code == 200, view.text
    summary = cast(Json, cast(Json, view.json())["run"])
    assert summary["state"] == "succeeded"
    assert "state_reason" in summary and "outcome" in summary
    assert summary["stage"] in ("shadow", "live")
    assert summary["record_sha256"] == audited
    assert summary["record_persisted_at"] is not None
    listed = await net.call(
        "GET", f"/v1/engagements/{world.engagement_id}/agent-runs?state=recent", world.requester
    )
    assert listed.status_code == 200, listed.text
    (item,) = [r for r in cast(list[Json], listed.json()) if r["id"] == str(run_id)]
    assert item["record_sha256"] == audited


# --- the probe catches planted violations --------------------------------------------------------


@pytest.mark.usefixtures("fake_model")
async def test_seeded_run_record_violations_are_caught(
    seed: Seeder,
    world: World,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
) -> None:
    run_id = await _completed_run(world)
    net = Net(seed, http, idp)
    record = cast(
        Json, (await net.call("GET", f"/v1/agent-runs/{run_id}/record", world.requester)).json()
    )
    audited = await _persisted_digest(seed, run_id)
    assert record_problems(record, audited=audited, world=world, run_id=run_id) == []
    planted: list[Json] = [
        {**record, "record_sha256": "0" * 64},
        {**record, "prompt_sha256": None},
        {**record, "citations": []},
        {**record, "model_text": "the model's words"},
        {**record, "initiator_user_id": str(uuid.uuid4())},
    ]
    for violation in planted:
        assert record_problems(violation, audited=audited, world=world, run_id=run_id)
    # A record altered in the database behind the product's back no longer matches its audit row.
    await _untriggered(
        seed, "UPDATE agent_run_records SET record_sha256 = $2 WHERE run_id = $1", run_id, "f" * 64
    )
    tampered = cast(
        Json, (await net.call("GET", f"/v1/agent-runs/{run_id}/record", world.requester)).json()
    )
    assert record_problems(tampered, audited=audited, world=world, run_id=run_id)
