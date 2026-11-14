"""W-02-T19 (TASK-7935; W-02 §3.6, §3.7, §4.2; DEC-4930): session plans and partial failure.

Row acceptance: "Gathering starts only after Hannah approves the plan, an edited plan is
re-validated, and Retry those 3 reads only the 3 failed binders."

Without Temporal or a database: the plan card's fields from the run plan, the edit rules, the
failure ledger's shape and its lift from a tool's output, the binders read's ledger, and the two
new tools. The workflow's `items_retry` path replays from `agent-run-v1-failed-items-retry.json`
(recorded at the S43 end pass with Docker up).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from abacus.kernel.agent_tools import ONLY_REFS, FailedItem
from abacus.modules.agents import commands
from abacus.modules.agents.run_plan import READ_SOURCES, PlanContext, PlanStep, validate_plan
from abacus.modules.agents.tools.registry import row_fields

HANNAH = str(uuid4())
SAVE = "file.propose"
CTX = PlanContext(
    declared_writes=frozenset({SAVE}),
    client_scope=frozenset(),
    approver_holds={(HANNAH, SAVE): True},
    tool_actions={"files.propose_save": SAVE},
)


def _season_plan() -> list[PlanStep]:
    """AC-P1: the four steps of WB-03a, with the counts the planner's code declared."""
    return [
        PlanStep(
            "s1", "Read TY2025 returns, engagements and binders (read-only)", 0, "tool",
            "tax.season_counts",
            reads=(("tax_returns", 224), ("tax_engagements", 214), ("binders", 241),
                   ("offices", 3)),
        ),
        PlanStep("s2", "Group open returns by stage and office", 1, "compute",
                 "tax.season_counts", depends_on=("s1",)),
        PlanStep("s3", "Build the workbook: Summary, Gather, Prepare, Review, Deliver", 2,
                 "compute", "files.build_workbook",
                 arguments={"name": "TY2025 Season Progress — by office"}, depends_on=("s2",)),
        PlanStep("s4", "Save the workbook to Files", 3, "tool", "files.propose_save",
                 arguments={"folder": "deliverables"}, depends_on=("s3",), writes=(SAVE,),
                 approver_user_id=HANNAH),
    ]  # fmt: skip


def test_ac_p1_the_plan_card_reads_its_sources_with_counts_in_code_words() -> None:
    reads = commands.plan_reads(_season_plan())
    assert [(r.label, r.count) for r in reads] == [
        ("Tax returns", 224),
        ("Tax engagements", 214),
        ("Binders", 241),
        ("Offices", 3),
    ]
    assert all(r.label == READ_SOURCES[r.source] for r in reads)


def test_ac_p1_the_write_names_the_built_file_and_its_folder() -> None:
    steps = _season_plan()
    label = commands.write_label(steps[3], steps)
    assert label == "Create file TY2025 Season Progress — by office.xlsx in Files › Deliverables"


def test_a_plan_declaring_an_unknown_source_or_a_bad_count_is_refused() -> None:
    steps = _season_plan()
    bad = [PlanStep("x", "x", 0, "tool", "engagements.list", reads=(("payroll", 3),))]
    assert validate_plan(steps, CTX) == []
    assert "unknown_read_source:x" in validate_plan(bad, CTX)
    parsed = PlanStep.parse({"key": "y", "tool": "engagements.list", "reads": [{"source": "x"}]})
    assert parsed.reads == (("x", -1),)


def test_reads_round_trip_and_an_old_plan_dumps_unchanged() -> None:
    step = _season_plan()[0]
    assert PlanStep.parse(step.dump()) == step
    plain = PlanStep("k", "k", 0, "tool", "engagements.list")
    assert "reads" not in plain.dump()  # payloads of runs recorded before W-02-T19 stay the same


def test_ac_p3_an_edit_rewords_kept_steps_and_never_their_effect() -> None:
    steps = _season_plan()
    edited = commands._edited(  # pyright: ignore[reportPrivateUsage] -- the edit rule itself
        steps, ["s1", "s2", "s3", "s4"], {"s2": "Group open returns by office only"}
    )
    assert edited[1].label == "Group open returns by office only"
    assert edited[1].tool == steps[1].tool and edited[3].writes == steps[3].writes
    with pytest.raises(commands.PlanEditInvalid):
        commands._edited(steps, ["s1", "s2"], {"s4": "Save it"})  # pyright: ignore[reportPrivateUsage]


def test_ac_p3_an_edited_plan_whose_approver_lost_the_write_is_refused() -> None:
    steps = _season_plan()
    lost = PlanContext(
        declared_writes=CTX.declared_writes,
        client_scope=CTX.client_scope,
        approver_holds={},
        tool_actions=CTX.tool_actions,
    )
    assert validate_plan(steps, lost) == ["approver_lacks_action:s4"]


def test_the_failure_ledger_holds_references_and_codes_only() -> None:
    item = FailedItem(ref_type="binder", ref_id=str(uuid4()), source="binders",
                      error_code="not_readable")  # fmt: skip
    assert set(item.model_dump()) == {"ref_type", "ref_id", "source", "error_code"}
    with pytest.raises(ValidationError):
        FailedItem(ref_type="binder", ref_id="Feld K-1 from Box.pdf", source="binders",
                   error_code="not_readable")  # fmt: skip
    with pytest.raises(ValidationError):
        FailedItem.model_validate(item.model_dump() | {"detail": "Box said no"})


def test_the_ledger_is_not_a_row_list() -> None:
    from abacus.modules.requests.agent_tools import BindersOut

    assert "failed_items" not in row_fields(BindersOut)
    assert "binders" in row_fields(BindersOut)


def test_a_tool_outcome_lifts_the_outputs_ledger() -> None:
    from abacus.modules.agents.tools.runtime import (
        _failed_items,  # pyright: ignore[reportPrivateUsage] -- the lift itself
    )
    from abacus.modules.requests.agent_tools import BindersOut

    item = FailedItem(ref_type="binder", ref_id="b1", source="binders", error_code="x")
    assert _failed_items(BindersOut(binders=[], total=0, failed_items=[item])) == [item]
    assert _failed_items(SimpleNamespace(failed_items="no")) == []  # type: ignore[arg-type]


@dataclass(frozen=True)
class _Row:
    id: UUID
    name: str = "Feld 2025"
    client_name: str = "Jonah Feld"
    kind: str = "tax_return"
    status: str = "open"
    total_count: int = 4
    done_count: int = 1
    last_client_activity_at: Any = None


@pytest.mark.asyncio
async def test_ac_g4_binders_read_names_the_binders_it_could_not_reach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry those 3: `only_refs` narrows the read to the ledger, and any still unreadable stay
    in it (here one of three is back, two are not)."""
    from abacus.modules.requests import agent_tools, binder_index

    back, gone_a, gone_b = uuid4(), uuid4(), uuid4()
    page = SimpleNamespace(
        items=[_Row(back), _Row(uuid4())], next_cursor=None, total=241, total_capped=False,
        counts={"open": 2},
    )  # fmt: skip

    async def fake_list(*_: object, **__: object) -> object:
        return page

    monkeypatch.setattr(binder_index, "list_binders", fake_list)
    args = agent_tools.BindersIn(tax_year=2025, only_refs=[back, gone_a, gone_b])
    out = await agent_tools.read_binders(SimpleNamespace(), args)  # type: ignore[arg-type]
    assert [b.id for b in out.binders] == [back]
    assert sorted(i.ref_id for i in out.failed_items) == sorted([str(gone_a), str(gone_b)])
    assert {i.error_code for i in out.failed_items} == {"not_readable"}
    assert ONLY_REFS in agent_tools.BindersIn.model_fields


def test_only_tools_that_take_only_refs_can_retry_items() -> None:
    import abacus.modules.agents.tools.catalogue  # noqa: F401 -- registers the tools
    from abacus.modules.agents.run_commands import takes_only_refs

    assert takes_only_refs("binders.read")
    assert not takes_only_refs("engagements.list")
    assert not takes_only_refs(None)


def test_the_two_red_tools_are_registered_read_only() -> None:
    import abacus.modules.agents.tools.catalogue  # noqa: F401
    from abacus.modules.agents.tools.registry import registered_tools

    tools = registered_tools()
    assert tools["identity.list_offices"].kind == "read"
    assert tools["identity.list_offices"].action == "org_structure.list"
    assert tools["files.list_folders"].kind == "read"
    assert set(tools["files.list_folders"].input_model.model_fields) == {
        "writable_only",
        "parent_ref",
    }


@pytest.mark.asyncio
async def test_list_offices_reads_the_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.identity import agent_tools

    offices = [(uuid4(), "Chicago"), (uuid4(), "Denver"), (uuid4(), "New York")]

    async def fake(_: object) -> list[tuple[UUID, str]]:
        return offices

    monkeypatch.setattr(agent_tools, "firm_offices", fake)
    out = await agent_tools.list_offices(
        SimpleNamespace(tenant=None), agent_tools.ListOfficesIn()  # type: ignore[arg-type]
    )
    assert [o.name for o in out.offices] == ["Chicago", "Denver", "New York"] and out.total == 3


@pytest.mark.asyncio
async def test_list_folders_marks_what_the_approver_can_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.agents import file_tools

    async def resource(*_: object) -> object:
        return object()

    async def could(*_: object, **__: object) -> bool:
        return False

    monkeypatch.setattr(file_tools, "engagement_resource", resource)
    monkeypatch.setattr(file_tools, "member_could", could)
    agent = SimpleNamespace(
        tenant=None, tenant_id=uuid4(), engagement_id=uuid4(),
        initiator=SimpleNamespace(user_id=uuid4()),
    )  # fmt: skip
    none = await file_tools.list_folders(agent, file_tools.ListFoldersIn())  # type: ignore[arg-type]
    assert none.folders == []
    every = await file_tools.list_folders(agent, file_tools.ListFoldersIn(writable_only=False))  # type: ignore[arg-type]
    assert [f.id for f in every.folders] == ["deliverables", "workpapers", "correspondence"]
    assert not any(f.writable for f in every.folders)
    firm = await file_tools.list_folders(
        SimpleNamespace(engagement_id=None), file_tools.ListFoldersIn()  # type: ignore[arg-type]
    )
    assert firm.firm_folders == "unavailable"
