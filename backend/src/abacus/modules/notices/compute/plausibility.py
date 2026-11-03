"""Respond-by plausibility (N-04 US-2.2): the date against the type's usual window.

A mismatch shows amber "Check the respond-by date" and is never auto-corrected; a type without a
window is "Not checked".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from abacus.modules.notices.compute.notice_types import NoticeType

Verdict = Literal["plausible", "check", "not_checked"]


@dataclass(frozen=True)
class Plausibility:
    verdict: Verdict
    expected: date | None


def respond_by(
    notice_type: NoticeType, notice_date: date | None, value: date | None
) -> Plausibility:
    if notice_type.window_days is None or notice_date is None or value is None:
        return Plausibility("not_checked", None)
    expected = notice_date + timedelta(days=notice_type.window_days)
    return Plausibility("plausible" if value == expected else "check", expected)
