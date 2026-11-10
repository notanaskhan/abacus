"""The tax return's Activity kinds (T-04-T23; T-04 §4.6; SPEC-649 AC-5.1, AC-5.6; DEC-60, INV-5).
TAX-07 reads P-05's engagement activity with a `work_item_id` filter; this registers how each tax
action reads there, so `audit_trail` itself never changes (P-05 §4.3):

- the C9 catalogue entry (`register_activity_kinds`): its category and marker. A decision-class
  marker (`ok`) is only on actions a person takes (INV-1: the catalogue test fails the build on
  an agent decision);
- the AUD-29 link (`register_activity_links`): where a row's click goes, its search words, and
  whether the default list shows it;
- TAX-07's own filter group (`TAX_GROUP`: approvals, client, agent, tax_engine, issues) and the
  title verb, for "{Verb} by {Actor}" (`title`): an agent's row reads "… by <person> via Agent",
  or "by Accrued Agent" for proposals and self-checks only; an approval always names a person.

Every label is resolved at read time from identifiers (DEC-60): no Restricted value is in an
audit row or in a title here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from abacus.modules.audit_trail.api import (
    ActivityLink,
    CatalogueEntry,
    register_activity_kinds,
    register_activity_links,
)

TaxGroup = Literal["approvals", "client", "agent", "tax_engine", "issues"]


@dataclass(frozen=True)
class TaxActivityKind:
    group: TaxGroup
    verb: str  # TAX-07's title verb; "{verb} by {actor}"
    entry: CatalogueEntry
    link: ActivityLink
    agent_self: bool = False  # proposals and self-checks may read "by Accrued Agent"


def _k(
    group: TaxGroup,
    verb: str,
    category: str,
    mark: str = "pl",
    link: str = "none",
    *keywords: str,
    agent_self: bool = False,
) -> TaxActivityKind:
    return TaxActivityKind(
        group,
        verb,
        CatalogueEntry(category, mark),  # type: ignore[arg-type]  # literals checked below
        ActivityLink(link, keywords),  # type: ignore[arg-type]
        agent_self,
    )


# Only the tax module's own actions (P-04's checkpoint, issue and field actions keep their
# catalogue entries; TAX-07 groups them through `GROUP_OF`).
ACTIVITY_KINDS: Final[Mapping[str, TaxActivityKind]] = {
    "return_worksheet.created": _k("agent", "Worksheet added", "change", "pl", "document",
                                   "worksheet", agent_self=True),
    "k1_treatment.proposed": _k("agent", "K-1 treatment proposed", "change", "pl", "document",
                                "k-1", "treatment", agent_self=True),
    "k1_treatment.approved": _k("approvals", "K-1 treatment approved", "decision", "ok",
                                "document", "k-1", "treatment"),
    "k1_treatment.overridden": _k("approvals", "K-1 treatment overridden", "decision", "ok",
                                  "document", "k-1", "treatment"),
    "residency.proposed": _k("agent", "Residency proposed", "change", "pl", "none",
                             "residency", agent_self=True),
    "residency.confirmed": _k("approvals", "Residency confirmed", "decision", "ok", "none",
                              "residency"),
    "tax_return.draft_requested": _k("agent", "Draft requested", "run", "pl", "run", "draft"),
    "issue.explained": _k("issues", "Issue explained", "change", "pl", "none", "issue",
                          agent_self=True),
    "issue.system_resolved": _k("issues", "Issue resolved when the K-1 was released", "change",
                                "pl", "none", "issue", "k-1"),
    "tax_assistant.asked": _k("agent", "Assistant asked", "run", "pl", "none", "assistant"),
    "export.created": _k("tax_engine", "Exported", "export", "pl", "none", "export", "csv"),
}  # fmt: skip

# P-04's and T-01's actions as TAX-07 groups them (their catalogue entries are their owners').
GROUP_OF: Final[Mapping[str, TaxGroup]] = {
    **{action: kind.group for action, kind in ACTIVITY_KINDS.items()},
    "document.approved": "approvals",
    "document.approval_reversed": "approvals",
    "tax_return.final_approval_requested": "approvals",
    "tax_return.approved": "approvals",
    "checkpoint.proposed": "agent",
    "checkpoint.approved": "approvals",
    "field.value_recorded": "agent",
    "issue.created": "issues",
    "issue.resolved": "issues",
    "issue.sent_to_client": "client",
    "engine_import.approved": "tax_engine",
    "tax_return.exported": "tax_engine",
}
VERBS: Final[Mapping[str, str]] = {
    **{action: kind.verb for action, kind in ACTIVITY_KINDS.items()},
    "document.approved": "Document approved",
    "document.approval_reversed": "Approval reversed",
    "tax_return.final_approval_requested": "Final approval requested",
    "tax_return.approved": "Return approved",
    "checkpoint.proposed": "Checkpoint proposed",
    "checkpoint.approved": "Checkpoint approved",
    "field.value_recorded": "Field changed",
    "issue.created": "Issue raised",
    "issue.resolved": "Issue resolved",
    "issue.sent_to_client": "Question sent to the client",
}
_AGENT_SELF: Final = frozenset(
    {a for a, k in ACTIVITY_KINDS.items() if k.agent_self}
    | {"checkpoint.proposed", "issue.created"}
)
_DECISIONS: Final = frozenset(a for a, k in ACTIVITY_KINDS.items() if k.entry.mark == "ok") | {
    "document.approved",
    "tax_return.approved",
    "checkpoint.approved",
}


def title(action: str, actor_kind: str, actor_name: str, on_behalf_of: str | None) -> str:
    """TAX-07's "{Verb} by {Actor}" (INV-5). An agent's row names the person it acted for
    ("by Kevin Osei via Agent"); "by Accrued Agent" only on its own proposals and self-checks. A
    decision is always a person's: an agent decision row reads neutrally, never as approved."""
    verb = VERBS.get(action, action.replace("_", " ").replace(".", " ").capitalize())
    if actor_kind == "agent":
        if action in _DECISIONS:
            return verb  # INV-1: never "approved by the agent"; the catalogue flags it
        if on_behalf_of:
            return f"{verb} by {on_behalf_of} via Agent"
        return f"{verb} by Accrued Agent" if action in _AGENT_SELF else verb
    if actor_kind == "system":
        return verb
    return f"{verb} by {actor_name}"


def register() -> None:
    """At import (tax/api.py)."""
    register_activity_kinds({a: k.entry for a, k in ACTIVITY_KINDS.items()})
    register_activity_links({a: k.link for a, k in ACTIVITY_KINDS.items()})


__all__ = ["ACTIVITY_KINDS", "GROUP_OF", "VERBS", "TaxActivityKind", "register", "title"]
