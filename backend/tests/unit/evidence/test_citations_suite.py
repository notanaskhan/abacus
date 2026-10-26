"""P-03-T17 (TASK-1256; SPEC-322 AC-39, AC-40): the code-only citation conformance suite
(`evals/citations/suite.yaml`) scores 1.0, every case, every repeat: fabricated pages, boxes,
quotes and values, unicode deception and moved sources are caught, valid citations are accepted,
quotes of masked text verify and the clear value does not, and agent material holds no unmasked
TIN. Removing the masking, the box check, the value check or the TIN scrub makes it fail (the
seeded regressions). No model, no database."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

from abacus.kernel.tin_patterns import has_tin
from abacus.modules.evidence import pii, projection
from abacus.modules.evidence.citations import matching
from abacus.modules.evidence.citations.display import state_of
from abacus.modules.evidence.citations.matching import Box, WordLike, amount
from abacus.modules.evidence.citations.verifiers import verify_layer_page
from abacus.modules.evidence.masking import MaskRegion
from abacus.modules.evidence.models import CitationEvent
from abacus.modules.evidence.projection import Projection
from abacus.modules.evidence.words import Word

SUITE = Path(__file__).resolve().parents[4] / "evals" / "citations" / "suite.yaml"
DATA = cast(dict[str, Any], yaml.safe_load(SUITE.read_text(encoding="utf-8")))  # ANY-001: YAML
CASES = cast(list[dict[str, Any]], DATA["cases"])  # ANY-001: YAML cases
DOC = cast(dict[str, Any], DATA["document"])  # ANY-001: the seeded document


def _box(raw: list[float]) -> Box:
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


LAYER: Final = {
    int(n): [Word(str(t), float(a), float(b), float(c), float(d)) for t, a, b, c, d in words]
    for n, words in DOC["pages"].items()
}
PROJECTION: Final = Projection(
    frozenset(int(n) for n in DOC["scanned"]),
    tuple(
        MaskRegion(int(r["page"]), _box(r["bbox"]), r["kind"], r["last4"]) for r in DOC["regions"]
    ),
)
SHEET: Final = [[str(c) for c in row] for row in DOC["sheet"]]
FABRICATIONS: Final = frozenset(
    {
        "fabricated_page",
        "fabricated_bbox",
        "fabricated_quote",
        "fabricated_value",
        "unicode",
        "moved",
    }
)


def _value(raw: object) -> Decimal | None:
    """A claim's value as the verifier reads it: a number, or none that can match."""
    if raw is None:
        return None
    found = amount(str(raw))
    return found if found is not None else Decimal("-0.0001")  # text never matches a figure


def _material(which: str) -> str:
    """The agent material built from the seeded document, as `processing` builds it."""
    if which == "sheet":
        return " ".join(c for row in pii.masked_rows(SHEET) for c in row)
    texts: list[str] = []
    for n, words in LAYER.items():
        shown = PROJECTION.words(words, n)
        if shown is not None:
            texts.append(pii.scrub_tins(" ".join(w.text for w in shown)))
    return " ".join(texts)


def outcome(case: dict[str, Any]) -> str:  # ANY-001: a YAML case
    if "events" in case:
        events = [
            CitationEvent(kind=k, cause_ref=f"successor-{i}") for i, k in enumerate(case["events"])
        ]
        return state_of(events)[0]
    if "material" in case:
        return "leaked" if has_tin(_material(case["material"])) else "contained"
    box = case.get("bbox")
    verdict = verify_layer_page(
        LAYER,
        PROJECTION,
        int(case["page"]),
        box=_box(box) if box else None,
        quote=case.get("quote"),
        value=_value(case.get("value")),
    )
    return verdict.reason or "pass"


def _share(selected: list[dict[str, Any]]) -> float:  # ANY-001: YAML cases
    return sum(outcome(c) == c["expect"] for c in selected) / len(selected) if selected else 0.0


METRICS: Final = {
    "fabrication_caught": lambda: _share([c for c in CASES if c["category"] in FABRICATIONS]),
    "valid_citation_accepted": lambda: _share([c for c in CASES if c["category"] == "valid"]),
    "masked_quote_verified": lambda: _share([c for c in CASES if c["category"] == "masked_quote"]),
    "tin_in_agent_material": lambda: _share([c for c in CASES if c["category"] == "containment"]),
}


def score() -> float:
    hits = sum(outcome(c) == c["expect"] for _ in range(DATA["repeats"]) for c in CASES)
    return hits / (len(CASES) * DATA["repeats"])


def test_suite_covers_its_declared_categories() -> None:
    assert {c["category"] for c in CASES} == set(DATA["covers"])
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert {t["metric"] for t in DATA["thresholds"]} == set(METRICS)
    assert all(t["minimum"] == 1.0 for t in DATA["thresholds"])


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case: dict[str, Any]) -> None:  # ANY-001: a YAML case
    assert outcome(case) == case["expect"]


def test_the_suite_scores_one_on_every_repeat() -> None:
    assert score() == DATA["required_pass_rate"] == 1.0


@pytest.mark.parametrize("metric", sorted(METRICS))
def test_ac39_each_metric_meets_its_threshold(metric: str) -> None:
    minimum = next(t["minimum"] for t in DATA["thresholds"] if t["metric"] == metric)
    assert METRICS[metric]() >= minimum == 1.0


# The seeded regressions' stand-ins: each turns one rule off.
def _unmasked(words: Sequence[WordLike], _regions: object, _page: int) -> list[WordLike]:
    return list(words)


def _every_word(words: Sequence[WordLike], _box: object) -> list[WordLike]:
    return list(words)


def _first_word(words: Sequence[WordLike], _value: object) -> WordLike | None:
    return words[0] if words else None


def _unscrubbed(text: str) -> str:
    return text


def test_seeded_regression_without_masking_the_clear_value_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(projection, "masked_words", _unmasked)
    assert METRICS["masked_quote_verified"]() < 1.0
    assert score() < 1.0


def test_seeded_regression_without_the_box_check_fabricated_boxes_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(matching, "words_in", _every_word)
    assert METRICS["fabrication_caught"]() < 1.0


def test_seeded_regression_without_the_value_check_fabricated_values_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(matching, "_value_in", _first_word)
    assert METRICS["fabrication_caught"]() < 1.0


def test_seeded_regression_without_the_tin_scrub_material_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pii, "scrub_tins", _unscrubbed)
    assert METRICS["tin_in_agent_material"]() < 1.0
