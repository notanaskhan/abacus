"""P-06-T21 (P-06 §6; SPEC-030 AC-8; F-04.26): the upload reviewer's fake answers, offline.

The recorded answers cover every case of the suite once, parse as the reviewer's output, flag
what each case expects, and quote only text that is in the case's generated document. The
responder serves an answer only for its (prompt, request and document); the reviewer starts on
the fake route only when a reviewer responder is installed; a fake run's verdict also fails any
attempt that isn't what its case expects. No stack, no model.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from abacus.ai_gateway import FakeModel, ModelRequest, ProviderError, configure_provider
from abacus.modules.agents.api import (
    REVIEWER,
    install_fake_reviews,
    review_sha256,
    spec,
    upload_review_available,
)
from abacus.modules.agents.handoff import UploadReviewOutput
from abacus.modules.evidence.api import normalised_text
from abacus.modules.evidence.extraction import extract
from abacus_tools.evals.upload_review import (
    FAKE_ANSWERS,
    UNTRUSTED,
    ReviewCase,
    Seen,
    _documents,  # pyright: ignore[reportPrivateUsage] -- the suite's own document table
    fake_answers,
    load_suite,
    verdict,
)

YEAR_END = date(2025, 12, 31)  # the throwaway stack's engagement (abacus_tools.stack.seed)
PROMPT = spec(REVIEWER).prompt


def _files() -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for path in sorted(FAKE_ANSWERS.glob("*.json")):
        raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        found[str(raw["case"])] = raw
    return found


def _request(asked: str, document: list[str], checks: object = ()) -> ModelRequest:
    trusted = json.dumps({"request": asked, "checks_by_code": checks}, sort_keys=True)
    user = f"## task\n{trusted}\n{UNTRUSTED}\n{json.dumps(document)}\n</untrusted>"
    return ModelRequest(
        model="fake-small", system="", user=user, max_output_tokens=10, prompt_ref=PROMPT
    )


def test_every_case_has_one_recorded_answer_for_the_reviewers_prompt() -> None:
    files = _files()
    suite = load_suite()
    assert set(files) == {c.id for c in suite.cases}
    assert len(list(FAKE_ANSWERS.glob("*.json"))) == len(suite.cases)
    assert {f["prompt_ref"] for f in files.values()} == {PROMPT}
    # One answer per key: the loader refuses a second; every case's content differs.
    assert len(fake_answers()) == len(suite.cases)


@pytest.mark.parametrize("case", load_suite().cases, ids=lambda c: c.id)
def test_each_answer_parses_and_flags_what_its_case_expects(case: ReviewCase) -> None:
    output = UploadReviewOutput.model_validate(_files()[case.id]["response"])
    confident = {f.category for f in output.flags if f.confidence >= 0.5}
    # Code hides an "altered" flag when its own balance checks found the problem (TASK-058).
    hidden_by_code = {"altered"} if case.id.startswith("code_catches_") else set[str]()
    assert confident - hidden_by_code == case.expected
    assert output.no_concerns == (not output.flags)


@pytest.mark.parametrize("case", load_suite().cases, ids=lambda c: c.id)
def test_each_quote_is_in_the_generated_document(case: ReviewCase) -> None:
    """Every quote is in the page it names (code verifies the masked text on the stack too)."""
    output = UploadReviewOutput.model_validate(_files()[case.id]["response"])
    name, content = _documents(YEAR_END)[case.document]()
    found = extract(content, "application/pdf" if name.endswith(".pdf") else "text/csv")
    pages = {n: normalised_text(text) for n, text in enumerate(found.pages, start=1)}
    for flag in output.flags:
        for citation in flag.citations:
            assert citation.page is not None, "the cases' flags quote PDF pages"
            for line in citation.quote.splitlines():
                assert normalised_text(line) in pages[citation.page], (case.id, line)


def test_the_responder_serves_only_its_recorded_request_and_document() -> None:
    document = ["Page 1:\nSTATEMENT OF ACCOUNT"]
    request = _request("Invoice for freight", document)
    sha = review_sha256(request)
    assert sha is not None
    fake = install_fake_reviews(FakeModel(), {(PROMPT, sha): '{"no_concerns": true, "flags": []}'})
    # What code checked doesn't change the key: only the request and the document do.
    assert review_sha256(_request("Invoice for freight", document, checks=["x"])) == sha
    assert review_sha256(_request("Bank statement", document)) != sha
    assert review_sha256(_request("Invoice for freight", [*document, "Page 2:\nx"])) != sha
    answered = asyncio.run(fake.complete(request))
    assert json.loads(answered.text) == {"no_concerns": True, "flags": []}
    with pytest.raises(ProviderError):
        asyncio.run(fake.complete(_request("Bank statement", document)))


def test_the_reviewer_starts_on_the_fake_route_only_with_a_reviewer_responder() -> None:
    try:
        configure_provider(FakeModel())  # the local stack's fake model: no reviewer answers
        assert upload_review_available() is False
        configure_provider(install_fake_reviews(FakeModel(), {(PROMPT, "0" * 64): "{}"}))
        assert upload_review_available() is True
    finally:
        configure_provider(None)


def _seen(case: ReviewCase, shown: set[str], stage: str = "reviewed") -> Seen:
    return Seen(case.id, 1, stage, shown=frozenset(shown), contained=True, cost_usd=Decimal(0))


def test_a_fake_run_fails_any_attempt_that_is_not_what_its_case_expects() -> None:
    suite = load_suite()
    honest = [(c, _seen(c, set(c.expected))) for c in suite.cases]
    assert verdict(suite, honest, exact=True)[:2] == ("passed", [])
    # One clean case flagged draft: precision still clears 0.80, the recorded run doesn't.
    clean = next(c for c in suite.cases if c.id == "clean_aging")
    wrong = [(c, _seen(c, {"draft"}) if c is clean else s) for c, s in honest]
    assert verdict(suite, wrong)[0] == "passed"
    assert verdict(suite, wrong, exact=True)[1] == ["case:clean_aging"]
    errored = [(c, _seen(c, set(), "errored") if c is clean else s) for c, s in honest]
    assert verdict(suite, errored, exact=True)[1] == ["case:clean_aging"]
