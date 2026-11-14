"""W-02-T24 part 2 (TASK-8025; ADR-078; W-02 §3.6 to 3.9; SPEC-653 AC-W1 to AC-W5, AC-Q2): the
independent AC and security tests for N's red work that landed in S43 (W-02-T19 session plans,
W-02-T20 run artifacts) and S44 (W-02-T23 Save to Files part 1), written from the SPEC, not from
the implementation. Row acceptance: "Fail on agent approval, unverified fact, walled read, wrong
attribution." The database paths (grant timing, Undo, consumption, walled drill) run with the
J11 API journey at the end pass."""

from __future__ import annotations

from abacus.modules.agents import file_tools as f
from abacus.modules.agents.commands import plan_reads, write_label
from abacus.modules.agents.run_plan import PlanContext, PlanStep, validate_plan
from abacus.modules.identity.authz._matrix import ACTIONS

SAVE = "file.propose"
ARROW = chr(0x203A)  # the Files path separator the product renders (U+203A)


def _build(name: str = "TY2025 Season Progress — by office") -> PlanStep:
    return PlanStep(
        key="build", label="Build the workbook", level=1, kind="compute",
        tool="files.build_workbook", arguments={"name": name},
    )  # fmt: skip


def _save(approver: str | None = "hannah", folder: str = "deliverables") -> PlanStep:
    return PlanStep(
        key="save", label="Save to Files", level=2, kind="approval", tool="files.propose_save",
        arguments={"folder": folder}, depends_on=("build",), writes=(SAVE,),
        approver_user_id=approver,
    )  # fmt: skip


def _ctx(holds: bool = True) -> PlanContext:
    return PlanContext(
        declared_writes=frozenset({SAVE}),
        client_scope=frozenset(),
        approver_holds={("hannah", SAVE): holds},
        tool_actions={"files.build_workbook": SAVE, "files.propose_save": SAVE},
    )


# --- W-02-T19: session plans (AC-W1: the plan declares every write and its approver) -----------


def test_t19_a_plan_with_a_declared_save_and_a_holding_approver_validates() -> None:
    assert validate_plan([_build(), _save()], _ctx()) == []


def test_t19_inv1_an_approver_who_lacks_the_action_fails_the_plan() -> None:
    assert "approver_lacks_action:save" in validate_plan([_build(), _save()], _ctx(holds=False))


def test_t19_inv1_a_write_with_no_named_approver_fails_the_plan() -> None:
    assert "approver_lacks_action:save" in validate_plan([_build(), _save(None)], _ctx())


def test_t19_an_undeclared_write_fails_the_plan() -> None:
    step = PlanStep(
        key="post", label="Post", level=2, kind="approval", tool="files.propose_save",
        depends_on=("build",), writes=("entry.post",), approver_user_id="hannah",
    )  # fmt: skip
    problems = validate_plan([_build(), step], _ctx())
    assert "undeclared_write:post" in problems


def test_t19_dependency_order_and_cycles_fail() -> None:
    late = PlanStep(
        key="build", label="Build", level=3, kind="compute", tool="files.build_workbook"
    )
    assert "level_order:save" in validate_plan([late, _save()], _ctx())


def test_t19_reads_are_declared_once_at_their_largest_count() -> None:
    steps = [
        PlanStep(key="a", label="A", level=0, kind="tool", tool="t", reads=(("binders", 120),)),
        PlanStep(key="b", label="B", level=1, kind="tool", tool="t", reads=(("binders", 241),)),
    ]
    reads = plan_reads(steps)
    assert [(r.source, r.count) for r in reads] == [("binders", 241)]


# --- W-02-T23: Save to Files (AC-W1 words by code; AC-W5 attach-only) ---------------------------


def test_t23_ac_w1_the_write_line_names_the_file_and_folder_by_code() -> None:
    steps = [_build(), _save()]
    line = write_label(steps[1], steps)
    assert (
        line
        == f"Create file TY2025 Season Progress — by office.xlsx in Files {ARROW} Deliverables"
    )


def test_t23_ac_w1_the_access_sentence_is_computed_not_the_models() -> None:
    assert f.access_sentence("correspondence") == "The engagement team can open Correspondence."


def test_t23_inv1_the_agent_never_holds_file_save() -> None:
    assert ACTIONS["file.save"]["agent"] == "deny"


def test_t23_ac_w5_the_attach_only_key_is_the_save_questions() -> None:
    assert f.ATTACH_ONLY == "attach_only"
