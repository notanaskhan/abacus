"""Designed workpapers' Open-in-Excel layouts (A-05-T09; ADR-160 clause 13; SPEC-641; DEC-1954).

A designed workpaper (EBP-01 to EBP-09; A-04's planning papers stay list-shaped) registers its
layout: the sheets in order, each sheet's title as Excel shows it, and its cell-address anchors.
Its export writes every cell at its own address on its sheet, so an anchor such as `EBP-04!C14`
or `'EBP-04 Participant data'!F12:F15` names exactly the cells a person sees in Excel, and the
same address is the cell's key in the field history and the citation locator.

Addresses: `Sheet!A1` or `'Sheet name'!A1` (quoted when the title has a space), and a rectangular
range `A1:B3`; columns A to ZZ, rows 1 to 9999. Parsing is code's own (never a spreadsheet's).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

_ADDRESS: Final = re.compile(
    r"^(?:'(?P<quoted>[^'\[\]:*?/\\]{1,31})'|(?P<plain>[A-Za-z0-9_-]{1,31}))!"
    r"(?P<start>[A-Z]{1,2}[1-9][0-9]{0,3})(?::(?P<end>[A-Z]{1,2}[1-9][0-9]{0,3}))?$"
)
_CELL: Final = re.compile(r"^(?P<col>[A-Z]{1,2})(?P<row>[1-9][0-9]{0,3})$")


class AddressInvalid(ValueError):
    """Not a designed-workpaper cell address."""


@dataclass(frozen=True)
class SheetLayout:
    sheet_key: str  # the cell store's key (`main` for the paper's first sheet)
    title: str  # the sheet's name in the export ("EBP-04", "EBP-04 Participant data")


@dataclass(frozen=True)
class DesignedLayout:
    kind: str
    code: str
    sheets: tuple[SheetLayout, ...]
    anchors: Mapping[str, str]  # an anchor's name -> its address

    def sheet_of_title(self, title: str) -> SheetLayout | None:
        return next((s for s in self.sheets if s.title == title), None)


_LAYOUTS: dict[str, DesignedLayout] = {}


def _column(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def _letters(n: int) -> str:
    out = ""
    while n:
        n, rest = divmod(n - 1, 26)
        out = chr(65 + rest) + out
    return out


def parse(address: str) -> tuple[str, tuple[str, ...]]:
    """`(sheet title, cell keys in row-major order)` for an address; a range is expanded."""
    found = _ADDRESS.fullmatch(address)
    if found is None:
        raise AddressInvalid(address)
    title = found["quoted"] or found["plain"]
    start = _CELL.fullmatch(found["start"])
    end = _CELL.fullmatch(found["end"] or found["start"])
    if start is None or end is None:
        raise AddressInvalid(address)
    c1, c2 = _column(start["col"]), _column(end["col"])
    r1, r2 = int(start["row"]), int(end["row"])
    if c2 < c1 or r2 < r1 or (c2 - c1 + 1) * (r2 - r1 + 1) > 400:
        raise AddressInvalid(address)
    return title, tuple(f"{_letters(c)}{r}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1))


def resolve(layout: DesignedLayout, address: str) -> tuple[tuple[str, str], ...]:
    """The `(sheet_key, cell_key)` pairs an address names on this layout."""
    title, cells = parse(address)
    sheet = layout.sheet_of_title(title)
    if sheet is None:
        raise AddressInvalid(address)
    return tuple((sheet.sheet_key, c) for c in cells)


def register_designed_layout(layout: DesignedLayout) -> None:
    """`workpapers.api.register_designed_layout`: one per kind; every anchor resolves on it and
    no two sheets share a title or a key."""
    titles = [s.title for s in layout.sheets]
    keys = [s.sheet_key for s in layout.sheets]
    if not layout.sheets or len(set(titles)) != len(titles) or len(set(keys)) != len(keys):
        raise ValueError(f"designed layout {layout.kind!r}: sheets must be unique")
    for name, address in layout.anchors.items():
        try:
            resolve(layout, address)
        except AddressInvalid:
            raise ValueError(f"designed layout {layout.kind!r}: anchor {name!r}") from None
    known = _LAYOUTS.get(layout.kind)
    if known is not None and known != layout:
        raise ValueError(f"designed layout {layout.kind!r} is already registered")
    _LAYOUTS[layout.kind] = layout


def designed_layout(kind: str | None) -> DesignedLayout | None:
    return None if kind is None else _LAYOUTS.get(kind)


def is_cell_key(key: str) -> bool:
    return _CELL.fullmatch(key) is not None
