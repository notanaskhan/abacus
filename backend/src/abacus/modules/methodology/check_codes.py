"""Review-checklist check codes (T-08-T13; TASK-8837; T-08 §3; TAX-10, TAX-14; ADR-050; DEC-5839).

A `review_checklist` v2 item may name a `check_code`: a code-run check its owner registered here
(`register_check_code`; the standards runs of T-08-T14 run it). An item without one is manual (a
person ticks it). Import validation refuses an unknown code as a row problem
(`check_code_unknown`, the item's row and the `check_code` column), and publishing refuses it as a
payload problem; v1 payloads (no check codes, no threshold) still read unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

_CODES: dict[str, CheckCode] = {}
COLUMN: Final = "check_code"


@dataclass(frozen=True)
class CheckCode:
    code: str
    description: str
    forms: tuple[str, ...] = ()  # empty: every form


def register_check_code(code: str, description: str, forms: Sequence[str] = ()) -> None:
    """A check owner's code (the same code again replaces itself; another description refuses)."""
    known = _CODES.get(code)
    if known is not None and known.description != description:
        raise RuntimeError(f"check code {code!r} is already registered")
    _CODES[code] = CheckCode(code, description, tuple(forms))


def check_code(code: str) -> CheckCode | None:
    return _CODES.get(code)


def known_codes() -> frozenset[str]:
    return frozenset(_CODES)


def unknown_items(payload: Mapping[str, object]) -> list[int]:
    """The 0-based indexes of the items whose `check_code` is not registered."""
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    out: list[int] = []
    for i, item in enumerate(items):
        code = item.get(COLUMN) if isinstance(item, dict) else None
        if isinstance(code, str) and code.strip() and code.strip() not in _CODES:
            out.append(i)
    return out


def bound_count(payload: Mapping[str, object]) -> tuple[int, int]:
    """(bound, manual) items: TAX-10's "42 bound or manual items"."""
    items = payload.get("items")
    if not isinstance(items, list):
        return 0, 0
    bound = sum(1 for i in items if isinstance(i, dict) and i.get(COLUMN))
    return bound, len(items) - bound


__all__ = [
    "COLUMN",
    "CheckCode",
    "bound_count",
    "check_code",
    "known_codes",
    "register_check_code",
    "unknown_items",
]
