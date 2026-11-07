"""The OCR extraction conformance suite (P-11-T29; P-11 §8; `evals/ocr_extraction/suite.yaml`).

    python -m abacus_tools.evals.ocr_extraction --provider fake [--out DIR]
    python -m abacus_tools.evals.ocr_extraction --provider textract --out DIR [--blocking]

Reads every page of the synthetic scanned corpus (`abacus_tools.synthetic.scanned_corpus`)
through an OCR provider, then the code paths the product uses (`form_extraction.identify` and
`extract`, `pii.detect`), and scores them against the corpus goldens
(`backend/tests/golden/scanned_corpus.yaml`). `fake` replays the recorded Textract layers (CI's
code-only run, `tests/unit/evidence/test_ocr_extraction_suite.py`); `textract` calls Textract for
real (the nightly run in staging, `.github/workflows/ocr-nightly.yml`). Synthetic pages only: no
firm's document ever reaches this.

The nightly run is report-only until two consecutive runs pass, then `--blocking` (the row's
acceptance): a report-only run exits 0 whatever it scores and says so in its report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import yaml

from abacus.kernel.clock import system_now
from abacus.kernel.ocr import FakeOcr, OcrProvider, TextractOcr
from abacus.modules.evidence.api import ExtractedField as Extracted
from abacus.modules.evidence.api import PageWords, Word, detect_pii, extract_form, identify_form
from abacus_tools.synthetic.scanned_corpus import FACES, generate, recordings

ROOT: Final = Path(__file__).resolve().parents[4]
SUITE_FILE: Final = ROOT / "evals/ocr_extraction/suite.yaml"
GOLDEN_FILE: Final = ROOT / "backend/tests/golden/scanned_corpus.yaml"
WIDTH: Final = Decimal("612")
HEIGHT: Final = Decimal("792")
LOW_CONFIDENCE: Final = 0.90


def _golden() -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], yaml.safe_load(GOLDEN_FILE.read_text("utf-8")))


def golden_fields() -> dict[str, dict[str, str]]:
    """Each face's golden field values: the map's key and the value the corpus prints."""
    golden = _golden()
    whitley, santos = golden["whitley_cp2000"], golden["santos_cp14"]
    charges = cast(dict[str, str], santos["charges"])
    return {
        "whitley_cp2000": {
            "notice.amount_due": str(whitley["amount_due"]),
            "notice.changes.interest.shown": str(whitley["changes_shown"]),
        },
        "santos_cp14": {
            "notice.amount_due": str(santos["amount_due"]),
            "notice.charges.tax.amount": charges["tax"],
            "notice.charges.penalty.amount": charges["penalty"],
            "notice.charges.interest.amount": charges["interest"],
        },
    }


async def read_layers(provider: OcrProvider) -> dict[str, PageWords]:
    """Every corpus page through `provider`, as the word layer the product builds."""
    layers: dict[str, PageWords] = {}
    for page in generate():
        read = await provider.read(page.image, width_pt=WIDTH, height_pt=HEIGHT, api="detect_text")
        words = tuple(
            Word(
                w.text,
                float(w.bbox[0]),
                float(w.bbox[1]),
                float(w.bbox[2]),
                float(w.bbox[3]),
                float(w.confidence),
            )
            for w in read.words
        )
        layers[page.key] = PageWords(1, float(WIDTH), float(HEIGHT), 0, words)
    return layers


def _fields(layer: PageWords) -> dict[str, Extracted]:
    found = identify_form([layer])
    return {} if found is None else {f.field_key: f for f in extract_form(found, [layer])}


def _rate(hits: int, total: int) -> float:
    return 1.0 if total == 0 else hits / total


def metrics(layers: Mapping[str, PageWords]) -> dict[str, float]:
    """The suite's six metrics over the read layers (the plan's definitions)."""
    finish = {face.key: face.finish for face in FACES}
    obscured = {face.key: face.obscured for face in FACES}
    golden = _golden()
    exact = {"clean": [0, 0], "degraded": [0, 0]}
    wrong = confident = 0
    for key, expected in golden_fields().items():
        band = "clean" if finish[key] == "scan" else "degraded"
        found = _fields(layers[key])
        for field, value in expected.items():
            hit = found.get(field)
            exact[band][1] += 1
            if hit is not None and hit.value_text == value:
                exact[band][0] += 1
            elif hit is not None and not hit.low_confidence:
                wrong += 1
            if hit is not None and not hit.low_confidence:
                confident += 1
    respond = _fields(layers["whitley_cp2000"]).get("notice.respond_by")
    box_a = cast(dict[str, str], golden["feld_w2"])["box_a_last4"]
    regions = detect_pii(1, layers["feld_w2"].words)
    flagged = total = 0
    for key, words in obscured.items():
        for word in layers[key].words if words else ():
            if word.text in words:
                total += 1
                flagged += word.confidence < LOW_CONFIDENCE
    whitley = cast(dict[str, str], golden["whitley_cp2000"])
    return {
        "tin_region_recall": 1.0 if any(r.last4 == box_a for r in regions) else 0.0,
        "field_exact_match_clean": _rate(*exact["clean"]),
        "field_exact_match_degraded": _rate(*exact["degraded"]),
        "respond_by_exact": 1.0
        if respond is not None and respond.value_text == whitley["respond_by"]
        else 0.0,
        "confident_wrong_rate": _rate(wrong, confident) if confident else 0.0,
        "low_confidence_flag_recall": _rate(flagged, total),
    }


@dataclass(frozen=True)
class Verdict:
    passed: bool
    failed: list[str]


def verdict(scores: Mapping[str, float], thresholds: Sequence[Mapping[str, object]]) -> Verdict:
    failed = [
        str(t["metric"])
        for t in thresholds
        if ("minimum" in t and scores[str(t["metric"])] < float(cast(float, t["minimum"])))
        or ("maximum" in t and scores[str(t["metric"])] > float(cast(float, t["maximum"])))
    ]
    return Verdict(not failed, failed)


def thresholds() -> list[dict[str, object]]:
    suite = cast(dict[str, object], yaml.safe_load(SUITE_FILE.read_text("utf-8")))
    return cast(list[dict[str, object]], suite["thresholds"])


async def _run(provider: str) -> dict[str, float]:
    engine: OcrProvider = FakeOcr(recordings(generate())) if provider == "fake" else TextractOcr()
    return metrics(await read_layers(engine))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals.ocr_extraction")
    parser.add_argument("--provider", choices=["fake", "textract"], default="fake")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--blocking", action="store_true")
    args = parser.parse_args(argv)
    scores = asyncio.run(_run(cast(str, args.provider)))
    found = verdict(scores, thresholds())
    report = {
        "suite": "ocr_extraction",
        "provider": args.provider,
        "at": system_now().isoformat(),
        "blocking": bool(args.blocking),
        "passed": found.passed,
        "failed_thresholds": found.failed,
        "metrics": scores,
    }
    if args.out is not None:
        out = cast(Path, args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"ocr_extraction-{args.provider}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if found.passed or not args.blocking else 1


if __name__ == "__main__":
    sys.exit(main())
