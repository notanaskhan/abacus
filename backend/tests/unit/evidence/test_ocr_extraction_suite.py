"""P-11-T29: the code-only OCR conformance run (`evals/ocr_extraction/suite.yaml`), on FakeOcr over
the synthetic scanned corpus. Blocks merges in CI. Clean means a scan; degraded means a phone's
perspective or JPEG. The goldens are `tests/golden/scanned_corpus.yaml`, marked `requires_review`:
this proves the code against them, not a CPA's reading of them."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

from abacus.kernel.ocr import normalise
from abacus.modules.evidence import pii
from abacus.modules.evidence.form_extraction import Extracted, extract, identify
from abacus.modules.evidence.words import PageWords, Word
from abacus_tools.synthetic.scanned_corpus import FACES, generate

ROOT: Final = Path(__file__).resolve().parents[4]
SUITE = cast(
    dict[str, Any], yaml.safe_load((ROOT / "evals/ocr_extraction/suite.yaml").read_text())
)
GOLDEN = cast(
    dict[str, Any], yaml.safe_load((ROOT / "backend/tests/golden/scanned_corpus.yaml").read_text())
)
FINISH: Final = {face.key: face.finish for face in FACES}
OBSCURED: Final = {face.key: face.obscured for face in FACES}
WIDTH: Final = Decimal("612")
HEIGHT: Final = Decimal("792")

# Golden field key by face: the map's key and the value the corpus prints.
FIELDS: Final[dict[str, dict[str, str]]] = {
    "whitley_cp2000": {
        "notice.amount_due": GOLDEN["whitley_cp2000"]["amount_due"],
        "notice.changes.interest.shown": GOLDEN["whitley_cp2000"]["changes_shown"],
    },
    "santos_cp14": {
        "notice.amount_due": GOLDEN["santos_cp14"]["amount_due"],
        "notice.charges.tax.amount": GOLDEN["santos_cp14"]["charges"]["tax"],
        "notice.charges.penalty.amount": GOLDEN["santos_cp14"]["charges"]["penalty"],
        "notice.charges.interest.amount": GOLDEN["santos_cp14"]["charges"]["interest"],
    },
}


def _layer(key: str) -> PageWords:
    page = next(p for p in generate() if p.key == key)
    blocks = json.loads(page.textract).get("Blocks", [])
    words = normalise(blocks, width_pt=WIDTH, height_pt=HEIGHT)
    return PageWords(
        1,
        float(WIDTH),
        float(HEIGHT),
        0,
        tuple(
            Word(
                w.text,
                float(w.bbox[0]),
                float(w.bbox[1]),
                float(w.bbox[2]),
                float(w.bbox[3]),
                float(w.confidence),
            )
            for w in words
        ),
    )


def _fields(key: str) -> dict[str, Extracted]:
    layer = _layer(key)
    found = identify([layer])
    assert found is not None, key
    return {f.field_key: f for f in extract(found, [layer])}


def _rate(hits: int, total: int) -> float:
    return 1.0 if total == 0 else hits / total


def _metrics() -> dict[str, float]:
    exact = {"clean": [0, 0], "degraded": [0, 0]}
    wrong = confident = 0
    for key, expected in FIELDS.items():
        band = "clean" if FINISH[key] == "scan" else "degraded"
        found = _fields(key)
        for field, value in expected.items():
            hit = found.get(field)
            exact[band][1] += 1
            if hit is not None and hit.value_text == value:
                exact[band][0] += 1
            elif hit is not None and not hit.low_confidence:
                wrong += 1
            if hit is not None and not hit.low_confidence:
                confident += 1
    respond = _fields("whitley_cp2000").get("notice.respond_by")
    box_a = GOLDEN["feld_w2"]["box_a_last4"]
    regions = pii.detect(1, _layer("feld_w2").words)
    return {
        "tin_region_recall": 1.0 if any(r.last4 == box_a for r in regions) else 0.0,
        "field_exact_match_clean": _rate(*exact["clean"]),
        "field_exact_match_degraded": _rate(*exact["degraded"]),
        "respond_by_exact": 1.0
        if respond is not None and respond.value_text == GOLDEN["whitley_cp2000"]["respond_by"]
        else 0.0,
        "confident_wrong_rate": _rate(wrong, confident) if confident else 0.0,
        "low_confidence_flag_recall": _flag_recall(),
    }


def _flag_recall() -> float:
    flagged = total = 0
    for key, words in OBSCURED.items():
        if not words:
            continue
        for word in _layer(key).words:
            if word.text in words:
                total += 1
                flagged += word.confidence < 0.90
    return _rate(flagged, total)


@pytest.mark.parametrize(
    "threshold", cast(list[dict[str, Any]], SUITE["thresholds"]), ids=lambda t: t["metric"]
)
def test_the_suite_meets_its_threshold(threshold: dict[str, Any]) -> None:
    value = _metrics()[threshold["metric"]]
    if "minimum" in threshold:
        assert value >= threshold["minimum"], threshold["metric"]
    else:
        assert value <= threshold["maximum"], threshold["metric"]


def test_a_changed_golden_fails_the_exact_match() -> None:
    assert _fields("santos_cp14")["notice.amount_due"].value_text != "1982.41"
