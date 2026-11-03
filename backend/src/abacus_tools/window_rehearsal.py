"""Release-window rehearsal on the synthetic test firm (Q-04-T084, T085; DEC-1530, DEC-2081).

    python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2027-08-02 \
        --at 2027-10-05T19:05:00-05:00 --at 2027-10-12T19:05:00-05:00 [--md out.md]

No pilot firm is live (DEC-1391), so every window guard is inert on the real calendar. This runs
the real P-29 gate (`release.window_gate` over `deploy/windows.yaml`) at each instant as if the
named synthetic firm had been live since `--live-since`. The change is in memory only:
`deploy/windows.yaml` keeps the firm `synthetic: true`, and nothing here is a release.

For each instant it reads the window, the deadline week, the mini-freeze, the Tuesday slot and the
flip slot, and the gate's verdict on three release records: one with no window facts, one
`defect_only` with a rollback, and the same with a hotfix. The records are rehearsal records:
every digest is zero, which no build produces, so none can be mistaken for a real release.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from abacus_tools import release, release_windows

ROLLBACK: Final = "docs/runbooks/RB-16-busy-season-readiness.md"
_ZERO_SHA: Final = "0" * 40
_ZERO_256: Final = "0" * 64
# A rehearsal record: the six digests in their forms, all zero (no build has these).
BARE: Final[dict[str, object]] = {
    "git_sha": _ZERO_SHA,
    "image_digest": f"sha256:{_ZERO_256}",
    "spa_manifest_sha256": _ZERO_256,
    "alembic_head": "0000",
    "openapi_sha256": _ZERO_256,
    "infra_sha": _ZERO_SHA,
}
DEFECT_ONLY: Final[dict[str, object]] = {
    **BARE,
    "window_mode": "defect_only",
    "rollback": ROLLBACK,
}
HOTFIX: Final[dict[str, object]] = {
    **DEFECT_ONLY,
    "hotfix": {"reason": "rehearsal: production broken", "requested_by": "notanaskhan"},
}


@dataclass(frozen=True)
class Reading:
    at: datetime
    window: str | None
    deadline_week: str | None
    mini_freeze: str | None
    tuesday_slot: bool
    flip_slot: bool
    bare: tuple[str, ...]
    defect_only: tuple[str, ...]
    hotfix: tuple[str, ...]


def as_live(cal: release_windows.Calendar, code: str, since: date) -> release_windows.Calendar:
    """The calendar with the synthetic firm `code` live from `since`, for a rehearsal only."""
    found = [f for f in cal.firms if f.code == code]
    if not found or not found[0].synthetic:
        raise SystemExit(f"{code} is not a synthetic firm in the calendar: rehearse only on one")
    live = dataclasses.replace(found[0], synthetic=False, real_data_since=since)
    return dataclasses.replace(cal, firms=tuple(live if f.code == code else f for f in cal.firms))


def read(cal: release_windows.Calendar, at: datetime) -> Reading:
    week = release_windows.deadline_week(cal, at)
    freeze = release_windows.mini_freeze(cal, at)
    return Reading(
        at=at,
        window=release_windows.platform_window(cal, at),
        deadline_week=None if week is None else f"{week.start}/{week.end}",
        mini_freeze=None if freeze is None else f"{freeze.start}/{freeze.end}",
        tuesday_slot=release_windows.in_slot(cal, at),
        flip_slot=release_windows.flip_slot(cal, at),
        bare=release.window_gate(BARE, cal, at).why,
        defect_only=release.window_gate(DEFECT_ONLY, cal, at).why,
        hotfix=release.window_gate(HOTFIX, cal, at).why,
    )


def _verdict(why: Sequence[str]) -> str:
    return "promotes" if not why else "refused: " + ", ".join(why)


def table(readings: Iterable[Reading]) -> str:
    lines = [
        "| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot "
        "| No window facts | defect_only + rollback | + hotfix |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in readings:
        lines.append(
            f"| {r.at.isoformat()} | {r.window or '-'} | {r.deadline_week or '-'} "
            f"| {r.mini_freeze or '-'} | {'yes' if r.tuesday_slot else 'no'} "
            f"| {'yes' if r.flip_slot else 'no'} | {_verdict(r.bare)} "
            f"| {_verdict(r.defect_only)} | {_verdict(r.hotfix)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.window_rehearsal")
    parser.add_argument("--firm", required=True, help="the synthetic firm's pilot code")
    parser.add_argument("--live-since", required=True, type=date.fromisoformat)
    parser.add_argument("--at", action="append", required=True, type=datetime.fromisoformat)
    parser.add_argument("--windows", type=Path, default=release_windows.WINDOWS_FILE)
    parser.add_argument("--md", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    cal = as_live(release_windows.load(args.windows), args.firm, args.live_since)
    out = table(read(cal, at) for at in args.at)
    if args.md is not None:
        args.md.write_text(out)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
