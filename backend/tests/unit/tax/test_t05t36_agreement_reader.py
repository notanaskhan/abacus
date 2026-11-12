"""T-05-T36 (TASK-7626; DEC-4621): `tax.agreement_reader`'s code-side settle on the frozen suite.

Every case's recorded fake-model answer passes through `settle`, and the settled proposal is
graded by the suite's own graders (`abacus_tools.evals.tax_entity.reader_grades`): pass and
adversarial cases pass every grader; on every case, seeded ones included, code guarantees the
citation, number, reserved-action and convention-question graders. On the seed it proposes a
straight percentage with a monthly interim closing citing LPA §4.1 and Assignment §3.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from abacus.modules.agents.api import spec_v2
from abacus.modules.tax import agreement_reader as ar
from abacus_tools.evals import tax_entity as te

RAW = te.load("tax_agreement_reader")
CASES = [te.ReaderCase.model_validate(c) for c in RAW["cases"]]  # type: ignore[union-attr] -- a JSON value read from a row
CODE_GUARANTEED = {
    "citation_verified",
    "citation_coverage",
    "number_provenance",
    "reserved_actions_absent",
    "convention_question_recall",
}


def _answer(case: te.ReaderCase) -> ar.ReadAgreementOutput | None:
    p = case.output.proposal
    raw: dict[str, Any] = {  # Any: a JSON payload
        "kind": p.kind,
        "method": p.method,
        "convention": p.convention,
        "rungs": list(p.rungs),
        "transfers": list(p.transfers),
        "citations": {k: v.model_dump() for k, v in case.output.citations.items()},
    }
    try:
        return ar.ReadAgreementOutput.model_validate(raw)
    except ValidationError:
        return None  # outside the output schema: the gateway refuses it, nothing is proposed


def _settled(case: te.ReaderCase) -> te.ReaderOutput:
    given = ar.ReadAgreementInput(
        clauses=[ar.AgreementClause(id=c.id, text=c.text) for c in case.clauses]
    )
    read = ar.settle(_answer(case), given)
    kept = read.kept
    fields: dict[str, Any] = {k.parameter: k.value for k in kept}  # Any: mixed parameter values
    numbers = [n for k in read.kept for n in ar._numbers(k.value)]  # pyright: ignore[reportPrivateUsage] -- the test or the shared trajectory base reaches a private helper
    return te.ReaderOutput(
        proposal=te.Proposal(
            kind=fields.get("kind"),
            method=fields.get("method"),
            convention=fields.get("convention"),
            rungs=tuple(fields.get("rungs") or ()),
            transfers=tuple(fields.get("transfers") or ()),
        ),
        citations={k.parameter: te.Citation(clause=k.clause, quote=k.quote) for k in read.kept},
        numbers=tuple(numbers),
        question=read.question,
    )


def _grades(case: te.ReaderCase) -> dict[str, bool]:
    settled = case.model_copy(update={"output": _settled(case)})
    return {g.grader: g.passed for g in te.reader_grades(settled)}


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.category in ("pass", "adversarial")], ids=lambda c: c.id
)
def test_ac_pass_and_adversarial_cases_pass_every_grader_after_settle(
    case: te.ReaderCase,
) -> None:
    failed = sorted(g for g, ok in _grades(case).items() if not ok)
    assert failed == [], (case.id, failed)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_ac_code_guarantees_citations_numbers_and_the_question(case: te.ReaderCase) -> None:
    grades = _grades(case)
    failed = sorted(g for g in CODE_GUARANTEED if g in grades and not grades[g])
    assert failed == [], (case.id, failed)


def test_ac_on_the_seed_ridgeline_reads_a_monthly_interim_closing() -> None:
    case = next(c for c in CASES if c.id == "reader_ridgeline_706d")
    out = _settled(case)
    assert out.proposal.kind == "straight_percentage"
    assert out.proposal.method == "interim_closing"
    assert out.proposal.convention == "monthly"
    assert {c.clause for c in out.citations.values()} == {"lpa-4.1", "asg-3"}
    assert out.question is None


def test_ac_silent_or_conflicting_clauses_raise_the_convention_question() -> None:
    silent = [ar.AgreementClause(id="lpa-4.1", text="Allocated by Percentage Interests.")]
    both = [
        ar.AgreementClause(id="lpa-4.1", text="Use the calendar day convention."),
        ar.AgreementClause(id="lpa-9.4", text="Use the monthly convention."),
    ]
    answer = ar.ReadAgreementOutput(
        convention="monthly",
        citations={"convention": ar.ClauseCitation(clause="lpa-9.4", quote="monthly convention")},
    )
    for clauses in (silent, both):
        read = ar.settle(answer, ar.ReadAgreementInput(clauses=clauses))
        assert read.question == "convention" and read.value("convention") is None


def test_ac_an_unverified_quote_or_an_unsupported_number_is_dropped() -> None:
    clauses = [
        ar.AgreementClause(id="asg-3", text="Effective June 30, 2025, A assigns 5 percent to B.")
    ]
    answer = ar.ReadAgreementOutput(
        kind="straight_percentage",
        transfers=[{"date": "2025-06-30", "from": "A", "to": "B", "points": "50"}],  # type: ignore[list-item] -- a dict the model parses into a Transfer
        citations={
            "kind": ar.ClauseCitation(clause="asg-3", quote="in proportion"),
            "transfers": ar.ClauseCitation(clause="asg-3", quote="A assigns 5 percent to B"),
        },
    )
    read = ar.settle(answer, ar.ReadAgreementInput(clauses=clauses))
    assert read.kept == ()
    assert dict(read.dropped) == {
        "kind": "quote_not_in_clause",
        "transfers": "unsupported_number",
    }


def test_ac_a_refused_call_proposes_nothing() -> None:
    clauses = [ar.AgreementClause(id="lpa-4.1", text="Use the monthly convention.")]
    read = ar.settle(None, ar.ReadAgreementInput(clauses=clauses))
    assert read.kept == () and all(r == "refused" for _p, r in read.dropped)


def test_ac_the_spec_is_propose_only_with_untrusted_clauses() -> None:
    spec = spec_v2(ar.CAPABILITY)
    assert spec.autonomy == "propose"
    assert "agreement_clauses" in spec.untrusted_inputs
    assert spec.evaluation_suite == "evals/tax_agreement_reader"
    assert "action" not in ar.ReadAgreementOutput.model_fields
    assert "actions" not in ar.ReadAgreementOutput.model_fields
