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
