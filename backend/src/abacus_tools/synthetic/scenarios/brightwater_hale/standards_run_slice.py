"""TAX-14's firm standards run (T-08-T31, TASK-9032; DEC-6037). Synthetic content for the fixture
export, never product code.

Samuel Ito runs the 1065 Review Checklist v4 (42 checks) at Mon Sep 14, 2026, 9:18 AM CT on six of
the eight open 1065s, the day before the Sep 15 deadline. At 9:24 AM (a) Northgate is running at
31 of 42, Ridgeline and Marlowe have exceptions, and three have passed; at 9:26 AM (b) Northgate
has passed and the run is complete; c is the same six queued before the start. Ridgeline's two
exceptions link to its existing issues (no new issue); Marlowe's three raise three. The people
are the handoff's initials (01 §9.7 names only Olivia Brandt and Samuel Ito among them).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

CDT: Final = timezone(timedelta(hours=-5))
CHECKS: Final = 42
STARTED_AT: Final = datetime(2026, 9, 14, 9, 18, tzinfo=CDT)
COMPLETED_AT: Final = datetime(2026, 9, 14, 9, 26, tzinfo=CDT)
STARTED_BY: Final = "Samuel Ito"
STANDARD: Final = "1065 Review Checklist"
VERSION: Final = 4

# (client, office, preparer, reviewer, return status, review level, a's status, passed,
#  exceptions, linked issues, created issues, finished at a)
ROWS: Final = (
    ("Ridgeline Property Partners, LP", "New York", "OB", "SI", "in_review", "partner",
     "exceptions", 40, 2, 2, 0, (9, 19)),
    ("Northgate Medical Partners, LLP", "Chicago", "BN", "NA", "in_review", "manager",
     "running", 31, 0, 0, 0, None),
    ("Marlowe Street Holdings, LP", "New York", "DS", "TR", "action_required", None,
     "exceptions", 39, 3, 0, 3, (9, 20)),
    ("Kestrel Ventures Fund I, LP", "New York", "NP", "TR", "awaiting_signature", None,
     "passed", 42, 0, 0, 0, (9, 20)),
    ("Bramble & Finch Design, LLC", "Chicago", "GT", "YK", "prepared", None,
     "passed", 42, 0, 0, 0, (9, 21)),
    ("Harborview Dental Properties, LP", "New York", "OB", "SI", "approved", None,
     "passed", 42, 0, 0, 0, (9, 21)),
)  # fmt: skip
# Ridgeline's expanded checks (TAX-14 a): code, words, outcome, the linked issue's words.
RIDGELINE_CHECKS: Final = (
    ("C-04", "K-1 count equals Item I", "pass", None),
    ("C-09", "Schedule K equals Σ K-1s", "pass", None),
    ("C-12", "Schedule M-3 required test applied", "pass", None),
    ("C-15", "TB balanced and Unmapped 0", "pass", None),
    ("C-17", "Schedule M-2 line 9 equals Schedule L line 21", "exception",
     "Tax-exempt interest 6,200 omitted from the capital rollforward"),
    ("C-22", "Partnership representative designated", "pass", None),
    ("C-31", "Transfer of interest: §743(b)/§754 position documented", "exception",
     "§743(b) placeholder 28,595 pending the §754 decision"),
    ("C-38", "PTET elections and payments recorded", "pass", None),
)  # fmt: skip
OTHER_VERSIONS: Final = (
    ("1065 Review Checklist v3", "superseded"),
    ("1120-S Review Checklist v3", "current"),
    ("1041 Review Checklist v2", "current"),
)


def tax14_run() -> dict[str, object]:
    """TAX-14 a, b and c in the standards-run read's shape, with the expanded checks."""
    rows: list[dict[str, object]] = []
    for client, office, prep, rev, status, level, state, passed, exc, linked, created, at in ROWS:
        done = None if at is None else STARTED_AT.replace(hour=at[0], minute=at[1])
        rows.append({
            "client_name": client, "office": office, "preparer": prep, "reviewer": rev,
            "return_status": status, "review_level": level, "status": state,
            "checks_passed": passed, "exceptions": exc, "linked_issues": linked,
            "created_issues": created,
            "completed_at": None if done is None else done.isoformat(),
        })  # fmt: skip
    selected = len(rows)
    tiles = {
        s: sum(1 for r in rows if r["status"] == s) for s in ("running", "passed", "exceptions")
    }
    if tiles["running"] + tiles["passed"] + tiles["exceptions"] != selected:
        raise ValueError("TAX-14's tiles do not add up to the selection")
    return {
        "standard": STANDARD,
        "version_no": VERSION,
        "checks_count": CHECKS,
        "started_at": STARTED_AT.isoformat(),
        "completed_at": COMPLETED_AT.isoformat(),
        "started_by": STARTED_BY,
        "open_1065s": 8,
        "rows": rows,
        "ridgeline_checks": [
            {"code": c, "title": t, "outcome": o, "linked": linked}
            for c, t, o, linked in RIDGELINE_CHECKS
        ],
        "other_versions": [{"label": lb, "state": st} for lb, st in OTHER_VERSIONS],
    }
