"""T-04-T31 (TASK-6819; DEC-3413; T-04 AC-4.3 to AC-4.5): the tax fix runner and Explain.

Row acceptance: "Setting 'Add 1,550 to line 2a and IT-201 line 20' yields one proposal with two
cited rows and status In progress, approval through SHL-10 resolves the issue as a person, and
Explain returns only verified citations."
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import ToolCallIn
from abacus.modules.identity.api import AgentContext
from abacus.modules.review import issue_resolutions, issue_runs, slots
from abacus.modules.tax import explain as ex
from abacus.modules.tax import fix_runner as fr

INSTRUCTION = "Add 1,550 to line 2a and IT-201 line 20"
ISSUE, ENTITY, RUN = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
SCH_E, IT201 = uuid.uuid4(), uuid.uuid4()
K1 = uuid.uuid4()


def _judgment(*changes: tuple[str, str, str]) -> fr.FixJudgment:
    return fr.FixJudgment.model_validate(
        {"changes": [{"line": ln, "op": op, "amount": a} for ln, op, a in changes]}
    )


# --- code's rules --------------------------------------------------------------------------------


def test_the_persons_numbers_are_read_and_line_names_are_not_amounts() -> None:
    assert fr.numbers_in(INSTRUCTION) == {Decimal(1550), Decimal(201), Decimal(20)}
    assert Decimal(2) not in fr.numbers_in("line 2a")


def test_the_suggested_instruction_is_codes_wording() -> None:
    lines = list(fr.FIX_LINES.values())
    assert fr.suggested_instruction(Decimal(1550), lines) == INSTRUCTION


def test_both_lines_are_planned_from_the_persons_figure() -> None:
    rows = fr.plan_rows(
        _judgment(("f1040.l2a", "add", "1,550"), ("it201.line20", "add", "1,550")), INSTRUCTION
    )
    assert [(r.line.key, r.amount) for r in rows] == [
        ("f1040.l2a", Decimal(1550)),
        ("it201.line20", Decimal(1550)),
    ]
    assert fr.new_value(rows[1], Decimal(0)) == Decimal(1550)
    assert fr.new_value(rows[0], None) == Decimal(1550)


def test_a_figure_the_person_did_not_write_is_dropped() -> None:
    rows = fr.plan_rows(_judgment(("f1040.l2a", "add", "1,555")), INSTRUCTION)
    assert rows == ()  # DE-3: the model never supplies a number


def test_a_line_code_does_not_offer_never_validates() -> None:
    with pytest.raises(ValueError):
        _judgment(("f1040.l1a", "add", "1,550"))


def test_a_line_named_twice_is_proposed_once() -> None:
    rows = fr.plan_rows(
        _judgment(("f1040.l2a", "add", "1,550"), ("f1040.l2a", "set", "1,550")), INSTRUCTION
    )
    assert len(rows) == 1
    assert fr.plan_rows(None, INSTRUCTION) == ()


def test_the_instructions_reach_the_model_as_untrusted_data() -> None:
    source = inspect.getsource(fr._judge)  # pyright: ignore[reportPrivateUsage] -- the rule under test
    assert 'untrusted=("fix_instructions",)' in source


# --- the run, on doubles ------------------------------------------------------------------------


@dataclass
class _World:
    calls: list[str] = field(default_factory=list[str])
    proposed: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])  # Any: JSON
    linked: list[uuid.UUID] = field(default_factory=list[uuid.UUID])
    verified: bool = True
    consent: bool = True


def _agent() -> AgentContext:
    return SimpleNamespace(  # type: ignore[return-value]  # an AgentContext double
        tenant=TenantContext(uuid.uuid4(), "agent", str(RUN)),
        agent_run_id=RUN,
        engagement_id=uuid.uuid4(),
    )


def _install(monkeypatch: pytest.MonkeyPatch, world: _World, judgment: fr.FixJudgment) -> None:
    sheets = {
        "sch_e_p2": (SCH_E, "tax_exempt_interest", None),
        "it201": (IT201, "line20", "0"),
    }

    async def call_tool(_agent: object, call: ToolCallIn) -> object:
        world.calls.append(call.name)
        if call.name == "tax.read_return":
            if not world.consent:
                return SimpleNamespace(ok=False, code="consent_required", result=None)
            return SimpleNamespace(ok=True, code=None, result={"id": str(uuid.uuid4())})
        if call.name == "tax.list_documents":
            return SimpleNamespace(ok=True, code=None, result={"documents": [{"id": str(K1)}]})
        if call.name == "tax.read_worksheet":
            ws, key, value = sheets[str(call.arguments["worksheet_key"])]
            row = {"id": str(uuid.uuid4()), "field_key": key, "value": value}
            return SimpleNamespace(
                ok=True, code=None, result={"worksheet_id": str(ws), "fields": [row]}
            )
        if call.name == "tax.propose_field_changes":
            changes = cast(list[dict[str, Any]], call.arguments["changes"])  # Any: JSON
            world.proposed.extend(changes)
            return SimpleNamespace(ok=True, code=None, result={"proposal_id": str(uuid.uuid4())})
        raise AssertionError(call.name)

    async def instructions(_a: object, _i: uuid.UUID) -> str:
        return INSTRUCTION

    async def link(_a: object, _i: uuid.UUID, proposal: uuid.UUID) -> None:
        world.linked.append(proposal)

    async def judge(*_a: object) -> fr.FixJudgment:
        return judgment

    async def fields(_t: object, _v: uuid.UUID) -> tuple[object, ...]:
        return (
            SimpleNamespace(
                field_key=fr.CITING_BOXES[0],
                value_text="1,550",
                page_no=1,
                bbox=(0.1, 0.2, 0.3, 0.4),
            ),
        )

    async def cite(*_a: object, **_k: object) -> list[object]:
        return [SimpleNamespace(id=uuid.uuid4(), verified=world.verified)]

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        yield SimpleNamespace()

    monkeypatch.setattr("abacus.modules.agents.api.call_tool", call_tool)
    monkeypatch.setattr("abacus.modules.review.api.fix_instructions_of", instructions)
    monkeypatch.setattr("abacus.modules.review.api.record_fix_proposal", link)
    monkeypatch.setattr("abacus.modules.evidence.api.extracted_fields_of", fields)
    monkeypatch.setattr("abacus.modules.evidence.api.record_citations", cite)
    monkeypatch.setattr("abacus.kernel.uow.uow", unit)
    monkeypatch.setattr(fr, "_judge", judge)


BOTH = _judgment(("f1040.l2a", "add", "1,550"), ("it201.line20", "add", "1,550"))


@pytest.mark.asyncio
async def test_ac_one_proposal_with_two_cited_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World()
    _install(monkeypatch, world, BOTH)
    result = await fr.fix(_agent(), ISSUE, ENTITY, 2025)
    assert result.outcome == "proposed" and result.rows == 2
    assert [(c["field_key"], c["after"]) for c in world.proposed] == [
        ("tax_exempt_interest", "1550"),
        ("line20", "1550"),
    ]
    assert all(len(c["citation_ids"]) == 1 for c in world.proposed)
    assert world.calls.count("tax.propose_field_changes") == 1
    assert len(world.linked) == 1  # the proposal is named to the issue


@pytest.mark.asyncio
async def test_an_unverified_box_proposes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(verified=False)
    _install(monkeypatch, world, BOTH)
    result = await fr.fix(_agent(), ISSUE, ENTITY, 2025)
    assert (result.outcome, result.code) == ("nothing_to_propose", "uncited")
    assert "tax.propose_field_changes" not in world.calls


@pytest.mark.asyncio
async def test_a_missing_consent_waits_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(consent=False)
    _install(monkeypatch, world, BOTH)

    async def never(*_a: object) -> object:
        raise AssertionError("no model call without consent")

    monkeypatch.setattr(fr, "_judge", never)
    result = await fr.fix(_agent(), ISSUE, ENTITY, 2025)
    assert (result.outcome, result.needs) == ("waiting_on_inputs", ("consent_7216",))


def test_the_runner_never_resolves_or_writes_a_value() -> None:
    source = inspect.getsource(fr)
    for forbidden in ("resolve_on_approval", "record_value", "write_field", "UPDATE "):
        assert forbidden not in source


# --- Explain ------------------------------------------------------------------------------------


def _fact() -> ex.Fact:
    return ex.Fact(uuid.uuid4(), "K-1 box 18A", "1,550")


def test_explain_keeps_only_verified_citations() -> None:
    fact = _fact()
    answer = ex.ExplainOutput(
        text="K-1 box 18A reports 1,550 of tax-exempt interest. It belongs on IT-201 line 20.",
        citation_ids=[fact.citation_id, uuid.uuid4()],
    )
    body, cited = ex.settle(answer, [fact], 2025)
    assert cited == (fact.citation_id,)
    assert "1,550" in body and "IT-201 line 20" in body


def test_explain_drops_a_sentence_with_a_number_code_did_not_give() -> None:
    fact = _fact()
    answer = ex.ExplainOutput(
        text="K-1 box 18A reports 1,550. The tax effect is about 96.",
        citation_ids=[fact.citation_id],
    )
    body, _ = ex.settle(answer, [fact], 2025)
    assert "96" not in body and "1,550" in body


def test_explain_falls_back_to_codes_sentence() -> None:
    fact = _fact()
    body, cited = ex.settle(None, [fact], 2025)
    assert body == "K-1 box 18A reports 1,550."
    assert cited == (fact.citation_id,)
    uncited = ex.ExplainOutput(text="Box 18A reports 1,550.", citation_ids=[uuid.uuid4()])
    assert ex.settle(uncited, [fact], 2025)[1] == (fact.citation_id,)


# --- review: In progress, the run row, resolution as the approver -------------------------------


def test_set_fix_instructions_moves_the_issue_in_progress_and_records_the_run() -> None:
    source = inspect.getsource(issue_resolutions.set_fix_instructions)
    assert '"in_progress"' in source and '"status_changed"' in source
    assert 'record_issue_run(ctx, issue_id, run, "fix")' in source
    assert "fix_runner_registered(current.record_type)" in source


def test_the_runners_are_keyed_by_record_type() -> None:
    import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- the registration

    assert slots.fix_runner_registered("tax_return")
    assert slots.explainer_registered("tax_return")


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["rejected", "returned"])
async def test_only_an_approval_resolves(decision: str) -> None:
    assert (
        await issue_runs.resolve_on_approval(uuid.uuid4(), uuid.uuid4(), decision, uuid.uuid4())
        is None
    )


@pytest.mark.asyncio
async def test_the_resolution_is_the_approvers_and_needs_issue_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id, by = uuid.uuid4(), uuid.uuid4()
    seen: list[TenantContext] = []

    @asynccontextmanager
    async def session(_t: TenantContext) -> AsyncGenerator[object]:
        async def execute(*_a: object, **_k: object) -> object:
            return SimpleNamespace(first=lambda: SimpleNamespace(issue_id=ISSUE, agent_run_id=RUN))

        yield SimpleNamespace(execute=execute)

    async def member(_t: uuid.UUID, user: uuid.UUID) -> object:
        return SimpleNamespace(tenant=TenantContext(tenant_id, "human", str(user)))

    async def one(_t: TenantContext, _i: uuid.UUID) -> object:
        return SimpleNamespace(
            status="in_progress", record_type="tax_return", record_id=uuid.uuid4(), version=3,
            engagement_id=uuid.uuid4(),
        )  # fmt: skip

    async def record(*_a: object) -> tuple[object, object, str]:
        return None, object(), "x"

    async def refuse(*_a: object) -> None:
        from abacus.modules.identity.api import Forbidden

        raise Forbidden("issue.resolve", "role")

    @asynccontextmanager
    async def unit(t: TenantContext) -> AsyncGenerator[object]:
        seen.append(t)
        yield SimpleNamespace()

    monkeypatch.setattr(issue_runs, "tenant_session", session)
    monkeypatch.setattr("abacus.modules.identity.api.member_context", member)
    monkeypatch.setattr(issue_runs, "issue_row", one)
    monkeypatch.setattr(issue_runs, "record_of", record)
    monkeypatch.setattr(issue_runs, "authorise", refuse)
    monkeypatch.setattr(issue_runs, "uow", unit)
    assert await issue_runs.resolve_on_approval(tenant_id, uuid.uuid4(), "approved", by) is None
    assert seen == []  # approving the values is not the right to resolve
    source = inspect.getsource(issue_runs._resolve_as)  # pyright: ignore[reportPrivateUsage] -- the step under test
    assert "async with uow(person.tenant)" in source  # as the person, never the system


def test_the_agent_cannot_resolve_an_issue() -> None:
    source = inspect.getsource(issue_runs)
    assert "issue_events_resolution_by_a_person" in source
    assert "_RUN_OF" in source and "IssueRunMismatch" in source  # a run writes for its issue only
