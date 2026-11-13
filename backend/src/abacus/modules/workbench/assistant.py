"""`workbench.assistant` v1's turn (W-02-T12; W-02 §6; SPEC-653 §3.4 to §3.9; ADR-230; DEC-4718).
Red (agent; the spec and prompt are N's protected paths).

`AssistantTurn` is what one model turn of the Workbench assistant answers: AgentBlocks (p with
text, cite and fact segments; tables; kv; metrics; files; badges; cite lists; entity refs;
numbers by reference, P-24) and at most one of:

- `question`: one to four steps, each one question with options (key, title, detail) and a
  preselected key, never free text the agent invents as a choice (WB-01 a, b: one question at a
  time);
- `plan`: the steps it will run, what it will read (`source`, `count`) and every write it would
  make (`op`, `target`, `approver`): a plan is required whenever the turn would write
  (`plan: required_when_writes`); the session's owner approves it;
- `notice`: a code (`unavailable`, `out_of_scope`, `nothing_to_do`) and its wording.

`check_turn` is code's last word before a turn is shown: no reserved verb in any text (decide,
approve, sign off, release, send, post, export, transmit, adopt, publish, resolve, accept or
reject) and no write outside a plan; the line "Nothing was written." on a read-only turn is code's,
appended by the session (AC-A3), never the model's.
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.modules.agents.api import AgentBlocks

CAPABILITY: Final = "workbench.assistant"
NOTHING_WRITTEN: Final = "Nothing was written."
Int = classified("internal")
Conf = classified("confidential")
_RESERVED: Final = re.compile(
    r"\b(?:decid(?:e|ed)|approv(?:e|ed)|sign(?:ed)? off|releas(?:e|ed)|sen[dt]|post(?:ed)?|"
    r"export(?:ed)?|transmit(?:ted)?|adopt(?:ed)?|publish(?:ed)?|resolv(?:e|ed)|"
    r"accept(?:ed)?|reject(?:ed)?)\b",
    re.IGNORECASE,
)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class QuestionOption(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$"), Int]
    title: Annotated[str, Field(min_length=1, max_length=120), Conf]
    detail: Annotated[str | None, Field(max_length=240), Conf] = None


class QuestionStep(BaseModel):
    model_config = _cfg()

    q: Annotated[str, Field(min_length=1, max_length=240), Conf]
    options: Annotated[list[QuestionOption], Field(min_length=2, max_length=6), Conf]
    preselect: Annotated[str | None, Int] = None


class AssistantQuestion(BaseModel):
    model_config = _cfg()

    steps: Annotated[list[QuestionStep], Field(min_length=1, max_length=4), Conf]


class PlanRead(BaseModel):
    model_config = _cfg()

    source: Annotated[str, Field(min_length=1, max_length=80), Conf]
    count: Annotated[int, Field(ge=0), Int]


class PlanWrite(BaseModel):
    model_config = _cfg()

    op: Annotated[Literal["save_file"], Int]
    target: Annotated[str, Field(min_length=1, max_length=200), Conf]
    approver: Annotated[str, Field(min_length=1, max_length=120), Conf]


class PlanStepOut(BaseModel):
    model_config = _cfg()

    label: Annotated[str, Field(min_length=1, max_length=160), Conf]
    tool: Annotated[str | None, Field(max_length=80), Int] = None


class AssistantPlan(BaseModel):
    model_config = _cfg()

    steps: Annotated[list[PlanStepOut], Field(min_length=1, max_length=24), Conf]
    reads: Annotated[list[PlanRead], Field(max_length=20), Conf] = Field(
        default_factory=list[PlanRead]
    )
    writes: Annotated[list[PlanWrite], Field(max_length=5), Conf] = Field(
        default_factory=list[PlanWrite]
    )


class AssistantNotice(BaseModel):
    model_config = _cfg()

    code: Annotated[Literal["unavailable", "out_of_scope", "nothing_to_do"], Int]
    text: Annotated[str, Field(min_length=1, max_length=400), Conf]


class AssistantTurn(BaseModel):
    """One turn (module docstring): blocks and at most one of question, plan or notice."""

    model_config = _cfg()

    blocks: Annotated[AgentBlocks | None, Conf] = None
    question: Annotated[AssistantQuestion | None, Conf] = None
    plan: Annotated[AssistantPlan | None, Conf] = None
    notice: Annotated[AssistantNotice | None, Conf] = None

    @model_validator(mode="after")
    def _one(self) -> AssistantTurn:
        if sum(x is not None for x in (self.question, self.plan, self.notice)) > 1:
            raise ValueError("a turn carries at most one of question, plan or notice")
        if (
            self.blocks is None
            and self.question is None
            and self.plan is None
            and self.notice is None
        ):
            raise ValueError("a turn says something")
        return self


class AssistantInput(BaseModel):
    """What a turn is given: the person's message and the session's context labels (the tools
    read the records; the model never receives a record it has not read through a tool)."""

    model_config = _cfg()

    message: Annotated[str, Field(min_length=1, max_length=4000), Conf]
    context: Annotated[list[str], Field(max_length=12), Conf] = Field(default_factory=list[str])


def _texts(turn: AssistantTurn) -> list[str]:
    out: list[str] = []
    if turn.blocks is not None:
        out.append(turn.blocks.model_dump_json())
    if turn.question is not None:
        out += [s.q for s in turn.question.steps]
    if turn.plan is not None:
        out += [s.label for s in turn.plan.steps]
    if turn.notice is not None:
        out.append(turn.notice.text)
    return out


def check_turn(turn: AssistantTurn) -> str | None:
    """None when code accepts the turn; else why it is refused (INV-1)."""
    if any(_RESERVED.search(t) for t in _texts(turn)):
        return "reserved_action_named"
    if (
        turn.plan is not None
        and turn.plan.writes
        and any(
            w.approver.strip().casefold() in ("agent", "accrued agent") for w in turn.plan.writes
        )
    ):
        return "agent_cannot_approve"
    return None


__all__ = [
    "CAPABILITY",
    "NOTHING_WRITTEN",
    "AssistantInput",
    "AssistantNotice",
    "AssistantPlan",
    "AssistantQuestion",
    "AssistantTurn",
    "check_turn",
]
