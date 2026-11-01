"""A-04-T11 (TASK-2819; A-04 §3.1 AC1.1, §6 AC6.1; SPEC-620; DEC-1868): the section drafter.

Row acceptance: "On the fake model a draft writes cited suggestions only, an uncited value is
dropped and flagged Unsupported, an uncleared real firm gets 409 drafting_not_enabled, and the
seeded pack error fails the run before any model call." Also: a number nothing shows is dropped
(number provenance), the route answers 202 with the run it started, and a replayed start answers
the same run.

Boundary: `create_app()` over HTTP for the route (Temporal's `dispatch` captured); the run's draft
through `section_draft.draft` with the agent context proven from the run row, on the fake model.
The firm imports BH EBP v1 to v3 through K-01's workbook route; the engagement pins v3, whose
BH-EBP-140 step 8 carries the seeded defect.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from typing import Final, cast

import pytest

from abacus.ai_gateway import FakeModel, ModelRequest, configure_provider
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.agents import section_draft
from abacus.modules.agents.service import load_agent_context
from abacus.modules.methodology.api import version_steps
from abacus.modules.workpapers.api import PackConfigurationError
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import spec_of, workbook

from .tb_support import Books, Json, books
from .test_k01t05_methodology_programs import (
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
)

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("workpapers.core", "workpapers.drafting", "methodology.programs")
TEMPLATE: Final = "BH Audit Methodology · EBP"
PROMPT: Final = "workpapers.section_draft@v1"
PACK_ERROR: Final = (
    "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that "
    "EBP v3 does not include. No evidence written."
)
_STEP: Final = re.compile(r"S1: [A-Z0-9-]+ step \d+: ([^\"\\]+)")
CALLS: list[str] = []


def _answer(request: ModelRequest) -> str:
    """Three cells: B2 cited to S1 (kept), B3 uncited (dropped), B4 a number nothing shows."""
    CALLS.append(PROMPT)
    found = _STEP.search(request.user)
    quote = " ".join((found.group(1) if found else "").split()[:4]) or "none"
    return json.dumps(
        {
            "cells": [
                {
                    "cell": "B2",
                    "text": "Planned per the firm's program.",
                    "citations": [{"step": "S1", "quote": quote}],
                },
                {"cell": "B3", "text": "Keystone is relevant."},
                {
                    "cell": "B4",
                    "text": "Covers 999,999 of assets.",
                    "citations": [{"step": "S1", "quote": quote}],
                },
            ]
        }
    )


@pytest.fixture(autouse=True)
def _model() -> Iterator[None]:
    CALLS.clear()
    fake = FakeModel()
    fake.respond(PROMPT, _answer)
    configure_provider(fake)
    yield
    configure_provider(None)


@pytest.fixture
async def world(net: object, monkeypatch: pytest.MonkeyPatch) -> tuple[Books, uuid.UUID]:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T11') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    version = uuid.UUID(int=0)
    for number in (1, 2, 3):
        version = await _import(found.net, found.admin, TEMPLATE, workbook(spec_of("ebp", number)))
    await found.seed.run_untriggered(
        "UPDATE engagements SET methodology_version_id = $1 WHERE id = $2",
        version,
        found.site.engagement_id,
    )

    async def captured(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(section_draft, "dispatch", captured)
    monkeypatch.setattr(section_draft, "model_available", lambda: True)
    return found, version


async def _keys(world: Books, version: uuid.UUID, program: str) -> list[str]:
    steps = await version_steps(TenantContext(world.tenant_id, "system", "a04t11"), version)
    return [s.step_key for s in steps.steps if s.program_code == program]


async def _paper(world: Books, kind: str, keys: list[str]) -> uuid.UUID:
    paper = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "audit_area, created_by, kind, program_step_keys) VALUES ($1, $2, $3, $4, $5, $6, "
        "'Planning', $7, $8, $9)",
        paper,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
        "GAP" if kind == "general_audit_planning" else "IC",
        "General Audit Planning" if kind == "general_audit_planning" else "Internal Control",
        world.manager.user_id,
        kind,
        keys,
    )
    await world.seed.run(
        "INSERT INTO workpaper_sections (tenant_id, workpaper_id, sheet_key, title, position, "
        "band_kind) VALUES ($1, $2, 'planning', 'Planning', 0, 'menu')",
        world.tenant_id,
        paper,
    )
    for cell in ("B2", "B3", "B4"):
        await world.seed.run(
            "INSERT INTO workpaper_cells (tenant_id, workpaper_id, sheet_key, cell_key, "
            "value_source, set_by, section_key, row_key, col_key, value_state) VALUES ($1, $2, "
            "'main', $3, 'human', $4, 'planning', $5, 'B', 'empty')",
            world.tenant_id,
            paper,
            cell,
            world.manager.user_id,
            cell[1:],
        )
    return paper


async def _start(world: Books, paper: uuid.UUID, key: str | None = None) -> tuple[int, Json]:
    response = await world.net.http.post(
        f"/v1/engagements/{world.site.engagement_id}/workpapers/{paper}/drafts",
        json={"mode": "gap", "section_key": "planning"},
        headers={
            **world.net.headers(world.manager),
            "Idempotency-Key": key or str(uuid.uuid4()),
        },
    )
    return response.status_code, cast(Json, response.json())


async def test_ac_a_draft_writes_cited_suggestions_only_and_flags_the_unsupported(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, version = world
    paper = await _paper(
        books_, "general_audit_planning", (await _keys(books_, version, "BH-EBP-110"))[:4]
    )
    status, body = await _start(books_, paper)
    assert status == 202, body
    run_id = uuid.UUID(cast(str, body["run_id"]))
    agent = await load_agent_context(books_.tenant_id, run_id)
    outcome = await section_draft.draft(agent, paper, "gap", "planning")
    assert outcome.status == "completed"
    assert len(outcome.suggestion_ids) == 1
    assert {(u.cell, u.reason) for u in outcome.unsupported} == {
        ("B3", "uncited"),
        ("B4", "number_without_provenance"),
    }
    suggestion = await books_.seed.rows(
        "SELECT target_type, target_id, field_key, proposed_value, cardinality(citation_ids) AS n "
        "FROM suggestions WHERE agent_run_id = $1",
        run_id,
    )
    assert [(r["target_type"], r["target_id"], r["field_key"], r["n"]) for r in suggestion] == [
        ("workpaper_cell", paper, "B2", 1)
    ]
    # Suggestions only: no cell row and no version from the agent (AC1.1).
    assert (
        await books_.seed.value(
            "SELECT count(*) FROM workpaper_cells WHERE workpaper_id = $1", paper
        )
        == 3
    )
    assert (
        await books_.seed.value(
            "SELECT count(*) FROM workpaper_versions WHERE workpaper_id = $1 "
            "AND produced_by_kind = 'agent'",
            paper,
        )
        == 0
    )
    output = await books_.seed.value("SELECT output FROM agent_runs WHERE id = $1", run_id)
    unsupported = cast(Json, json.loads(output) if isinstance(output, str) else output)[
        "unsupported"
    ]
    assert {(u["cell"], u["reason"]) for u in cast(list[Json], unsupported)} == {
        ("B3", "uncited"),
        ("B4", "number_without_provenance"),
    }


async def test_a_replayed_start_answers_the_same_run(world: tuple[Books, uuid.UUID]) -> None:
    books_, version = world
    paper = await _paper(
        books_, "general_audit_planning", (await _keys(books_, version, "BH-EBP-110"))[:4]
    )
    key = str(uuid.uuid4())
    first = await _start(books_, paper, key)
    again = await _start(books_, paper, key)
    assert first[0] == 202 and first[1]["run_id"] == again[1]["run_id"]


async def test_ac_an_uncleared_real_firm_gets_409_drafting_not_enabled(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, version = world
    paper = await _paper(
        books_, "general_audit_planning", (await _keys(books_, version, "BH-EBP-110"))[:4]
    )
    await books_.seed.run_untriggered(
        "UPDATE firms SET synthetic = false WHERE tenant_id = $1", books_.tenant_id
    )
    status, body = await _start(books_, paper)
    assert (status, body["detail"]) == (409, "drafting_not_enabled")
    assert (
        await books_.seed.value(
            "SELECT count(*) FROM agent_runs WHERE agent_id = 'workpapers.section_drafter'"
        )
        == 0
    )


async def test_ac_the_seeded_pack_error_fails_the_run_before_any_model_call(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, version = world
    paper = await _paper(books_, "internal_control", await _keys(books_, version, "BH-EBP-140"))
    status, body = await _start(books_, paper)
    assert status == 202, body
    run_id = uuid.UUID(cast(str, body["run_id"]))
    agent = await load_agent_context(books_.tenant_id, run_id)
    with pytest.raises(PackConfigurationError):
        await section_draft.draft(agent, paper, "ic", "planning")
    assert CALLS == []  # no model call
    run = (
        await books_.seed.rows(
            "SELECT status, failure_code, output FROM agent_runs WHERE id = $1", run_id
        )
    )[0]
    assert (run["status"], run["failure_code"]) == ("failed", "pack_configuration_error")
    output = cast(
        Json, json.loads(run["output"]) if isinstance(run["output"], str) else run["output"]
    )
    assert output["message"] == PACK_ERROR
    assert (
        await books_.seed.value("SELECT count(*) FROM suggestions WHERE agent_run_id = $1", run_id)
        == 0
    )
    assert (
        await books_.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'section_draft.failed'",
            books_.tenant_id,
        )
        == 1
    )
