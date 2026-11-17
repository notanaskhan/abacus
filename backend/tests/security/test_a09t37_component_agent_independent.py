# ac-test-author: ayushkbhatia
"""A-09-T37 (TASK-8523; ADR-078 independent AC tests for N's identity, component, host and agent
work; SPEC-658 F1, F4, F6; A-09 §6).

Written from SPEC-658 and A-09 §6, not from the services. Each test plants the violation (a
foreign component, a non-human or support caller, an unverified cell, a model's own number) and
expects the code to refuse it, so a build without the component scope rule, the live-human check
or the citation verifier fails here:

- component scope: the room guard and the room read refuse any component the grant does not name
  (404), and a non-human or firm caller (404);
- the message rule refuses another component's figures, never small counts;
- live human: the proposer's run and the AUD-31 mapper's run refuse agents and support sessions;
- citations verified: an unverified E3 cell blocks its proposal before anything is written, and
  an E3 without a cell is never kept;
- never adopt, approve or post: both capabilities hold propose tools only, the agent is denied
  every approve, apply, edit, adopt and confirm action, and the proposer's action is held by no
  person and by the agent only at task_scope;
- data boundary: the mapper's model input has no amount field; the proposer never shows E3's
  amount; both stay `client_data: none`;
- attribution: an agent proposal is the agent's, on behalf of its initiator, naming its run;
- the send's Undo and the late sweep are guarded in their SQL (10 seconds, the sender, once).
"""

from __future__ import annotations

import inspect
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.agents.specs._specs_v2 import SPECS_V2
from abacus.modules.assurance import (
    agent_tools,
    component_auditors,
    component_late,
    component_room,
    component_scope,
    tb_mapper,
)
from abacus.modules.assurance import elimination_proposer as ep
from abacus.modules.identity.api import Forbidden
from abacus.modules.identity.authz.matrix import RULES

pytestmark = pytest.mark.asyncio
OWN = uuid.uuid4()
OTHER = uuid.uuid4()


def _person(kind: str = "human", *, client: bool = True, support: bool = False) -> Any:  # noqa: ANN401  # a stand-in context
    return SimpleNamespace(
        tenant=SimpleNamespace(actor_kind=kind),
        client=client,
        is_support=support,
        user_id=uuid.uuid4(),
    )


async def test_the_room_guard_refuses_a_component_the_grant_does_not_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def granted(_ctx: object) -> frozenset[uuid.UUID]:
        return frozenset({OWN})

    monkeypatch.setattr(component_scope, "component_ids", granted)
    assert await component_scope.require_room(_person(), OWN) == OWN
    with pytest.raises(NotFound):
        await component_scope.require_room(_person(), OTHER)


@pytest.mark.parametrize(("kind", "client"), [("agent", True), ("system", True), ("human", False)])
async def test_the_room_read_refuses_non_humans_and_firm_callers(
    monkeypatch: pytest.MonkeyPatch, kind: str, client: bool
) -> None:
    async def grants(_tenant: object, _user: object) -> list[object]:
        return [
            SimpleNamespace(
                role=component_room.ROLE, scope_kind=component_room.SCOPE, scope_id=OWN
            )
        ]

    monkeypatch.setattr(component_room, "active_grants", grants)
    with pytest.raises(NotFound):
        await component_room.room(_person(kind, client=client), OWN)


async def test_the_room_read_refuses_another_components_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def grants(_tenant: object, _user: object) -> list[object]:
        return [
            SimpleNamespace(
                role=component_room.ROLE, scope_kind=component_room.SCOPE, scope_id=OWN
            )
        ]

    monkeypatch.setattr(component_room, "active_grants", grants)
    with pytest.raises(NotFound):
        await component_room.room(_person(), OTHER)


def test_a_message_naming_another_components_figure_is_refused() -> None:
    others = [12_000_000_00]  # another component's 12,000,000.00
    assert component_scope.foreign_figures("Your PM is 12,000,000.", [], others) == [12_000_000_00]
    assert component_scope.foreign_figures("Send 3 files by day 14.", [], others) == []
    assert component_scope.foreign_figures("Your PM is 9,600.", [9_600_00], others) == []


@pytest.mark.parametrize(
    ("kind", "support"), [("agent", False), ("system", False), ("human", True)]
)
async def test_the_proposer_run_is_a_live_persons_only(kind: str, support: bool) -> None:
    with pytest.raises(Forbidden):
        await ep.run_proposals(
            _person(kind, client=False, support=support),
            engagement_id=uuid.uuid4(),
            work_item_id=uuid.uuid4(),
            consolidation_id=uuid.uuid4(),
            entities=[],
            inventory_version_id=None,
        )


@pytest.mark.parametrize(("kind", "support"), [("agent", False), ("human", True)])
async def test_the_mapper_run_is_a_live_persons_only(kind: str, support: bool) -> None:
    with pytest.raises(Forbidden):
        await tb_mapper.run_suggestions(_person(kind, client=False, support=support), uuid.uuid4())


def _line(caption: str, debit: str, credit: str) -> agent_tools.EliminationLineIn:
    return agent_tools.EliminationLineIn(
        caption=caption,
        client_entity_id=uuid.uuid4(),
        debit=Decimal(debit),
        credit=Decimal(credit),
    )


async def test_an_unverified_cell_blocks_its_proposal_before_anything_is_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[object] = []

    async def unverified(*_a: object, **_k: object) -> list[object]:
        return [SimpleNamespace(id=uuid.uuid4(), verified=False)]

    async def propose(*_a: object, **_k: object) -> object:
        written.append(_k)
        return SimpleNamespace(id=uuid.uuid4())

    import abacus.modules.adjustments.api as adjustments_api
    import abacus.modules.evidence.api as evidence_api

    monkeypatch.setattr(evidence_api, "record_citations", unverified)
    monkeypatch.setattr(adjustments_api.eliminations, "propose_by_agent", propose)

    class _Tx:
        async def __aenter__(self) -> object:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    import abacus.kernel.uow as kernel_uow

    def fake_uow(_tenant: object) -> _Tx:
        return _Tx()

    monkeypatch.setattr(kernel_uow, "uow", fake_uow)
    agent = SimpleNamespace(tenant=None, engagement_id=uuid.uuid4())
    args = agent_tools.EliminationProposalsIn(
        work_item_id=uuid.uuid4(),
        consolidation_id=uuid.uuid4(),
        proposals=[
            agent_tools.EliminationProposalIn(
                key="unrealized_profit:mfg:dist",
                level=2,
                description="Unrealized profit in ending inventory",
                computation="1,000,000 x 24.0% = 240,000",
                lines=[
                    _line("Cost of goods sold", "240000", "0"),
                    _line("Inventory", "0", "240000"),
                ],
                cell=agent_tools.EliminationCellIn(
                    evidence_version_id=uuid.uuid4(),
                    sheet="By vendor",
                    cell="C14",
                    value=Decimal("1000000"),
                ),
            )
        ],
    )  # fmt: skip
    out = await agent_tools.propose_eliminations(agent, args)  # type: ignore[arg-type]  # a stand-in agent
    assert out.entry_ids == [] and out.blocked == 1
    assert written == []


def test_an_unrealized_profit_without_a_cell_is_never_kept() -> None:
    entity = ep.EntityTb(
        "s", uuid.uuid4(), "Seller", 3, "p",
        {"Intercompany receivable": Decimal("10"), "Net sales - intercompany": Decimal("-100"),
         "Cost of goods sold": Decimal("60")},
    )  # fmt: skip
    buyer = ep.EntityTb(
        "b", uuid.uuid4(), "Buyer", 3, "p",
        {"Intercompany payable": Decimal("-10"), "Inventory": Decimal("50"),
         "Cost of goods sold": Decimal("70")},
    )  # fmt: skip
    given = ep.candidates([entity, buyer])
    e3 = next(c for c in given if c.kind == "unrealized_profit")
    answer = ep.ProposerOutput(
        entries=[ep.ProposerEntry(key=e3.key, description="Profit", note="")]
    )
    assert ep.settle(answer, [e3], {e3.key: Decimal("50")}).kept == ()


@pytest.mark.parametrize("capability", [tb_mapper.CAPABILITY, ep.CAPABILITY])
def test_both_capabilities_only_propose_and_stay_off_client_data(capability: str) -> None:
    spec = SPECS_V2[capability]
    assert set(cast(dict[str, object], spec["tools"])) == {"propose"}
    assert spec["autonomy"] == "propose" and spec["client_data"] == "none"


@pytest.mark.parametrize(
    "action",
    ["elimination.approve", "elimination.apply", "elimination.edit", "mapping_set.confirm",
     "proposed_entry.approve", "posting_batch.post"],
)  # fmt: skip
def test_the_agent_is_denied_every_decision(action: str) -> None:
    assert action in RULES, f"{action} is declared"
    assert RULES[action].decisions.get("agent", "deny") == "deny"


def test_the_proposers_action_is_held_by_no_person() -> None:
    rule = RULES["elimination.agent_propose"]
    assert rule.decisions.get("agent") == "task_scope"
    assert {r for r, d in rule.decisions.items() if d != "deny" and r != "agent"} == set()


def test_the_model_inputs_carry_no_amounts() -> None:
    assert "amount" not in tb_mapper.TbAccount.model_fields
    assert "balance" not in tb_mapper.TbAccount.model_fields
    entity = ep.EntityTb("s", uuid.uuid4(), "Seller", 3, "p", {"Inventory": Decimal("1")})
    shown = ep.model_input(
        [ep.Candidate("unrealized_profit:s:b", "unrealized_profit", 2, ("s", "b"),
                      (ep.Line("Cost of goods sold", "b"), ep.Line("Inventory", "b")), (), "",
                      Decimal("0.24"))],
        {entity.key: entity.name},
    )  # fmt: skip
    assert all(line.amount is None for line in shown.candidates[0].lines)


def test_an_agent_proposal_is_the_agents_on_behalf_of_its_initiator() -> None:
    from abacus.modules.adjustments import eliminations

    source = inspect.getsource(eliminations.propose_by_agent)
    assert "'agent'" in source and "on_behalf_of_user_id" in source and "run_id" in source


def test_the_send_undo_and_the_late_sweep_are_guarded() -> None:
    undo = " ".join(str(v) for k, v in vars(component_auditors).items() if k.isupper())
    assert (
        "interval '10 seconds'" in undo
        and "sent_by = :by" in undo
        and "completed_at IS NULL" in undo
    )
    assert "went_late_at IS NULL" in str(component_late._STAMP)  # pyright: ignore[reportPrivateUsage]  # the sweep's guard
