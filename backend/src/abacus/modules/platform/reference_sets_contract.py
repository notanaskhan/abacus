"""C21 v1 part A, the contract: platform reference sets (K-02-T02; K-02 §4.2, §4.3, §4.4, §4.5).
Contract: `docs/contracts/rules-tables.md`. ADR-300 (P-62) binds.

Reference sets are global tables of public law (due-date rules, legal holidays, disaster
postponements, the 8879 form set with Pub 1345 tolerances, information-return thresholds,
retention minimums and standards sets), published as immutable, effective-dated versions under a
two-person rule. Rules are database rows, never constants (AGENTS 16): nothing here carries a
rule's value.

The routes live in `reference_sets_routes.py` and the service in `reference_sets.py` (K-02-T05).
There are no write routes: the operator CLI (K-02-T06) is the only writer until PLT-01 (G-04).

The module APIs (`reference_value` and the typed readers) have signatures frozen with C21 (S17);
T-01's and T-02's consumer contract tests import them. Every result names the version it was
read from (INV-2 provenance).

Classification (ADR-031): reference payloads are public law, `public`; a version's handles and
reason are `internal`. No reference set holds TRI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import ReferenceSetVersionStatus
from abacus.kernel.classification import classified

# The seven kinds of ADR-300 (`state_breach_matrix` and `state_retention_rules` are reserved for
# Q-05, which writes their schemas).
ReferenceSetKind = Literal[
    "due_date_rules",
    "legal_holidays",
    "disaster_postponements",
    "form_8879_set",
    "information_return_thresholds",
    "retention_minimums",
    "standards_sets",
]
Jurisdiction = Literal["US", "DC"]
SetKey = Annotated[str, Field(pattern=r"^[a-z0-9_.]{3,80}$")]
PayloadHash = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Usd = Annotated[int, Field(ge=0)]  # whole dollars


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- payloads, one per kind (payload_schema_version 1) -------------------------------------------


class DueDateOffset(BaseModel):
    """When a return is due: the day of the month that falls this many months after period end."""

    model_config = _frozen()

    months_after_period_end: Annotated[int, Field(ge=0, le=24), classified("public")]
    day: Annotated[int, Field(ge=1, le=31), classified("public")]


class DueDateExtension(BaseModel):
    model_config = _frozen()

    form: Annotated[str, Field(min_length=1, max_length=20), classified("public")]  # "4868"
    months: Annotated[int, Field(ge=1, le=12), classified("public")]


class DueDateRuleRow(BaseModel):
    """One form's rule: 1040/4868, 1041/7004, 1065/7004, 1120-S/7004, 1120/7004, 990/8868,
    5500/5558, 706/4768, 709 (each verified per season, outside the repo)."""

    model_config = _frozen()

    form: Annotated[str, Field(min_length=1, max_length=20), classified("public")]
    fye_rule: Annotated[Literal["calendar_year", "fiscal_year", "any"], classified("public")]
    original: Annotated[DueDateOffset, classified("public")]
    extension: Annotated[DueDateExtension | None, classified("public")]
    authority: Annotated[str, Field(min_length=1, max_length=200), classified("public")]


class DueDateRulesPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["due_date_rules"], classified("public")]
    rows: Annotated[
        list[DueDateRuleRow], Field(min_length=1, max_length=200), classified("public")
    ]


class LegalHoliday(BaseModel):
    model_config = _frozen()

    date: Annotated[date, classified("public")]
    name: Annotated[str, Field(min_length=1, max_length=100), classified("public")]
    jurisdiction: Annotated[Jurisdiction, classified("public")]  # DC Emancipation Day is "DC"


class LegalHolidaysPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["legal_holidays"], classified("public")]
    rows: Annotated[list[LegalHoliday], Field(min_length=1, max_length=200), classified("public")]


class PostponementArea(BaseModel):
    model_config = _frozen()

    # A USPS state code, not a status (named so the status-vocabulary check leaves it alone).
    state_code: Annotated[str, Field(pattern=r"^[A-Z]{2}$"), classified("public")]
    # Empty: the whole state.
    counties: Annotated[list[str], Field(max_length=300), classified("public")]


class PostponementWindow(BaseModel):
    model_config = _frozen()

    start: Annotated[date, classified("public")]
    end: Annotated[date, classified("public")]


class DisasterPostponement(BaseModel):
    model_config = _frozen()

    notice_id: Annotated[str, Field(min_length=1, max_length=40), classified("public")]
    areas: Annotated[list[PostponementArea], Field(min_length=1), classified("public")]
    window: Annotated[PostponementWindow, classified("public")]
    postponed_to: Annotated[date, classified("public")]
    acts: Annotated[list[str], Field(max_length=50), classified("public")]


class DisasterPostponementsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["disaster_postponements"], classified("public")]
    rows: Annotated[list[DisasterPostponement], Field(max_length=500), classified("public")]


class Form8879Row(BaseModel):
    """Which authorization form a return type uses (older revisions allowed: 8879-C and 8879-S
    for TY2025)."""

    model_config = _frozen()

    return_type: Annotated[str, Field(min_length=1, max_length=20), classified("public")]
    tax_year: Annotated[int, Field(ge=2000, le=2100), classified("public")]
    jurisdiction: Annotated[Jurisdiction, classified("public")]
    authorization_form: Annotated[str, Field(min_length=1, max_length=20), classified("public")]
    revision: Annotated[str, Field(min_length=1, max_length=20), classified("public")]


class Pub1345Tolerances(BaseModel):
    """DEC-85: the amounts past which a signed 8879 must be relocked (verified each season,
    never defaulted)."""

    model_config = _frozen()

    total_income_or_agi_usd: Annotated[Usd, classified("public")]
    tax_withholding_refund_balance_usd: Annotated[Usd, classified("public")]


class Form8879SetPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["form_8879_set"], classified("public")]
    rows: Annotated[list[Form8879Row], Field(min_length=1, max_length=100), classified("public")]
    tolerances: Annotated[Pub1345Tolerances, classified("public")]


class InformationReturnThreshold(BaseModel):
    model_config = _frozen()

    form: Annotated[str, Field(min_length=1, max_length=20), classified("public")]  # "1099-NEC"
    payment_year: Annotated[int, Field(ge=2000, le=2100), classified("public")]
    threshold_usd: Annotated[Usd, classified("public")]
    min_transactions: Annotated[int | None, Field(ge=0), classified("public")]


class InformationReturnThresholdsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["information_return_thresholds"], classified("public")]
    rows: Annotated[
        list[InformationReturnThreshold], Field(min_length=1, max_length=100), classified("public")
    ]


class RetentionMinimum(BaseModel):
    """DEC-71 (counsel-approved, never defaulted): a legal floor per record type and line."""

    model_config = _frozen()

    record_type: Annotated[str, Field(min_length=1, max_length=60), classified("public")]
    service_line: Annotated[str, Field(min_length=1, max_length=40), classified("public")]
    floor_years: Annotated[int, Field(ge=0, le=100), classified("public")]
    anchor: Annotated[str, Field(min_length=1, max_length=60), classified("public")]
    authority: Annotated[str, Field(min_length=1, max_length=200), classified("public")]


class RetentionMinimumsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["retention_minimums"], classified("public")]
    rows: Annotated[
        list[RetentionMinimum], Field(min_length=1, max_length=500), classified("public")
    ]


StandardsFamily = Literal["gaas_nonissuer", "ssars", "sqms"]


class StandardsSetRow(BaseModel):
    """A standards set K-01's KNW-02d maps to. No PCAOB or issuer family exists (X-07, DEC-19);
    a published code is never removed or moved to another family (K-02-T05 validates)."""

    model_config = _frozen()

    # K-01's `standards_sets.code` CHECK (0180).
    code: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,59}$"), classified("public")]
    label: Annotated[str, Field(min_length=1, max_length=200), classified("public")]
    standard_refs: Annotated[list[str], Field(max_length=100), classified("public")]
    family: Annotated[StandardsFamily, classified("public")]


class StandardsSetsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["standards_sets"], classified("public")]
    rows: Annotated[
        list[StandardsSetRow], Field(min_length=1, max_length=100), classified("public")
    ]


ReferencePayload = Annotated[
    DueDateRulesPayload
    | LegalHolidaysPayload
    | DisasterPostponementsPayload
    | Form8879SetPayload
    | InformationReturnThresholdsPayload
    | RetentionMinimumsPayload
    | StandardsSetsPayload,
    Field(discriminator="kind"),
]


# --- sets, versions and resolution ---------------------------------------------------------------


class ReferenceSourceCitationOut(BaseModel):
    """Where a version's rows come from, e.g. "Pub 1345 (rev.) — verify"."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("public")]
    url: Annotated[str | None, classified("public")] = None


class ReferenceSetVersionOut(BaseModel):
    """One published (or withdrawn) version. Drafts are never served (ADR-300); superseded is
    computed at read time: a later published version is effective on or before `as_of`."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    set_key: Annotated[str, classified("public")]
    version: Annotated[int, classified("public")]
    status: Annotated[ReferenceSetVersionStatus, classified("internal")]
    tax_year: Annotated[int | None, classified("public")]
    effective_from: Annotated[date, classified("public")]
    payload_schema_version: Annotated[int, classified("internal")]
    payload_hash: Annotated[str, classified("internal")]
    source_citations: Annotated[list[ReferenceSourceCitationOut], classified("public")]
    # The operator and approver handles (INV-5): two different people.
    drafted_by: Annotated[str, classified("internal")]
    approved_by: Annotated[str | None, classified("internal")]
    change_reason: Annotated[str, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]
    payload: Annotated[ReferencePayload, classified("public")]


class ReferenceSetOut(BaseModel):
    """A set and the version in effect today (none before its first publish)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("public")]
    kind: Annotated[ReferenceSetKind, classified("public")]
    jurisdiction: Annotated[str | None, classified("public")]
    title: Annotated[str, classified("public")]
    content_owner: Annotated[str, classified("internal")]
    description: Annotated[str | None, classified("public")]
    current_version: Annotated[int | None, classified("public")]
    current_effective_from: Annotated[date | None, classified("public")]


class ReferenceSetResolvedOut(BaseModel):
    """The version in effect on `as_of`: the latest `effective_from` on or before it, ties to the
    highest version."""

    model_config = ConfigDict(frozen=True)

    set: Annotated[ReferenceSetOut, classified("public")]
    as_of: Annotated[date, classified("public")]
    version: Annotated[ReferenceSetVersionOut, classified("public")]


# --- C21 part A module API results (frozen S17; `reference_sets.py` builds them) ----------------


@dataclass(frozen=True)
class ResolvedReference:
    """A set resolved on a date, with the version id the consumer stores."""

    key: str
    kind: ReferenceSetKind
    as_of: date
    version_id: UUID
    version: int
    effective_from: date
    payload: (
        DueDateRulesPayload
        | LegalHolidaysPayload
        | DisasterPostponementsPayload
        | Form8879SetPayload
        | InformationReturnThresholdsPayload
        | RetentionMinimumsPayload
        | StandardsSetsPayload
    )
    # Additive (K-02-T05): the version's tax year, when the set is per tax year.
    tax_year: int | None = None


@dataclass(frozen=True)
class Form8879For:
    """The authorization form for a return type and year (T-01's envelope picks it)."""

    return_type: str
    tax_year: int
    jurisdiction: str
    authorization_form: str
    revision: str
    reference_set_version_id: UUID


@dataclass(frozen=True)
class TolerancesFor:
    """DEC-85's relock tolerances for a tax year (T-01's I-8879-DRIFT reads these rows)."""

    tax_year: int
    total_income_or_agi_usd: int
    tax_withholding_refund_balance_usd: int
    reference_set_version_id: UUID


@dataclass(frozen=True)
class ThresholdFor:
    form: str
    payment_year: int
    threshold_usd: int
    min_transactions: int | None
    reference_set_version_id: UUID


@dataclass(frozen=True)
class RetentionFloor:
    record_type: str
    service_line: str
    floor_years: int
    anchor: str
    reference_set_version_id: UUID
