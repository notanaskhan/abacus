"""P-10-T43 (SPEC-647 AC-S2, AC-S4; DEC-4301): the side queue and the turn's plan, pure.

The workflow's command order is pinned by its recorded histories
(`tests/workflows/test_s37_runs_replay.py`); the HTTP rules are in
`tests/integration/agent_tests/test_p10t43_sessions.py`."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from abacus.modules.agents import session_turns
from abacus.modules.agents.run_plan import PlanContext, PlanStep, validate_plan
from abacus.modules.workbench.session_queue import SessionQueue, SessionWork
from abacus.modules.workbench.sessions import key_hash, ref_of


def test_acs2_a_message_typed_while_a_question_is_open_is_answered_first() -> None:
    queue = SessionQueue()
    queue.message(1)
    first = queue.take()
    assert first is not None and first == SessionWork("message", 1)
    queue.turn_ended(first, asked=2)  # the turn asked: item 2 is the open question
    queue.message(3)  # Hannah types while the question is open
    queue.answer(4, question_seq=2)
    side = queue.take()
    assert side is not None and side == SessionWork("message", 3)
    queue.turn_ended(side, asked=0)
    assert queue.open_question == 2  # the question stays open
    answer = queue.take()
    assert answer is not None and answer == SessionWork("answer", 4, 2)
    queue.turn_ended(answer, asked=0)
    assert queue.open_question == 0 and queue.take() is None


def test_a_stale_answer_is_dropped() -> None:
    queue = SessionQueue(open_question=5)
    queue.answer(6, question_seq=2)  # answers a question that is no longer open
    queue.message(7)
    assert queue.take() == SessionWork("message", 7)


def test_a_new_question_replaces_the_open_one_and_the_queue_survives_continue_as_new() -> None:
    queue = SessionQueue(open_question=2)
    queue.message(3)
    work = queue.take()
    assert work is not None
    queue.turn_ended(work, asked=4)
    queue.message(5)
    pending, open_question = queue.snapshot()
    resumed = SessionQueue.resume(pending, open_question)
    assert resumed.open_question == 4 and resumed.take() == SessionWork("message", 5)


class _ListIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: str = "Firm reports"


class _SaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str


class _ProposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[str]


def _spec(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401 -- a stand-in spec
    tools = {
        "files.list": SimpleNamespace(kind="read", action="file.read", input_model=_ListIn),
        "workbook.compute": SimpleNamespace(
            kind="compute", action="workbook.compute", input_model=_ListIn
        ),
        "files.save_approved": SimpleNamespace(
            kind="approved_write", action="file.save", input_model=_SaveIn
        ),
        "files.propose_save": SimpleNamespace(
            kind="propose", action="proposal.create", input_model=_ProposeIn
        ),
    }
    monkeypatch.setattr(session_turns, "registered_tools", lambda: tools)
    return SimpleNamespace(tools=SimpleNamespace(names=lambda: tuple(tools)))


def test_an_inline_turn_is_offered_read_tools_only(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(monkeypatch)
    assert session_turns.read_only_tools(spec) == {"files.list", "workbook.compute"}
    assert session_turns.write_actions(spec) == {
        "files.save_approved": "file.save",
        "files.propose_save": "proposal.create",
    }


def test_acs4_a_write_proposing_plan_names_the_owner_as_approver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(monkeypatch)
    hannah = uuid.uuid4()
    steps = session_turns.plan_steps(
        {
            "steps": [
                {"label": "Read the returns", "tool": "files.list"},
                {
                    "label": "Propose saving the workbook",
                    "tool": "files.propose_save",
                    "arguments": {"changes": ["workbook"]},
                },
                {
                    "label": "Save the workbook to Files",
                    "tool": "files.save_approved",
                    "write": True,
                    "arguments": {"artifact_id": "a1"},
                },
            ]
        },
        spec,
        hannah,
    )
    assert [s["key"] for s in steps] == ["s1", "s2", "s3"]
    assert steps[0]["arguments"] == {"folder": "Firm reports"}  # the input model's defaults
    assert steps[1]["arguments"] == {"changes": ["workbook"]}
    assert steps[1]["writes"] == [] and steps[1]["approver_user_id"] is None  # SHL-10 decides
    assert steps[2]["depends_on"] == ["s2"] and steps[2]["writes"] == ["file.save"]
    assert steps[2]["approver_user_id"] == str(hannah) and steps[0]["approver_user_id"] is None
    problems = validate_plan(
        [PlanStep.parse(s) for s in steps],
        PlanContext(
            declared_writes=frozenset({"file.save"}),
            client_scope=frozenset(),
            approver_holds={(str(hannah), "file.save"): True},
            tool_actions={
                "files.list": "file.read",
                "files.propose_save": "proposal.create",
                "files.save_approved": "file.save",
            },
        ),
    )
    assert problems == []


def test_the_idempotency_key_is_stored_as_a_fingerprint_and_refs_are_read_by_kind() -> None:
    assert len(key_hash("k-1")) == 64 and key_hash("k-1") != "k-1"
    refs = [{"kind": "engagement", "id": "e1"}, {"kind": "capability", "id": "tax.assistant"}]
    assert ref_of(refs, "capability") == "tax.assistant" and ref_of(refs, "client") is None


@pytest.mark.parametrize(
    ("step", "code"),
    [
        ({"label": "Save", "tool": "files.save_approved", "arguments": {}}, "invalid_arguments"),
        (
            {"label": "Save", "tool": "files.save_approved", "arguments": {"x": 1}},
            "invalid_arguments",
        ),
        ({"label": "Elsewhere", "tool": "mail.send", "arguments": {}}, "tool_not_in_spec"),
    ],
)
def test_a_plan_whose_arguments_do_not_validate_writes_no_child_run(
    monkeypatch: pytest.MonkeyPatch, step: dict[str, object], code: str
) -> None:
    spec = _spec(monkeypatch)
    with pytest.raises(session_turns.PlanInvalid) as refused:
        session_turns.plan_steps({"steps": [step]}, spec, uuid.uuid4())
    assert refused.value.code == code
