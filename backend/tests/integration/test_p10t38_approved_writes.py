"""P-10-T38 (TASK-6802; SPEC-647 AC-P1 to AC-P6; ADR P-35; DEC-3402): the proposals bridge and the
approved write, against Postgres.

Row acceptance: "Hannah Leclerc's approval saves the workbook only after 10 s under the actor
Hannah Leclerc via Agent, Undo inside 10 s leaves Files unchanged, and an approver who lost
file.save blocks it."

A v2 run builds its workbook and proposes "Save to Files" through C17 (`call_tool`); it ends
"Ready for review" (`succeeded`); Hannah approves at 9:27 AM. The executor's activity runs under
the frozen business clock (a synthetic firm), so "before" and "after" the window are exact.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import cast

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.agents.approved_write_workflow import ApprovedWriteInput
from abacus.modules.agents.approved_writes import execute_approved_write, rederive_run
from abacus.modules.agents.file_tools import SAVE_TOOL
from abacus.modules.agents.proposal_undo import undo_proposal
from abacus.modules.agents.proposals import approve_proposal
from abacus.modules.agents.service import load_run_v2_context, load_write_context
from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool
from abacus.modules.identity.api import GrantNotYetDue

from .conftest import MigratedDatabase
from .review_support import Cast, make_cast, person_ctx

pytestmark = pytest.mark.asyncio
T0 = datetime.fromisoformat("2026-09-14T09:27:00-05:00")


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture
async def team(migrated_db: MigratedDatabase) -> Cast:
    found = await make_cast(migrated_db.superuser_dsn)
    await found.seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", found.tenant)
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t38', 'P-10-T38') ON CONFLICT DO NOTHING",
        found.tenant,
    )
    forget_flags()
    return found


async def _cite(team: Cast) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await team.seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, locator, verified, verifier_version, created_by_kind, "
            "created_by_run_id) VALUES ($1, $2, 'proposal_probe', $3, 1, 'record_field', "
            '\'tax_return\', $3, \'{"record_type": "tax_return", "field": "line"}\', true, '
            "'v1', 'agent', $3) RETURNING id",
            team.tenant,
            team.engagement,
            uuid.uuid4(),
        ),
    )


async def _run(team: Cast) -> uuid.UUID:
    run_id = uuid.uuid4()
    client = await team.seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", team.engagement
    )
    await team.seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, client_scope) "
        "VALUES ($1, $2, 'audit.planning', 2, $3, $4, ARRAY['file.propose', 'proposal.create'], "
        "'running', 'run', 'manual', 4118, ARRAY[$5::uuid])",
        run_id,
        team.tenant,
        team.engagement,
        team["marcus"].user_id,  # Marcus Delaney started the run; Hannah decides its write
        client,
    )
    return run_id


async def _proposed(team: Cast) -> tuple[uuid.UUID, uuid.UUID]:
    """The run builds and proposes; then it ends "Ready for review"."""
    run_id = await _run(team)
    agent = await load_run_v2_context(team.tenant, run_id)
    built = await call_tool(
        agent,
        ToolCallIn(
            run_id=run_id,
            step_seq=3,
            attempt=1,
            name="files.build_workbook",
            arguments={
                "name": "TY2025 Season Progress — by office",
                "sheets": [{"title": "Summary", "rows": [["Office", "Open"], ["Chicago", 82]]}],
                "citation_ids": [str(await _cite(team))],
            },
        ),
    )
    assert built.ok, built.code
    artifact = cast(dict[str, object], built.result)["artifact_id"]
    proposed = await call_tool(
        agent,
        ToolCallIn(
            run_id=run_id,
            step_seq=4,
            attempt=1,
            name="files.propose_save",
            arguments={"artifact_id": artifact, "folder": "deliverables"},
        ),
    )
    assert proposed.ok, proposed.code
    await team.seed.run(
        "UPDATE agent_runs SET state = 'succeeded', finished_at = now() WHERE id = $1", run_id
    )
    return run_id, uuid.UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))


async def _approve(team: Cast, proposal: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    with frozen(T0):
        view = await approve_proposal(
            person_ctx(team["hannah"]), proposal, seen_version=1, edits=[]
        )
    decision = await team.seed.rows(
        "SELECT id, approval_grant_id FROM proposal_decisions WHERE proposal_id = $1", proposal
    )
    assert view is not None and len(decision) == 1
    return cast(uuid.UUID, decision[0]["id"]), cast(uuid.UUID, decision[0]["approval_grant_id"])


def _input(
    team: Cast, run_id: uuid.UUID, proposal: uuid.UUID, grant: uuid.UUID
) -> ApprovedWriteInput:
    return ApprovedWriteInput(str(team.tenant), str(run_id), str(proposal), str(grant), SAVE_TOOL)


async def _files(team: Cast) -> int:
    return cast(
        int,
        await team.seed.value(
            "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1 AND source = 'agent_run'",
            team.tenant,
        ),
    )


async def test_ac_p1_the_copy_lands_only_after_10_seconds_as_hannah_via_agent(team: Cast) -> None:
    run_id, proposal = await _proposed(team)
    _, grant = await _approve(team, proposal)
    due = await team.seed.value(
        "SELECT extract(epoch FROM not_before - created_at) FROM approval_grants WHERE id = $1",
        grant,
    )
    assert grant is not None and float(cast(float, due)) >= 9.0
    with frozen(T0.replace(second=5)), pytest.raises(GrantNotYetDue):
        await execute_approved_write(_input(team, run_id, proposal, grant))
    assert await _files(team) == 0
    with frozen(T0.replace(second=11)):
        assert await execute_approved_write(_input(team, run_id, proposal, grant)) == "saved"
    assert await _files(team) == 1
    saved = await team.seed.rows(
        "SELECT actor_kind, on_behalf_of_user_id, after_ref FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'file.saved'",
        team.tenant,
    )
    assert len(saved) == 1
    assert saved[0]["actor_kind"] == "agent"
    assert saved[0]["on_behalf_of_user_id"] == team["hannah"].user_id
    after = saved[0]["after_ref"]
    after = json.loads(after) if isinstance(after, str) else after
    assert after["grant"] == str(grant)
    with frozen(T0.replace(second=12)):
        assert await rederive_run(team.tenant, run_id) == "approved"
    # Spent once: the same call again saves nothing new.
    with frozen(T0.replace(second=13)):
        await execute_approved_write(_input(team, run_id, proposal, grant))
    assert await _files(team) == 1


async def test_ac_p2_undo_inside_10_seconds_leaves_files_unchanged(team: Cast) -> None:
    run_id, proposal = await _proposed(team)
    decision, grant = await _approve(team, proposal)
    with frozen(T0.replace(second=4)):
        await undo_proposal(person_ctx(team["hannah"]), proposal, decision)
    with frozen(T0.replace(second=11)):
        assert await execute_approved_write(_input(team, run_id, proposal, grant)) == "undone"
        assert await rederive_run(team.tenant, run_id) == "succeeded"
    assert await _files(team) == 0
    voided = await team.seed.value(
        "SELECT voided_at IS NOT NULL FROM approval_grants WHERE id = $1", grant
    )
    assert voided is True


async def test_ac_p3_an_approver_who_lost_file_save_blocks_it(team: Cast) -> None:
    run_id, proposal = await _proposed(team)
    _, grant = await _approve(team, proposal)
    await team.seed.run(
        "UPDATE memberships SET status = 'revoked', revoked_at = now() "
        "WHERE tenant_id = $1 AND user_id = $2",
        team.tenant,
        team["hannah"].user_id,
    )
    with frozen(T0.replace(second=11)):
        reason = await execute_approved_write(_input(team, run_id, proposal, grant))
    assert reason == "approver_lost_action"
    assert await _files(team) == 0
    failed = await team.seed.rows(
        "SELECT payload FROM run_events WHERE run_id = $1 AND type = 'proposal.write_failed'",
        run_id,
    )
    assert len(failed) == 1


async def test_ac_p6_the_agent_never_issues_or_spends_a_grant_for_itself(team: Cast) -> None:
    run_id, proposal = await _proposed(team)
    agent = await load_write_context(team.tenant, run_id)
    # No grant: the write is refused before its handler runs.
    refused = await call_tool(
        agent,
        ToolCallIn(
            run_id=run_id,
            step_seq=9,
            attempt=1,
            name=SAVE_TOOL,
            arguments={"proposal_id": str(proposal)},
        ),
    )
    assert (refused.ok, refused.code) == (False, "no_grant")
    assert await _files(team) == 0
