"""Q-03-T235 (TASK-6738; DEC-3304): the labeler gap-fill. "Unresolved target types show the
catalogue noun, never an id or a Restricted value." A tenant labeler reads as the viewer's firm
or, for the label index, the indexer's; a type nobody names reads as its noun; a label carrying a
TIN form is refused."""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform import audit_slots
from abacus.modules.platform.audit_slots import AuditLabel

TENANT = TenantContext(uuid.uuid4(), "system", "q03t235")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    for registry in ("_LABELERS", "_TENANT_LABELERS", "_NOUNS"):
        monkeypatch.setattr(audit_slots, registry, dict(getattr(audit_slots, registry)))


def _viewer() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT.tenant_id, "human", str(user)),
        user,
        uuid.uuid4(),
        "security_admin",
        datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("target_type", "noun"),
    [
        ("engagement", "Engagement"),
        ("eqr_review", "EQR review"),
        ("evidence_item", "Document"),
        ("legal_hold", "Legal hold"),
        ("pbc_binder", "PBC binder"),
        ("eqr_checklist", "EQR checklist"),
        ("governance_communication", "Governance communication"),
        ("", "Record"),
    ],
)
def test_an_unnamed_type_reads_as_its_noun(target_type: str, noun: str) -> None:
    if target_type == "engagement":
        audit_slots.register_audit_noun("engagement", "Engagement")
    assert audit_slots.audit_noun(target_type) == noun
    assert not any(ch.isdigit() for ch in audit_slots.audit_noun(target_type))


def test_a_noun_carries_no_identifier() -> None:
    with pytest.raises(ValueError):
        audit_slots.register_audit_noun("thing", "Thing 42")
    with pytest.raises(ValueError):
        audit_slots.register_audit_noun("thing", "  ")


async def test_a_tenant_labeler_reads_as_the_viewers_firm_or_the_indexers() -> None:
    seen: list[TenantContext] = []

    async def labeler(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
        seen.append(tenant)
        return {
            i: AuditLabel(f"Engagement {chr(65 + n)}", "confidential") for n, i in enumerate(ids)
        }

    audit_slots.register_audit_tenant_labeler("probe_engagement", labeler)
    viewer = _viewer()
    by_viewer = await audit_slots.audit_labels(viewer, "probe_engagement", ["a"])
    assert by_viewer["a"].text == "Engagement A" and seen[-1] is viewer.tenant
    by_index = await audit_slots.audit_labels(None, "probe_engagement", ["a"], tenant=TENANT)
    assert by_index["a"].text == "Engagement A" and seen[-1] is TENANT
    # No viewer and no firm: nothing is named (fail closed).
    assert await audit_slots.audit_labels(None, "probe_engagement", ["a"]) == {}
    audit_slots.register_audit_tenant_labeler("probe_engagement", labeler)  # a reload: idempotent

    async def other(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
        return {}

    with pytest.raises(ValueError):
        audit_slots.register_audit_tenant_labeler("probe_engagement", other)


async def test_a_label_with_a_tin_or_above_confidential_is_refused() -> None:
    async def labeler(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
        del tenant, ids
        return {
            "ok": AuditLabel("Northwind Robotics 401(k) Plan PY2025", "confidential"),
            "ein": AuditLabel("Plan 12-3456789", "internal"),
            "restricted": AuditLabel("Anything", "restricted"),
        }

    audit_slots.register_audit_tenant_labeler("probe_client", labeler)
    found = await audit_slots.audit_labels(None, "probe_client", ["ok"], tenant=TENANT)
    assert set(found) == {"ok"}


async def test_a_failing_tenant_labeler_names_nothing() -> None:
    async def labeler(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
        raise RuntimeError("boom")

    audit_slots.register_audit_tenant_labeler("probe_failing", labeler)
    assert await audit_slots.audit_labels(None, "probe_failing", ["a"], tenant=TENANT) == {}


def test_the_owning_modules_register_their_types() -> None:
    importlib.import_module("abacus.api")  # the owning modules register at import
    from abacus.modules.platform.api import registered_audit_types

    labelled, _ = registered_audit_types()
    assert {"user", "engagement", "work_item", "client", "workpaper"} <= labelled
