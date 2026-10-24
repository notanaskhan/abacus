"""P-03-T08 (SPEC-322 AC-12; C4 §3.2; DEC-265): re-reading a quote from the word layer by its
stored box and hash, the masked projection, the computed state and the host reference."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from abacus.modules.evidence.citations.display import host_of, state_of
from abacus.modules.evidence.citations.matching import (
    layer_sha256,
    quote_span,
    reread_span,
    union,
    verify_on_layer,
)
from abacus.modules.evidence.masking import MaskRegion, mask_token, masked_text, masked_words
from abacus.modules.evidence.models import CitationEvent
from abacus.modules.evidence.words import Word

# Two lines; the quote "investments 16,500,000.00 Net" runs across both.
WORDS = (
    Word("Total", 72.0, 84.0, 94.0, 94.0),
    Word("investments", 97.0, 84.0, 150.0, 94.0),
    Word("16,500,000.00", 153.0, 84.0, 217.0, 94.0),
    Word("Net", 72.0, 100.0, 90.0, 110.0),
    Word("assets", 93.0, 100.0, 120.0, 110.0),
)
TEXT = " ".join(w.text for w in WORDS)


def _stored(quote: str) -> tuple[tuple[float, float, float, float], bytes]:
    found = verify_on_layer(WORDS, TEXT, box=None, quote=quote, value=None)
    assert found.box is not None and found.sha256 is not None
    return found.box, found.sha256


def test_the_verified_run_re_reads_from_its_box_and_hash() -> None:
    box, digest = _stored("investments 16,500,000.00")
    assert [w.text for w in reread_span(WORDS, box, digest) or []] == [
        "investments",
        "16,500,000.00",
    ]


def test_a_two_line_quote_re_reads_though_its_box_holds_other_words() -> None:
    box, digest = _stored("16,500,000.00 Net")
    # The union of a two-line run covers "Total" and "investments" too; only the run hashes.
    assert box == (72.0, 84.0, 217.0, 110.0)
    run = reread_span(WORDS, box, digest)
    assert run is not None and [w.text for w in run] == ["16,500,000.00", "Net"]
    assert union(run) == box


def test_a_digest_no_run_has_is_none() -> None:
    box, _ = _stored("investments 16,500,000.00")
    assert reread_span(WORDS, box, b"\x00" * 32) is None
    assert reread_span(WORDS, (400.0, 400.0, 500.0, 500.0), layer_sha256(WORDS[:1])) is None


def test_masked_words_become_one_token_per_region() -> None:
    words = (
        Word("SSN", 72.0, 84.0, 90.0, 94.0),
        Word("000-00-6081", 93.0, 84.0, 150.0, 94.0),
        Word("EIN", 72.0, 100.0, 90.0, 110.0),
        Word("12-", 93.0, 100.0, 110.0, 110.0),
        Word("3450287", 111.0, 100.0, 150.0, 110.0),
    )
    regions = [
        MaskRegion(1, (92.0, 83.0, 151.0, 95.0), "ssn", "6081"),
        MaskRegion(1, (92.0, 99.0, 151.0, 111.0), "ein", "0287"),
        MaskRegion(2, (0.0, 0.0, 600.0, 800.0), "dob", None),  # another page: not applied
    ]
    assert masked_text(words, regions, 1) == "SSN •••-••-6081 EIN ••-•••0287"
    masked = masked_words(words, regions, 1)
    assert [w.masked for w in masked] == [False, True, False, True]
    assert (masked[3].x0, masked[3].x1) == (93.0, 150.0)  # the token spans both words


def test_mask_tokens_follow_p03_4_4() -> None:
    assert mask_token("ssn", "6081") == "•••-••-6081"
    assert mask_token("itin", "1234") == "•••-••-1234"
    assert mask_token("ein", "0287") == "••-•••0287"
    assert mask_token("bank_account", "1234") == "••••1234"
    assert mask_token("routing_number", "0021") == "••••0021"
    assert mask_token("dob", "1990") == "••/••/••••"
    assert mask_token("ssn", None) == "••••"


def _event(kind: str, minutes: int) -> CitationEvent:
    return CitationEvent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        citation_id=uuid.uuid4(),
        kind=kind,
        cause_ref="evidence_version:next",
        successor_citation_id=None,
        actor_kind="system",
        actor_user_id=None,
        at=datetime(2026, 9, 14, tzinfo=UTC) + timedelta(minutes=minutes),
    )


def test_state_is_the_latest_moved_or_broken_unless_relinked() -> None:
    assert state_of([]) == ("valid", None)
    moved = _event("moved", 1)
    assert state_of([moved]) == ("moved", moved)
    assert state_of([moved, _event("broken", 2)])[0] == "broken"
    assert state_of([moved, _event("relinked", 3)]) == ("relinked", None)


def test_host_ref_is_an_anchor_type_and_id() -> None:
    host = uuid.uuid4()
    assert host_of(f"workpaper_cell:{host}") == ("workpaper_cell", host)
    assert host_of("workpaper_cell") is None
    assert host_of("workpaper_cell:not-an-id") is None
    assert quote_span(WORDS, "Total") is not None  # the fixture words are the verifier's


def test_search_finds_every_whole_word_run_with_one_rect_per_line() -> None:
    from abacus.modules.evidence.citations.matching import line_rects, quote_spans

    words = (
        *WORDS,
        Word("Total", 72.0, 120.0, 94.0, 130.0),
        Word("investments", 97.0, 120.0, 150.0, 130.0),
    )
    runs = quote_spans(words, "total investments", limit=10)
    assert [[w.text for w in r] for r in runs] == [["Total", "investments"]] * 2
    assert quote_spans(words, "investment", limit=10) == []
    assert len(quote_spans(words, "total", limit=1)) == 1
    across = quote_spans(WORDS, "16,500,000.00 Net", limit=10)
    assert line_rects(across[0]) == [(153.0, 84.0, 217.0, 94.0), (72.0, 100.0, 90.0, 110.0)]
