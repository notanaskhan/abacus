"""The Today brief's view models (I-02-T03 stub; SPEC-654; I-02 §3, §4.3). Contract:
`docs/contracts/today.md`.

What the shapes carry, and what they never carry:
- **Counts are code.** `CountCell.count`, the group counts and every number in `LeadFact.values`
  come from the C13 gate service (`review`'s `human_gates`) in the same request as HOME-01's; no
  field here is fed by `daily_briefings.blocks` (I-COUNT; the T05 contract test holds it).
- **Model prose is verified blocks, by reference.** `why_blocks` and `summary_blocks` are a stored
  `EngagementBriefing`'s `AgentBlocks` `p` parts (ADR-230): facts by reference into the run's fact
  registry, citations verified before display (INV-2). Any unverified or unavailable briefing
  leaves them empty and the row shows its code `context_line`.
- **Walls** leave an engagement out of every cell, card, group and drill-in; nothing counts what
  was left out (DEC-43). Every route reads the caller's own brief.
- **Deep links are C13's** (`deep_link` on each gate); the brief hardcodes no target.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")

BriefStatus = Literal["building", "ready"]
BriefingStatus = Literal["building", "ready", "unverified", "failed", "unavailable"]
UnavailableReason = Literal[
    "boundary_refused", "consent_7216", "metadata_only", "budget_soft_limit", "flag_off"
]
# C13's band kinds (DF-25 taxonomy, HOME-02 band order) plus the derived Overdue cell.
CellKind = Literal[
    "decision", "sign_off", "approval_send", "signature", "needs_attention", "overdue"
]
LeadKey = Literal[
    "lead.overdue",
    "lead.due_tomorrow",
    "lead.blocked_signoffs",
    "lead.decisions_blocking",
    "lead.signatures_week",
]
GroupKey = Literal[
    "high_risk", "late", "due_tomorrow", "ready_for_signoff", "needs_attention", "running"
]
DueTone = Literal["red_tint", "amber", "neutral"]
Layout = Literal["focus", "by_engagement"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


class CountCell(BaseModel):
    """One Today cell: a C13 band (or Overdue) with its count and the HOME-02 filter it opens."""

    model_config = _frozen()

    kind: Annotated[CellKind, Internal]
    count: Annotated[int, Field(ge=0), Internal]
    href: Annotated[str, Field(max_length=300), Internal]  # /home/approvals?band=<kind>


class LeadFact(BaseModel):
    """One fact the frontend's copy templates turn into the fact paragraph (§3.2): integers, dates
    and the short labels of C13 blocker refs; never model text."""

    model_config = _frozen()

    key: Annotated[LeadKey, Internal]
    values: Annotated[dict[str, int | str], Confidential]  # {"due": 9, "total": 11, "date": …}
    refs: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])  # gate ids


class DueChip(BaseModel):
    model_config = _frozen()

    due_on: Annotated[date, Internal]
    days: Annotated[int, Internal]  # from the firm's today on `kernel.clock`; negative when late
    tone: Annotated[DueTone, Internal]


class GateRow(BaseModel):
    """A highlighted row: one C13 gate with its words and its source."""

    model_config = _frozen()

    gate_id: Annotated[UUID, Internal]
    kind: Annotated[CellKind, Internal]
    title: Annotated[str, Confidential]  # C13's title ("§754 election — Ridgeline …")
    due: Annotated[DueChip | None, Internal] = None
    state: Annotated[str | None, Field(max_length=60), Internal] = None  # a C2 code ("blocked")
    deep_link: Annotated[str, Field(max_length=300), Internal]
    # The code context line HOME-01 shows; the row's words whenever no verified why exists.
    context_line: Annotated[str, Confidential]
    # A verified why line (AgentBlocks `p` parts by reference), or empty.
    why_blocks: Annotated[list[dict[str, object]], Confidential] = Field(
        default_factory=list[dict[str, object]]
    )  # Any: AgentBlocks v1 parts, validated against the closed schema at store time
    folded: Annotated[int, Field(ge=0), Internal] = 0  # "+n more" gates blocked by this one
    # HOME-01 rows lit with this one (the linked highlight, HOME-05 a, d).
    highlight_refs: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class Card(BaseModel):
    """One engagement the viewer has open gates or attention on, in card order (§3.4)."""

    model_config = _frozen()

    engagement_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID | None, Internal] = None
    label: Annotated[str, Confidential]
    rows: Annotated[list[GateRow], Confidential]
    more: Annotated[int, Field(ge=0), Internal] = 0
    briefing_id: Annotated[UUID | None, Internal] = None
    briefing_status: Annotated[BriefingStatus | None, Internal] = None
    unavailable_reason: Annotated[UnavailableReason | None, Internal] = None
    summary_blocks: Annotated[list[dict[str, object]], Confidential] = Field(
        default_factory=list[dict[str, object]]
    )  # Any: AgentBlocks v1 parts (the `by_engagement` layout's card body)


class GroupItem(BaseModel):
    model_config = _frozen()

    ref_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    detail: Annotated[str | None, Confidential] = None  # code text or a verified risk line's words
    detail_blocks: Annotated[list[dict[str, object]], Confidential] = Field(
        default_factory=list[dict[str, object]]
    )  # Any: AgentBlocks v1 parts (High risk's risk_line)
    pills: Annotated[list[str], Internal] = Field(default_factory=list[str])  # C2 codes
    deep_link: Annotated[str | None, Field(max_length=300), Internal] = None
    assignable: Annotated[bool, Internal] = False  # shows "Assign open items"
    actor: Annotated[str | None, Confidential] = None  # Running: "Marcus Delaney" (formatActor)


class Group(BaseModel):
    """A drill group (§3.5); Late is always present, the others only when not empty."""

    model_config = _frozen()

    key: Annotated[GroupKey, Internal]
    count: Annotated[int, Field(ge=0), Internal]
    summary: Annotated[str | None, Confidential] = None  # "All Ridgeline items and …"
    href: Annotated[str | None, Field(max_length=300), Internal] = None
    items: Annotated[list[GroupItem], Confidential] = Field(default_factory=list[GroupItem])


class Availability(BaseModel):
    """Whether the narrative and the ask composer are offered, and why not (DF-04)."""

    model_config = _frozen()

    narrative: Annotated[bool, Internal]
    narrative_reason: Annotated[UnavailableReason | Literal["not_synthetic"] | None, Internal] = (
        None
    )
    ask: Annotated[bool, Internal]
    ask_reason: Annotated[str | None, Field(max_length=40), Internal] = None


class TodayVM(BaseModel):
    """`GET /v1/me/today`: the viewer's day."""

    model_config = _frozen()

    brief_date: Annotated[date, Internal]
    brief_id: Annotated[UUID | None, Internal] = None  # the day's user snapshot
    first_name: Annotated[str, Confidential]
    items: Annotated[int, Field(ge=0), Internal]  # "11 items across 4 engagements"
    engagements: Annotated[int, Field(ge=0), Internal]
    cells: Annotated[list[CountCell], Internal]
    lead_facts: Annotated[list[LeadFact], Confidential]
    layout: Annotated[Layout, Internal] = "focus"
    needs_you_first: Annotated[list[GateRow], Confidential]
    cards: Annotated[list[Card], Confidential]
    groups: Annotated[list[Group], Confidential]
    availability: Annotated[Availability, Internal]
    status: Annotated[BriefStatus, Internal]
    needs_build: Annotated[bool, Internal] = False
    built_at: Annotated[datetime | None, Internal] = None
    # The building line's counts ("from 11 items, 4 deadlines and 3 runs").
    building_counts: Annotated[dict[str, int], Internal] = Field(default_factory=dict[str, int])


class DownstreamRow(BaseModel):
    model_config = _frozen()

    work_item_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]  # "Feld 2025 Form 1040"
    state_line: Annotated[str, Confidential]  # "Draft K-1 · pre-release"
    deep_link: Annotated[str, Field(max_length=300), Internal]


class AssignPrefill(BaseModel):
    """One SHL-17 to-do prefill for an open item; the person presses Create (INV-1, INV-5)."""

    model_config = _frozen()

    gate_id: Annotated[UUID, Internal]
    assignee_user_id: Annotated[UUID, Internal]
    assignee_name: Annotated[str, Confidential]
    title: Annotated[str, Confidential]  # "Approve the M-2 fix — Ridgeline Capital Accounts"
    due_on: Annotated[date, Internal]
    anchor_label: Annotated[str, Confidential]  # "Ridgeline 2025 Form 1065 · Capital Accounts"
    anchor_ref: Annotated[str, Field(max_length=120), Internal]


class NotAssignable(BaseModel):
    model_config = _frozen()

    gate_id: Annotated[UUID, Internal]
    reason: Annotated[Literal["reserved_to_you"], Internal]


class DrillVM(BaseModel):
    """`GET /v1/me/today/work-items/{id}`: HOME-05 b / SHL-23 2."""

    model_config = _frozen()

    work_item_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]  # "Ridgeline Property Partners, LP · 2025 Form 1065"
    summary_blocks: Annotated[list[dict[str, object]], Confidential] = Field(
        default_factory=list[dict[str, object]]
    )  # Any: AgentBlocks v1 parts (the engagement briefing summary)
    summary_fallback: Annotated[str | None, Confidential] = None  # code, when no verified summary
    blockers: Annotated[list[GateRow], Confidential]
    downstream: Annotated[list[DownstreamRow], Confidential] = Field(
        default_factory=list[DownstreamRow]
    )
    prefills: Annotated[list[AssignPrefill], Confidential] = Field(
        default_factory=list[AssignPrefill]
    )
    not_assignable: Annotated[list[NotAssignable], Internal] = Field(
        default_factory=list[NotAssignable]
    )
    open_href: Annotated[str, Field(max_length=300), Internal]
    # HOME-01 rows to select and scroll into view (Sign-off rows 7 and 8).
    select_refs: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class HistoryRow(BaseModel):
    model_config = _frozen()

    brief_id: Annotated[UUID, Internal]
    brief_date: Annotated[date, Internal]
    built_at: Annotated[datetime, Internal]
    counts: Annotated[dict[str, int], Internal]  # cell kind → count


class HistoryPage(BaseModel):
    model_config = _frozen()

    items: Annotated[list[HistoryRow], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class TodayBuildIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    brief_date: Annotated[date, Internal]
    mode: Annotated[Literal["missing", "force"], Internal] = "missing"


class TodayBuildAcceptedOut(BaseModel):
    model_config = _frozen()

    status_url: Annotated[str, Internal]
    started: Annotated[int, Field(ge=0), Internal]  # engagement briefings started


__all__ = [
    "AssignPrefill",
    "Availability",
    "BriefingStatus",
    "Card",
    "CountCell",
    "DownstreamRow",
    "DrillVM",
    "DueChip",
    "GateRow",
    "Group",
    "GroupItem",
    "HistoryPage",
    "HistoryRow",
    "LeadFact",
    "NotAssignable",
    "TodayBuildAcceptedOut",
    "TodayBuildIn",
    "TodayVM",
]
