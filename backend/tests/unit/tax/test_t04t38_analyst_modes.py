"""T-04-T38 (TASK-7413; T-04 §6; DEC-4410): `tax.return_analyst` modes `k1_treatments` and
`residency` on a fake model and fake C17 calls.

Row acceptance: "On the fake model the Ridgeline proposal carries 7 treatments with code-computed
figures only, the 150-day variant returns Action required with option 2 recommended, and neither
mode can confirm, approve or send."
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import BaseModel

from abacus.modules.agents.api import spec_v2
from abacus.modules.tax import analyst_modes as am
from abacus.modules.tax import residency_service as rs

Loose = Any  # Any: a stand-in agent context


pytestmark = pytest.mark.asyncio
ENTITY = uuid.uuid4()
RETURN = uuid.uuid4()
RIDGELINE = [
    ("passive", "Passive", "Passive", False, "proposed"),
    ("ptp", "Not a PTP", "Not a PTP", False, "proposed"),
    ("qbi", "Eligible — QBI 307,900; deduction 61,580", "Eligible — 56,320", False, "proposed"),
    ("niit", "Included — 307,900 + 4,600", "Included", False, "proposed"),
    ("basis", "Sufficient — outside basis 4,674,575", "Sufficient", False, "proposed"),
    (
        "state",
        "IL 141,634 · CO 96,989 · NY 69,277",
        "IL 46.0 · CO 31.5 · NY 22.5",
        False,
        "proposed",
    ),
    ("ptet_credits", "IL 7,011 · CO 4,268 · NY 4,746", "IL 6,412 only", True, "proposed"),
    ("tax_exempt", "Form 1040 line 2a 1,550 · NY addition 1,550", "2a 1,400", False, "approved"),
]


@dataclass
class Outcome:
    ok: bool
    result: object = None
    code: str | None = None


@dataclass
class FakeTools:
    """C17 as the mode sees it; it records every call."""

    responses: dict[str, Outcome]
    calls: list[tuple[str, dict[str, object]]] = field(
        default_factory=list[tuple[str, dict[str, object]]]
    )

    async def __call__(self, name: str, arguments: dict[str, object]) -> Outcome:
        self.calls.append((name, arguments))
        return self.responses[name]


class _Agent:
    tenant = object()
    engagement_id = uuid.uuid4()
    agent_run_id = uuid.uuid4()


def _install(monkeypatch: pytest.MonkeyPatch, tools: FakeTools, answer: BaseModel | None) -> None:
    def make(_agent: object) -> FakeTools:
        return tools

    monkeypatch.setattr(am, "_Tools", make)

    async def judge(*_: object) -> BaseModel | None:
        return answer

    monkeypatch.setattr(am, "_judge", judge)


def _treatments() -> dict[str, object]:
    return {
        "treatments": [
            {
                "id": str(uuid.uuid4()),
                "kind": kind,
                "status": status,
                "resolved_text": resolved,
                "prior_text": prior,
                "changed": changed,
            }
            for kind, resolved, prior, changed, status in RIDGELINE
        ]
    }


async def test_ridgeline_proposes_seven_treatments_with_codes_figures_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = FakeTools(
        {
            "tax.read_prior_year": Outcome(True, _treatments()),
            "tax.propose_pass_through_treatments": Outcome(
                True, {"proposal_id": str(uuid.uuid4())}
            ),
        }
    )
    invented = am.K1TreatmentsOutput(
        treatments=[
            am.TreatmentRationale(
                kind="ptet_credits",
                rationale=(
                    "Ridgeline elected PTET in Colorado and New York for 2025. "
                    "That saves the client about 9,999 in tax."
                ),
            ),
            am.TreatmentRationale(
                kind="qbi", rationale="QBI is 307,900 and the deduction 61,580."
            ),
        ]
    )
    _install(monkeypatch, tools, invented)
    result = await am.k1_treatments_mode(cast(Loose, _Agent()), ENTITY, 2025)
    assert result.outcome == "proposed" and result.proposed == 7
    (name, arguments) = tools.calls[-1]
    assert name == "tax.propose_pass_through_treatments"
    changes = cast(list[dict[str, str]], arguments["changes"])
    assert len(changes) == 7
    assert {c["treatment"] for c in changes} == {r[1] for r in RIDGELINE if r[4] == "proposed"}
    assert result.rationale is not None
    ptet, _ = result.rationale["ptet_credits"]
    assert "9,999" not in ptet and "elected PTET" in ptet  # a number not code's is dropped
    assert result.rationale["qbi"][0] == "QBI is 307,900 and the deduction 61,580."
    assert tools.calls[0][0] == "tax.read_prior_year"  # §7216 gates the first call


async def test_without_consent_the_mode_waits_and_proposes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = FakeTools({"tax.read_prior_year": Outcome(False, code="consent_required")})
    _install(monkeypatch, tools, None)
    result = await am.k1_treatments_mode(cast(Loose, _Agent()), ENTITY, 2025)
    assert (result.outcome, result.code) == ("waiting_on_inputs", "consent_required")
    assert [n for n, _ in tools.calls] == ["tax.read_prior_year"]


@dataclass(frozen=True)
class _Det:
    id: uuid.UUID


def _view(days: int, home: str) -> rs.ResidencyView:
    cite = uuid.uuid4()
    facts = rs.facts_from_sources(
        [
            rs.Source("organizer", cite, {"nyc_days": days, "main_home": home}),
            rs.Source("coop_statement", uuid.uuid4(), {"place": "New York City"}),
        ]
    )
    return rs.ResidencyView(
        determination_id=uuid.uuid4(),
        status="review_point",
        conflict=False,
        facts=tuple(rs.FactView(f.key, f.value, f.citation_ids, f.source_kind) for f in facts),
        options=(),
        confirmed_by_name=None,
        confirmed_at=None,
        issue_id=None,
        version=1,
    )


async def test_the_150_day_variant_is_action_required_with_option_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    determination = uuid.uuid4()

    async def found(*_: object) -> _Det:
        return _Det(determination)

    async def view(*_: object) -> rs.ResidencyView:
        return _view(150, "Rhinebeck")

    monkeypatch.setattr(rs, "determination", found)
    monkeypatch.setattr(rs, "residency_view", view)
    tools = FakeTools(
        {
            "tax.read_return": Outcome(True, {}),
            "tax.compute_residency_facts": Outcome(
                True, {"recommended": "full_year_nys_part_year_nyc", "conflict": True}
            ),
            "tax.propose_residency": Outcome(True, {"proposal_id": str(uuid.uuid4())}),
        }
    )
    _install(
        monkeypatch,
        tools,
        am.ResidencyOutput(rationale="150 NYC days; the main home is Rhinebeck."),
    )
    result = await am.residency_mode(cast(Loose, _Agent()), ENTITY, 2025, RETURN)
    assert result.outcome == "action_required"
    assert result.recommended == "full_year_nys_part_year_nyc"  # option 2
    assert result.client_question is not None
    assert result.client_question[1].splitlines()[1] == (
        "- Full-year New York State, part-year New York City"
    )
    computed = dict(tools.calls)["tax.compute_residency_facts"]
    assert computed["nyc_days"] == 150 and computed["main_home_outside_nyc"] is True
    assert dict(tools.calls)["tax.propose_residency"]["option"] == "full_year_nys_part_year_nyc"


async def test_281_days_proposes_full_year_without_a_client_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def found(*_: object) -> _Det:
        return _Det(uuid.uuid4())

    async def view(*_: object) -> rs.ResidencyView:
        return _view(281, "New York City")

    monkeypatch.setattr(rs, "determination", found)
    monkeypatch.setattr(rs, "residency_view", view)
    tools = FakeTools(
        {
            "tax.read_return": Outcome(True, {}),
            "tax.compute_residency_facts": Outcome(
                True, {"recommended": "full_year_nys_nyc", "conflict": False}
            ),
            "tax.propose_residency": Outcome(True, {"proposal_id": str(uuid.uuid4())}),
        }
    )
    _install(monkeypatch, tools, None)
    result = await am.residency_mode(cast(Loose, _Agent()), ENTITY, 2025, RETURN)
    assert (result.outcome, result.recommended, result.client_question) == (
        "proposed",
        "full_year_nys_nyc",
        None,
    )


async def test_neither_mode_can_confirm_approve_or_send() -> None:
    spec = spec_v2(am.ANALYST)
    assert not set(spec.task_scope) & am.NEVER
    tools = spec.tools
    names = {*tools.read, *tools.compute, *tools.propose, *tools.approved_write}
    assert not tools.approved_write
    assert all("confirm" not in n and "send" not in n and "approve" not in n for n in names)
    assert {"tax.propose_pass_through_treatments", "tax.propose_residency"} <= set(tools.propose)


async def test_code_keeps_only_sentences_with_its_own_numbers() -> None:
    allowed = frozenset({Decimal(150), Decimal(2025)})
    text = "There are 150 NYC days in 2025. The client owes 12,345. Rhinebeck is the main home."
    assert am.keep_sentences(text, allowed) == (
        "There are 150 NYC days in 2025. Rhinebeck is the main home."
    )
