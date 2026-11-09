"""A-07-T32 (TASK-6509; A-07 §6, F10; DEC-3109): code-only capabilities on the v1 recording path.

Row acceptance: five capabilities with a code plan, ToolCards, AgentBlocks narration from
templates ("I have not evaluated them"), verified citations, and drafts or suggestions only.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import code_runs
from abacus.modules.agents.blocks import BlocksRejected, Fact
from abacus.modules.assurance import agent_capabilities as caps

pytestmark = pytest.mark.asyncio
ENGAGEMENT, WORK_ITEM, PERSON = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _run(**over: object) -> code_runs.CodeRun:
    base: dict[str, object] = {
        "agent_id": caps.EQR_DIGEST,
        "engagement_id": ENGAGEMENT,
        "initiator_user_id": PERSON,
        "task_scope": ("eqr.build_digest",),
        "steps": (code_runs.CodeStep("eqr.assemble_digest", "Assemble judgments digest"),),
        "narration": code_runs.blocks(
            code_runs.text_part(code_runs.txt("I assembled "), code_runs.fact("cards"))
        ),
        "facts": {"cards": Fact(id="cards", kind="count", value="6", basis="cards")},
    }
    base.update(over)
    return code_runs.CodeRun(**base)  # type: ignore[arg-type]  # test overrides


@pytest.mark.parametrize(
    "tool", ["report.release", "archive.lock", "eqr.concur", "rep_letter.send"]
)
def test_a_plan_never_names_a_final_verb(tool: str) -> None:
    with pytest.raises(code_runs.ReservedAction):
        code_runs.check_plan(_run(steps=(code_runs.CodeStep(tool, "x"),)))


def test_the_five_plans_name_no_reserved_verb() -> None:
    for tool in (
        "eqr.assemble_digest",
        "completion.check_sign_offs",
        "completion.check_review_notes",
        "ebp.read_tie_out",
        "completion.refresh_procedures",
        "independence.request_reconfirmation",
        "rep_letter.compose_draft",
        "governance_letter.compose_draft",
        "archive.build_index",
        "archive.check_items",
    ):
        code_runs.check_plan(_run(steps=(code_runs.CodeStep(tool, "x"),)))


@pytest.mark.parametrize(
    "words", ["I approved the release.", "The report was signed off.", "There are 6 cards."]
)
async def test_narration_with_a_human_act_or_a_free_number_writes_nothing(words: str) -> None:
    run = _run(narration=code_runs.blocks(code_runs.text_part(code_runs.txt(words))))

    @asynccontextmanager
    async def never() -> AsyncIterator[None]:
        raise AssertionError("nothing is written")
        yield

    tx = SimpleNamespace(session=SimpleNamespace(execute=never), record=None)
    with pytest.raises(BlocksRejected):
        await code_runs.record_code_run(tx, uuid.uuid4(), run)  # type: ignore[arg-type]  # double


async def test_the_digest_says_it_has_not_evaluated_them(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[code_runs.CodeRun] = []

    async def item(_t: TenantContext, _w: uuid.UUID) -> object:
        return SimpleNamespace(engagement_id=ENGAGEMENT)

    async def build(_ctx: object, _w: uuid.UUID) -> int:
        return 2

    async def record(_t: TenantContext, run: code_runs.CodeRun) -> uuid.UUID:
        code_runs.validate_blocks(run.narration, run.facts, run.citations)
        recorded.append(run)
        return uuid.uuid4()

    @asynccontextmanager
    async def session(_t: TenantContext) -> AsyncIterator[object]:
        async def scalar(*_a: object, **_k: object) -> int:
            return 6

        yield SimpleNamespace(scalar=scalar)

    from abacus.modules.assurance import eqr_service

    monkeypatch.setattr(caps, "assurance_item", item)
    monkeypatch.setattr(eqr_service, "build_digest", build)
    monkeypatch.setattr(caps, "_record", record)
    monkeypatch.setattr(caps, "tenant_session", session)
    ctx = SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "human", str(PERSON)), user_id=PERSON)
    await caps.eqr_digest(ctx, WORK_ITEM)  # type: ignore[arg-type]  # a test double
    (run,) = recorded
    words = " ".join(
        str(s.get("text", ""))
        for p in run.narration["parts"]
        for s in p["segments"]  # type: ignore[index, union-attr]  # AgentBlocks payload
    )
    assert "I have not evaluated them." in words
    assert run.facts["cards"].value == "6" and run.initiator_user_id == PERSON


def test_every_capability_has_a_dock_label() -> None:
    from abacus.modules.agents.runs import AGENT_LABEL

    assert set(caps.CAPABILITIES) <= set(AGENT_LABEL)
