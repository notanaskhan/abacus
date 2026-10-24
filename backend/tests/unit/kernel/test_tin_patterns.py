"""Q-02 AC-22's validity rules (Q-02-T32; ADR-167 §2): which nine-digit forms count as a TIN.

A match counts only when it passes its number type's validity rules (SSN: area, group and serial;
ITIN: the leading 9 and the middle-digit ranges; EIN: the assigned prefixes). Masked forms never
count. No literal in this file is an issued-looking SSN or EIN: valid numbers are generated at
run time from the rules, and fixed examples use the 9xx area or invalid prefixes (ADR-085).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from abacus.kernel.classification import mask
from abacus.kernel.tin_patterns import (
    find_tins,
    scrub_tins,
    valid_ein,
    valid_itin,
    valid_ssn,
)

_INVALID_EIN_PREFIXES = {0, 7, 8, 9, 17, 18, 19, 28, 29, 49, 69, 70, 78, 79, 89, 96, 97}
_ITIN_GROUPS = [*range(50, 66), *range(70, 89), *range(90, 93), *range(94, 100)]

# --- generators: valid numbers built from the rules at run time ---------------------------------


def _ssn(area: int, group: int, serial: int) -> str:
    return f"{area:03d}{group:02d}{serial:04d}"


def _itin(area: int, group: int, serial: int) -> str:
    return f"9{area:02d}{group:02d}{serial:04d}"


def _ein(prefix: int, serial: int) -> str:
    return f"{prefix:02d}{serial:07d}"


ssns = st.builds(
    _ssn,
    st.integers(1, 899).filter(lambda a: a != 666),
    st.integers(1, 99),
    st.integers(1, 9999),
)
itins = st.builds(
    _itin,
    st.integers(0, 99),
    st.sampled_from(_ITIN_GROUPS),
    st.integers(0, 9999),
)
eins = st.builds(
    _ein,
    st.integers(0, 99).filter(lambda p: p not in _INVALID_EIN_PREFIXES),
    st.integers(0, 9_999_999),
)


def _ssn_form(digits: str, sep: str) -> str:
    return f"{digits[:3]}{sep}{digits[3:5]}{sep}{digits[5:]}"


def _ein_form(digits: str) -> str:
    return f"{digits[:2]}-{digits[2:]}"


# --- the rules -----------------------------------------------------------------------------------


@given(ssns)
def test_ac22_generated_ssns_pass_the_ssn_rules(digits: str) -> None:
    assert valid_ssn(digits)


def test_ac22_the_ssn_rules_refuse_unissued_areas_groups_and_serials() -> None:
    assert not valid_ssn("000123456")  # area 000
    assert not valid_ssn("666123456")  # area 666
    assert not valid_ssn("900123456")  # area 9xx is never an SSN
    assert not valid_ssn("123004567")  # group 00
    assert not valid_ssn("123450000")  # serial 0000
    assert not valid_ssn("12345678")  # eight digits


@given(itins)
def test_ac22_generated_itins_pass_the_itin_rules(digits: str) -> None:
    assert valid_itin(digits)
    assert not valid_ssn(digits)


def test_ac22_the_itin_rules_need_a_leading_9_and_an_assigned_middle_pair() -> None:
    assert valid_itin("900701234")
    for group in ("00", "12", "45", "49", "66", "69", "89", "93"):
        assert not valid_itin(f"900{group}1234"), group
    assert not valid_itin("800701234")


@given(eins)
def test_ac22_generated_eins_pass_the_ein_rules(digits: str) -> None:
    assert valid_ein(digits)


def test_ac22_the_ein_rules_refuse_unassigned_prefixes() -> None:
    for prefix in sorted(_INVALID_EIN_PREFIXES):
        assert not valid_ein(f"{prefix:02d}1234567"), prefix


# --- finding them in text ------------------------------------------------------------------------


@given(ssns, st.sampled_from(["", "-", " "]), st.text(max_size=20), st.text(max_size=20))
def test_ac22_an_ssn_is_found_bare_dashed_or_spaced_inside_any_text(
    digits: str, sep: str, before: str, after: str
) -> None:
    text = f"{before} {_ssn_form(digits, sep)} {after}"
    assert any(m.digits == digits for m in find_tins(text))


@given(itins)
def test_ac22_an_itin_is_found(digits: str) -> None:
    [found] = find_tins(f'{{"taxpayer": "{_ssn_form(digits, "-")}"}}')
    assert found.digits == digits


@given(eins)
def test_ac22_an_ein_is_found_dashed_or_bare(digits: str) -> None:
    assert [m.digits for m in find_tins(f"EIN {_ein_form(digits)}.")] == [digits]
    assert [m.digits for m in find_tins(f"EIN {digits}")] == [digits]


def test_ac22_fullwidth_digits_are_read_as_digits() -> None:
    fullwidth = "".join(chr(0xFF10 + int(d)) for d in "900701234")
    assert [m.digits for m in find_tins(f"x {fullwidth} y")] == ["900701234"]


@given(st.one_of(ssns, itins))
def test_ac22_masked_forms_pass(digits: str) -> None:
    for masked in (
        mask(digits, "tin"),
        f"XX-XXX{digits[-4:]}",
        f"***-**-{digits[-4:]}",
        f"tin_last4={digits[-4:]}",
        digits[:8],
    ):
        assert find_tins(masked) == [], masked


def test_ac22_invalid_numbers_and_other_digit_runs_pass() -> None:
    for text in (
        "900-45-6789",  # 9xx area, ITIN middle 45: neither an SSN nor an ITIN
        "07-1234567",  # an unassigned EIN prefix
        "1234567890",  # ten digits
        "amount 123456789.25",  # a decimal amount, not an identifier
        "x123456789",  # part of a longer token
        "3f2a9c1e-1d2b-4e5f-8a9b-123456789abc",  # a UUID
        "2026-10-24T10:11:12.123456789Z",  # nanoseconds
    ):
        assert find_tins(text) == [], text


@given(st.lists(st.one_of(ssns, itins), min_size=1, max_size=3), st.text(max_size=30))
def test_ac22_scrub_tins_leaves_no_unmasked_tin(numbers: list[str], filler: str) -> None:
    text = f" {filler} ".join(_ssn_form(n, "-") for n in numbers)
    scrubbed = scrub_tins(text)
    assert find_tins(scrubbed) == []
    for n in numbers:
        assert _ssn_form(n, "-") not in scrubbed
        assert mask(n, "tin") in scrubbed


def test_ac22_scrub_tins_leaves_other_text_alone() -> None:
    assert scrub_tins("no identifiers here: 123-45, 2026") == "no identifiers here: 123-45, 2026"
