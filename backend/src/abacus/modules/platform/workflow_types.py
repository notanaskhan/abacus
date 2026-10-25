"""Tenant provisioning workflow inputs and results (Q-01-T45; ADR-156; platform-ops contract
section 3.6). Frozen dataclasses of strings: payloads are sealed by the codec (ADR-017), and the
admin addresses (Confidential) are never logged."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionTenantInput:
    tenant_id: str  # created by provision_firm
    slug: str
    synthetic: bool  # as the operator asked; the definer recorded it, the app role never sets it
    plan: str  # a plan code (F-03-T28 `plans`)
    admins: tuple[str, ...]  # first administrators' email addresses (Confidential)
    idempotency_key: str
    operator: str  # the operator's handle, never an email address


@dataclass(frozen=True)
class ProvisionTenantResult:
    tenant_id: str
    key_status: str  # firms.kms_key_status when the workflow ended
    entitlement_rows: int
    invitations_sent: int


@dataclass(frozen=True)
class TenantKeyInput:
    """Q-01-T27: whose key, and the operator who provisioned the firm (every step names them)."""

    tenant_id: str
    operator: str


@dataclass(frozen=True)
class IncidentFactsInput:
    """Q-02-T33 (RB-27): Accrued's facts about an Accrued-side incident, as staff entered them.
    The title is Confidential: payloads are sealed by the codec and it is never logged."""

    title: str
    event_kind: str
    discovered_at: str  # ISO 8601 with offset
    consumers_affected: int | None
    unencrypted: bool | None
    confirmed_at: str  # ISO 8601 with offset: when Accrued confirmed it (the 72-hour clock)


@dataclass(frozen=True)
class IncidentPropagationInput:
    """Q-02-T33: one Accrued incident into each named firm's register, as the system."""

    accrued_ref: str
    tenant_ids: tuple[str, ...]
    facts: IncidentFactsInput
    staff_id: str  # the platform staff member who asked (identifier only)
    reason_sha256: str  # the staff reason's fingerprint; the text is never stored


@dataclass(frozen=True)
class IncidentPropagationStep:
    """One firm's entry: which firm, and the propagation it belongs to."""

    accrued_ref: str
    tenant_id: str
    facts: IncidentFactsInput
    staff_id: str
    reason_sha256: str


@dataclass(frozen=True)
class IncidentStepResult:
    """v2: one firm's step. `written` is a new entry; `identical` an entry these same facts
    already wrote (a retry or a repeat)."""

    tenant_id: str
    ref: str
    status: str  # written | identical


@dataclass(frozen=True)
class IncidentPropagationOutcome:
    """v2: what the run did, recorded once at its end (`incident_propagations`, `completed`)."""

    accrued_ref: str
    staff_id: str
    reason_sha256: str
    firms: int
    written: int
    identical: int
    failed_tenant_ids: tuple[str, ...]


@dataclass(frozen=True)
class IncidentPropagationResult:
    """The run's result: every firm's entry, and the firms that failed every attempt (v2; a v1
    run has none failed, since a failure ended it)."""

    written: tuple[IncidentStepResult, ...]
    failed_tenant_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanaryInput:
    """Q-01-T30: whose canary (the synthetic firm the Schedule names)."""

    tenant_id: str


@dataclass(frozen=True)
class CanaryPlan:
    """The canary run's firm, the staff member it acts as and the engagement it writes in."""

    tenant_id: str
    user_id: str
    engagement_id: str


@dataclass(frozen=True)
class CanaryOutcome:
    """How the steps went, before the report: the first failed step and its code, or a pass."""

    tenant_id: str
    passed: bool
    failed_step: str | None
    code: str | None
    route: str | None  # the screener's route (`fake`, `bedrock`), when the step ran


@dataclass(frozen=True)
class CanaryResult:
    """A canary run's result, as the next run reads it (two consecutive failures page). Codes,
    step names and the route only: never a name, a value or document text."""

    tenant_id: str
    passed: bool
    failed_step: str | None
    code: str | None
    route: str | None
    paged: bool
