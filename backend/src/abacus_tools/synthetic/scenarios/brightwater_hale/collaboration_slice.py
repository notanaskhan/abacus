"""The `collaboration` slice (P-05-T12; P-05 §5.4; SPEC-650 AC-1, AC-7, AC-17 to AC-29): Northwind's
comment and to-dos on its Internal Control paper, through collaboration's services as the people
who wrote them (never direct inserts), so `make seed-demo` shows what fixture mode shows
(`apps/web/src/fixtures/seed/collaboration.ts`).

- **SHL-18a.** Mon Sep 14, 2026, 12:35 PM: Margaret Okonkwo on Exceptions!A3, mentioning Hannah
  Leclerc: "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM."
- **SHL-17a.** 12:36 PM: Margaret's to-do on Exceptions row 6 for Marcus Delaney, due Wed Sep 16,
  with its four checklist items.
- **SHL-17f.** Marcus's four open to-dos at 12:40 PM: 1 overdue (Sep 11, from Hannah) + 1 today
  (Sep 14, his own) + 2 this week (Sep 16 from Margaret, Sep 18 from Hannah) = 4.

The paper is the engagement's Internal Control paper (`planning_slice.IC_PAPER`), found or
created as the completion slice does. The slice writes no Activity events of its own: AUD-29
leaves collaboration events out except deletions and redactions (P-05 OQ-4), so Northwind's
23-event timeline (12 Human + 11 via Agent + 0 Policy) is the other slices' (see TASK-6706).
Opt-in (`--slice collaboration`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "collaboration"
NEEDS: Final = ("audit_core",)
CT: Final = ZoneInfo("America/Chicago")
SHEET: Final = "Exceptions"
# The SHL-17f clock: Marcus opens My to-dos at 12:40 PM on Mon Sep 14, 2026.
LIST_AT: Final = datetime(2026, 9, 14, 12, 40, tzinfo=CT)

THREAD_BODY: Final = (
    "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM."
)
THREAD_AT: Final = datetime(2026, 9, 14, 12, 35, tzinfo=CT)


@dataclass(frozen=True)
class SeedTodo:
    key: str
    title: str
    by: str  # the creator's seat initials
    assignee: str
    due_on: date
    at: datetime
    locator: dict[str, str | int] | None
    checklist: tuple[str, ...] = ()


TODOS: Final[tuple[SeedTodo, ...]] = (
    SeedTodo(
        "form5500",
        "Confirm Summit Plan Administrators' Form 5500 timeline",
        "HL",
        "MD",
        date(2026, 9, 11),
        datetime(2026, 9, 10, 9, 0, tzinfo=CT),
        None,
    ),
    SeedTodo(
        "review7",
        "Review the 7 Internal Control exceptions before Hannah's review",
        "MD",
        "MD",
        date(2026, 9, 14),
        datetime(2026, 9, 10, 9, 1, tzinfo=CT),
        {"sheet": SHEET},
    ),
    SeedTodo(
        "loan_offsets",
        "Confirm the 3 loan offsets ($14,850) are reported as distributions on Schedule H",
        "HL",
        "MD",
        date(2026, 9, 18),
        datetime(2026, 9, 10, 9, 2, tzinfo=CT),
        {"sheet": SHEET, "row": 7},
    ),
    SeedTodo(
        "row6",
        "Request opt-out elections for the 4 auto-enrolled participants",
        "MO",
        "MD",
        date(2026, 9, 16),
        datetime(2026, 9, 14, 12, 36, tzinfo=CT),
        {"sheet": SHEET, "row": 6},
        (
            "List the 4 participants from EBP-04 Participant data F12:F15",
            "Ask Dana Kowalski for their signed opt-out elections",
            "Link what comes back to Exceptions row 6",
            "If none exist, raise the missed-deferral finding in Findings",
        ),
    ),
)


def bucket_of(due: date, today: date) -> str:
    """SHL-17f's buckets: Overdue, Today, This week (the next six days), Later."""
    if due < today:
        return "overdue"
    if due == today:
        return "today"
    return "this_week" if (due - today).days <= 6 else "later"


def todo_id_of(key: str) -> str:
    return stable_id(f"todo:northwind:{key}")


@register_slice(SLICE)
def collaboration_events() -> list[Event]:
    events = [
        Event(
            "collaboration:thread:exceptions-a3",
            THREAD_AT,
            "collaboration.thread_seeded",
            "MO",
            SLICE,
            {
                "locator": {"sheet": SHEET, "cell": "A3"},
                "body": THREAD_BODY,
                "mention": ["HL"],
            },
            client="Northwind Robotics, Inc.",
        )
    ]
    for todo in TODOS:
        events.append(
            Event(
                f"collaboration:todo:{todo.key}",
                todo.at,
                "collaboration.todo_seeded",
                todo.by,
                SLICE,
                {
                    "key": todo.key,
                    "title": todo.title,
                    "assignee": todo.assignee,
                    "due_on": todo.due_on.isoformat(),
                    "locator": todo.locator,
                    "checklist": list(todo.checklist),
                },
                client="Northwind Robotics, Inc.",
            )
        )
    return events
