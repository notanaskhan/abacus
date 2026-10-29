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


class EngineSummaryLineOut(BaseModel):
    """One engine figure from an approved import only (ADR-231)."""

    model_config = ConfigDict(frozen=True)

    line_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    amount: Annotated[Decimal, classified("restricted", tri=True)]


class LadderStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Annotated[AssignmentRole, classified("internal")]
    person: Annotated[PersonChipOut | None, classified("confidential")]
    signed_off_at: Annotated[datetime | None, classified("confidential")]


class K1DependencyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_return_id: Annotated[UUID | None, classified("internal")]
    issuer_name: Annotated[str, classified("confidential")]
    status: Annotated[K1HandoffStatus, classified("internal")]


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


class IntakeCategoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    requested: Annotated[int, classified("internal")]
    received: Annotated[int, classified("internal")]


class TaxReturnIntakeOut(BaseModel):
    """TAX-03: binder card, categories, requests and files, questionnaires and K-1 hand-offs."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID | None, classified("internal")]
    categories: Annotated[list[IntakeCategoryOut], classified("internal")]
    waiting_files: Annotated[int, classified("internal")]
    questionnaire_ids: Annotated[list[UUID], classified("internal")]
    k1_handoffs: Annotated[list[K1DependencyOut], classified("confidential")]


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
