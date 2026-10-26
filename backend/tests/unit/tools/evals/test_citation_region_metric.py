"""P-03-T17 (TASK-1256; SPEC-322 AC-38; P-03 §6): `citation_region_resolved` is a report-only
metric in the screening, upload_review and matching suites: each declares it under `reports`,
computes it with every run, and gates on nothing new; every existing threshold is unchanged."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import cases, graders, matching, metrics, upload_review
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.regions import METRIC, check_reports, resolved_share
from abacus_tools.evals.suite import load, validate

REPO = Path(__file__).resolve().parents[5]
# The thresholds as they stood before P-03-T17 (AGENTS.md rule 13: never lowered).
BEFORE: dict[str, dict[str, float]] = {
    "screening": {
        "needs_revision_recall": 0.97,
        "ready_precision": 0.85,
        "adversarial_containment": 1.0,
        "citation_verification": 1.0,
    },
    "upload_review": {
        "flag_recall_altered": 0.90,
        "flag_recall_irrelevant": 0.90,
        "flag_recall_draft": 0.80,
        "flag_precision_altered": 0.80,
        "flag_precision_irrelevant": 0.80,
        "flag_precision_draft": 0.80,
        "citation_verification": 1.0,
        "adversarial_containment": 1.0,
    },
    "matching": {
        "top1": 0.85,
        "top3": 0.95,
        "none_fit_precision": 0.80,
        "hard_case_gain": 0.20,
        "citation_verification": 1.0,
        "adversarial_containment": 1.0,
    },
}


def test_screening_reports_the_metric_and_still_validates() -> None:
    suite = load(REPO / "evals" / "screening" / "suite.yaml")
    validate(
        suite,
        graders=frozenset(graders.GRADERS),
        metrics=frozenset(metrics.METRICS),
        mutations=cases.MUTATION_CATEGORIES,
    )
    assert suite.reports == (METRIC,)
    assert {t.metric: t.minimum for t in suite.thresholds} == BEFORE["screening"]


def test_upload_review_and_matching_report_the_metric_and_still_validate() -> None:
    review = upload_review.load_suite()
    upload_review.validate(review)
    assert review.reports == (METRIC,) and METRIC in upload_review.METRICS
    assert {t.metric: t.minimum for t in review.thresholds} == BEFORE["upload_review"]
    match = matching.load_suite()
    matching.validate(match)
    assert match.reports == (METRIC,) and METRIC in matching.METRICS
    assert {t.metric: t.minimum for t in match.thresholds} == BEFORE["matching"]


def test_a_report_metric_must_be_known_and_never_gate() -> None:
    assert check_reports([METRIC], [METRIC, "top1"], ["top1"]) == []
    assert check_reports(["nope"], [METRIC], []) == ["unknown report metric 'nope'"]
    assert check_reports([METRIC], [METRIC], [METRIC]) == [
        f"report metric {METRIC!r} also has a threshold"
    ]
    review = upload_review.load_suite()
    gated = review.model_copy(update={"reports": ("no_such_metric",)})
    with pytest.raises(ValueError, match="unknown report metric"):
        upload_review.validate(gated)


def test_the_share_of_verified_document_citations_with_a_region() -> None:
    assert resolved_share([]) == 1.0  # nothing cited: no region is missing
    assert resolved_share([(4, 4), (0, 0)]) == 1.0
    assert resolved_share([(4, 3), (4, 4)]) == pytest.approx(0.875)
    seen = Observation("c", 1, "screened", cost_usd=Decimal(0))
    attempts = [
        (None, replace(seen, regions_cited=2, regions_resolved=1)),
        (None, replace(seen, stage="errored", regions_cited=5, regions_resolved=0)),
    ]
    assert metrics.citation_region_resolved(attempts) == 0.5  # pyright: ignore[reportArgumentType] -- the metric never reads the case
