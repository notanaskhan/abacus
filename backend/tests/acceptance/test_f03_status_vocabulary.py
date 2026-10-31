"""F-03-T10 (ADR-078): conformance tests for `docs/product/status-vocabulary.yaml`, written from
the sources and not from the YAML or its generator.

The sources, restated below as data:

- blueprint section 3.3.1, the canonical status table (display label and pill or disc per state);
- addendum section 3.2 and gap analysis section 6.5, the status additions (the addendum's
  table is the longer of the two; 6.5 adds nothing to it);
- the handoff's `lib/status.js`: 21 objects and 144 words, restated in `STATUS_JS`.

Nothing here is read from the YAML to build an expectation. The YAML is only the thing under test.
Where the YAML disagrees with a source, the test stays and is `xfail(strict=True)` with a finding
(`TASK-355`; each of the four marks below cites its issue, #206 to #209, because SKIP-001 reads
the reason literal).

Rules taken from the sources, not from the YAML header:

- every 3.3.1 object and every state in it has an entry with its display label and its pill
  variant; a state the table shows with a disc or glyph only has no pill variant (none is
  invented);
- Overdue, past due and the transient run badge are derived and never stored;
- pill text is sentence case (3.3.1, first paragraph);
- `match` is source tracing only and is never a status (status.js `VARIANTS`);
- every one of the 144 handoff words is mapped to a registry code or marked as having no home,
  with a reason, and a word that is also a label on the equivalent 3.3.1 object maps there;
- every status literal in the OpenAPI document has a YAML entry.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel import _statuses

REPO = Path(__file__).resolve().parents[3]
Json = dict[str, Any]  # YAML and OpenAPI documents, untyped by their libraries

DISC = "disc"  # the source gives only a disc or glyph: the YAML must not invent a pill variant
ANY = "any"  # the source names no variant for this word, or ambiguously

# The pill variants of 3.3.1 and status.js, without `match` (source tracing only, never a status),
# plus `state`, which 3.3.1 names in its first paragraph, and `tag` (a category, never a state).
VARIANTS = {
    "state", "amber", "green-tint", "green", "red-tint", "red",
    "neutral", "muted", "soon", "outline", "tag",
}  # fmt: skip

# ---------------------------------------------------------------------------------------------
# Blueprint 3.3.1 and addendum 3.2: object -> "display label | pill variant" per state.
# Placeholders are written {x}; they compare equal whatever their name.
# ---------------------------------------------------------------------------------------------
TABLE = {
    # 3.3.1
    "engagement": """
        Prospect | neutral
        Accepted | neutral
        Declined | soon
        Letter signed | green-tint
        Active | state
        On hold | muted
        Delivered | green
        Archived | soon
    """,
    "return": """
        Not started | neutral
        Gathering | state
        Preparing | state
        Draft | any
        Working | any
        Prepared | neutral
        In review | state
        Action required | red-tint
        Issues | any
        Approved | green-tint
        Awaiting signature | amber
        Filed | green-tint
        Accepted | green
        Rejected | red-tint
        Fixing | state
    """,
    "return_flag": """
        Extended · {date} | tag
        On hold | muted
        Superseded | soon
        Amended | tag
    """,
    "return_sync_chip": """
        Not yet exported | outline
        Ready for export | outline
        Ready | any
        Exporting… | outline
        Synced {date} | outline
        Out of sync | outline
        Import pending approval | outline
        Export failed | outline
    """,
    "k1_package": """
        Not prepared | neutral
        Draft K-1 · pre-release | amber
        Released {date} | green-tint
        Viewed | green-tint
        Downloaded | green-tint
        Bounced | red-tint
        Superseded (amended K-1) | soon
    """,
    "audit_engagement": """
        Planning | state
        Fieldwork | state
        In review | state
        Completion | state
        Ready to release | green-tint
        Released {date} | green
        Archive in {days} days | muted
        Archived | soon
        Processing | state
    """,
    "audit_section": """
        Not started | disc
        Queued | disc
        In progress | disc
        Waiting on inputs | disc
        Ready | disc
        Running | disc
        Blocked on a {role} decision | disc
        Prepared · {initials} | disc
        Reviewed · {initials} | disc
        Signed off | disc
        Locked | soon
        Failed — see run | disc
        Changed after sign-off | disc
    """,
    "close": """
        Not started | neutral
        In progress | state
        In review | state
        Approved | green-tint
        Delivered | green
        Locked | soon
        {n} days past due | any
    """,
    "close_task": """
        Queued | disc
        Running | disc
        Needs attention | disc
        Done | disc
        Failed | disc
    """,
    "agent_run": """
        Queued | muted
        Planning… | disc
        Plan ready — approve? | amber
        Dispatched | neutral
        Running | disc
        Needs your answer | amber
        Blocked on a {role} decision | disc
        Waiting on inputs | muted
        Ready for review | state
        Approved | green
        {n} of {total} approved | green-tint
        Rejected | red-tint
        Failed | red
        Cancelled | muted
    """,
    "workbench_session": """
        Live | disc
        Running | disc
        Needs your answer | disc
        Ready for review | state
        Complete | disc
        Failed | disc
    """,
    "request": """
        Draft | neutral
        Requested {date} | disc
        Uploaded \u2013 needs review | disc
        Received ✓ | green
        Returned · {reason} | red-tint
        Not applicable | muted
        Overdue | red-tint
    """,
    "request_close": """
        Requested | disc
        Received | disc
        Matched | green-tint
        Pending incorporation | amber
        Incorporated | green
    """,
    "document": """
        Uploading | disc
        Processing | disc
        Classified | neutral
        Matched | green-tint
        Approved | disc
        Rejected | disc
        Superseded | soon
    """,
    "inbox_item": """
        New | disc
        Waiting | disc
        Filed | disc
        Ignored | disc
    """,
    "issue": """
        Open | any
        In progress | any
        Resolved | any
        Verified | any
        Reopened | any
        Not applicable | muted
    """,
    "issue_severity": """
        High | disc
        Medium | disc
        Low | disc
    """,
    "issue_audit_route": """
        Under evaluation | state
        Converted to misstatement | neutral
        Converted to deficiency | neutral
    """,
    "review_note": """
        Open | amber
        Responded | state
        Cleared | green
        Closed | green-tint
        Withdrawn | soon
    """,
    "deficiency": """
        Exception for resolution | amber
        Proposed | state
        Concluded | neutral
        Communicated | green-tint
    """,
    "deficiency_severity": """
        Deficiency | red-tint
        Significant deficiency | red
        Material weakness | red
    """,
    "misstatement": """
        Candidate | state
        Confirmed | neutral
        Below CT | muted
        Proposed to client | amber
        Booked | green
        Passed on SUM | neutral
    """,
    "misstatement_type": """
        Factual | any
        Judgmental | any
        Projected | any
    """,
    "proposed_entry": """
        Proposed | state
        Within threshold | disc
        Review required | disc
        Approved | green
        Client approved | green
        Posted | green-tint
        Failed post | red
        Reversed | soon
    """,
    "envelope": """
        Draft | neutral
        Sent | amber
        Viewed | amber
        {signed} of {total} signed | amber
        Completed | green
        Declined | red-tint
        Expired | muted
        Voided | soon
    """,
    "notice": """
        New | red-tint
        Classified | neutral
        Analyzing | state
        Response drafted | state
        Approved | green-tint
        Response sent | amber
        Awaiting IRS | muted
        Resolved | green
        Escalated | red-tint
    """,
    "integration": """
        Available | outline
        Connecting | disc
        Connected | disc
        Needs attention | amber
        Needs reauth | amber
        Disconnected | neutral
        Coming soon | soon
    """,
    "agent_template": """
        Available | outline
        Installed | disc
        Update available | amber
        Coming soon | soon
    """,
    "consent": """
        Requested | amber
        Signed · expires {date} | green
        Expiring | amber
        Expired | red-tint
        Declined | neutral
        Revoked | soon
    """,
    "consent_purpose": """
        Consent to use | tag
        Consent to disclose — AI sub-processors | tag
        Consent to disclose — offshore preparers | tag
        Consent to disclose — named third party | tag
    """,
    "binder": """
        Draft | neutral
        Published | state
        Unpublished | muted
        Complete | green-tint
        Closed | soon
    """,
    "archive": """
        Archive in {days} days | muted
        Locked · WORM | soon
        Addition logged | amber
    """,
    "checkpoint": """
        Proposed | state
        Approved | green
        Rejected | red-tint
        Current | tag
    """,
    "project": """
        Scoping | neutral
        Active | state
        Delivered | green
        Closed | soon
    """,
    "tie_out_tally": """
        tie | green
        off {amount} | amber
        Check | amber
        Pending | muted
        Ties once posted | any
        Reconciled ✓ | green
    """,
    # addendum 3.2 (gap 6.5 lists the same sets, without Late and Held)
    "program_board": """
        Not started | disc
        In progress | disc
        In review | disc
        Complete | disc
    """,
    "control_board": """
        Not started | disc
        Testing | disc
        Pending | muted
        Preparer review | disc
        Manager review | disc
        Review complete | disc
    """,
    "card_overlay": """
        Needs input | amber
        Waiting on client | muted
        Agent running | disc
        Sent back | disc
    """,
    "template_version": """
        Draft | neutral
        Published | green-tint
        Deprecated | muted
    """,
    "engagement_template_link": """
        Current | green-tint
        Update available | state
        Updated {date} | neutral
        Held | muted
    """,
    "consolidation": """
        Draft | state
        Finalized | green-tint
    """,
    "elimination_entry": """
        Proposed | outline
        Approved | green-tint
        Posted | green
    """,
    "component": """
        Full scope | tag
        Specific procedures | tag
        Analytical only | tag
    """,
    "component_instructions": """
        Draft | neutral
        Sent | state
        Acknowledged | green-tint
    """,
    "component_deliverable": """
        Expected | muted
        Received | state
        Reviewed | green-tint
        Late | red-tint
    """,
    "linked_value": """
        TB-linked | any
        Formula | any
        Override | any
        Stale override | any
    """,
    "control_test_result": """
        Not tested | disc
        No exceptions noted | disc
        Exceptions noted | red-tint
        Not applicable | muted
    """,
    "attest_exception": """
        Noted | red-tint
        Response received | state
        Evaluated | green-tint
    """,
    "ia_issue_rating": """
        High | red
        Medium | amber
        Low | neutral
    """,
    "action_plan": """
        Open | neutral
        In progress | state
        Implemented | green-tint
        Validated | green
        Overdue | red-tint
    """,
    "todo": """
        Open | disc
        Done | disc
        Overdue | red-tint
    """,
    "comment_thread": """
        Open | any
        Resolved | muted
    """,
    "evidence_screening": """
        Passed | disc
        Flagged | disc
        Not screened | disc
    """,
    "trigger": """
        On | green-tint
        Off | muted
        Duplicate | amber
    """,
    "saved_prompt_access": """
        Firm | tag
        Service line | tag
        Personal | tag
    """,
    "learned_context_item": """
        Proposed | outline
        Approved | green-tint
        Retired | muted
    """,
}  # fmt: skip

# Display words the sources say are derived from a date or a run and never stored:
# 3.3.1 "Overdue" (request) and "derived chip '4 days past due'" (close); addendum 3.2 "Overdue
# derived" (action plan, to-do); 3.3.1 "(run badge, transient)" for "Processing".
DERIVED_BY_SOURCE = {
    "request": "Overdue",
    "close": "{n} days past due",
    "action_plan": "Overdue",
    "todo": "Overdue",
    "audit_engagement": "Processing",
}

# 3.3.1 "Request (client words)": To do, Done, Ignored; "Not prepared" and "Draft (pre-release)"
# K-1 packages read "Not released yet" on the portal.
CLIENT_WORDS = {"request": {"To do", "Done", "Ignored"}, "k1_package": {"Not released yet"}}

# 3.3.1 labels that are not title-cased words: the tally literals are lower case in the table.
LOWER_CASE_BY_SOURCE = {"tie", "off {amount}"}
# Words a sentence-case label may capitalise after its first: acronyms and the one hyphenated
# compound the table spells with capitals.
CAPITALISED_BY_SOURCE = {
    "TB-linked",
    "Interim",  # AUD-06 g spells the chip "TB: Interim · 8/31/2026" (A-02-T02; verbatim, DEC-15)
    # The product's name for its one agent: AUD-08 and TPL-20 cells "Suggested by Accrued Agent"
    # (A-04-T01; verbatim, DEC-15).
    "Accrued",
    "Agent",
    # AUD-07's version pill after the dot: "Version 1 · Proposed", "Version 2 · Decided"
    # (A-04-T01; verbatim, DEC-15).
    "Proposed",
    "Decided",
}

# ---------------------------------------------------------------------------------------------
# The handoff's lib/status.js: every word, per object. 21 objects, 144 words.
# ---------------------------------------------------------------------------------------------
STATUS_JS = {
    "Engagement": ["Draft", "Letter sent", "Active", "On hold", "Complete", "Archived"],
    "Tax return": [
        "Not started", "Waiting on client", "Preparing", "Working", "Processing", "In review",
        "Ready to file", "Transmitted", "Accepted", "Rejected", "Filed", "Extended",
    ],
    "Return sync chip": [
        "Not yet exported", "Ready for export", "Exporting", "Synced", "Out of sync",
        "Import pending approval", "Export failed",
    ],
    "Document": [
        "Requested", "Received", "Processing", "Needs review", "Approved", "Rejected",
        "Duplicate", "Superseded",
    ],
    "Audit": [
        "Not started", "Planning", "Processing", "Fieldwork", "Completion", "In review",
        "Ready to issue", "Issued", "Archived",
    ],
    "Audit section": [
        "Queued", "Running", "In progress", "Waiting on inputs", "Blocked", "Ready", "Complete",
        "Exceptions", "Failed", "Skipped",
    ],
    "Workpaper": [
        "Not started", "In progress", "Prepared", "Review notes", "Reviewed", "Not applicable",
    ],
    "Close": ["Not started", "In progress", "In review", "Reopened", "Closed"],
    "Close task": [
        "Queued", "Running", "Waiting on client", "Issues found", "No issues", "Reconciled",
        "Failed", "Skipped",
    ],
    "Request": ["Draft", "Sent", "Viewed", "Answered", "Overdue", "Closed", "Cancelled"],
    "Inbox item": ["Unprocessed", "Waiting", "Filed", "Ignored"],
    "Issue": ["Open", "Review point", "Waiting on client", "Resolved", "Dismissed"],
    "Audit finding": [
        "Observation", "Deficiency", "Significant deficiency", "Material weakness", "Corrected",
        "Uncorrected", "Passed",
    ],
    "Agent run": [
        "Queued", "Running", "Waiting on you", "Complete", "Exceptions", "Failed", "Cancelled",
    ],
    "AJE": ["Proposed", "In review", "Approved", "Posted", "Passed", "Rejected", "Reversed"],
    "Session": ["Running", "Waiting on you", "Paused", "Done", "Failed", "Archived"],
    "Agent template": [
        "Available", "Installed", "Update available", "Draft", "Coming soon", "Deprecated",
    ],
    "Integration": [
        "Available", "Connecting", "Connected", "Syncing", "Disconnected", "Coming soon",
    ],
    "Signature": [
        "Draft", "Sent", "Viewed", "Partially signed", "Signed", "Declined", "Expired", "Voided",
    ],
    "Notice": [
        "New", "Researching", "Response drafted", "Responded", "Resolved", "Response overdue",
    ],
    "Tally": ["Ties", "Off", "Check", "Pending"],
}  # fmt: skip

# The 3.3.1 / 3.2 objects that stand for each handoff object (the handoff's "Signature" is 3.3.1's
# Envelope, its "AJE" the Proposed entry, its "Session" the Workbench session; "Audit finding"
# spans the two audit-finding tables of 3.3.1).
HOME_OBJECTS = {
    "Engagement": ["engagement"],
    "Tax return": ["return"],
    "Return sync chip": ["return_sync_chip"],
    "Document": ["document"],
    "Audit": ["audit_engagement"],
    "Audit section": ["audit_section"],
    "Workpaper": ["audit_section"],
    "Close": ["close"],
    "Close task": ["close_task"],
    "Request": ["request"],
    "Inbox item": ["inbox_item"],
    "Issue": ["issue"],
    "Audit finding": ["deficiency_severity", "misstatement"],
    "Agent run": ["agent_run"],
    "AJE": ["proposed_entry"],
    "Session": ["workbench_session"],
    "Agent template": ["agent_template"],
    "Integration": ["integration"],
    "Signature": ["envelope"],
    "Notice": ["notice"],
    "Tally": ["tie_out_tally"],
}

# ---------------------------------------------------------------------------------------------
# OpenAPI: which fields are statuses, and which 3.3.1 object a few of them belong to.
# ---------------------------------------------------------------------------------------------
# Fields named `state` or `status` that are not an object status.
NOT_A_STATUS = {
    "FlowStepOut.state": "position of a step in a flow (done, current, todo)",
    "CompleteIn.state": "free-text input, not a vocabulary",
    # C5 v1.1 portal half (P-08-T01): client-side card states, never a firm object's status.
    "PortalHomeTodoOut.state": "a to-do card's state on POR-02 (open, none, overdue)",
    "PortalHomeStageOut.state": "a client stage's place in the tracker (done, current, upcoming)",
    # C5 section portal-pbc (R-01-T01): the client's words for a request (status-vocabulary's
    # `request.client_label`, To do · Done · Ignored · Returned, as codes) and the screens' own
    # control states, never a firm object's status (docs/contracts/portal-pbc.md §4).
    "PortalRowOut.client_status": "a request's client words (to_do, done, ignored, returned)",
    "PortalRequestOut.client_status": "a request's client words (to_do, done, ignored, returned)",
    "IgnoreUndoneOut.client_status": "a request's client words after an undo (to_do)",
    "PortalMarkDoneOut.state": "the Mark as Done button (tonal, ready, marked)",
    "PortalRoomRowOut.state": "a room row's sub-line (uploaded, due, in_review, returned)",
    # P-08-T10 (ADR-168): what a verified sign-in code leads to, not a stored object's status.
    "PortalSignInVerifyOut.state": "the sign-in step's outcome (signed_in, mfa_required, …)",
}
# The 3.3.1 object a field's literals must all belong to (named from the sources: Deficiency,
# Review note, Tie-out tally, Integration / connection, Proposed entry (AJE), Audit section /
# workpaper, Engagement, Request).
OBJECT_OF_FIELD = {
    "DeficiencyOut.status": "deficiency",
    "ReviewNoteOut.status": "review_note",
    "NoteOut.state": "review_note",
    "TieResultOut.status": "tie_out_tally",
    "ConnectionOut.status": "integration",
    "AdjustmentOut.status": "proposed_entry",
    "WorkpaperOut.status": "audit_section",
    "WorkingPaperOut.status": "audit_section",
    "EngagementOut.status": "engagement",
    "EngagementSummaryOut.status": "engagement",
    "RequestItemOut.status": "request",
    "ItemHitOut.status": "request",
    "DecisionOut.item_status": "request",
    # P-08-T01: contacts.portal_state, the DF-31 invitation words.
    "ContactPortalStatusOut.portal_status": "invitation",
}

# Findings: fields whose literals have no YAML entry anywhere. The reason names the literals.
NO_YAML_ENTRY = {
    # S6 batch B (#390, follow-ups v2): `drafted` has no status-vocabulary entry yet; recorded as
    # a finding for its owner, as the other rows here are.
    "FollowUpOut.status": "drafted",
    "AdjustmentOut.status": "client_accepted, client_declined",
    "GlImportOut.status": "waiting_for_tb",
    "LogEntryOut.status": "failed_validation",
    "MatrixRowOut.status": "needs_sign_off, open_notes",
    "RetrievalOut.status": "failed_validation",
    "SupportSessionOut.status": "ended",
    "WallOut.status": "removed",
    # Q-02-T38 (#395): the firm-export stub's codes; their words are G-02's screen copy, registered
    # when G-02-T11 adds the ADM-06 card (docs/contracts/compliance-kernel.md).
    "FirmExportOut.status": "awaiting_approval, building",
    # A-02-T06 (C20 v1 stub): a sync run's codes are RetrievalOut's (`sync_runs.status`), with the
    # same gap; registered with the details drawer's words (A-02-T18).
    "SyncRunRefOut.status": "failed_validation",
    "SyncRunSummaryOut.status": "failed_validation",
    # R-01-T16 (C16 v1.1 stub): the sender-domain codes; their words ("Pending DNS", "Verified")
    # are a DF-31 addition that must land before R-01-T28 (docs/screens/ADM-10.md, Open gaps).
    "SendingDomainOut.status": "pending_dns, verified, failed, revoked",
    # G-02-T04 (audit-log stub, DEC-417): the export's `building` and the values' `withheld` and
    # `unavailable` get their DF-31 entries with the live routes (G-02-T08, G-02-T17).
    "AuditExport.status": "building",
    "AuditValuesOut.status": "withheld, unavailable",
}
# Findings: fields with a literal outside the 3.3.1 object they belong to.
OUTSIDE_ITS_OBJECT = {
    "AdjustmentOut.status": "client_accepted, client_declined are not proposed_entry codes",
    "ConnectionOut.status": "active is the retired connection code (integration.connected)",
    "WorkpaperOut.status": "draft, ready are not audit_section codes",
}
# Findings: status fields typed as a bare string, so no literal can be checked.
UNTYPED = {
    "FileMatchOut.status", "GraphEngagementOut.status", "GraphItemOut.status",
    "ProcedureOut.status", "ReviewOut.status",
    # I-01-T01 (HOME contracts, #431): the home rows carry each owner's own status word as a
    # string until the HOME-01 build types them per source; recorded as findings like the rest.
    "DeadlineRowOut.status", "HomeTileOut.by_status", "WorkRowOut.status",
}  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------
def _placeholders(label: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", label).strip()


def _parse_table() -> dict[str, list[tuple[str, str]]]:
    parsed: dict[str, list[tuple[str, str]]] = {}
    for obj, block in TABLE.items():
        rows: list[tuple[str, str]] = []
        for line in block.strip().splitlines():
            label, variant = (part.strip() for part in line.rsplit("|", 1))
            assert variant in VARIANTS | {DISC, ANY}, (obj, line)
            rows.append((_placeholders(label), variant))
        parsed[obj] = rows
    return parsed


SOURCE_ROWS = _parse_table()
REGISTRY = cast(Json, yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text()))
OBJECTS = cast(dict[str, Json], REGISTRY["objects"])
HANDOFF = cast(dict[str, dict[str, Json]], REGISTRY["handoff_words"])
OPENAPI = cast(Json, json.loads(document()))
SCHEMAS = cast(dict[str, Json], OPENAPI["components"]["schemas"])


def _codes(obj: str) -> dict[str, Json]:
    return {str(code): cast(Json, entry) for code, entry in OBJECTS[obj]["codes"].items()}


def _entries() -> Iterator[tuple[str, str, Json]]:
    for obj in OBJECTS:
        for code, entry in _codes(obj).items():
            yield obj, code, entry


def _strings(entry: Json) -> list[str]:
    """Every display string an entry carries: its label, its context labels, its client label."""
    found = [cast(str, entry["label"])]
    found += [cast(str, v) for v in cast(Json, entry.get("context_labels", {})).values()]
    if "client_label" in entry:
        found.append(cast(str, entry["client_label"]))
    return found


def _with_label(obj: str, label: str) -> list[Json]:
    return [e for e in _codes(obj).values() if _placeholders(cast(str, e["label"])) == label]


def _shown_as(obj: str, label: str) -> bool:
    return any(_placeholders(s) == label for e in _codes(obj).values() for s in _strings(e))


# ---------------------------------------------------------------------------------------------
# 3.3.1 and 3.2 coverage
# ---------------------------------------------------------------------------------------------
def test_the_source_tables_restate_every_object_the_yaml_header_counts() -> None:
    assert len(STATUS_JS) == 21
    assert sum(len(words) for words in STATUS_JS.values()) == 144
    assert all(len(set(words)) == len(words) for words in STATUS_JS.values())


@pytest.mark.parametrize("obj", sorted(SOURCE_ROWS))
def test_every_source_object_has_a_yaml_object(obj: str) -> None:
    assert obj in OBJECTS, f"{obj} is in blueprint 3.3.1 or addendum 3.2 and has no YAML object"
    assert _codes(obj), f"{obj} has no codes"


# One mark per finding. SKIP-001 reads the reason as a literal, so each carries its own issue
# reference to its issue. The detail per field is in
# the dictionaries above and in the assertion message.
FINDING_LABEL = pytest.mark.xfail(
    strict=True,
    reason='F-03-T10 finding: tie_out_tally.reconciled is "Reconciled" but 3.3.1 displays '
    '"Reconciled ✓" (TASK-355 #206)',
)
FINDING_UNTYPED = pytest.mark.xfail(
    strict=True,
    reason="F-03-T10 finding: status field typed as a bare string, no literal to check "
    "(TASK-355 #207)",
)
FINDING_NO_ENTRY = pytest.mark.xfail(
    strict=True,
    reason="F-03-T10 finding: status literal with no YAML entry in any object, see "
    "NO_YAML_ENTRY (TASK-355 #208)",
)
FINDING_OUTSIDE = pytest.mark.xfail(
    strict=True,
    reason="F-03-T10 finding: status literal outside the 3.3.1 object its field belongs to, "
    "see OUTSIDE_ITS_OBJECT (TASK-355 #209)",
)
LABEL_FINDINGS = {("tie_out_tally", "Reconciled ✓")}


def _row_params() -> list[Any]:  # pytest.param objects, untyped by pytest
    params: list[Any] = []  # pytest.param objects
    for obj, rows in SOURCE_ROWS.items():
        for label, variant in rows:
            marks: list[pytest.MarkDecorator] = []
            if (obj, label) in LABEL_FINDINGS:
                marks.append(FINDING_LABEL)
            params.append(pytest.param(obj, label, variant, id=f"{obj}::{label}", marks=marks))
    return params


@pytest.mark.parametrize(("obj", "label", "variant"), _row_params())
def test_every_source_state_has_its_display_label_and_variant(
    obj: str, label: str, variant: str
) -> None:
    assert obj in OBJECTS, f"no YAML object {obj}"
    assert _shown_as(obj, label), f"{obj}: no code shows {label!r}"
    if variant == ANY:
        return
    primary = _with_label(obj, label)
    if not primary:  # the word is only a context label there: coverage is all the source fixes
        return
    variants = {cast("str | None", e.get("variant")) for e in primary}
    if variant == DISC:
        assert variants == {None}, (
            f"{obj} {label!r}: source gives a disc only, YAML has {variants}"
        )
    else:
        assert variant in variants, f"{obj} {label!r}: source says {variant}, YAML has {variants}"


@pytest.mark.parametrize(("obj", "words"), sorted(CLIENT_WORDS.items()))
def test_client_words_are_carried_as_client_labels(obj: str, words: set[str]) -> None:
    carried = {cast(str, e["client_label"]) for e in _codes(obj).values() if "client_label" in e}
    assert words <= carried, f"{obj}: missing client words {sorted(words - carried)}"


@pytest.mark.parametrize(("obj", "label"), sorted(DERIVED_BY_SOURCE.items()))
def test_words_the_sources_call_derived_are_derived_and_never_stored(obj: str, label: str) -> None:
    entries = {
        c: e for c, e in _codes(obj).items() if _placeholders(e["label"]) == _placeholders(label)
    }
    assert entries, f"{obj} has no code labelled {label!r}"
    for code, entry in entries.items():
        assert entry["derived"] is True, f"{obj}.{code} must be derived"
        assert code not in _statuses.STORED.get(obj, ()), f"{obj}.{code} is stored"


def test_no_overdue_or_past_due_code_is_stored_anywhere() -> None:
    for obj, code, entry in _entries():
        if "overdue" in code or "past_due" in code:
            assert entry["derived"] is True, f"{obj}.{code} must be derived"
            assert code not in _statuses.STORED.get(obj, ()), f"{obj}.{code} is stored"


# ---------------------------------------------------------------------------------------------
# Variants and sentence case
# ---------------------------------------------------------------------------------------------
def test_no_status_has_the_match_variant_or_a_variant_the_sources_do_not_name() -> None:
    for obj, code, entry in _entries():
        variants = {cast("str | None", entry.get("variant"))}
        variants |= {cast(str, v) for v in cast(Json, entry.get("context_variants", {})).values()}
        assert "match" not in variants, f"{obj}.{code} uses the source-tracing variant"
        assert variants - {None} <= VARIANTS, f"{obj}.{code}: unknown variant in {variants}"


def _not_sentence_case(text: str) -> bool:
    if text in LOWER_CASE_BY_SOURCE:
        return False
    plain = re.sub(r"^[^\w{]+", "", _placeholders(text))  # a leading glyph is not a word
    words = [w.strip("()…?,.:;") for w in re.split(r"[\s\u00b7\u2014\u2013]+", plain)]
    words = [w for w in words if w and w != "{}" and w[0].isalpha()]
    if not words:
        return False  # a glyph and a placeholder only
    # A label that opens with a placeholder or a glyph has no first word to capitalise.
    opens_with_word = plain[0].isalpha()
    if opens_with_word and not words[0][0].isupper():
        return True
    rest = words[1:] if opens_with_word else words
    return any(w[0].isupper() and not w.isupper() and w not in CAPITALISED_BY_SOURCE for w in rest)


def test_every_label_is_sentence_case() -> None:
    offenders = [
        f"{obj}.{code}: {s!r}"
        for obj, code, entry in _entries()
        for s in _strings(entry)
        if _not_sentence_case(s)
    ]
    assert not offenders, offenders


# ---------------------------------------------------------------------------------------------
# status.js: the 144 words
# ---------------------------------------------------------------------------------------------
def _word_params() -> list[tuple[str, str]]:
    return [(obj, word) for obj, words in STATUS_JS.items() for word in words]


def test_the_yaml_lists_exactly_the_words_in_status_js() -> None:
    assert set(HANDOFF) == set(STATUS_JS)
    for obj, words in STATUS_JS.items():
        assert list(HANDOFF[obj]) == words, obj


@pytest.mark.parametrize(("obj", "word"), _word_params(), ids=lambda v: str(v))
def test_every_status_js_word_is_mapped_to_a_real_code_or_marked_as_having_none(
    obj: str, word: str
) -> None:
    entry = HANDOFF[obj][word]
    if entry.get("status") is False:
        assert str(entry.get("reason", "")).strip(), f"{obj}.{word}: no reason given"
        return
    target, code = cast(str, entry["object"]), str(entry["code"])
    assert target in OBJECTS, f"{obj}.{word} -> unknown object {target}"
    assert code in _codes(target), f"{obj}.{word} -> {target}.{code} does not exist"


@pytest.mark.parametrize(("obj", "word"), _word_params(), ids=lambda v: str(v))
def test_a_status_js_word_that_is_a_label_on_its_3_3_1_object_maps_there(
    obj: str, word: str
) -> None:
    entry = HANDOFF[obj][word]
    homes = HOME_OBJECTS[obj]
    same = [
        (home, code)
        for home in homes
        for code, e in _codes(home).items()
        if _placeholders(cast(str, e["label"])).lower() == word.lower()
    ]
    if not same:
        return
    assert entry.get("status") is not False, f"{obj}.{word} is 3.3.1's {same} but marked unmapped"
    assert (entry["object"], str(entry["code"])) in same, (
        f"{obj}.{word} maps to {entry['object']}.{entry['code']}; 3.3.1 has {same}"
    )


def test_no_status_js_word_maps_onto_a_derived_code_unless_its_meaning_is_derived() -> None:
    derived_words = {("Request", "Overdue"), ("Notice", "Response overdue")}
    for obj, word in _word_params():
        entry = HANDOFF[obj][word]
        if entry.get("status") is False:
            continue
        code_entry = _codes(entry["object"])[str(entry["code"])]
        if code_entry["derived"] is True:
            assert (obj, word) in derived_words or "overdue" not in word.lower(), (obj, word)


# ---------------------------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------------------------
def _is_status_name(name: str) -> bool:
    return name in {"status", "state"} or name.endswith("_status")


def _status_fields() -> dict[str, Json]:
    """Every `status` / `*_status` / `state` property of every schema, by `Schema.field`."""
    found: dict[str, Json] = {}
    for schema, definition in SCHEMAS.items():
        for name, prop in cast(dict[str, Json], definition.get("properties", {})).items():
            key = f"{schema}.{name}"
            if _is_status_name(name) and key not in NOT_A_STATUS and prop.get("type") != "object":
                found[key] = prop
    return found


def _literals(prop: Json) -> list[str] | None:
    if "enum" in prop:
        return [str(v) for v in prop["enum"]]
    # A one-value `Literal["drafting"]` is emitted as `const` (C11's render ticket).
    if "const" in prop:
        return [str(prop["const"])]
    # An optional status (`Literal[...] | None`) is the enum beside a null (G-02-T11); a union of
    # enums (`FirmStandardVersionStatus | Literal["superseded"]`, K-02) is every member's values,
    # and is an enum only when each member is.
    variants = [v for v in prop.get("anyOf", []) if v.get("type") != "null"]
    if len(variants) == 1:
        return _literals(variants[0])
    if len(variants) > 1:
        parts = [_literals(v) for v in variants]
        if all(p is not None for p in parts):
            return [code for p in parts if p is not None for code in p]
        return None
    if "$ref" in prop:
        target = SCHEMAS[str(prop["$ref"]).rsplit("/", 1)[1]]
        return [str(v) for v in target["enum"]] if "enum" in target else None
    return None


STATUS_FIELDS = _status_fields()
ALL_CODES = {code for obj in OBJECTS for code in _codes(obj)}


def _field_params(
    known: set[str] | dict[str, str], finding: pytest.MarkDecorator
) -> list[Any]:  # pytest.param objects, untyped by pytest
    params: list[Any] = []  # pytest.param objects
    for key in sorted(STATUS_FIELDS):
        marks = [finding] if key in known else []
        params.append(pytest.param(key, id=key, marks=marks))
    return params


@pytest.mark.parametrize("field", _field_params(UNTYPED, FINDING_UNTYPED))
def test_every_openapi_status_field_is_an_enum(field: str) -> None:
    assert _literals(STATUS_FIELDS[field]) is not None, f"{field} is not an enum"


@pytest.mark.parametrize("field", _field_params(NO_YAML_ENTRY, FINDING_NO_ENTRY))
def test_every_openapi_status_literal_has_a_yaml_entry(field: str) -> None:
    literals = _literals(STATUS_FIELDS[field])
    if literals is None:
        return  # the untyped fields are the previous test's finding
    missing = [v for v in literals if v not in ALL_CODES]
    assert not missing, f"{field}: no YAML entry for {missing}"


def _object_params() -> list[Any]:  # pytest.param objects, untyped by pytest
    params: list[Any] = []  # pytest.param objects
    for key in sorted(OBJECT_OF_FIELD):
        marks = [FINDING_OUTSIDE] if key in OUTSIDE_ITS_OBJECT else []
        params.append(pytest.param(key, id=key, marks=marks))
    return params


@pytest.mark.parametrize("field", _object_params())
def test_an_openapi_status_field_uses_only_codes_of_its_own_object(field: str) -> None:
    assert field in STATUS_FIELDS, f"{field} is not an OpenAPI status field any more"
    literals = _literals(STATUS_FIELDS[field])
    assert literals is not None
    outside = [v for v in literals if v not in _codes(OBJECT_OF_FIELD[field])]
    assert not outside, f"{field}: {outside} are not {OBJECT_OF_FIELD[field]} codes"


def test_the_known_openapi_gaps_still_name_real_fields() -> None:
    for key in set(NO_YAML_ENTRY) | set(OUTSIDE_ITS_OBJECT) | UNTYPED | set(OBJECT_OF_FIELD):
        assert key in STATUS_FIELDS, f"{key} is no longer an OpenAPI status field: update the list"
    assert set(NOT_A_STATUS) <= {
        f"{s}.{n}" for s, d in SCHEMAS.items() for n in cast(Json, d.get("properties", {}))
    }
