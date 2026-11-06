"""The synthetic scanned corpus (P-11-T28; P-11 §8; DEC-2314; DEC-78).

Test-only faces drawn from Brightwater Hale's figures, rasterised with skew, noise, JPEG and a
phone's perspective, each with the Textract-shaped JSON `FakeOcr` replays. Deterministic from a seed:
the same seed gives the same bytes and the same SHA-256 keys. Fictional people and payers only. The
faces live in `abacus_tools` (ADR-101): no production layout ever carries them (DEC-78), and no
template or rule reads them. Golden values: `backend/tests/golden/scanned_corpus.yaml`.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageDraw, ImageFilter

WIDTH: Final = 1224
HEIGHT: Final = 1584
_CHAR: Final = 11
_LINE: Final = 34
_LEFT: Final = 90
_TOP: Final = 90
DEFAULT_SEED: Final = 0x7B13C4


@dataclass(frozen=True)
class Face:
    key: str
    finish: str  # scan, phone or jpeg
    lines: tuple[tuple[str, ...], ...]
    obscured: frozenset[str] = frozenset()  # words printed through a smudge: low confidence


FACES: Final[tuple[Face, ...]] = (
    Face(
        "whitley_cp2000",
        "scan",
        (
            ("Notice", "CP2000"),
            ("Notice", "number:", "CP2000"),
            ("Tax", "year:", "2024"),
            ("Notice", "date:", "August", "24,", "2026"),
            ("Respond", "by:", "September", "23,", "2026"),
            ("Amount", "due:", "$753.01"),
            ("Social", "Security", "number:", "4471"),
            ("Increase", "in", "tax:", "$686.40"),
            ("Interest:", "$66.61"),
            ("Shown", "on", "return"),
            ("Interest", "412.00", "3,532.00", "3,120.00"),
            ("Payers", "reported"),
            ("Front", "Range", "Bank", "1,870.00"),
            ("Lakeview", "Credit", "Union", "1,250.00"),
            ("Total", "3,120.00"),
        ),
    ),
    Face(
        "santos_cp14",
        "phone",
        (
            ("Notice", "CP14"),
            ("Notice", "number:", "CP14"),
            ("Tax", "year:", "2024"),
            ("Notice", "date:", "July", "6,", "2026"),
            ("Pay", "by:", "July", "27,", "2026"),
            ("Amount", "due:", "$1,982.40"),
            ("Social", "Security", "number:", "2290"),
            ("Tax", "you", "owed:", "$1,842.00"),
            ("Penalties:", "$92.10"),
            ("Amount", "you", "owed"),
            ("Tax", "1,842.00"),
            ("Penalty", "92.10"),
            ("Interest", "48.30"),
        ),
        frozenset({"July", "27,"}),
    ),
    Face(
        "feld_w2",
        "scan",
        (
            ("Form", "W-2", "Wage", "and", "Tax", "Statement", "2025"),
            ("a", "Employee's", "SSN", "000-00-6081"),
            ("b", "Employer", "EIN", "00-0000417"),
            ("c", "Mercer", "Hill", "Health"),
            ("1", "Wages,", "tips", "268,400.00"),
            ("2", "Federal", "income", "tax", "withheld", "51,120.00"),
        ),
    ),
    Face(
        "feld_1095c",
        "jpeg",
        (
            ("Form", "1095-C", "2025"),
            ("Employee", "Claire", "Feld"),
            ("Employer", "Mercer", "Hill", "Health"),
            ("Offer", "of", "coverage", "code", "1E"),
        ),
    ),
    Face(
        "iyer_1099div_corrected",
        "scan",
        (
            ("CORRECTED", "Form", "1099-DIV", "2025"),
            ("Payer", "Halvard", "Securities"),
            ("1a", "Total", "ordinary", "dividends", "4,120.00"),
            ("1b", "Qualified", "dividends", "3,310.00"),
        ),
    ),
    Face(
        "ridgeline_k1",
        "scan",
        (
            ("Schedule", "K-1", "Form", "1065", "2025"),
            ("Partnership", "Ridgeline", "Holdings", "LP"),
            ("1", "Ordinary", "business", "income", "84,300.00"),
            ("18A", "Tax-exempt", "interest", "1,200.00"),
            ("19A", "Cash", "distributions", "40,000.00"),
        ),
    ),
    Face(
        "front_range_statement",
        "scan",
        (
            ("Front", "Range", "Bank", "Statement"),
            ("Statement", "period", "12/01/2025", "12/31/2025"),
            ("Opening", "balance", "14,200.00"),
            ("12/05", "Deposit", "2,100.00"),
            ("12/18", "Check", "1042", "(700.00)"),
            ("Closing", "balance", "15,600.00"),
        ),
    ),
    Face(
        "calloway_instrument",
        "phone",
        (
            ("Promissory", "Note"),
            ("Borrower", "Calloway", "Partners"),
            ("Principal", "250,000.00"),
            ("Rate", "6.25%"),
        ),
    ),
)


@dataclass(frozen=True)
class CorpusPage:
    key: str
    page: int
    media_type: str
    image: bytes
    textract: str  # the recorded response `FakeOcr` replays

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.image).hexdigest()


def _blocks(face: Face, rng: random.Random) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for row, tokens in enumerate(face.lines):
        x = _LEFT
        top = _TOP + row * _LINE
        for token in tokens:
            width = _CHAR * len(token)
            confidence = (
                round(rng.uniform(62.0, 74.0), 1)
                if token in face.obscured
                else round(rng.uniform(96.0, 99.6), 1)
            )
            blocks.append(
                {
                    "BlockType": "WORD",
                    "Text": token,
                    "Confidence": confidence,
                    "Geometry": {
                        "BoundingBox": {
                            "Left": x / WIDTH,
                            "Top": top / HEIGHT,
                            "Width": width / WIDTH,
                            "Height": 20 / HEIGHT,
                        }
                    },
                }
            )
            x += width + _CHAR
    return blocks


def _render(face: Face, rng: random.Random) -> tuple[bytes, str]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    for row, tokens in enumerate(face.lines):
        x = _LEFT
        top = _TOP + row * _LINE
        for token in tokens:
            draw.text((x, top), token, fill="black")
            x += _CHAR * len(token) + _CHAR
    skew = rng.uniform(-1.2, 1.2)
    image = image.rotate(skew, fillcolor="white", resample=Image.Resampling.BILINEAR)
    pixels = image.load()
    assert pixels is not None
    for _ in range(4000):
        spot = (rng.randrange(WIDTH), rng.randrange(HEIGHT))
        level = rng.randrange(180, 255)
        pixels[spot] = (level, level, level)
    if face.finish == "phone":
        drift = rng.uniform(0.006, 0.02)
        image = image.transform(
            image.size,
            Image.Transform.PERSPECTIVE,
            (1, drift, 0, drift / 2, 1, 0, drift / 4000, drift / 6000),
            Image.Resampling.BILINEAR,
            fillcolor="white",
        ).filter(ImageFilter.GaussianBlur(0.6))
    buffer = io.BytesIO()
    if face.finish == "scan":
        image.save(buffer, format="PNG", optimize=False)
        return buffer.getvalue(), "image/png"
    image.save(buffer, format="JPEG", quality=70, subsampling=2)
    return buffer.getvalue(), "image/jpeg"


def generate(seed: int = DEFAULT_SEED) -> tuple[CorpusPage, ...]:
    """Every face, one page each, the same bytes for the same seed."""
    rng = random.Random(seed)  # noqa: S311 -- synthetic layout noise, never a secret
    pages: list[CorpusPage] = []
    for face in FACES:
        image, media = _render(face, rng)
        textract = json.dumps({"Blocks": _blocks(face, rng)}, sort_keys=True)
        pages.append(CorpusPage(face.key, 1, media, image, textract))
    return tuple(pages)


def recordings(pages: Sequence[CorpusPage]) -> Mapping[str, str]:
    """`FakeOcr`'s recordings: page-image SHA-256 to its Textract JSON."""
    return {page.sha256: page.textract for page in pages}
