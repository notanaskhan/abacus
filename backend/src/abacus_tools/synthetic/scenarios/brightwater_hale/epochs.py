"""View epochs and named snapshots on the one Brightwater Hale timeline (SPEC-307 AC-2; DEC-27,
G-C02; F-04.18).

Epochs are *view* filters: E0 is the firm at Mon 14 Sep 2026, 9:24 AM CT, with Harlow & Pike
and Tessellate hidden; E1 adds Harlow & Pike (from 10:05 AM); E2 adds Tessellate. Service lines
are slices, not epochs (`slices.py`). Loading a snapshot replays every event dated up to it and
anchors the tenant clock there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from zoneinfo import ZoneInfo

CT: Final = ZoneInfo("America/Chicago")
DEMO_INSTANT: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)

Epoch = Literal["E0", "E1", "E2"]
# The clients each epoch adds to the view (A-09 and X-02 bring their content).
EPOCH_ADDS: Final[dict[Epoch, tuple[str, ...]]] = {
    "E0": (),
    "E1": ("Harlow & Pike",),
    "E2": ("Tessellate",),
}


@dataclass(frozen=True)
class Snapshot:
    name: str
    at: datetime


SNAPSHOTS: Final[tuple[Snapshot, ...]] = (
    Snapshot("E0", DEMO_INSTANT),
    Snapshot("2026-09-24", datetime(2026, 9, 24, 9, 0, tzinfo=CT)),
    Snapshot("2026-10-01", datetime(2026, 10, 1, 9, 0, tzinfo=CT)),
    Snapshot("2026-10-06T11:20", datetime(2026, 10, 6, 11, 20, tzinfo=CT)),
    Snapshot("2026-10-21T14:10", datetime(2026, 10, 21, 14, 10, tzinfo=CT)),
    Snapshot("2026-10-26T16:15", datetime(2026, 10, 26, 16, 15, tzinfo=CT)),
    Snapshot("2026-10-27", datetime(2026, 10, 27, 9, 0, tzinfo=CT)),
    Snapshot("2026-11-09", datetime(2026, 11, 9, 9, 0, tzinfo=CT)),
    Snapshot("2026-11-13", datetime(2026, 11, 13, 9, 0, tzinfo=CT)),
    Snapshot("2026-11-16", datetime(2026, 11, 16, 9, 0, tzinfo=CT)),
    Snapshot("2027-01-11", datetime(2027, 1, 11, 9, 0, tzinfo=CT)),
)
_BY_NAME: Final = {s.name: s for s in SNAPSHOTS}


def snapshot(name: str) -> Snapshot:
    """A named snapshot; anything else is an error (no ad hoc instants)."""
    found = _BY_NAME.get(name)
    if found is None:
        raise KeyError(f"no snapshot {name!r}; the snapshots are {', '.join(_BY_NAME)}")
    return found
