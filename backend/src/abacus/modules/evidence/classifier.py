"""Rule classification of a received document (N-01-T17; N-01 §3.4; DEC-1177). Pure.

Form family, form code, kind and tax year from the file name and the first pages' text layer,
by the rules in `classifier_rules.yaml` (a repo parameter file, versioned). Code classifies first;
the matcher (N-01-T22) only proposes on top. Nothing here reads a database or logs text: the
caller passes the file name, the page texts and the detected TIN last fours, and stores the
result in `document_classifications`.

Confidence is per field, 0 to 1: a value both the name and the text agree on is surer than one
from the text alone, which is surer than one from the name alone. Conflicting years take the
text's, at low confidence. The overall confidence is the lowest of the family's and the year's
(an unknown year counts only for a tax form).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Final, cast

import yaml

_BOTH: Final = 0.95
_TEXT: Final = 0.85
_NAME: Final = 0.7
_CONFLICT: Final = 0.5
_TEXT_PAGES: Final = 2  # the cues sit on the first page or two
_TEXT_CHARS: Final = 20_000
_NAME_YEAR = re.compile(r"\b((?:19|20)\d\d)\b")
_SEPARATORS = re.compile(r"[\s_.\-]+")


@dataclass(frozen=True)
class _Family:
    family: str
    code: str | None
    kind: str
    corrected: bool
    names: tuple[re.Pattern[str], ...]
    texts: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Rules:
    version: str
    families: tuple[_Family, ...]
    year_texts: tuple[re.Pattern[str], ...]
    corrected_names: tuple[re.Pattern[str], ...]
    low_confidence_below: float


@dataclass(frozen=True)
class Classification:
    """What the rules say a document is; `confidences` per field and `overall`."""

    form_family: str
    form_code: str | None
    kind: str
    tax_year: int | None
    corrected: bool | None
    page_count: int
    taxpayer_tin_last4: str | None
    confidences: dict[str, float]
    rules_version: str

    @property
    def overall(self) -> float:
        return self.confidences["overall"]


def _patterns(raw: object) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(str(p), re.IGNORECASE) for p in cast(list[object], raw or []))


@cache
def rules() -> Rules:
    """The parameter file, read once."""
    text = resources.files("abacus.modules.evidence").joinpath("classifier_rules.yaml")
    body = cast(dict[str, object], yaml.safe_load(text.read_text(encoding="utf-8")))
    families = tuple(
        _Family(
            family=str(f["family"]),
            code=None if f.get("code") is None else str(f["code"]),
            kind=str(f["kind"]),
            corrected=bool(f.get("corrected", False)),
            names=_patterns(f.get("names")),
            texts=_patterns(f.get("texts")),
        )
        for f in cast(list[dict[str, object]], body["families"])
    )
    return Rules(
        version=str(body["version"]),
        families=families,
        year_texts=_patterns(body.get("year_texts")),
        corrected_names=_patterns(body.get("corrected_names")),
        low_confidence_below=float(cast(float, body["low_confidence_below"])),
    )


def normalised_name(file_name: str) -> str:
    """The file name for matching: lower case, the extension dropped, separators one space."""
    stem = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    return _SEPARATORS.sub(" ", stem.lower()).strip()


def _family_of(
    name: str, text: str, families: tuple[_Family, ...]
) -> tuple[_Family | None, float, str]:
    """The first family the name or text matches, its confidence and the name without the
    matched form number (so "CP2000" is never read as a year)."""
    by_name = next((f for f in families if any(p.search(name) for p in f.names)), None)
    by_text = next((f for f in families if any(p.search(text) for p in f.texts)), None)
    stripped = name
    if by_name is not None:
        for p in by_name.names:
            stripped = p.sub(" ", stripped)
    if by_name is not None and by_text is not None:
        if by_name.family == by_text.family:
            # One family: the text's code, unless only the name says corrected (W-2c).
            chosen = by_name if by_name.corrected and not by_text.corrected else by_text
            return chosen, _BOTH, stripped
        return by_text, _CONFLICT, stripped
    if by_text is not None:
        return by_text, _TEXT, stripped
    if by_name is not None:
        return by_name, _NAME, stripped
    return None, 0.0, stripped


def _year_of(stripped_name: str, text: str, given: Rules) -> tuple[int | None, float]:
    named = {int(y) for y in _NAME_YEAR.findall(stripped_name)}
    from_name = next(iter(named)) if len(named) == 1 else None
    from_text: int | None = None
    for pattern in given.year_texts:
        found = pattern.search(text)
        if found is not None:
            from_text = int(found.group(1))
            break
    if from_name is not None and from_text is not None:
        return (from_text, _BOTH) if from_name == from_text else (from_text, _CONFLICT)
    if from_text is not None:
        return from_text, _TEXT
    if from_name is not None:
        return from_name, _NAME
    return None, 0.0


def classify(
    file_name: str,
    page_texts: list[str],
    *,
    page_count: int,
    tin_last4s: list[str] | None = None,
    given: Rules | None = None,
) -> Classification:
    """The rules' classification. `page_texts` in page order (empty for a scan or a non-PDF);
    `tin_last4s` the detected taxpayer TIN last fours in page order (SSN or ITIN first)."""
    use = given or rules()
    name = normalised_name(file_name)
    text = " ".join(page_texts[:_TEXT_PAGES])[:_TEXT_CHARS].lower()
    family, family_confidence, stripped = _family_of(name, text, use.families)
    year, year_confidence = _year_of(stripped, text, use)
    by_family = family is not None and family.corrected
    by_name = any(p.search(name) for p in use.corrected_names)
    corrected: bool | None = True if by_family or by_name else None
    kind = family.kind if family is not None else "other"
    counted = [family_confidence]
    if kind == "tax_form":
        counted.append(year_confidence)
    return Classification(
        form_family=family.family if family is not None else "Other",
        form_code=family.code if family is not None else None,
        kind=kind,
        tax_year=year,
        corrected=corrected,
        page_count=page_count,
        taxpayer_tin_last4=(tin_last4s or [None])[0],
        confidences={
            "form_family": family_confidence,
            "tax_year": year_confidence,
            "overall": min(counted),
        },
        rules_version=use.version,
    )
