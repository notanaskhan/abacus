"""T-07-T14 (TASK-8040; SPEC-656 AC-1.4, AC-2.1 to AC-2.4; INV-1, INV-2): the reader's tools.

Acceptance (the task row): "No tool can adopt, approve, lock or reopen, a proposal with an
unverified clause citation is rejected, and a figure that is not a code fact fails number
provenance." The database path of a proposal runs in the end pass's integration suite.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest

import abacus.modules.tax.api  # registers the tools
from abacus.modules.agents.tools import registry
from abacus.modules.tax import instrument_tools as tools

assert abacus.modules.tax.api

NAMES = ("tax.read_instrument_clauses", "tax.read_trust_facts", "tax.propose_trust_determinations")


def _tool(name: str) -> registry.AgentTool:
    return registry.tool(name)


def test_no_tool_can_adopt_approve_lock_or_reopen() -> None:
    kinds = {name: _tool(name).kind for name in NAMES}
    assert kinds == {NAMES[0]: "read", NAMES[1]: "read", NAMES[2]: "propose"}
    for name in NAMES:
        tool = _tool(name)
        assert tool.data_class == "tri"
        assert not any(
            v in f"{tool.name} {tool.action}" for v in ("adopt", "approve", "lock", "reopen")
        )
        assert tool.description == f"tool.{name}@v1"
    assert _tool(NAMES[0]).untrusted == ("clauses",)


def test_figures_skip_clause_labels_statutes_and_years() -> None:
    text = (
        "Complex trust under Art. III(a) and §663(b) since 2011; trustee fees 30,000 to principal"
    )
    assert tools._figures(text) == [Decimal("30000")]


def _args(value_text: str, fact_ids: list[str], clauses: bool = True) -> tools.DeterminationsIn:
    return tools.DeterminationsIn(
        client_entity_id=uuid.uuid4(),
        tax_year=2025,
        determinations=[
            tools.ProposedDetermination(
                key="trustee_fees", value_code="principal", value_text=value_text,
                clauses=[tools.ClauseCite(clause_id=uuid.uuid4(), quote="charged to principal")]
                if clauses else [],
                fact_ids=fact_ids,
            )
        ],
    )  # fmt: skip


@pytest.fixture
def facts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def return_of(agent: object, args: object) -> tuple[uuid.UUID, uuid.UUID]:
        return uuid.uuid4(), uuid.uuid4()

    async def known(agent: object, args: object) -> dict[str, Decimal]:
        return {"expense:fees": Decimal("30000.00")}

    monkeypatch.setattr(tools, "_return_of", return_of)
    monkeypatch.setattr(tools, "_facts", known)


async def test_a_figure_that_is_not_a_named_fact_fails_number_provenance(facts: None) -> None:
    agent = cast(Any, object())
    with pytest.raises(tools.NumberProvenance):
        await tools.propose_trust_determinations(
            agent, _args("Fees of 31,000 to principal", ["expense:fees"])
        )
    with pytest.raises(tools.NumberProvenance):
        await tools.propose_trust_determinations(agent, _args("Fees of 30,000 to principal", []))
    with pytest.raises(tools.NumberProvenance):
        await tools.propose_trust_determinations(agent, _args("Fees", ["expense:invented"]))


async def test_a_governed_key_without_a_clause_is_rejected(facts: None) -> None:
    with pytest.raises(tools.UnverifiedCitation):
        await tools.propose_trust_determinations(
            cast(Any, object()),
            _args("Fees of 30,000 to principal", ["expense:fees"], clauses=False),
        )
