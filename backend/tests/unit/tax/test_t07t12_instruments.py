"""T-07-T12 (TASK-8039; SPEC-656 AC-1.3, AC-3.1): code segmentation and the citation rule.

Acceptance (the task row): "The Calloway agreement segments into Articles I to V with (a)/(b)
clauses on the right pages, an uncited trust-type edit is refused, and L3 approval locks all
seven determinations." The segmentation and the uncited refusal are tested here on a synthetic
layer with the agreement's structure; the L3 lock runs in the end pass's integration suite (it
needs a sign-off row and the outbox consumer).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

import pytest

from abacus.modules.tax.instruments import segment as seg
from abacus.modules.tax.instruments import service

type _Fake = Any  # Any: a bare context double


@dataclass(frozen=True)
class _W:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    confidence: float = 1.0


@dataclass(frozen=True)
class _P:
    page: int
    words: tuple[_W, ...]


def _line(text: str, top: float, indent: float = 72.0) -> list[_W]:
    out: list[_W] = []
    x = indent
    for word in text.split():
        out.append(_W(word, x, top, x + 6 * len(word), top + 10))
        x += 6 * len(word) + 4
    return out


# The Calloway Family Trust Agreement's structure (TXT-01): title page, Articles I to V, the
# (a)/(b) clauses of III and IV, Article III running over the page break from 3 to 4.
PAGES = (
    _P(1, tuple(_line("CALLOWAY FAMILY TRUST AGREEMENT", 100) + _line("Dated 2011", 120))),
    _P(2, tuple(
        _line("ARTICLE I — NAME", 80) + _line("This trust shall be known as the", 100, 90)
        + _line("ARTICLE II — PRINCIPAL AND INCOME", 140)
        + _line("Capital gains shall be allocated to principal.", 160, 90)
    )),
    _P(3, tuple(
        _line("ARTICLE III — DISTRIBUTIONS", 80)
        + _line("(a) The trustee may distribute the net income", 100, 90)
        + _line("to or for the beneficiaries in such shares", 120, 110)
    )),
    _P(4, tuple(
        _line("as the trustee determines.", 72, 110)
        + _line("(b) The trustee may pay principal for health,", 100, 90)
        + _line("education, maintenance and support.", 120, 110)
        + _line("ARTICLE IV — UNDISTRIBUTED INCOME", 160)
        + _line("(a) Income not distributed shall be added to principal.", 180, 90)
        + _line("(b) Principal may be invaded under the standard of III(b).", 200, 90)
        + _line("ARTICLE V — TRUSTEE", 240)
        + _line("(c) Trustee fees shall be charged to principal.", 260, 90)
    )),
)  # fmt: skip


def test_ac13_calloway_segments_into_articles_i_to_v_with_their_clauses() -> None:
    found = seg.segment(PAGES)
    by = {c.label: c for c in found.clauses}
    assert [c.label for c in found.clauses] == [
        "Art. I", "Art. II", "Art. III", "Art. III(a)", "Art. III(b)", "Art. IV", "Art. IV(a)",
        "Art. IV(b)", "Art. V", "Art. V(c)",
    ]  # fmt: skip
    assert by["Art. III"].heading == "DISTRIBUTIONS"
    assert (by["Art. III(a)"].page_from, by["Art. III(a)"].page_to) == (3, 4)  # over the break
    assert [r["page"] for r in by["Art. III(a)"].regions()] == [3, 4]
    assert by["Art. III(b)"].parent == "Art. III" and by["Art. IV(a)"].parent == "Art. IV"
    assert (by["Art. V(c)"].page_from, by["Art. II"].page_from) == (4, 2)
    assert found.status == "segmented" and found.confidence == 1
    assert len({c.text_sha256() for c in found.clauses}) == len(found.clauses)


def test_ac13_low_confidence_ocr_or_a_gap_needs_review() -> None:
    blurred = tuple(
        _P(p.page, tuple(_W(w.text, w.x0, w.top, w.x1, w.bottom, 0.5) for w in p.words))
        for p in PAGES
    )
    assert seg.segment(blurred).status == "needs_review"
    no_articles = (_P(1, tuple(_line("A letter of wishes, not an agreement.", 100))),)
    assert seg.segment(no_articles).status == "needs_review"
    assert seg.roman("IV") == 4 and seg.roman("IX") == 9


async def test_ac31_an_uncited_trust_type_edit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    async def supported(
        tenant: object, engagement: object, ids: list[uuid.UUID]
    ) -> frozenset[uuid.UUID]:
        return frozenset()

    monkeypatch.setattr(service, "supported_citations", supported)
    ctx = cast(_Fake, type("Ctx", (), {"tenant": None})())
    with pytest.raises(service.UncitedChange):
        await service._cited(ctx, uuid.uuid4(), "trust_type", [])  # pyright: ignore[reportPrivateUsage] -- the citation guard
    with pytest.raises(service.UncitedChange):  # a citation that is not verified and live
        await service._cited(ctx, uuid.uuid4(), "trust_type", [uuid.uuid4()])  # pyright: ignore[reportPrivateUsage] -- the citation guard
    await service._cited(ctx, uuid.uuid4(), "exemption", [])  # pyright: ignore[reportPrivateUsage] -- the citation guard
