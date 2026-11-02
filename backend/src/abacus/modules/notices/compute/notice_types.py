"""The notice-type catalogue (`notice_types.yaml`, PROTECTED; N-04 §4.2)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, cast

import yaml

AnalysisKind = Literal["underreporter_comparison", "balance_due", "none"]
_FILE = Path(__file__).with_name("notice_types.yaml")


@dataclass(frozen=True)
class NoticeType:
    key: str
    agency: Literal["irs", "state"] | None
    code: str | None
    title: str
    analysis_kind: AnalysisKind
    window_days: int | None
    partner_owned: bool
    templates: dict[str, str]
    response_page_hint: str | None


@cache
def catalogue() -> dict[str, NoticeType]:
    raw = cast(dict[str, object], yaml.safe_load(_FILE.read_text(encoding="utf-8")))
    types = cast(dict[str, dict[str, object]], raw["types"])
    return {
        key: NoticeType(
            key=key,
            agency=cast("Literal['irs', 'state'] | None", entry["agency"]),
            code=cast("str | None", entry["code"]),
            title=str(entry["title"]),
            analysis_kind=cast(AnalysisKind, entry["analysis_kind"]),
            window_days=cast("int | None", entry["window_days"]),
            partner_owned=bool(entry["partner_owned"]),
            templates=cast(dict[str, str], entry["templates"]),
            response_page_hint=cast("str | None", entry["response_page_hint"]),
        )
        for key, entry in types.items()
    }


def lookup(code: str | None, *, agency: Literal["irs", "state"] | None = None) -> NoticeType:
    """The type for a printed notice code ("CP2000", "cp14"); a state notice with an unmapped code
    is `state_generic`, anything else unmapped is `unknown`."""
    wanted = (code or "").strip().upper().replace(" ", "")
    for entry in catalogue().values():
        if entry.code is not None and entry.code == wanted:
            return entry
    return catalogue()["state_generic" if agency == "state" else "unknown"]
