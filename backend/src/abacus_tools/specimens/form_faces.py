"""TPL-17's test-only form faces (F-07-T15; F-07 §H; DEC-4731): the Ridgeline 2025 Form 1065
page 1, Schedule K (pages 4 and 5), Schedules L and M-2 (page 6), and the Jonah Feld and Pell
Street II LLC K-1s, as C11 blocks with one declared value per field. Pure data: nothing here
renders, reads a tenant or touches a database.

The figures are the blueprint's (§9.4, Ridgeline TY2025) and TPL-17's; masked identifiers only
(no full EIN, SSN or PTIN). They foot: Schedule K line 2 + line 5 = 1,250,000 = the Analysis of
Net Income line 1 = 25,000 + 787,500 + 437,500 = M-2 line 3; M-2 5,960,000 + 250,000 + 1,250,000 =
7,460,000, less 600,000 = 6,860,000, which is Schedule L's 6,866,200 less the omitted 6,200
(TPL-17's "off 6,200"); Jonah Feld's K-1 is 25 % of Schedule K.

A face is a test-only specimen, not the IRS form: T-06 renders the real faces from database
templates (DEC-78). This module's field manifest shape (`id, page, rect_pt, label, value,
match_id, diagnostic`) is the additive C11 request F-07-T21 files.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

AS_OF: Final = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
TITLE: Final = "Ridgeline Property Partners, LP · 2025 Form 1065 · specimen faces (test only)"
LAYOUT: Final = "report"


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    value: str
    match_id: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class Face:
    id: str
    heading: str
    fields: tuple[Field, ...]


def _f(
    key: str, label: str, value: str, match_id: str | None = None, diagnostic: str | None = None
) -> Field:
    return Field(key, label, value, match_id, diagnostic)


FACES: Final[tuple[Face, ...]] = (
    Face(
        "1065-p1",
        "Form 1065 · page 1 · U.S. Return of Partnership Income · 2025",
        (
            _f("p1.activity", "A Principal business activity", "Real estate rental"),
            _f("p1.product", "B Principal product or service", "Residential and commercial rent"),
            _f("p1.code", "C Business code number", "531110"),
            _f("p1.name", "Name of partnership", "Ridgeline Property Partners, LP"),
            _f("p1.street", "Number and street", "410 Elm Street"),
            _f("p1.city", "City or town", "Chicago"),
            _f("p1.state", "State", "IL"),
            _f("p1.zip", "ZIP code", "60610"),
            _f("p1.ein", "D Employer identification number", "••-•••0287"),
            _f("p1.started", "E Date business started", "01/15/2018"),
            _f("p1.assets", "F Total assets", "$17,914,500"),
            _f("p1.method", "H Accounting method", "Accrual"),
            _f("p1.k1s", "I Number of Schedules K-1 attached", "5"),
            _f("p1.m3", "J Schedules C and M-3 attached", "Not checked", None, "m3_required"),
            _f("p1.obi", "Ordinary business income (loss)", "0"),
            _f("p1.gp", "General partner or LLC member manager", "Owen Calder, Ridgeline GP LLC"),
            _f("p1.preparer", "Paid preparer", "Daniel Reyes"),
            _f("p1.ptin", "PTIN", "P•••••512"),
            _f("p1.firm", "Firm name", "Brightwater Hale LLP"),
            _f("p1.firm_ein", "Firm EIN", "••-•••4118"),
        ),
    ),
    Face(
        "sch-k-p4",
        "Schedule K · page 4 · Partners' Distributive Share Items",
        (
            _f(
                "k.l2",
                "2 Net rental real estate income (attach Form 8825)",
                "1,231,600",
                "sch-k-2",
            ),
            _f("k.l5", "5 Interest income", "18,400", "sch-k-5"),
        ),
    ),
    Face(
        "sch-k-p5",
        "Schedule K · page 5 · and the Analysis of Net Income (Loss)",
        (
            _f("k.l18a", "18a Tax-exempt interest income", "6,200", "sch-k-18a"),
            _f(
                "k.l19a",
                "19a Distributions of cash and marketable securities",
                "600,000",
                "sch-k-19a",
            ),
            _f("k.l20a", "20a Investment income", "18,400", "sch-k-20a"),
            _f("an.l1", "Analysis of Net Income (Loss), line 1", "1,250,000", "analysis-1"),
            _f("an.gp", "2 General partners · Partnership", "25,000"),
            _f("an.lp_ind", "Limited partners · Individual (passive)", "787,500"),
            _f("an.lp_pship", "Limited partners · Partnership", "437,500"),
        ),
    ),
    Face(
        "sch-l-m2-p6",
        "Schedules L, M-1 and M-2 · page 6 · as drafted",
        (
            _f("l.l21", "Schedule L line 21 Partners' capital accounts, end of year", "6,866,200"),
            _f("m2.l1", "M-2 line 1 Balance at beginning of year", "5,960,000"),
            _f("m2.l2a", "M-2 line 2a Capital contributed: cash", "250,000"),
            _f("m2.l3", "M-2 line 3 Net income (loss)", "1,250,000"),
            _f("m2.l4", "M-2 line 4 Other increases (itemize)", "—", None, "m2_off"),
            _f("m2.l5", "M-2 line 5 Add lines 1 through 4", "7,460,000"),
            _f("m2.l6a", "M-2 line 6a Distributions: cash", "600,000"),
            _f("m2.l9", "M-2 line 9 Balance at end of year", "6,860,000", "m2-9"),
        ),
    ),
    Face(
        "k1-feld",
        "Schedule K-1 (Form 1065) · 2025 · partner one",
        (
            _f("k1f.partner", "Partner's name", "Jonah Feld"),
            _f("k1f.tin", "Partner's identifying number", "•••-••-4417"),
            _f("k1f.b2", "Box 2 Net rental real estate income (loss)", "307,900", "k1-feld-2"),
            _f("k1f.b5", "Box 5 Interest income", "4,600", "k1-feld-5"),
            _f("k1f.b18a", "Box 18A Tax-exempt interest income", "1,550", "k1-feld-18a"),
            _f("k1f.b19a", "Box 19A Distributions", "150,000", "k1-feld-19a"),
            _f("k1f.end", "Ending capital account (as drafted)", "1,912,500"),
            _f("k1f.status", "Status", "Draft K-1 · pre-release"),
        ),
    ),
    Face(
        "k1-pell-street-ii",
        "Schedule K-1 (Form 1065) · 2025 · partner two",
        (
            _f("k1p.partner", "Partner's name", "Pell Street II LLC"),
            _f("k1p.period", "Partner from", "7/1/2025"),
            _f("k1p.tin", "Partner's identifying number", "••-•••8810"),
            _f("k1p.b2", "Box 2 Net rental real estate income (loss)", "30,790", "k1-ps2-2"),
            _f("k1p.b5", "Box 5 Interest income", "460", "k1-ps2-5"),
            _f("k1p.b18a", "Box 18A Tax-exempt interest income", "155", "k1-ps2-18a"),
            _f("k1p.b19a", "Box 19A Distributions", "30,000", "k1-ps2-19a"),
            _f("k1p.end", "Ending capital account (as drafted)", "332,655"),
            _f("k1p.status", "Status", "Draft K-1 · pre-release"),
        ),
    ),
)


def values() -> dict[str, str]:
    return {f.key: f.value for face in FACES for f in face.fields}


def blocks() -> list[object]:
    """One face a page: a heading and a key-value block whose values are declared variables."""
    out: list[object] = []
    for i, face in enumerate(FACES):
        if i > 0:
            out.append({"type": "page_break"})
        out.append({"type": "heading", "level": 2, "text": face.heading})
        out.append(
            {
                "type": "kv",
                "rows": [
                    {"key": f.label, "value": [{"type": "var", "key": f.key}]} for f in face.fields
                ],
            }
        )
    return out


def content_hash() -> str:
    raw = json.dumps({"blocks": blocks(), "values": values()}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def amount(key: str) -> Decimal:
    return Decimal(values()[key].replace(",", "").replace("$", ""))


@dataclass(frozen=True)
class Located:
    """One located value: the C11 region the renderer reported (rect in points, top-left)."""

    key: str
    page: int
    rect_pt: tuple[float, float, float, float]


def manifest(
    located: Sequence[Located], page_sizes: Sequence[tuple[float, float]], images: Sequence[str]
) -> dict[str, object]:
    """The field manifest: each field on its own face's page, found exactly once there."""
    page_of = {f.key: n for n, face in enumerate(FACES, start=1) for f in face.fields}
    fields: list[dict[str, object]] = []
    for n, face in enumerate(FACES, start=1):
        for f in face.fields:
            hits = [r for r in located if r.key == f.key and r.page == page_of[f.key]]
            if len(hits) != 1:
                raise ValueError(f"{f.key}: {len(hits)} regions on page {n}, expected 1")
            fields.append(
                {
                    "id": f.key,
                    "page": n,
                    "rect_pt": list(hits[0].rect_pt),
                    "label": f.label,
                    "value": f.value,
                    "match_id": f.match_id,
                    "diagnostic": f.diagnostic,
                }
            )
    pages = [
        {"n": n, "face": face.id, "image": images[n - 1], "width_pt": w, "height_pt": h}
        for n, (face, (w, h)) in enumerate(zip(FACES, page_sizes, strict=True), start=1)
    ]
    return {"version": 1, "title": TITLE, "pages": pages, "fields": fields}


def manifest_json(document: Mapping[str, object]) -> str:
    return json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


__all__ = [
    "AS_OF",
    "FACES",
    "LAYOUT",
    "TITLE",
    "Face",
    "Field",
    "Located",
    "amount",
    "blocks",
    "content_hash",
    "manifest",
    "manifest_json",
    "values",
]
