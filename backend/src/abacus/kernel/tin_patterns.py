"""Unmasked taxpayer IDs in free text: the SSN, ITIN and EIN validity rules (ADR-167 §2;
Q-02-T32; DEC-295).

The AI gateway refuses a model context holding one (`pii_in_context`); the log, Sentry and metric
scrubbers mask one wherever a string reaches them. Both read these rules, which is why they live
in the kernel (the kernel cannot import the gateway, ADR-101).

A form is nine digits that are not part of a longer digit run (anything that is not a digit is a
boundary: a letter, a comma, a dot, an escape), written bare, as `ddd-dd-dddd`, `dd-ddddddd` or
`ddd ddd ddd`. A separator is a hyphen or dash, a dot, a slash or a space, may differ between
groups and may have spaces around it. A form counts only when it passes its type's rules:
- SSN: the area is not 000, 666 or 900-999; the group is not 00; the serial is not 0000.
- ITIN: the first digit is 9 and the fourth and fifth are 50-65, 70-88, 90-92 or 94-99.
- EIN: the two-digit prefix is one the IRS assigns.
`ddd-dd-dddd` is read as an SSN or ITIN, `dd-ddddddd` as an EIN, a bare or `ddd ddd ddd` run as
any of the three, and so are nine digits broken three or more times by single spaces, tabs or
hyphens (`1 2 3 4 5 6 7 8 9`, a comb-box form; P-03-T15 review N2). Masked forms (fewer than
nine digits shown, or the last-four form `mask()` produces) never match. Before matching, text
is NFKC-normalised, zero-width characters and soft hyphens are removed, and every script's
decimal digits are read as ASCII digits. UUIDs and hex runs of 32 or more characters are
identifiers, never TINs, and are skipped.

False positives are accepted (failing closed is the point of a backstop): a nine-digit amount or
number that passes the rules is treated as a TIN. Known limits (DEC-295): a TIN split across lines
or context parts, or encoded (base64, spelled out), is not seen; P-03's masked material is the
main control for those.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Literal

from abacus.kernel.classification import mask

TinType = Literal["ssn", "itin", "ein"]

_UNASSIGNED_EIN_PREFIXES: Final = frozenset(
    {0, 7, 8, 9, 17, 18, 19, 28, 29, 49, 69, 70, 78, 79, 89, 96, 97}
)
_ITIN_GROUPS: Final = frozenset([*range(50, 66), *range(70, 89), *range(90, 93), *range(94, 100)])
_D: Final = "[0-9]"
# A hyphen or dash, the minus sign, a dot or a slash, with up to two spaces around it; or spaces.
_SEP: Final = r"(?:[ \t]{0,2}[\-\u2010-\u2015\u2212./][ \t]{0,2}|[ \t]{1,2})"
_NOT_AFTER_DIGIT: Final = r"(?<![0-9])"
_NOT_BEFORE_DIGIT: Final = r"(?![0-9])"
_SSN_FORM: Final = re.compile(
    rf"{_NOT_AFTER_DIGIT}(?P<a>{_D}{{3}})(?P<s1>{_SEP})?(?P<g>{_D}{{2}})(?P<s2>{_SEP})?"
    rf"(?P<s>{_D}{{4}}){_NOT_BEFORE_DIGIT}"
)
_EIN_FORM: Final = re.compile(
    rf"{_NOT_AFTER_DIGIT}(?P<p>{_D}{{2}}){_SEP}(?P<s>{_D}{{7}}){_NOT_BEFORE_DIGIT}"
)
_THREES_FORM: Final = re.compile(
    rf"{_NOT_AFTER_DIGIT}(?P<x>{_D}{{3}}){_SEP}(?P<y>{_D}{{3}}){_SEP}(?P<z>{_D}{{3}})"
    rf"{_NOT_BEFORE_DIGIT}"
)
# P-03-T15 review N2: nine digits with at most one space, tab or hyphen between any two and at
# least three such breaks (a W-9's comb boxes read as `1 2 3 4 5 6 7 8 9`), read as any type.
_SPACED_FORM: Final = re.compile(
    rf"{_NOT_AFTER_DIGIT}{_D}(?:[ \t\-]?{_D}){{8}}{_NOT_BEFORE_DIGIT}"
)
_HEX: Final = "[0-9a-fA-F]"
_OPAQUE: Final = re.compile(
    rf"(?<![0-9a-fA-F])(?:{_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{12}}|{_HEX}{{32,}})"
    rf"(?![0-9a-fA-F])"
)
_INVISIBLE: Final = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))


def valid_ssn(digits: str) -> bool:
    if len(digits) != 9 or not digits.isascii() or not digits.isdigit():
        return False
    area, group, serial = digits[:3], digits[3:5], digits[5:]
    return (
        area not in ("000", "666")
        and not area.startswith("9")
        and group != "00"
        and serial != "0000"
    )


def valid_itin(digits: str) -> bool:
    if len(digits) != 9 or not digits.isascii() or not digits.isdigit():
        return False
    return digits[0] == "9" and int(digits[3:5]) in _ITIN_GROUPS


def valid_ein(digits: str) -> bool:
    if len(digits) != 9 or not digits.isascii() or not digits.isdigit():
        return False
    return int(digits[:2]) not in _UNASSIGNED_EIN_PREFIXES


@dataclass(frozen=True)
class TinMatch:
    """One unmasked TIN form in normalised text. `digits` is Restricted: never log it."""

    type: TinType
    digits: str
    start: int
    end: int


def _ascii_digit(ch: str) -> str:
    value = unicodedata.decimal(ch, None)
    return str(value) if value is not None else ch


def normalised(text: str) -> str:
    """NFKC, without zero-width characters or soft hyphens, with every decimal digit in ASCII."""
    if text.isascii():
        return text
    clean = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    if clean.isascii():
        return clean
    return "".join(ch if ch.isascii() else _ascii_digit(ch) for ch in clean)


def _any_type(digits: str) -> TinType | None:
    if valid_ssn(digits):
        return "ssn"
    if valid_itin(digits):
        return "itin"
    return "ein" if valid_ein(digits) else None


def _find(text: str) -> list[TinMatch]:
    # UUIDs and long hex runs are blanked to letters of the same length, so offsets hold.
    probe = _OPAQUE.sub(lambda m: "x" * len(m.group()), text)
    found: list[TinMatch] = []
    for m in _SSN_FORM.finditer(probe):
        digits = m.group("a") + m.group("g") + m.group("s")
        if m.group("s1") is None and m.group("s2") is None:
            kind = _any_type(digits)
        else:
            kind = "ssn" if valid_ssn(digits) else ("itin" if valid_itin(digits) else None)
        if kind is not None:
            found.append(TinMatch(kind, digits, m.start(), m.end()))
    for m in _EIN_FORM.finditer(probe):
        digits = m.group("p") + m.group("s")
        if valid_ein(digits):
            found.append(TinMatch("ein", digits, m.start(), m.end()))
    for m in _THREES_FORM.finditer(probe):
        digits = m.group("x") + m.group("y") + m.group("z")
        kind = _any_type(digits)
        if kind is not None:
            found.append(TinMatch(kind, digits, m.start(), m.end()))
    for m in _SPACED_FORM.finditer(probe):
        if sum(not c.isdigit() for c in m.group()) < 3:
            continue  # a bare, SSN, EIN or three-group shape: the forms above read it by its rules
        digits = "".join(c for c in m.group() if c.isdigit())
        kind = _any_type(digits)
        if kind is not None:
            found.append(TinMatch(kind, digits, m.start(), m.end()))
    kept: list[TinMatch] = []
    for match in sorted(found, key=lambda f: (f.start, -f.end)):
        if not kept or match.start >= kept[-1].end:
            kept.append(match)
    return kept


def find_tins(text: str) -> list[TinMatch]:
    """Every unmasked TIN form in `text` (positions are in its NFKC normalisation)."""
    return _find(normalised(text))


def has_tin(text: str) -> bool:
    return bool(find_tins(text))


def scrub_tins(text: str) -> str:
    """`text` with each unmasked TIN form replaced by its mask; unchanged when there is none."""
    clean = normalised(text)
    matches = _find(clean)
    if not matches:
        return text
    out: list[str] = []
    at = 0
    for match in matches:
        if match.start < at:
            continue
        out.append(clean[at : match.start])
        out.append(mask(match.digits, "tin"))
        at = match.end
    out.append(clean[at:])
    return "".join(out)


__all__ = [
    "TinMatch",
    "TinType",
    "find_tins",
    "has_tin",
    "normalised",
    "scrub_tins",
    "valid_ein",
    "valid_itin",
    "valid_ssn",
]
