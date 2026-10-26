"""SPEC-341 AC-44 (Q-02-T41, TASK-1287; ADR-169 §3): a completed specialist run yields one
insert-only `agent_run_records` row holding the capability, spec and prompt versions with the
prompt SHA-256, model, route, region, register version, boundary basis, input hashes, records
read (identifiers), citations (locators and quote hashes), outcome, initiator and
`record_sha256`; a run completed 90 days ago still yields it after its raw trace is gone.

A real screener run (retrieved trial balance, the fake model's stock answer) is persisted through
the `agents.persist_run_record` activity, as its workflow does. Expectations come from ADR-169
§3, not the implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from typing import cast

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from abacus.ai_gateway import FakeModel, configure_provider, prompt
from abacus.kernel.clock import frozen, system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.activities import persist_run_record_activity
from abacus.modules.agents.api import (
    SCREENER,
    create_screening_run,
    install_fake_responses,
    load_agent_context,
    screen,
)
from abacus.modules.agents.run_records import (
    PERSISTED,
    persist_run_record,
    record_for,
    record_sha256,
)
from abacus.modules.agents.workflow_types import RunInput
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, World, retrieve
from .walls_support import Net

Json = dict[str, object]


@pytest.fixture(autouse=True)
def _model() -> Iterator[None]:
    fake = FakeModel()
    install_fake_responses(fake)
    configure_provider(fake)
    yield
    configure_provider(None)


async def _activity(argument: RunInput) -> None:
    env = ActivityEnvironment()
    run = cast("Callable[[RunInput], Awaitable[None]]", persist_run_record_activity)
    await env.run(run, argument)


async def _screened(world: World) -> uuid.UUID:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    await screen(await load_agent_context(world.tenant_id, run_id))
    return run_id


async def _record_row(seed: Seeder, run_id: uuid.UUID) -> Json:
    rows = await seed.rows("SELECT * FROM agent_run_records WHERE run_id = $1", run_id)
    assert len(rows) == 1
    found = dict(rows[0])
    for column in ("input_hashes", "records_read", "citations", "outcome"):
        found[column] = json.loads(cast(str, found[column]))
    return found


async def test_ac44_a_completed_run_persists_one_record_with_its_facts(
    seed: Seeder, world: World
) -> None:
    run_id = await _screened(world)
    await _activity(RunInput(str(world.tenant_id), str(run_id)))

    row = await _record_row(seed, run_id)
    [run] = await seed.rows("SELECT * FROM agent_runs WHERE id = $1", run_id)
    usage = await seed.rows(
        "SELECT prompt_id, prompt_version, model, route, inputs_hash, boundary_basis, "
        "terms_version FROM usage_records WHERE agent_run_id = $1 ORDER BY created_at",
        run_id,
    )
    [result] = await seed.rows(
        "SELECT evidence_version_id, citations::text AS citations FROM screening_results "
        "WHERE agent_run_id = $1",
        run_id,
    )
    call = usage[-1]
    ref = f"{call['prompt_id']}@{call['prompt_version']}"

    assert row["capability"] == SCREENER == run["agent_id"]
    assert row["spec_version"] == run["spec_version"]
    assert row["stage"] == "live"
    assert row["engagement_id"] == world.engagement_id
    assert row["initiator_user_id"] == world.requester.user_id
    assert row["prompt_ref"] == ref
    assert row["prompt_sha256"] == prompt(ref).sha256
    assert row["model"] == call["model"]
    assert row["route"] == call["route"] == "fake"
    assert row["region"] == "local"
    assert row["boundary_basis"] == call["boundary_basis"]
    assert row["terms_version"] == call["terms_version"]
    assert row["input_hashes"] == {
        "context": run["context_hash"],
        "model_calls": sorted({u["inputs_hash"] for u in usage}),
    }
    assert {"type": "evidence_version", "id": str(result["evidence_version_id"])} in cast(
        list[Json], row["records_read"]
    )
    cited = cast(list[Json], json.loads(result["citations"]))
    assert cited, "the stock screener answer cites cells"
    citations = cast(list[Json], row["citations"])
    assert len(citations) == len(cited)
    for stored, original in zip(citations, cited, strict=True):
        assert stored["source"] == "screening_result"
        assert cast(Json, stored["locator"])["cell"] == original["cell"]
        if original.get("quote"):
            assert isinstance(stored["quote_sha256"], str)
    text = json.dumps(row, default=str)
    for original in cited:
        for key in ("quote", "value"):
            if isinstance(original.get(key), str) and len(cast(str, original[key])) > 3:
                assert cast(str, original[key]) not in text  # never the quoted words
    assert cast(Json, row["outcome"])["state"] == "succeeded"
    assert cast(Json, cast(Json, row["outcome"])["outputs"]) == {"screening_result": 1}
    assert row["started_at"] == run["started_at"]
    assert row["completed_at"] == run["finished_at"]
    assert row["record_sha256"] == record_sha256(row)

    events = [e for e in await seed.events(world.tenant_id) if e.action == PERSISTED]
    assert len(events) == 1
    assert events[0].actor_kind == "system"
    assert events[0].target_id == str(run_id)
    assert events[0].after == {"record_sha256": row["record_sha256"]}


async def test_ac44_persisting_again_writes_nothing_more(seed: Seeder, world: World) -> None:
    run_id = await _screened(world)
    first = await persist_run_record(world.tenant_id, run_id)
    again = await persist_run_record(world.tenant_id, run_id)
    assert first is not None and again == first
    assert (
        await seed.value("SELECT count(*) FROM agent_run_records WHERE run_id = $1", run_id) == 1
    )
    assert (await seed.actions(world.tenant_id)).count(PERSISTED) == 1


async def test_ac44_a_running_run_gets_no_record_yet(seed: Seeder, world: World) -> None:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    assert await persist_run_record(world.tenant_id, run_id) is None
    assert (
        await seed.value("SELECT count(*) FROM agent_run_records WHERE run_id = $1", run_id) == 0
    )


async def test_ac44_an_unknown_run_is_a_non_retryable_failure(world: World) -> None:
    with pytest.raises(ApplicationError) as caught:
        await _activity(RunInput(str(world.tenant_id), str(uuid.uuid4())))
    assert caught.value.non_retryable
    with pytest.raises(NotFound):
        await persist_run_record(world.tenant_id, uuid.uuid4())


async def test_ac44_a_run_completed_90_days_ago_still_yields_its_record_after_the_trace(
    seed: Seeder, world: World, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    run_id = await _screened(world)
    digest = await persist_run_record(world.tenant_id, run_id)
    stored = await _record_row(seed, run_id)
    # The raw trace expires (ADR-032, ~30 days): the gateway's attempts are gone.
    await seed.run("DELETE FROM usage_records WHERE agent_run_id = $1", run_id)

    with frozen(system_now() + timedelta(days=90)):
        found = await record_for(world.requester.context(), run_id)
    assert found.record_sha256 == digest == stored["record_sha256"]
    assert found.projection == "content"
    assert found.prompt_ref == stored["prompt_ref"] and found.model == stored["model"]
    assert found.input_hashes == stored["input_hashes"]
    assert found.records_read == stored["records_read"] and found.records_read
    assert found.citations == stored["citations"] and found.citations
    assert record_sha256(stored) == digest  # the fields still hash to what was audited

    net = Net(seed, http, idp)
    response = await net.call("GET", f"/v1/agent-runs/{run_id}/record", world.requester)
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    assert body["record_sha256"] == digest
    assert body["capability"] == SCREENER
    assert cast(Json, body["outcome"])["state"] == "succeeded"
    assert len(cast(list[Json], body["citations"])) == len(cast(list[Json], stored["citations"]))
    trace = await net.call("GET", f"/v1/agent-runs/{run_id}/trace", world.requester)
    assert trace.status_code == 200 and cast(Json, trace.json())["attempts"] == 0


async def test_ac44_the_record_read_answers_404_until_persisted_and_to_outsiders(
    seed: Seeder, world: World, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    run_id = await _screened(world)
    net = Net(seed, http, idp)
    path = f"/v1/agent-runs/{run_id}/record"
    assert (await net.call("GET", path, world.requester)).status_code == 404
    await persist_run_record(world.tenant_id, run_id)
    assert (await net.call("GET", path, world.requester)).status_code == 200
    outsider = await seed.person(world.tenant_id)  # a member of the firm, not the engagement
    assert (await net.call("GET", path, outsider)).status_code in (403, 404)
    other_firm = await seed.person(await seed.firm())
    assert (await net.call("GET", path, other_firm)).status_code in (403, 404)


async def test_ac44_records_are_insert_only_and_written_by_the_system_only(
    seed: Seeder, world: World
) -> None:
    run_id = await _screened(world)
    await persist_run_record(world.tenant_id, run_id)
    system = TenantContext(world.tenant_id, "system", f"agent-run:{run_id}")
    for statement in (
        "UPDATE agent_run_records SET stage = 'shadow'",
        "DELETE FROM agent_run_records",
        "TRUNCATE agent_run_records",
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(system) as session:
                await session.execute(text(statement))
    # A person's context cannot write one (ADR-169: the run's workflow writes it).
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            world.tenant_id,
            ("human", str(world.requester.user_id)),
            "INSERT INTO agent_run_records SELECT * FROM agent_run_records WHERE run_id = $1",
            run_id,
        )
