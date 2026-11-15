"""Brightwater Hale's Connect catalogue: the scenario's content and the stub's typed fixtures
(W-01-T03; SPEC-659 AC-1 to AC-3, AC-5; DEC-5046).

The rows are the scenario's content document (`files/connect_catalog.json`, the canvas
`CX.items` list with Drata and Vanta published Oct 1 for E2; DF-35, DF-36), read here and counted
by code: the catalogue at a clock instant holds the rows published by then; status counts are by
tile; category counts are catalogue totals by tag (one tile can count in two categories). This is
the synthetic tenant on staging, where every listed tile has a fake adapter; on a real firm the
service's honesty rule (AC-4) turns tiles without a registered adapter into Coming soon.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any, Final, cast

E0: Final = datetime.fromisoformat("2026-09-14T09:24:00-05:00")
E2: Final = datetime.fromisoformat("2026-10-01T09:24:00-05:00")
_DOC: Final = Path(__file__).resolve().parent / "files" / "connect_catalog.json"
# WB-10's category glyph tones (AC-5): never a vendor logo or brand colour.
TONES: Final = {
    "tax": "olive",
    "erp": "olive",
    "practice": "olive",
    "docs": "clay",
    "comms": "ochre",
    "prod": "ochre",
    "crm": "brick",
    "spend": "brick",
    "hris": "espresso",
    "grc": "espresso",
}


@cache
def document() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_DOC.read_text(encoding="utf-8")))


def rows(at: datetime = E0) -> list[dict[str, Any]]:
    """The tiles published by `at`, in sort order."""
    items = cast(list[dict[str, Any]], document()["items"])
    live = [r for r in items if datetime.fromisoformat(str(r["published_at"])) <= at]
    return sorted(live, key=lambda r: int(r["sort_order"]))


def status_counts(at: datetime = E0) -> dict[str, int]:
    counted = Counter(str(r["status_e0"]) for r in rows(at))
    return {
        "all": sum(counted.values()),
        "connected": counted["connected"],
        "available": counted["available"],
        "coming_soon": counted["coming_soon"],
    }


def category_counts(at: datetime = E0) -> dict[str, int]:
    counted = Counter(str(c) for r in rows(at) for c in cast(list[str], r["categories"]))
    return {str(c["code"]): counted[str(c["code"])] for c in document()["categories"]}


def connected_names(at: datetime = E0) -> list[str]:
    return [str(r["name"]) for r in rows(at) if r["status_e0"] == "connected"]
