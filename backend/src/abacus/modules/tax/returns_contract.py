"""Tax returns v1, the contract (T-02-T01; T-02 §4.3; C1 additive). Contract:
`docs/contracts/tax-returns.md`.

The practice board and the return workspace: TAX-01's rows and tiles, the `ReturnFrame` record
TAX-02 and TAX-03 sit in, TAX-02's overview composite, TAX-03's intake composite, assignment and
the person-gated status transitions. Final approval is T-01's (`tax/approval.py`, through
`tax.api`); T-02 declares none of its routes. Status words are the registry's `return` object;
"Ready" is `approved`'s tile word.

The routes live in `returns_routes.py`: the board's (list, summary, assignment) since T-02-T09,
the record, overview, intake and transitions 501 until T-02-T13.

Classification (ADR-031): figures are TRI; client and people names are confidential; codes and ids
are internal. No TIN appears.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import K1HandoffStatus, ReturnStatus, ReturnSyncChipStatus
from abacus.kernel.classification import classified

Form = Literal["1040", "1041", "1065", "1120s", "1120", "990", "706", "709", "1040x"]
ReviewLevel = Literal["detail", "manager", "partner"]
AssignmentRole = Literal["preparer", "reviewer", "signer"]
TransitionEvent = Literal["start_preparation", "start_review"]
# TAX-02 (T-02-T14): a step's disc (01 §3.3.1: olive ✓, half disc, empty ring).
StepState = Literal["done", "in_progress", "not_started"]
LadderStep = Literal[
    "preparer", "detail_review", "manager_review", "partner_review", "final_approval"
]
PipelineStep = Literal["gather", "prepare", "review", "deliver"]
IssueSeverity = Literal["high", "medium", "low"]
IssueKind = Literal["missing_information", "action_required", "review_point"]
RecordLinkKey = Literal["client", "engagement", "binder", "files", "relationships"]
FilingKey = Literal["due", "extension", "jurisdictions", "engine", "consents", "office"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class PersonChipOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    initials: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]


class TaxReturnSignerOut(BaseModel):
    """A C7 signer chip on a row awaiting signature (T-02-T12): who, and whether they signed."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    signed: Annotated[bool, classified("internal")]


class TaxReturnRowOut(BaseModel):
    """One TAX-01 row."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    form: Annotated[Form, classified("internal")]
    tax_year: Annotated[int, classified("internal")]
    status: Annotated[ReturnStatus, classified("internal")]
    review_level: Annotated[ReviewLevel | None, classified("internal")]
    extended: Annotated[bool, classified("internal")]
    on_hold: Annotated[bool, classified("internal")]
    sync: Annotated[ReturnSyncChipStatus | None, classified("internal")]
    preparer: Annotated[PersonChipOut | None, classified("confidential")]
    reviewer: Annotated[PersonChipOut | None, classified("confidential")]
    signer: Annotated[PersonChipOut | None, classified("confidential")]
    office_id: Annotated[UUID | None, classified("internal")]
    original_due_on: Annotated[date | None, classified("internal")]
    extended_due_on: Annotated[date | None, classified("internal")]
    # The C21 rule that produced the due date, as a code ("1065 · 15th day of 3rd month").
    due_rule_code: Annotated[str | None, classified("internal")]
    tags: Annotated[list[str], classified("internal")]
    # T-02-T12 (additive): the C3 open-issue count (null renders "—") and the C7 signer chips.
    issues: Annotated[int | None, classified("internal")] = None
    signers: Annotated[list[TaxReturnSignerOut], classified("confidential")] = Field(
        default_factory=list[TaxReturnSignerOut]
    )


class StatusTileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[ReturnStatus, classified("internal")]
    count: Annotated[int, classified("internal")]


class OfficeTotalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    office_id: Annotated[UUID, classified("internal")]
    open: Annotated[int, classified("internal")]
    done: Annotated[int, classified("internal")]


class TaxReturnSummaryOut(BaseModel):
    """TAX-01 tiles: per canonical status, open and done, extended, office totals (wall-safe)."""

    model_config = ConfigDict(frozen=True)

    tax_year: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    open: Annotated[int, classified("internal")]
    done: Annotated[int, classified("internal")]
    extended: Annotated[int, classified("internal")]
    tiles: Annotated[list[StatusTileOut], classified("internal")]
    offices: Annotated[list[OfficeTotalOut], classified("internal")]


class TabCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tab: Annotated[str, classified("internal")]
    count: Annotated[int | None, classified("internal")]


class TaxReturnRecordOut(BaseModel):
    """The `ReturnFrame`: subbar, tab counts and what the viewer may do."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[TaxReturnRowOut, classified("confidential")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    engine_return_id: Annotated[str | None, classified("confidential")]
    approval_policy_version_id: Annotated[UUID | None, classified("internal")]
    tabs: Annotated[list[TabCountOut], classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-02-T14 (additive): what the OverviewCard's sub adds after the client ("Married filing
    # jointly", or the office: "Denver"; an entity return names its kind) and the engine's deep
    # link ("Open in CCH Axcess"; https, built server-side from `engine_return_id`, null when the
    # return has no engine id).
    card_detail: Annotated[str | None, classified("confidential")] = None
    engine_url: Annotated[str | None, classified("internal")] = None


class EngineSummaryLineOut(BaseModel):
    """One engine figure from an approved import only (ADR-231)."""

    model_config = ConfigDict(frozen=True)

    line_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    # Null renders "—" (a line the engine left blank, as 2a on the Feld estimate).
    amount: Annotated[Decimal | None, classified("restricted", tri=True)]
    # T-02-T14 (additive): the statement grammar. `line_ref` is the form's line ("1a",
    # "Sch 1 line 5"); `indent` a sub-line (3a under 3b); `total` a total or the double-ruled
    # grand total; `note` the amber ⚑ line under it, with `issue` when it names a C3 issue.
    line_ref: Annotated[str | None, classified("internal")] = None
    indent: Annotated[bool, classified("internal")] = False
    total: Annotated[Literal["total", "grand"] | None, classified("internal")] = None
    note: Annotated[str | None, classified("restricted", tri=True)] = None
    issue: Annotated[bool, classified("internal")] = False


class LadderStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Annotated[AssignmentRole, classified("internal")]
    person: Annotated[PersonChipOut | None, classified("confidential")]
    signed_off_at: Annotated[datetime | None, classified("confidential")]
    # T-02-T14 (additive): the Team band's PhaseRow. `step` names the rung (the role alone does
    # not: three reviewer levels); `note` is the sub-line as the read model words it ("Kevin Osei ·
    # submitted Sep 8", "LW · not started"; null draws "Not assigned"); `blocked_by` is the amber
    # second line ("Draft K-1 · pre-release").
    step: Annotated[LadderStep | None, classified("internal")] = None
    state: Annotated[StepState, classified("internal")] = "not_started"
    note: Annotated[str | None, classified("confidential")] = None
    blocked_by: Annotated[str | None, classified("confidential")] = None


class K1DependencyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_return_id: Annotated[UUID | None, classified("internal")]
    issuer_name: Annotated[str, classified("confidential")]
    status: Annotated[K1HandoffStatus, classified("internal")]
    # T-02-T14 (additive): the dependency banner's words ("Ridgeline 1065", "Ridgeline") and the
    # source return's due date.
    source_label: Annotated[str | None, classified("confidential")] = None
    short_name: Annotated[str | None, classified("confidential")] = None
    source_due_on: Annotated[date | None, classified("internal")] = None
    # Final approval waits on this K-1 (the amber dependency banner).
    blocking: Annotated[bool, classified("internal")] = False


class RecordLinkOut(BaseModel):
    """A Record band row on TAX-02's rail (Client, Engagement, Binder, Files, Relationships)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[RecordLinkKey, classified("internal")]
    sub: Annotated[str, classified("confidential")]
    target_id: Annotated[UUID | None, classified("internal")] = None


class FilingRowOut(BaseModel):
    """A Filing band KV row (and the gathering state's pro forma rows)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[FilingKey, classified("internal")]
    value: Annotated[str, classified("confidential")]
    # The consents row's green micro pill ("Signed · expires Dec 31 2026") and its ink-3 detail.
    pill: Annotated[str | None, classified("confidential")] = None
    detail: Annotated[str | None, classified("confidential")] = None


class LabelValueOut(BaseModel):
    """A KV row whose key is the import's own label (the pro forma's "2024 AGI")."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    value: Annotated[str, classified("restricted", tri=True)]


class PipelineStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: Annotated[PipelineStep, classified("internal")]
    state: Annotated[StepState, classified("internal")]
    sub: Annotated[str, classified("confidential")]


class TaxPlanRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    detail: Annotated[str | None, classified("restricted", tri=True)] = None
    state: Annotated[StepState, classified("internal")]


class K1ClassificationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_name: Annotated[str, classified("confidential")]
    tags: Annotated[list[str], classified("confidential")]
    # The hand-off's pill ("Draft K-1 · pre-release", "Waiting on K-1" in state amber; "Released
    # Sep 15" green), worded by the read model from the C10 hand-off.
    pill: Annotated[str | None, classified("confidential")] = None
    pill_tone: Annotated[Literal["state", "green"] | None, classified("internal")] = None


class OverviewIssueOut(BaseModel):
    """One of the top open C3 issues (severity drives the flag's colour)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    kind: Annotated[IssueKind, classified("internal")]
    severity: Annotated[IssueSeverity, classified("internal")]


class TwoYearStatOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[Literal["agi", "total_tax", "refund"], classified("internal")]
    prior: Annotated[Decimal, classified("restricted", tri=True)]
    current: Annotated[Decimal, classified("restricted", tri=True)]
    # Computed server-side, one decimal (code computes; the screen never does arithmetic).
    change_pct: Annotated[Decimal | None, classified("restricted", tri=True)]


class TaxReturnOverviewOut(BaseModel):
    """TAX-02: the team ladder, pipeline, filing band, engine summaries, top issues and K-1
    dependencies."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    ladder: Annotated[list[LadderStepOut], classified("confidential")]
    engine_version: Annotated[str | None, classified("confidential")]
    engine_summary: Annotated[list[EngineSummaryLineOut], classified("restricted", tri=True)]
    open_issues: Annotated[int, classified("internal")]
    k1_dependencies: Annotated[list[K1DependencyOut], classified("confidential")]
    consent_ok: Annotated[bool | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-02-T14 (additive): the rest of TAX-02's rail and canvas, composed by T-02-T13's read
    # model. Empty lists draw no band or card (no invented rows).
    record_links: Annotated[list[RecordLinkOut], classified("confidential")] = Field(
        default_factory=list[RecordLinkOut]
    )
    filing: Annotated[list[FilingRowOut], classified("confidential")] = Field(
        default_factory=list[FilingRowOut]
    )
    pipeline: Annotated[list[PipelineStepOut], classified("confidential")] = Field(
        default_factory=list[PipelineStepOut]
    )
    engine_synced_on: Annotated[date | None, classified("internal")] = None
    engine_footnote: Annotated[str | None, classified("restricted", tri=True)] = None
    # The gathering state: the pro forma's import label and KV rows in place of the estimate.
    pro_forma_label: Annotated[str | None, classified("confidential")] = None
    pro_forma: Annotated[list[LabelValueOut], classified("restricted", tri=True)] = Field(
        default_factory=list[LabelValueOut]
    )
    plan: Annotated[list[TaxPlanRowOut], classified("restricted", tri=True)] = Field(
        default_factory=list[TaxPlanRowOut]
    )
    k1_classifications: Annotated[list[K1ClassificationOut], classified("confidential")] = Field(
        default_factory=list[K1ClassificationOut]
    )
    carryforwards: Annotated[str | None, classified("restricted", tri=True)] = None
    issues: Annotated[list[OverviewIssueOut], classified("confidential")] = Field(
        default_factory=list[OverviewIssueOut]
    )
    two_year: Annotated[list[TwoYearStatOut], classified("restricted", tri=True)] = Field(
        default_factory=list[TwoYearStatOut]
    )


class IntakeCategoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    requested: Annotated[int, classified("internal")]
    received: Annotated[int, classified("internal")]
    # T-02-T18 (additive): the category's words, as the binder names it.
    label: Annotated[str | None, classified("internal")] = None


class IntakeBinderOut(BaseModel):
    """T-02-T18: the rail's binder card ("2025 Binder · Published Feb 3 · Kevin Osei")."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    status: Annotated[str, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]
    published_by_name: Annotated[str | None, classified("confidential")]
    marked_done_at: Annotated[datetime | None, classified("internal")]
    marked_done_by_name: Annotated[str | None, classified("confidential")]
    last_upload_at: Annotated[datetime | None, classified("internal")]


class IntakeDuplicateOut(BaseModel):
    """A flagged duplicate upload on the request (T-02-T17), for Keep newer or Discard duplicate."""

    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]


class IntakeRequestOut(BaseModel):
    """T-02-T18: one request row with what answers it (file name and channel) or its asking."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    category: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    overdue: Annotated[bool, classified("internal")]
    requested_at: Annotated[datetime | None, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]
    latest_version_id: Annotated[UUID | None, classified("internal")]
    file_name: Annotated[str | None, classified("confidential")]
    uploaded_on: Annotated[date | None, classified("internal")]
    channel: Annotated[str | None, classified("internal")]
    linked_count: Annotated[int | None, classified("internal")]
    owed_by: Annotated[str | None, classified("confidential")]
    # T-02-T19 (TAX-03 e): the client's repeat of the filed copy, flagged and not yet resolved.
    duplicate: Annotated[IntakeDuplicateOut | None, classified("internal")] = None


class IntakeSuggestionOut(BaseModel):
    """The matcher's top proposal for a waiting file (the agent proposes; a person files)."""

    model_config = ConfigDict(frozen=True)

    request_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    confidence: Annotated[int, classified("internal")]  # 0-100


class IntakeWaitingFileOut(BaseModel):
    """T-02-T18: one inbox file waiting on the client, with code's flags ("2024 ≠ 2025")."""

    model_config = ConfigDict(frozen=True)

    attachment_id: Annotated[UUID, classified("internal")]
    thread_id: Annotated[UUID, classified("internal")]
    # T-02-T19: the message the file came with, which N-01's triage apply files or ignores on.
    message_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    channel: Annotated[str, classified("internal")]
    sender: Annotated[str, classified("confidential")]
    subject: Annotated[str, classified("confidential")]
    received_at: Annotated[datetime, classified("internal")]
    # The extracted tax year when the viewer may see extracted values (absent for client service).
    tax_year: Annotated[int | None, classified("internal")]
    wrong_year: Annotated[bool, classified("internal")]
    duplicate: Annotated[bool, classified("internal")]
    flags: Annotated[list[str], classified("internal")]
    suggestion: Annotated[IntakeSuggestionOut | None, classified("internal")]


class IntakeQuestionnaireOut(BaseModel):
    """T-02-T18: a Questions band row; answers are POR-05's, read in their own drawer."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    answered: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    submitted_at: Annotated[datetime | None, classified("internal")]
    submitted_by_name: Annotated[str | None, classified("confidential")]


SuggestionsState = Literal["shown", "consent_missing", "agents_off", "hidden"]


class TaxReturnIntakeOut(BaseModel):
    """TAX-03: binder card, categories, requests and files, questionnaires and K-1 hand-offs."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID | None, classified("internal")]
    categories: Annotated[list[IntakeCategoryOut], classified("internal")]
    waiting_files: Annotated[int, classified("internal")]
    questionnaire_ids: Annotated[list[UUID], classified("internal")]
    k1_handoffs: Annotated[list[K1DependencyOut], classified("confidential")]
    # T-02-T18 additions, each with a default.
    tax_year: Annotated[int | None, classified("internal")] = None
    binder: Annotated[IntakeBinderOut | None, classified("internal")] = None
    requests_total: Annotated[int, classified("internal")] = 0
    requests_received: Annotated[int, classified("internal")] = 0
    requests: Annotated[list[IntakeRequestOut], classified("confidential")] = []
    waiting: Annotated[list[IntakeWaitingFileOut], classified("confidential")] = []
    # Whether the dock shows the matcher's suggestions, or the DF-04 line and why (DV-7).
    suggestions: Annotated[SuggestionsState, classified("internal")] = "agents_off"
    questionnaires: Annotated[list[IntakeQuestionnaireOut], classified("confidential")] = []
    allowed_actions: Annotated[list[str], classified("internal")] = []


class AssignmentIn(BaseModel):
    model_config = _frozen()

    role: Annotated[AssignmentRole, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class BulkAssignIn(BaseModel):
    model_config = _frozen()

    return_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]
    role: Annotated[AssignmentRole, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class BulkAssignOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    assigned: Annotated[int, classified("internal")]
    refused: Annotated[list[UUID], classified("internal")]


class TransitionIn(BaseModel):
    """A person's move; the person-gated moves (approval, filing) are not here (409 `{gate}`)."""

    model_config = _frozen()

    event: Annotated[TransitionEvent, classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]
