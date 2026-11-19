"""Cohort approval and execution rules (T-08-T12; TASK-8725; SPEC-710; ADR-126; DEC-5719), pure.

- **Approve**: a live person with a manager-or-above engagement role, never an agent or the system;
  approving creates nothing by itself: it issues a single-use grant the execution consumes.
- **Withdraw**: only before the cohort's execution starts.
- **Order**: cohorts execute FIFO by approval time within a season, one at a time.
- **Steps**: each row runs the same steps (engagement, returns, assignments, binder roll-forward,
  letter and consent drafts, invitations), each keyed `{season}:{row}:{step}`, so re-running a
  row skips the steps already done and creates no duplicate; every created record reads
  "system on behalf of" the approver.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

APPROVER_ROLES: Final = frozenset(
    {"engagement_partner", "manager", "firm_partner", "firm_manager"}
)
STEPS: Final = (
    "engagement", "returns", "assignments", "binder_roll_forward", "letter_draft",
    "consent_draft", "invitations",
)  # fmt: skip
Refusal = Literal["not_a_person", "role_below_manager", "already_started"]


def approval_refusal(actor_kind: str, role: str | None) -> Refusal | None:
    if actor_kind != "human":
        return "not_a_person"
    if role not in APPROVER_ROLES:
        return "role_below_manager"
    return None


def withdraw_refusal(started_at: datetime | None) -> Refusal | None:
    return "already_started" if started_at is not None else None


@dataclass(frozen=True, slots=True)
class Approved:
    cohort: str
    approved_at: datetime


def fifo(approved: Iterable[Approved]) -> list[str]:
    return [a.cohort for a in sorted(approved, key=lambda a: (a.approved_at, a.cohort))]


def step_key(season: str, row: str, step: str) -> str:
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}")
    return f"{season}:{row}:{step}"


def pending_steps(season: str, row: str, done: Sequence[str]) -> list[str]:
    """The row's steps still to run, in order (a re-run creates nothing already created)."""
    finished = set(done)
    return [s for s in STEPS if step_key(season, row, s) not in finished]


__all__ = [
    "APPROVER_ROLES", "STEPS", "Approved", "approval_refusal", "fifo", "pending_steps",
    "step_key", "withdraw_refusal",
]  # fmt: skip
