"""T-08-T26 (TASK-8921; T-08 AC5.1, AC7.3; SPEC-710 AC-23, AC-27, AC-32, AC-33; DEC-5923; red):
`tax.return_analyst` modes `two_year` and `planning_screen`.

Row acceptance: "Every output is a suggestion with verified citations, an unconsented taxpayer is
refused with consent_7216, and the fast eval subset passes in CI." Here: code settles each mode's
answer (every figure a fact, quotes on offered pages, every subject answered once, no talking
points in a two-year answer, no client draft or action field at all); the rendered text carries
code's values; an unconsented taxpayer is refused 409 `consent_7216_missing` before any model
call; the modes' only writes are suggestions on two registered targets; the C17 reads are
declared on the spec with TRI; and the tax suite's fast subset still passes on the fake model.
"""

from __future__ import annotations

import asyncio
import inspect
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from abacus.modules.tax import practice_modes as pm
from abacus.modules.tax.compute.two_year import ComparisonLine

D = Decimal
PROMPTS = Path(pm.__file__).resolve().parents[2] / "ai_gateway" / "prompts"


def _given(mode: str = "two_year") -> pm.ModeInput:
    line = ComparisonLine("scha.11", "Sch A 11 Gifts by cash or check", D("12500"), D("11000"),
                          D("1500"), D("13.6"), True)  # fmt: skip
    subjects, facts = pm.two_year_facts([line])
    return pm.ModeInput(
        mode=mode,  # type: ignore[arg-type] -- the two modes
        subjects=subjects, facts=facts,
        sources=[pm.SourceIn(source="sa", title="2025 Charitable Contributions Summary",
                             pages=[1, 2])],
        untrusted=["sa page 1: Receipt from the community foundation"],
    )  # fmt: skip


def _blocks(*segments: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "parts": [{"kind": "p", "segments": list(segments)}]}


def _answer(**over: object) -> pm.ModeOutput:
    body: dict[str, object] = {
        "key": "scha.11",
        "blocks": _blocks(
            {"kind": "text", "text": "Gifts rose from "}, {"kind": "fact", "fact_id": "laa_py"},
            {"kind": "text", "text": " to "}, {"kind": "fact", "fact_id": "laa_cy"},
            {"kind": "text", "text": ": the summary lists a new pledge to the foundation."},
        ),
        "quotes": [{"source": "sa", "page": 1, "quote": "Receipt from the community foundation"}],
    }  # fmt: skip
    body.update(over)
    return pm.ModeOutput.model_validate({"subjects": [body]})


def test_two_year_settles_and_renders_code_values() -> None:
    settled = pm.settle(_given(), _answer())
    assert [s.key for s in settled] == ["scha.11"]
    text = pm.render(settled[0].blocks, _given().facts)
    assert text == (
        "Gifts rose from 11,000 to 12,500: the summary lists a new pledge to the foundation."
    )


def test_a_free_number_is_refused() -> None:
    bad = _answer(blocks=_blocks({"kind": "text", "text": "Gifts rose by 1,500 this year."}))
    with pytest.raises(pm.OutputRefused):
        pm.settle(_given(), bad)


def test_quotes_must_sit_on_offered_pages_and_every_subject_is_answered() -> None:
    off = _answer(quotes=[{"source": "sa", "page": 9, "quote": "Receipt from the foundation"}])
    with pytest.raises(pm.OutputRefused) as caught:
        pm.settle(_given(), off)
    assert caught.value.facts == {"reason": "page_not_offered"}
    other = _answer(key="1040.11")
    with pytest.raises(pm.OutputRefused) as caught:
        pm.settle(_given(), other)
    assert caught.value.facts == {"reason": "subjects_not_answered"}


def test_two_year_takes_no_talking_points_and_the_output_has_no_client_draft() -> None:
    with pytest.raises(pm.OutputRefused) as caught:
        pm.settle(_given(), _answer(talking_points=_blocks({"kind": "text", "text": "Call."})))
    assert caught.value.facts == {"reason": "talking_points_not_offered"}
    fields = set(pm.SubjectOut.model_fields) | set(pm.ModeOutput.model_fields)
    assert not fields & {"client_draft", "actions", "send", "raise_with_client"}
    with pytest.raises(ValueError):
        pm.ModeOutput.model_validate({"subjects": [], "client_draft": "Dear Claire"})


def test_planning_accepts_talking_points() -> None:
    settled = pm.settle(
        _given("planning_screen"),
        _answer(talking_points=_blocks({"kind": "text", "text": "Ask about the pledge timing."})),
    )
    assert settled[0].talking_points is not None


def test_fact_ids_carry_no_digits_of_the_line() -> None:
    _subjects, facts = pm.two_year_facts([
        ComparisonLine("1040.11", "11 AGI", D("598030"), D("551940"), D("46090"), D("8.4"), True),
    ])  # fmt: skip
    assert all(not any(ch.isdigit() for ch in f.id) for f in facts)
    assert [f.id for f in facts] == ["laa_cy", "laa_py", "laa_delta", "laa_pct"]


def test_an_unconsented_taxpayer_is_refused_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.tax import two_year_service
    from abacus.modules.tax.practice_tools_errors import Consent7216Missing

    called: list[str] = []

    async def comparison(_ctx: object, _r: object) -> object:
        return type("C", (), {"lines": (), "engagement_id": uuid4()})()

    async def subject(_t: object, _r: object) -> tuple[object, int]:
        return uuid4(), 2025

    async def consented(*_a: object) -> bool:
        return False

    async def answer(*_a: object) -> object:
        called.append("model")
        raise AssertionError("no model call without consent")

    monkeypatch.setattr(two_year_service, "comparison", comparison)
    monkeypatch.setattr(pm, "return_subject", subject)
    monkeypatch.setattr(pm, "_consented", consented)
    monkeypatch.setattr(pm, "_answer", answer)
    ctx = type("Ctx", (), {"tenant": object()})()
    with pytest.raises(Consent7216Missing) as caught:
        asyncio.run(pm.two_year_explain(ctx, uuid4()))  # type: ignore[arg-type] -- a stand-in
    assert caught.value.code == "consent_7216_missing" and called == []


def test_the_only_writes_are_suggestions_on_registered_targets() -> None:
    import abacus.api as composition_root

    assert composition_root
    from abacus.modules.agents.proposal_slots import (
        _APPLIERS,  # pyright: ignore[reportPrivateUsage]
    )

    assert {pm.EXPLANATION_TARGET, pm.RATIONALE_TARGET} <= set(_APPLIERS)
    source = inspect.getsource(pm)
    assert "create_proposal" not in source and "message.send" not in source.replace(
        "`message.send`", ""
    )
    assert source.count("create_suggestion(") == 3  # one per line; rationale and talking points


def test_the_spec_declares_the_reads_with_tri_and_the_prompts_exist() -> None:
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(pm.CAPABILITY)
    names = spec.tools.names()
    assert {"tax.read_engine_summary", "tax.read_planning_candidate"} <= set(names)
    assert "tri" in spec.data_classes
    assert {"planning.read", "suggestion.create"} <= set(spec.task_scope)
    for prompt in ("two_year", "planning_screen"):
        assert (PROMPTS / f"tax.return_analyst.{prompt}" / "v1.txt").exists()


def test_the_tax_fast_subset_still_passes(tmp_path: Path) -> None:
    from abacus_tools.evals import tax_return

    assert tax_return.main(tmp_path, "fast") == 0
