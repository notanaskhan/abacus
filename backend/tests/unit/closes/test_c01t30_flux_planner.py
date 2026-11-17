"""C-01-T30 (red): `close.agent` modes flux and planner (SPEC-655 AC-21, AC-22, AC-49; DEC-5413).

The payroll explanation's drivers foot to 7,670 or the run escalates; planner rows come only from
code's closed sets and land as suggestions a person adopts.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from abacus.modules.closes import agent, agent_runs

D = Decimal


def _money(fid: str, value: str) -> agent.FactIn:
    return agent.FactIn(id=fid, kind="money", value=value, basis="code")


PAYROLL = [
    _money("change", "7670.00"),
    _money("current", "69030.00"),
    _money("prior", "61360.00"),
    _money("c1", "4350.00"),  # two new hires
    _money("c2", "1850.00"),  # the bonus run
    _money("c3", "1470.00"),  # overtime during the install
    _money("c4", "61360.00"),  # the base payroll
    _money("p1", "-61360.00"),  # last month's base payroll, sign reversed
]


def _flux(**kw: object) -> agent.CloseAgentInput:
    return agent.CloseAgentInput(mode="flux", close_id=uuid.uuid4(), facts=PAYROLL, **kw)  # type: ignore[arg-type] -- optional fields


def _drivers(*groups: list[str]) -> agent.CloseAgentOutput:
    return agent.FAKE_RESPONSES["flux"].model_copy(
        update={
            "drivers": [
                agent.DriverOut(label=f"Driver {chr(65 + n)}", fact_ids=g)
                for n, g in enumerate(groups)
            ]
        }
    )


def test_ac49_the_payroll_drivers_foot_to_7670() -> None:
    settled = agent.settle(_flux(), agent.FAKE_RESPONSES["flux"])
    assert [d.amount for d in settled.drivers] == [D("4350.00"), D("1850.00"), D("1470.00")]
    assert sum(d.amount for d in settled.drivers) == D("7670.00")


def test_ac49_drivers_may_net_a_prior_line_against_a_current_one() -> None:
    settled = agent.settle(_flux(), _drivers(["c1", "c2"], ["c4", "p1", "c3"]))
    assert sum(d.amount for d in settled.drivers) == D("7670.00")


def test_ac49_drivers_that_do_not_foot_are_refused() -> None:
    with pytest.raises(agent.OutputRefused) as refused:
        agent.settle(_flux(), _drivers(["c1"], ["c2"]))
    assert refused.value.facts["reason"] == "drivers_do_not_foot"


@pytest.mark.parametrize(
    "groups", [[["change"]], [["c1", "c1"], ["c2", "c3"]], [["c9"]], [["current"]]]
)
def test_a_driver_uses_only_offered_line_facts_once(groups: list[list[str]]) -> None:
    with pytest.raises(agent.OutputRefused) as refused:
        agent.settle(_flux(), _drivers(*groups))
    assert refused.value.facts["reason"] == "driver_fact_not_offered"


def test_a_driver_label_never_carries_a_figure() -> None:
    with pytest.raises(ValueError):
        agent.DriverOut(label="Bonus 1,850", fact_ids=["c2"])


def test_drivers_outside_flux_are_refused() -> None:
    bank = agent.CloseAgentInput(mode="bank_rec", close_id=uuid.uuid4(), facts=PAYROLL)
    with pytest.raises(agent.OutputRefused) as refused:
        agent.settle(bank, _drivers(["c1"]))
    assert refused.value.facts["reason"] == "drivers_outside_flux"


CHOICES = [
    agent.PlanChoiceIn(row_key="1000", procedures=["reconciliation"], sources=["bank_feed"]),
    agent.PlanChoiceIn(
        row_key="1350", procedures=["amortization", "rollforward"], sources=["accrued_register"]
    ),
    agent.PlanChoiceIn(row_key="1500", procedures=["depreciation"], sources=["files"]),
]
PLAN_FACTS = [
    agent.FactIn(id="months", kind="count", value="14", basis="code"),
    agent.FactIn(id="accounts", kind="count", value="3", basis="code"),
]


def _planner(rows: list[agent.PlanRowOut]) -> tuple[agent.CloseAgentInput, agent.CloseAgentOutput]:
    given = agent.CloseAgentInput(
        mode="planner", close_id=uuid.uuid4(), facts=PLAN_FACTS, choices=CHOICES
    )
    return given, agent.FAKE_RESPONSES["planner"].model_copy(update={"rows": rows})


def test_ac21_planner_rows_come_from_the_closed_sets_and_may_leave_a_row_out() -> None:
    given, answer = _planner(
        [agent.PlanRowOut(row_key="1000", procedure="reconciliation", source="bank_feed")]
    )
    assert len(agent.settle(given, answer).rows) == 1


@pytest.mark.parametrize(
    "row",
    [
        agent.PlanRowOut(row_key="1000", procedure="aging", source="bank_feed"),
        agent.PlanRowOut(row_key="1000", procedure="reconciliation", source="files"),
        agent.PlanRowOut(row_key="9999", procedure="reconciliation", source="bank_feed"),
    ],
)
def test_ac21_a_row_outside_its_sets_is_refused(row: agent.PlanRowOut) -> None:
    given, answer = _planner([row])
    with pytest.raises(agent.OutputRefused) as refused:
        agent.settle(given, answer)
    assert refused.value.facts["reason"] == "option_not_offered"


def test_ac21_an_account_planned_twice_is_refused() -> None:
    row = agent.PlanRowOut(row_key="1000", procedure="reconciliation", source="bank_feed")
    given, answer = _planner([row, row])
    with pytest.raises(agent.OutputRefused):
        agent.settle(given, answer)


@pytest.mark.parametrize(
    ("account_type", "classification", "procedure"),
    [
        ("Bank", "asset", "reconciliation"),
        ("Fixed Asset", "asset", "depreciation"),
        ("Accounts Payable", "liability", "aging_cutoff"),
        ("Something Else", "liability", "accrual"),
    ],
)
def test_code_offers_each_account_type_its_closed_sets(
    account_type: str, classification: str, procedure: str
) -> None:
    procedures, sources = agent_runs.choices_for(account_type, classification)
    assert procedure in procedures and sources
    assert all(p in agent_runs.METHOD for p in procedures)


def test_register_lines_are_calibrated_to_the_activity_sign() -> None:
    snap = uuid.uuid4()
    lines = [(snap, 1, D("-3000.00"), "Customer A"), (snap, 2, D("-1000.00"), "Customer B")]
    facts = agent_runs.line_facts("c", lines, D("4000.00"), reverse=False)
    assert [f.value for f in facts] == [D("3000.00"), D("1000.00")]
    assert [f.raw for f in facts] == [D("-3000.00"), D("-1000.00")]  # the citation claims these
    prior = agent_runs.line_facts("p", lines, D("4000.00"), reverse=True)
    assert [f.value for f in prior] == [D("-3000.00"), D("-1000.00")]


def test_the_draft_text_reads_the_facts() -> None:
    blocks = agent.FAKE_RESPONSES["flux"].blocks
    text = agent_runs.plain_text(blocks, {f.id: f for f in PAYROLL})
    assert text.startswith("Payroll rose 7,670.00 on two new hires")


def test_the_capability_reads_the_trial_balance_for_its_citations() -> None:
    from abacus.modules.agents.api import spec_v2

    assert "trial_balance.read" in spec_v2(agent.CAPABILITY).task_scope
    assert frozenset(spec_v2(agent.CAPABILITY).task_scope) == agent.TASK_SCOPE
