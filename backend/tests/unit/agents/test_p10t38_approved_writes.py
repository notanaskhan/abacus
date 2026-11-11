"""P-10-T38 (TASK-6802; SPEC-647 AC-P1 to AC-P6; DEC-3402): the proposals bridge's code rules.

Row acceptance: "Hannah Leclerc's approval saves the workbook only after 10 s under the actor
Hannah Leclerc via Agent, Undo inside 10 s leaves Files unchanged, and an approver who lost
file.save blocks it."
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from abacus.kernel.safe_xlsx import Sheet
from abacus.modules.agents.approved_write_workflow import UNDO_WINDOW, approved_write_id
from abacus.modules.agents.approved_writes import (
    HeldEffect,
    derive_outcome,
    grant_window,
    held_effect,
    write_arguments,
    write_digest,
    write_seq,
)
from abacus.modules.agents.file_tools import FILE_SAVE, SAVE, SAVE_TOOL
from abacus.modules.agents.tools.registry import (
    AgentTool,
    ToolInvalid,
    registered_tools,
    validate_tool,
)
from abacus.modules.agents.tools.runtime import args_hash
from abacus.modules.evidence.run_files import WorkbookTooLarge, workbook_bytes


def test_ac_p5_the_outcome_follows_every_proposal() -> None:
    assert derive_outcome(["approved"] * 3 + ["rejected"] * 2) == "partially_approved"
    assert derive_outcome(["approved", "approved_with_edits"]) == "approved"
    assert derive_outcome(["rejected", "rejected"]) == "rejected"
    assert derive_outcome(["approved", "pending"]) == "succeeded"  # "Ready for review"
    assert derive_outcome([]) == "succeeded"


def test_ac_p1_the_grant_is_due_after_the_undo_window() -> None:
    decided = datetime(2026, 9, 14, 14, 27, tzinfo=UTC)  # 9:27 AM CT
    not_before, expires = grant_window(decided)
    assert not_before - decided == UNDO_WINDOW == timedelta(seconds=10)
    assert expires > not_before


def test_the_grant_pays_for_exactly_one_call() -> None:
    proposal = uuid.uuid4()
    effect = HeldEffect(SAVE_TOOL, SAVE)
    assert write_digest(effect, proposal) == args_hash(SAVE_TOOL, write_arguments(proposal))
    assert write_digest(effect, uuid.uuid4()) != write_digest(effect, proposal)
    assert write_seq(proposal) >= 1_000_000
    assert approved_write_id("t", "g") == "approved_write:t:g"


def test_file_save_holds_its_effect_on_file_save() -> None:
    import abacus.modules.agents.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the held effect

    assert held_effect(FILE_SAVE) == HeldEffect(SAVE_TOOL, SAVE)


def test_the_files_tools_are_registered_by_kind() -> None:
    import abacus.modules.agents.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the tools

    tools = registered_tools()
    assert tools["files.build_workbook"].kind == "compute"
    assert tools["files.propose_save"].kind == "propose"
    assert tools["files.propose_save"].action == "file.propose"
    save = tools[SAVE_TOOL]
    assert (save.kind, save.action, save.scope_action) == (
        "approved_write",
        "file.save",
        "file.propose",
    )


class _In(BaseModel):
    proposal: int = 0


class _Out(BaseModel):
    id: uuid.UUID


async def _noop(*_: object) -> _Out:
    return _Out(id=uuid.uuid4())


def test_an_approved_write_must_declare_its_scope_action() -> None:
    bare = AgentTool(
        "files.save_copy",
        "approved_write",
        "file.save",
        "tool.files.save_copy@v1",
        "internal",
        _In,
        _Out,
        _noop,
    )
    with pytest.raises(ToolInvalid):
        validate_tool(bare)
    with pytest.raises(ToolInvalid):  # its own action is never its reach
        validate_tool(
            AgentTool(
                "files.save_copy",
                "approved_write",
                "file.save",
                "tool.files.save_copy@v1",
                "internal",
                _In,
                _Out,
                _noop,
                scope_action="file.save",
            )
        )
    with pytest.raises(ToolInvalid):  # only an approved_write declares one
        validate_tool(
            AgentTool(
                "files.read_copy",
                "read",
                "evidence.read",
                "tool.files.read_copy@v1",
                "internal",
                _In,
                _Out,
                _noop,
                scope_action="file.propose",
            )
        )


def test_the_workbook_is_deterministic_and_bounded() -> None:
    sheets = [Sheet("Summary", [["Office", "Open"], ["Chicago", 82], ["=HYPERLINK()", 1]])]
    assert workbook_bytes(sheets) == workbook_bytes(sheets)
    with pytest.raises(WorkbookTooLarge):
        workbook_bytes([])
    with pytest.raises(WorkbookTooLarge):
        workbook_bytes([Sheet(f"S{n}", []) for n in range(13)])
