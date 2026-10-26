"""P-03-T15 review N2: the kernel's TIN backstop reads a TIN drawn one digit per box (a W-9's
comb) or broken by single spaces or hyphens three or more times, by the same validity rules; the
shaped forms keep their own rules (a dashed SSN form that fails them is still no EIN)."""

from __future__ import annotations

import pytest

from abacus.kernel.tin_patterns import find_tins, scrub_tins


@pytest.mark.parametrize(
    "text",
    ["9 0 0 7 0 1 2 3 4", "SSN 9 0 0 7 0 1 2 3 4 on file", "9-0-0-7-0-1-2-3-4", "900 7 0 12 34"],
)
def test_n2_a_comb_or_broken_tin_is_found_and_scrubbed(text: str) -> None:
    assert [m.type for m in find_tins(text)] == ["itin"]
    scrubbed = scrub_tins(text)
    assert find_tins(scrubbed) == [] and "1234" in scrubbed


@pytest.mark.parametrize(
    "text",
    ["0 0 0 0 0 0 0 0 0", "1 2 3 4 5 6 7 8", "555 123 4567", "900-45-6789", "2026 10 26 12 00"],
)
def test_n2_invalid_or_short_runs_are_left_alone(text: str) -> None:
    assert find_tins(text) == []
