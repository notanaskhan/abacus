"""SPEC-031 (TASK-060): what a client reads about a request (why it's asked, what good looks
like) and how the firm plans it (blocks fieldwork, effort). Every word is the firm's, the
template's, or the fixed copy below (ADR-111): no model writes any of it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

EFFORTS: Final = ("small", "medium", "large")
# SPEC-031 Q3: minutes per effort for the client's estimate; no estimate counts as medium (D4).
MINUTES: Final = {"small": 15, "medium": 45, "large": 120}
UNESTIMATED: Final = "medium"
MAX_LENGTH: Final = 1000


@dataclass(frozen=True)
class Guidance:
    why: str | None = None
    good_looks_like: str | None = None
    blocks_fieldwork: bool = False
    effort: str | None = None
    source: str | None = None  # template, kind_default, firm or drafted; None for nothing


# D3 (founder-approved copy, 2026-10-12), shown to clients verbatim.
KIND_DEFAULTS: Final[dict[str, Guidance]] = {
    "bank_statement": Guidance(
        "To confirm the cash the company held at year end, we compare each bank account's "
        "balance with the bank's own record.",
        "The bank's statement for every account, covering the year-end date and showing "
        "opening and closing balances. Download it from online banking as a PDF; a photo or "
        "scan is harder to read.",
        effort="small",
        source="kind_default",
    ),
    "ar_aging": Guidance(
        "To see who owes the company money at year end and for how long, and to check it "
        "agrees with your accounting system.",
        "An aged receivables report as of the year-end date, by customer, with totals by age "
        "band, exported from your accounting system without edits.",
        effort="small",
        source="kind_default",
    ),
    "ap_aging": Guidance(
        "To see what the company owed its suppliers at year end and confirm nothing is missing.",
        "An aged payables report as of the year-end date, by supplier, with totals by age "
        "band, exported from your accounting system without edits.",
        effort="small",
        source="kind_default",
    ),
    "schedule": Guidance(
        "To understand how a year-end balance is made up.",
        "A spreadsheet listing each item that makes up the balance, with a total that agrees "
        "with your accounting system at year end.",
        effort="medium",
        source="kind_default",
    ),
}


def for_new_item(template: Guidance | None, kind: str | None) -> Guidance:
    """AC-2: the template's guidance when it has text; otherwise the fixed copy for the
    document kind (keeping the template's fieldwork and effort settings); otherwise empty."""
    t = template or Guidance()
    if t.why or t.good_looks_like:
        return Guidance(t.why, t.good_looks_like, t.blocks_fieldwork, t.effort, "template")
    default = KIND_DEFAULTS.get(kind or "")
    if default is not None:
        return Guidance(
            default.why,
            default.good_looks_like,
            t.blocks_fieldwork,
            t.effort or default.effort,
            "kind_default",
        )
    if t.blocks_fieldwork or t.effort:
        return Guidance(None, None, t.blocks_fieldwork, t.effort, "template")
    return Guidance()


def after_kind_change(current: Guidance, kind: str | None) -> Guidance | None:
    """The guidance after the item's document kind changes, or None to keep it: the firm's own
    and the template's stand, as does approved drafted guidance (SPEC-035); the kind's fixed copy
    follows the kind."""
    if current.source in ("firm", "template", "drafted"):
        return None
    default = KIND_DEFAULTS.get(kind or "")
    if default is None:
        return Guidance(None, None, current.blocks_fieldwork, None, None)
    return Guidance(
        default.why,
        default.good_looks_like,
        current.blocks_fieldwork,
        default.effort,
        "kind_default",
    )


def for_client(source: str | None, kind: str | None, shown: bool) -> Guidance | None:
    """SPEC-035 AC-5 (ADR-111): what replaces approved drafted guidance for a client when the
    firm doesn't show it: the kind's fixed copy, or nothing. None: show the item's own."""
    if source != "drafted" or shown:
        return None
    return KIND_DEFAULTS.get(kind or "") or Guidance()


def estimate_minutes(efforts: list[str | None]) -> int:
    return sum(MINUTES[e or UNESTIMATED] for e in efforts)
