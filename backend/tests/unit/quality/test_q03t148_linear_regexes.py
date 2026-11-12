"""Q-03-T148 (TASK-7805): the three regexes CodeQL flagged as polynomial (py/polynomial-redos)
are rewritten to run in linear time and to accept exactly what they accepted before.

- `assurance.governance_comms._AMOUNT` (read with `.search`): an amount in a letter section.
- `reporting.templates.has_markup`: markup, a URL or a template expression in firm wording.
- `evidence.export_download._RANGE` (read with `.fullmatch`): the one `Range` header.

Each is checked against the old pattern on generated text over the characters that matter, and on
the attack strings CodeQL named, with a time bound the old patterns miss by orders of magnitude.
"""

from __future__ import annotations

import re
import time

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.assurance import governance_comms
from abacus.modules.evidence import export_download
from abacus.modules.reporting import templates

OLD_AMOUNT = re.compile(r"\$\s?\d|\d[\d,]*\.\d{2}\b|\b\d{1,3}(,\d{3})+\b")
OLD_MARKUP = re.compile(
    r"<\s*/?\s*[a-z!?][^>]*>|<%|\{\{|\{%|\$\{|\b(?:https?|ftp|file|data|javascript|mailto):"
    r"|\bwww\.",
    re.IGNORECASE,
)
OLD_RANGE = re.compile(r"\s*bytes\s*=\s*(\d{0,19})\s*-\s*(\d{0,19})\s*")

AMOUNT_TEXT = st.text(alphabet="0123456789,.$ a", max_size=40)
MARKUP_TEXT = st.text(alphabet="<>/! ?aZ%{}$:w.htp", max_size=40)


@st.composite
def _range_headers(draw: st.DrawFn) -> str:
    lead = draw(st.sampled_from(["", " ", "  "]))
    around = draw(st.sampled_from(["", " "]))
    after = draw(st.sampled_from(["", " "]))
    first = draw(st.text(alphabet="0123456789 ", max_size=22))
    last = draw(st.text(alphabet="0123456789 ", max_size=22))
    return f"{lead}bytes{around}={after}{first}-{last}"


RANGE_TEXT = st.one_of(st.text(alphabet="bytes=-0123456789 \t", max_size=40), _range_headers())
LONG = 200_000
BOUND = 1.0  # seconds; the old patterns take minutes at this length


def _quick(fn: object, text: str) -> None:
    started = time.perf_counter()
    fn(text)  # type: ignore[operator]
    assert time.perf_counter() - started < BOUND


@settings(max_examples=3000, deadline=None)
@given(AMOUNT_TEXT)
def test_the_amount_check_finds_what_it_found(text: str) -> None:
    found = governance_comms._AMOUNT.search(text) is not None  # pyright: ignore[reportPrivateUsage]
    assert found == (OLD_AMOUNT.search(text) is not None)


@settings(max_examples=3000, deadline=None)
@given(MARKUP_TEXT)
def test_the_markup_check_finds_what_it_found(text: str) -> None:
    assert templates.has_markup(text) == (OLD_MARKUP.search(text) is not None)


@settings(max_examples=3000, deadline=None)
@given(RANGE_TEXT)
def test_the_range_header_matches_what_it_matched(text: str) -> None:
    new = export_download._RANGE.fullmatch(text)  # pyright: ignore[reportPrivateUsage]
    old = OLD_RANGE.fullmatch(text)
    assert (new is None) == (old is None)
    if new is not None and old is not None:
        assert new.groups() == old.groups()


def test_the_examples_still_read_as_before() -> None:
    amount = governance_comms._AMOUNT  # pyright: ignore[reportPrivateUsage]
    for text in ("$5", "1,234", "x 12.50 y", "1,2.00", ",5.00", "1,234,567"):
        assert amount.search(text), text
    for text in ("2027", "1.5", "12,34", "no figures"):
        assert not amount.search(text), text
    assert templates.has_markup("<b>bold</b>") and templates.has_markup("< / p >")
    assert templates.has_markup("see www.example") and templates.has_markup("{{ x }}")
    assert not templates.has_markup("2 < 3 > 1") and not templates.has_markup("<<")
    assert export_download.parse_range("bytes=0-99", 1000) is not None


def test_codeqls_attack_strings_run_in_linear_time() -> None:
    _quick(governance_comms._AMOUNT.search, "0" * LONG)  # pyright: ignore[reportPrivateUsage]
    _quick(governance_comms._AMOUNT.search, "1," * LONG)  # pyright: ignore[reportPrivateUsage]
    _quick(templates.has_markup, "<" + " " * LONG)
    _quick(templates.has_markup, "<!" * LONG)
    _quick(export_download._RANGE.fullmatch, "bytes=" + " " * LONG + "x")  # pyright: ignore[reportPrivateUsage]
