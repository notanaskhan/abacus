"""SPEC-033 AC-3, AC-7, AC-8 (TASK-065): the matcher's spec, its context (candidates as R1..Rn,
the document the only untrusted field), its output's bounds, the skip rule, and its suite."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from abacus.modules.agents.api import MATCHER, spec
from abacus.modules.agents.handoff import MatchOutput
from abacus.modules.agents.inbox_match import build_context, refs
from abacus.modules.evidence.api import Candidate, MatchMaterial
from abacus.modules.evidence.matching import Reason, Suggestion, should_match
from abacus_tools.evals.matching import (
    DOCUMENTS,
    INJECTION,
    REQUESTS,
    MatchCase,
    Seen,
    _documents,  # pyright: ignore[reportPrivateUsage] -- the suite's own fixtures
    load_suite,
    validate,
    verdict,
)

LEASE, LOAN = uuid.uuid4(), uuid.uuid4()
PAGES = {1: "COMMERCIAL LEASE AGREEMENT\nTenant: Example Company Inc"}


def _material() -> MatchMaterial:
    return MatchMaterial(
        uuid.uuid4(),
        uuid.uuid4(),
        "scan0044.pdf",
        "extracted",
        (
            Candidate(LEASE, "Lease agreements", "Leases", None, (), 0, ()),
            Candidate(LOAN, "Debt agreements", "Debt", None, (), 0, ()),
        ),
        True,
        ((1, PAGES[1]),),
        (),
        False,
        PAGES,
        {},
    )


def test_ac3_the_matcher_is_declared_to_propose_only() -> None:
    matcher = spec(MATCHER)
    assert matcher.autonomy == "propose"
    assert matcher.prompt == "evidence.inbox_match@v1"
    assert matcher.task_scope == frozenset({"evidence.read", "inbox_match.run"})
    assert matcher.limits.max_cost_usd == Decimal("0.01")
    assert list(matcher.untrusted_inputs) == ["document"]
    assert matcher.essential is False


def test_ac3_candidates_are_references_and_the_document_alone_is_untrusted() -> None:
    material = _material()
    assert refs(material) == {"R1": LEASE, "R2": LOAN}
    rendered = build_context(material, "2026-12-31", "Example Company Inc", ["document"]).render()
    assert rendered.count('<untrusted name="document">') == 1
    before = rendered.split('<untrusted name="document">', 1)[0]
    assert '"ref": "R1"' in before and "Lease agreements" in before
    assert "COMMERCIAL LEASE AGREEMENT" not in before
    assert str(LEASE) not in rendered  # D1: the model never sees request ids


def test_ac3_the_output_is_bounded_and_answers_one_way() -> None:
    quote = {"page": 1, "quote": "COMMERCIAL LEASE AGREEMENT"}
    proposal = {"request": "R1", "confidence": 0.9, "rationale": "A lease.", "citations": [quote]}
    assert MatchOutput.model_validate({"none_fit": False, "proposals": [proposal]})
    assert MatchOutput.model_validate({"none_fit": True, "rationale": "A flyer.", "proposals": []})
    bad_answers: tuple[dict[str, object], ...] = (
        {"none_fit": True, "proposals": [proposal]},
        {"none_fit": False, "proposals": []},
        {"none_fit": False, "proposals": [{**proposal, "request": "R61"}]},
        {"none_fit": False, "proposals": [{**proposal, "request": str(LEASE)}]},
        {"none_fit": False, "proposals": [{**proposal, "citations": []}]},
        {"none_fit": False, "proposals": [proposal] * 4},
    )
    for bad in bad_answers:
        with pytest.raises(ValidationError):
            MatchOutput.model_validate(bad)


def _scored(*items: tuple[int, tuple[str, ...]]) -> list[Suggestion]:
    return [
        Suggestion(uuid.uuid4(), score, (), "content", tuple(Reason(c) for c in codes))
        for score, codes in items
    ]


def test_ac3_the_matcher_is_skipped_only_when_code_is_decisive() -> None:
    assert not should_match(_scored((100, ("kind", "date", "account")), (50, ("kind",))))
    assert should_match(_scored((100, ("kind", "date")), (70, ("kind", "date"))))  # a tie-ish
    assert should_match(_scored((60, ("file_name",)), (10, ())))  # names only
    assert should_match(_scored((70, ("kind",)), (0, ())))  # kind alone isn't enough
    assert should_match([])


def test_ac7_the_suite_validates_and_every_case_has_its_document() -> None:
    suite = load_suite()
    validate(suite)
    assert {c.document for c in suite.cases} <= DOCUMENTS
    assert {c.expected for c in suite.cases} - {"none"} <= set(REQUESTS)
    assert sum(c.hard for c in suite.cases) >= 10
    made = _documents(date(2026, 12, 31), "Example Company Inc")
    assert all(made[c.document]() for c in suite.cases)


def test_ac8_the_injection_case_carries_its_instruction() -> None:
    lease = _documents(date(2026, 12, 31), "Example Company Inc")["lease_injection"]()
    assert INJECTION.split(":")[0].encode() in lease


def _case(expected: str, *, hard: bool = False) -> MatchCase:
    return MatchCase(id="c", document="lease", name="x.pdf", expected=expected, hard=hard)


def test_ac7_metrics_grade_the_pipeline_against_the_baseline() -> None:
    attempts = [
        (
            _case("leases", hard=True),
            Seen("c", 1, "matched", (), ("debt",), ("leases",), ("leases", "debt")),
        ),
        (_case("debt", hard=True), Seen("c", 1, "skipped", ("debt",), ("debt",), (), ("debt",))),
        (_case("none"), Seen("c", 1, "matched", ("minutes",), (), (), (), True)),
    ]
    status, _, metrics = verdict(load_suite(), attempts)
    assert metrics["top1"] == 1.0
    assert metrics["none_fit_precision"] == 1.0
    assert metrics["top1_hard_file_name"] == 0.5
    assert metrics["hard_case_gain"] == 0.5
    assert metrics["skip_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert status in ("passed", "failed")  # adversarial containment needs adversarial cases
