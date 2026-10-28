"""The flip guard (Q-04-T004; SPEC-403 AC-8, AC-9; P-29 rule 3; DEC-02, DEC-807).

`make flag` and `make entitlement` ask it before they write anything. For a pilot firm (one listed
in `deploy/windows.yaml`) every flip names an approver who is not its operator and a rollback
link. Inside the firm's window it also needs the Tuesday 19:00-21:00 CT slot (never in a deadline
week or a mini-freeze) unless it is a hotfix with a reason, and the ops request it runs from; a
`prompt.<capability>` variant also needs the eval report and the shadow run at that version
(P-29 rule 4). A firm that is not listed (the synthetic firms, the Dev firm) keeps today's rules:
an operator and a reason.

The verdict carries the audit references the write records: fingerprints of the approver, the
rollback, the request, the eval report and the shadow run, the slot's start as Unix seconds, and
a hotfix marker (audit references never hold text, TASK-026 D2).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import UUID

from abacus_tools import release_windows

_HANDLE: Final = re.compile(r"[a-z][a-z0-9._-]{0,60}")
_ROLLBACK: Final = re.compile(
    r"(https://[^\s]{1,280}|docs/[A-Za-z0-9_./-]{1,200}(#[a-z0-9-]{1,80})?)"
)
PROMPT_PREFIX: Final = "prompt."


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True)
class Flip:
    """One requested change for one firm."""

    firm: UUID
    operator: str
    at: datetime
    flags: tuple[str, ...] = ()
    approved_by: str | None = None
    rollback: str | None = None
    request: Path | None = None
    request_sha256: str | None = None  # an ops request's fingerprint, when its file is not here
    hotfix: str | None = None
    eval_report: str | None = None
    shadow_run: str | None = None


@dataclass(frozen=True)
class Verdict:
    why: tuple[str, ...]
    window: str | None
    pilot: bool
    refs: dict[str, str | int] = field(default_factory=dict[str, str | int])

    @property
    def allowed(self) -> bool:
        return not self.why


def _slot_start(cal: release_windows.Calendar, at: datetime) -> int:
    here = at.astimezone(cal.flip_slot.tz)
    start = datetime.combine(here.date(), cal.flip_slot.start, cal.flip_slot.tz)
    return int(start.timestamp())


def check(cal: release_windows.Calendar, flip: Flip) -> Verdict:
    """Why the flip may not run now (empty when it may), and the references it records."""
    firm = cal.firm(flip.firm)
    if firm is None:
        return Verdict((), None, False)
    why: list[str] = []
    window = release_windows.in_window(cal, flip.firm, flip.at)
    if flip.approved_by is None or not _HANDLE.fullmatch(flip.approved_by):
        why.append("approver_missing")
    elif flip.approved_by == flip.operator:
        why.append("approver_is_operator")
    if flip.rollback is None or not _ROLLBACK.fullmatch(flip.rollback):
        why.append("rollback_missing")
    request_text: str | None = None
    if flip.request is not None:
        try:
            request_text = flip.request.read_text(encoding="utf-8")
        except OSError:
            why.append("request_unreadable")
    if flip.request_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", flip.request_sha256):
        why.append("request_unreadable")
    if flip.hotfix is not None and not 10 <= len(flip.hotfix.strip()) <= 300:
        why.append("hotfix_reason_missing")
    if window is not None:
        if flip.hotfix is None and not release_windows.flip_slot(cal, flip.at, flip.firm):
            why.append("no_slot")
        if flip.request is None and flip.request_sha256 is None:
            why.append("request_missing")
        if any(name.startswith(PROMPT_PREFIX) for name in flip.flags) and (
            flip.eval_report is None or flip.shadow_run is None
        ):
            why.append("prompt_needs_eval_report_and_shadow_run")
    refs: dict[str, str | int] = {}
    if flip.approved_by is not None:
        refs["approved_by"] = fingerprint(flip.approved_by)
    if flip.rollback is not None:
        refs["rollback"] = fingerprint(flip.rollback)
    if request_text is not None:
        refs["request"] = fingerprint(request_text)
    elif flip.request_sha256 is not None:
        refs["request"] = flip.request_sha256
    if flip.eval_report is not None:
        refs["eval_report"] = fingerprint(flip.eval_report)
    if flip.shadow_run is not None:
        refs["shadow_run"] = fingerprint(flip.shadow_run)
    if window is not None and release_windows.in_slot(cal, flip.at):
        refs["slot"] = _slot_start(cal, flip.at)
    if flip.hotfix is not None:
        refs["hotfix"] = 1
    return Verdict(tuple(why), window, True, refs)


def next_slot(cal: release_windows.Calendar, firm: UUID, after: datetime) -> datetime | None:
    """The firm's next allowed slot start within 60 days, for the refusal's hint."""
    tz = cal.flip_slot.tz
    day = after.astimezone(tz).date()
    for offset in range(61):
        start = datetime.combine(day + timedelta(days=offset), cal.flip_slot.start, tz)
        if start >= after and release_windows.flip_slot(cal, start, firm):
            if release_windows.in_window(cal, firm, start) is None:
                return None
            return start
    return None


__all__ = ["Flip", "Verdict", "check", "fingerprint", "next_slot"]
