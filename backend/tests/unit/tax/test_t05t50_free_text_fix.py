"""T-05-T50 rest (TASK-7932; DEC-4927): free-text workbook fix instructions.

When the closed grammar names nothing, the model (`issues.fix_runner.workbook@v1`, a mode of
`issues.fix_runner`) says which cells the words name; code keeps a cell only on one of the form's
sheets with an amount the person wrote verbatim, and computes every value itself (ADR-050). A
refused call proposes nothing. The mode's suite is frozen before the prompt (ADR-079).
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from abacus.modules.tax import workbook_fix as wf
from abacus.modules.tax.workbook_fix import WorkbookFixChange, WorkbookFixJudgment, kept

D = Decimal
FORM = "1065"


def _answer(*changes: tuple[str, str, str, str]) -> WorkbookFixJudgment:
    return WorkbookFixJudgment(
        changes=[WorkbookFixChange(sheet=s, cell=c, op=o, amount=a) for s, c, o, a in changes]  # type: ignore[arg-type] -- the op literal from a test tuple
    )


def test_ac_code_keeps_a_named_cell_with_the_persons_own_amount() -> None:
    words = "Please put the 6,200 of tax-exempt interest into the M-2, cell B6 on sheet 07."
    [cell] = kept(_answer(("07", "b6", "add", "6,200")), words, FORM)
    assert (cell.op, cell.amount, cell.at.key) == ("add", D("6200"), "07!B6")


def test_ac_an_amount_the_person_did_not_write_is_dropped() -> None:
    words = "Add the Harborline interest to 07 B6."
    assert kept(_answer(("07", "B6", "add", "6,200")), words, FORM) == ()


def test_ac_sheet_keys_cell_refs_and_form_designators_are_not_amounts() -> None:
    words = "Fix the M-2 on 07 M-2!B6 please"
    for amount in ("07", "6", "2"):
        assert kept(_answer(("07", "B6", "set", amount)), words, FORM) == ()


def test_ac_a_sheet_off_the_form_or_a_bad_cell_is_dropped() -> None:
    words = "Add 6,200 to B6."
    assert kept(_answer(("12", "B6", "add", "6,200")), words, FORM) == ()
    assert kept(_answer(("07", "=A1", "add", "6,200")), words, FORM) == ()


def _wire(
    monkeypatch: pytest.MonkeyPatch, judgment: WorkbookFixJudgment | None
) -> dict[str, Any]:  # Any: what the fakes saw
    from abacus.modules.agents import api as agents_api
    from abacus.modules.identity.api import AgentContext
    from abacus.modules.review import api as review_api

    seen: dict[str, Any] = {"judged": 0}  # Any: what the fakes saw

    async def instructions_of(*_a: object) -> str:
        return seen["words"]

    async def judge(*_a: object) -> WorkbookFixJudgment | None:
        seen["judged"] += 1
        return judgment

    async def values(*_a: object) -> dict[str, dict[str, object]]:
        return {"07!B6": {"t": "decimal", "v": "6860000"}}

    async def create(_agent: object, **kw: Any) -> uuid.UUID:  # noqa: ANN401 -- Any: the proposal's fields
        seen["rows"] = kw["rows"]
        return uuid.uuid4()

    async def record(*_a: object) -> None:
        return None

    monkeypatch.setattr(review_api, "fix_instructions_of", instructions_of)
    monkeypatch.setattr(review_api, "current_values", values)
    monkeypatch.setattr(review_api, "record_fix_proposal", record)
    monkeypatch.setattr(agents_api, "create_proposal", create)
    monkeypatch.setattr(wf, "judge", judge)
    seen["agent"] = AgentContext.__new__(AgentContext)
    object.__setattr__(seen["agent"], "engagement_id", uuid.uuid4())
    object.__setattr__(seen["agent"], "tenant", object())
    return seen


def test_ac_free_text_proposes_the_value_code_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _wire(monkeypatch, _answer(("07", "B6", "add", "6,200")))
    seen["words"] = "Please put the 6,200 into the M-2, cell B6 on sheet 07."
    out = asyncio.run(wf.fix(seen["agent"], uuid.uuid4(), uuid.uuid4(), FORM))
    assert (out.outcome, out.rows, seen["judged"]) == ("proposed", 1, 1)
    assert seen["rows"][0].after == {"t": "decimal", "v": "6866200"}  # 6,860,000 + 6,200, by code


def test_ac_the_grammar_first_and_no_model_when_it_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _wire(monkeypatch, None)
    seen["words"] = "Add 6,200 to 07 M-2!B6"
    out = asyncio.run(wf.fix(seen["agent"], uuid.uuid4(), uuid.uuid4(), FORM))
    assert (out.outcome, seen["judged"]) == ("proposed", 0)


def test_ac_a_refused_call_or_nothing_kept_proposes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _wire(monkeypatch, None)
    seen["words"] = "Something is off in the M-2"
    out = asyncio.run(wf.fix(seen["agent"], uuid.uuid4(), uuid.uuid4(), FORM))
    assert (out.outcome, out.code) == ("nothing_to_propose", "no_cell_named")
    seen = _wire(monkeypatch, _answer(("07", "B6", "add", "6,200")))
    seen["words"] = "Something is off in the M-2"
    out = asyncio.run(wf.fix(seen["agent"], uuid.uuid4(), uuid.uuid4(), FORM))
    assert out.code == "no_cell_named"


def test_ac_the_mode_is_its_own_prompt_and_evaluation() -> None:
    from abacus.ai_gateway._eval_suites import EVAL_SUITE_MODES
    from abacus.ai_gateway.prompts import prompt

    assert EVAL_SUITE_MODES["issues.fix_runner"][wf.PROMPT] == 1
    body = prompt(wf.PROMPT).text
    assert "<untrusted>" in body and "never compute" in body


def test_ac_the_suite_is_frozen_passes_and_every_grader_has_a_seeded_case() -> None:
    from abacus_tools.evals import workbook_fix as suite

    raw = suite.load()
    assert raw["thresholds"] == dict(suite.FROZEN)
    report = suite.run_suite(raw)
    assert report["status"] == "passed", report["reasons"]
    assert report["graders_without_a_seeded_case"] == []


def test_ac_a_lowered_threshold_is_refused(tmp_path: Path) -> None:
    from abacus_tools.evals import workbook_fix as suite

    raw = suite.load()
    raw["thresholds"] = {**raw["thresholds"], "amount_provenance": 0.9}  # type: ignore[dict-item] -- a YAML mapping
    (tmp_path / "workbook_fix").mkdir()
    (tmp_path / "workbook_fix" / "suite.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(suite.ThresholdsChanged):
        suite.load(tmp_path)


def test_sec_the_call_names_the_returns_7216_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    """Security review (TASK-7933): the gateway checks §7216 consents only for the subjects a call
    names, so the free-text call names the return's partnership for its year."""
    import abacus.ai_gateway as gateway
    from abacus.ai_gateway import DataSubject
    from abacus.modules.identity.api import AgentContext
    from abacus.modules.tax import entity_tri

    entity, return_id = uuid.uuid4(), uuid.uuid4()
    seen: list[Any] = []  # Any: the gateway call the fake received

    async def subjects(_t: object, r: uuid.UUID) -> tuple[DataSubject, ...]:
        assert r == return_id
        return (DataSubject(entity, 2025),)

    async def call(c: Any) -> Any:  # noqa: ANN401 -- Any: a GatewayCall and its result double
        seen.append(c)
        raise RuntimeError("refused")  # a refused call proposes nothing

    monkeypatch.setattr(entity_tri, "entity_return_subjects", subjects)
    monkeypatch.setattr(gateway, "call", call)
    agent = AgentContext.__new__(AgentContext)
    for k, v in {
        "tenant": object(),
        "engagement_id": uuid.uuid4(),
        "agent_run_id": uuid.uuid4(),
    }.items():
        object.__setattr__(agent, k, v)
    assert asyncio.run(wf.judge(agent, "put 6,200 in the M-2", FORM, return_id)) is None
    assert seen[0].context.data_subjects == (DataSubject(entity, 2025),)
