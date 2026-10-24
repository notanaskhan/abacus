"""Unmasked taxpayer IDs in free text: the SSN, ITIN and EIN validity rules (ADR-167 §2;
Q-02-T32; DEC-295).

The AI gateway refuses a model context holding one (`pii_in_context`); the log, Sentry and metric
scrubbers mask one wherever a string reaches them. Both read these rules, which is why they live
in the kernel (the kernel cannot import the gateway, ADR-101).

A form counts only when it is nine digits, as `ddd-dd-dddd` (one separator, used twice, or none)
or `dd-ddddddd`, standing alone (no letter or digit touching it, and not part of a decimal
amount), and passes its type's rules:
- SSN: the area is not 000, 666 or 900-999; the group is not 00; the serial is not 0000.
- ITIN: the first digit is 9 and the fourth and fifth are 50-65, 70-88, 90-92 or 94-99.
- EIN: the two-digit prefix is one the IRS assigns.
A bare nine-digit run counts when any of the three passes. Masked forms (fewer than nine digits
shown, or the last-four form `mask()` produces) never match. Text is NFKC-normalised first, so
full-width digits are digits. False positives are accepted: a nine-digit number that passes the
rules is treated as a TIN (failing closed is the point of a backstop).
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
# Hyphen, the Unicode hyphens and dashes, the minus sign and a space.
_SEP: Final = r"[\- \u00a0\u2010-\u2015\u2212]"
_BEFORE: Final = r"(?<![0-9A-Za-z])(?<![0-9][.,])"
_AFTER: Final = r"(?![0-9A-Za-z])(?![.,][0-9])"
_SSN_FORM: Final = re.compile(
    rf"{_BEFORE}(?P<a>[0-9]{{3}})(?P<sep>{_SEP}?)(?P<g>[0-9]{{2}})(?P=sep)(?P<s>[0-9]{{4}}){_AFTER}"
)
_EIN_FORM: Final = re.compile(rf"{_BEFORE}(?P<p>[0-9]{{2}}){_SEP}(?P<s>[0-9]{{7}}){_AFTER}")


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


def normalised(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _find(text: str) -> list[TinMatch]:
    found: list[TinMatch] = []
    for m in _SSN_FORM.finditer(text):
        digits = m.group("a") + m.group("g") + m.group("s")
        bare = m.group("sep") == ""
        if valid_ssn(digits):
            found.append(TinMatch("ssn", digits, m.start(), m.end()))
        elif valid_itin(digits):
            found.append(TinMatch("itin", digits, m.start(), m.end()))
        elif bare and valid_ein(digits):
            found.append(TinMatch("ein", digits, m.start(), m.end()))
    for m in _EIN_FORM.finditer(text):
        digits = m.group("p") + m.group("s")
        if valid_ein(digits):
            found.append(TinMatch("ein", digits, m.start(), m.end()))
    return sorted(found, key=lambda match: match.start)


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
