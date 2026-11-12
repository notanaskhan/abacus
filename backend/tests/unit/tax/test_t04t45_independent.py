"""T-04-T45 (ADR-078; TASK-7515): independent acceptance tests for the agent work of T-04-T25 (the
drafter), T-04-T31 (the fix runner and Explain), T-04-T37 (the assistant) and T-04-T38 (the
analyst's K-1 and residency modes), written from SPEC-649, T-04 §6 and the rows' acceptance, not
from the implementation.

Row acceptance: "Tests prove the agent principal never approves, resolves, confirms, signs, sends
or requests approval, and that a revoked consent stops the next tool call." Each test names the
guard it holds; removing that guard makes it fail.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.api import create_app  # every module's tools and specs register at import
from abacus.modules.agents import api as agents_api
from abacus.modules.agents.specs._specs_v2 import SPECS_V2
from abacus.modules.agents.tools import runtime
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.identity.api import RULES
from abacus.modules.review.api import UncitedChange
from abacus.modules.tax import analyst_modes, drafter, drafter_run, explain, fix_runner
from abacus.modules.tax.review_tree import assistant_word

assert callable(create_app)
D = Decimal
CAPABILITIES = ("tax.return_drafter", "issues.fix_runner", "tax.return_analyst", "tax.assistant")
# I-AGENT-NEVER's verbs, and the request that starts a human's final approval.
HUMAN_VERBS = (
    "approve",
    "unapprove",
    "resolve",
    "confirm",
    "sign",
    "sign_off",
    "send",
    "release",
    "decide",
    "accept",
    "reject",
    "waive",
    "post",
    "file",
    "request_approval",
)


def _human_only(action: str) -> bool:
    verb = action.split(".", 1)[1]
    return any(
        verb == v or verb.startswith(f"{v}_") or verb.endswith(f"_{v}") for v in HUMAN_VERBS
    )


# --- INV-1: the agent principal never approves, resolves, confirms, signs, sends or requests -----


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_inv1_no_tax_capability_holds_a_human_only_action(capability: str) -> None:
    """Guard: each spec's `task_scope` lists `proposal.create` and reads only."""
    scope = cast(list[str], SPECS_V2[capability]["task_scope"])
    assert "proposal.create" in scope
    assert [a for a in scope if _human_only(a)] == []


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_inv1_every_tool_is_a_read_a_compute_or_a_propose(capability: str) -> None:
    """Guard: the specs offer no write or approved-write tool; a change is always a proposal."""
    tools = cast(dict[str, list[str]], SPECS_V2[capability]["tools"])
    assert set(tools) <= {"read", "compute", "propose"}
    kinds = {n: t.kind for n, t in registered_tools().items()}
    for kind, names in tools.items():
        for name in names:
            assert kinds[name] == kind, name


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_inv1_autonomy_is_propose_and_plans_are_required_for_writes(capability: str) -> None:
    spec = SPECS_V2[capability]
    assert spec["autonomy"] == "propose"
    assert spec["plan"] == "required_when_writes"


def test_inv1_the_matrix_never_lets_the_agent_take_a_human_only_tax_or_review_action() -> None:
    """Guard: `agent: deny` (or the agent's absence) on every human-only action of the tax, review
    and issue families: even a task scope listing one could not hold it."""
    families = ("tax_return.", "return_worksheet.", "k1_treatment.", "residency.", "issue.")
    families += ("proposal.", "checkpoint.", "sign_off.", "review_note.")
    checked = 0
    for action, rule in RULES.items():
        if not action.startswith(families) or not _human_only(action):
            continue
        checked += 1
        assert rule.decisions.get("agent") not in ("allow", "task_scope"), action
    assert checked >= 8


def test_inv1_the_fix_runner_never_resolves_its_issue() -> None:
    """Guard: the runner's scope has no `issue.resolve` and no tool that resolves; the person's
    approval of its proposal resolves the issue as them (`review.issue_runs`)."""
    spec = SPECS_V2["issues.fix_runner"]
    scope = cast(list[str], spec["task_scope"])
    assert "issue.resolve" not in scope
    tools = [n for names in cast(dict[str, list[str]], spec["tools"]).values() for n in names]
    assert not any("resolve" in name for name in tools)


# --- 422 uncited_change and numbers by reference -------------------------------------------------


def test_uncited_change_is_a_422_with_its_code() -> None:
    """Guard: approving a proposal with an uncited agent row refuses with this code (INV-2)."""
    assert UncitedChange.code == "uncited_change"
    from abacus.kernel.errors import DomainInvalid

    assert issubclass(UncitedChange, DomainInvalid)


def test_numbers_by_reference_the_fix_runner_keeps_only_the_persons_figures() -> None:
    """Guard: `plan_rows` drops an amount that is not one of the person's own numbers, a line code
    does not offer, and a second change to the same line."""
    judgment = fix_runner.FixJudgment(
        changes=[
            fix_runner.FixChange(line="f1040.l2a", op="add", amount="1,550"),
            fix_runner.FixChange(line="it201.line20", op="add", amount="1,551"),  # not theirs
            fix_runner.FixChange(line="f1040.l2a", op="set", amount="1550"),  # same line again
        ]
    )
    rows = fix_runner.plan_rows(judgment, "Add 1,550 to line 2a and IT-201 line 20")
    assert [(r.line.key, r.op, r.amount) for r in rows] == [("f1040.l2a", "add", D(1550))]
    assert fix_runner.plan_rows(None, "anything") == ()


def test_numbers_by_reference_code_computes_the_new_value() -> None:
    row = fix_runner.PlannedRow(fix_runner.FIX_LINES["f1040.l2a"], "add", D(1550))
    assert fix_runner.new_value(row, D(4210)) == D(5760)
    assert fix_runner.new_value(row, None) == D(1550)
    setting = fix_runner.PlannedRow(fix_runner.FIX_LINES["it201.line20"], "set", D(1550))
    assert fix_runner.new_value(setting, D(9)) == D(1550)


def test_numbers_by_reference_the_analyst_drops_any_sentence_with_a_number_not_codes() -> None:
    """Guard: `keep_sentences` keeps a sentence only if every number in it is code's."""
    allowed = frozenset({D(307900), D(2025)})
    text = "Box 2 is 307,900 for 2025. The deduction is 61,999. It is passive."
    assert (
        analyst_modes.keep_sentences(text, allowed) == "Box 2 is 307,900 for 2025. It is passive."
    )


def test_numbers_by_reference_a_k1_rationale_never_changes_a_resolved_value() -> None:
    fact = analyst_modes.K1Fact(uuid.uuid4(), "passive", "proposed", "Passive", None, False)
    answer = analyst_modes.K1TreatmentsOutput.model_validate(
        {"treatments": [{"kind": "passive", "rationale": "It is 99,999.", "citation_ids": []}]}
    )
    out = analyst_modes.settle_k1(answer, [fact], frozenset())
    assert out["passive"][0] == "Passive: Passive."  # code's own sentence when nothing stands
    assert "99,999" not in out["passive"][0]


def test_numbers_by_reference_the_drafter_drops_a_number_in_a_note() -> None:
    """Guard: `judged_set` keeps code's default where the model's note carries a digit, and offers
    only code's worksheets (an unoffered key is dropped)."""
    judgment = drafter.ReturnDraftJudgment.model_validate(
        {
            "worksheets": [
                {"key": "it201", "tsj": "J", "new_this_year_note": "New: 2 W-2s this year"},
                {"key": "w2", "tsj": "S", "new_this_year_note": "A new employer"},
                {"key": "not_offered", "tsj": "T", "new_this_year_note": None},
            ]
        }
    )
    plans = {p.key: p for p in drafter.judged_set(["it201", "w2"], "J", judgment)}
    assert set(plans) == {"it201", "w2"}
    assert plans["it201"].new_this_year_note is None
    assert plans["it201"].tsj == "J"
    assert (plans["w2"].tsj, plans["w2"].new_this_year_note) == ("S", "A new employer")


# --- budget and step limits ----------------------------------------------------------------------


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_every_capability_is_bounded(capability: str) -> None:
    limits = cast(dict[str, Any], SPECS_V2[capability]["limits"])
    assert 0 < int(limits["max_steps"]) <= 40
    assert 0 < int(limits["max_tool_calls"]) <= 40
    assert 0 < int(limits["max_seconds"]) <= 600
    assert D(0) < D(str(limits["max_cost_usd"])) <= D(1)
    assert SPECS_V2[capability]["client_data"] == "none"  # cleared only by a Bedrock report


def test_the_assistant_stops_repeating_itself() -> None:
    limits = cast(dict[str, Any], SPECS_V2["tax.assistant"]["limits"])
    assert int(limits["max_repeat_identical_calls"]) <= 2


# --- a revoked consent stops the next tool call --------------------------------------------------


def _agent() -> Any:  # noqa: ANN401 -- a stand-in AgentContext
    return SimpleNamespace(
        agent_run_id=uuid.uuid4(),
        tenant=SimpleNamespace(tenant_id=uuid.uuid4()),
        tenant_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
    )


class _PassedTheGate(Exception):
    pass


def test_consent_is_checked_on_every_call_so_a_revocation_stops_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard: `call_tool` asks C19 on each TRI call; nothing caches a grant across calls."""
    consent = {"held": True}
    asked: list[int] = []

    async def require(_tenant: object, subjects: list[object], **_: object) -> None:
        asked.append(len(subjects))
        if not consent["held"]:
            raise runtime.TriConsentRequired("consent_7216")

    def past_gate(*_: object) -> str:
        raise _PassedTheGate

    async def in_scope(*_: object) -> None:
        return None

    targets = SimpleNamespace(
        tri_subjects=(SimpleNamespace(),), engagement_ids=[uuid.uuid4()], client_ids=[]
    )
    monkeypatch.setattr(runtime, "require_tri_consent", require)
    monkeypatch.setattr(runtime, "default_targets", lambda *_: targets)
    monkeypatch.setattr(runtime, "_scope_and_rights", in_scope)
    monkeypatch.setattr(runtime, "args_hash", past_gate)
    agent = _agent()
    call = agents_api.ToolCallIn(
        run_id=agent.agent_run_id,
        step_seq=1,
        attempt=1,
        name="tax.read_return",
        arguments={"client_entity_id": str(uuid.uuid4()), "tax_year": 2025},
    )
    with pytest.raises(_PassedTheGate):
        asyncio.run(runtime.call_tool(agent, call))
    consent["held"] = False  # revoked mid-run
    refused = asyncio.run(runtime.call_tool(agent, call.model_copy(update={"step_seq": 2})))
    assert (refused.ok, refused.code) == (False, "consent_required")
    assert asked == [1, 1]


def _refusing(code: str):  # noqa: ANN202 -- a fake C17
    async def call_tool(_agent: object, call: Any) -> Any:  # noqa: ANN401 -- C17 stand-in
        return runtime.ToolOutcome(name=call.name, ok=False, code=code)

    return call_tool


def _no_model(*_: object, **__: object) -> object:
    raise AssertionError("no model call before consent")


def test_the_drafter_waits_on_inputs_without_a_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drafter_run, "call_tool", _refusing("consent_required"))
    monkeypatch.setattr(drafter_run, "call", _no_model)
    result = asyncio.run(drafter_run.draft(_agent(), uuid.uuid4(), 2025))
    assert (result.outcome, result.needs) == ("waiting_on_inputs", ("consent_7216",))


@pytest.mark.parametrize(
    "run",
    [
        lambda a: fix_runner.fix(a, uuid.uuid4(), uuid.uuid4(), 2025),
        lambda a: explain.explain(a, uuid.uuid4(), uuid.uuid4(), 2025),
        lambda a: analyst_modes.k1_treatments_mode(a, uuid.uuid4(), 2025),
    ],
)
def test_the_other_runs_wait_on_inputs_when_consent_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    run: Any,  # noqa: ANN401 -- a run factory
) -> None:
    monkeypatch.setattr(agents_api, "call_tool", _refusing("consent_required"))
    result = asyncio.run(run(_agent()))
    assert result.outcome == "waiting_on_inputs"


# --- DF-04: the assistant's capability states ----------------------------------------------------


@pytest.mark.parametrize(
    ("ready", "reason", "word"),
    [
        (True, None, "available"),
        (False, "consent_7216", "consent_required"),
        (False, "paused", "agents_off"),
        (False, "ai_policy_off", "agents_off"),
        (False, "route_not_cleared", "ai_unavailable"),
        (False, None, "ai_unavailable"),
    ],
)
def test_df04_the_assistant_says_why_it_is_unavailable(
    ready: bool, reason: str | None, word: str
) -> None:
    assert assistant_word(ready, reason) == word
