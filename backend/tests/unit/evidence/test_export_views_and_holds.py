"""Evidence's pure mappings and checks, without a database (A-01-T17, Q-02-T43, Q-02-T44;
SPEC-344, SPEC-341; Q-03-T147).

The integration suites drive these through their routes; these pin, on the unit suites alone,
what a mutation run decides: each contract field the export and firm export answers copy from
their views, the no-store headers on downloads and 410s, the export grant's canonical digest, the
stored scope's round trip, the INV-1 human check, and which open holds cover a version.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.responses import Response

from abacus.modules.evidence import (
    export_contract,
    exports,
    firm_export_contract,
    firm_exports,
    holds,
)
from abacus.modules.identity.api import Forbidden

exports_human = exports._human  # pyright: ignore[reportPrivateUsage] -- the helper under test
export_contract_out = export_contract._out  # pyright: ignore[reportPrivateUsage] -- the helper under test
firm_export_contract_out = firm_export_contract._out  # pyright: ignore[reportPrivateUsage] -- the helper under test
firm_export_contract_gone = firm_export_contract._gone  # pyright: ignore[reportPrivateUsage] -- the helper under test
holds_to_view = holds._to_view  # pyright: ignore[reportPrivateUsage] -- the helper under test
holds_system = holds._system  # pyright: ignore[reportPrivateUsage] -- the helper under test
holds_stored = holds._stored  # pyright: ignore[reportPrivateUsage] -- the helper under test
holds_covers = holds._covers  # pyright: ignore[reportPrivateUsage] -- the helper under test
holds_counts = holds._counts  # pyright: ignore[reportPrivateUsage] -- the helper under test
export_contract_no_store = export_contract._no_store  # pyright: ignore[reportPrivateUsage] -- the helper under test
firm_export_contract_no_store = firm_export_contract._no_store  # pyright: ignore[reportPrivateUsage] -- the helper under test

EXPORT = uuid.UUID("00000000-0000-4000-8000-0000000000e0")
ENGAGEMENT = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
WORK_ITEM = uuid.UUID("00000000-0000-4000-8000-0000000000f1")
CLIENT = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
ANA = uuid.UUID("00000000-0000-4000-8000-000000000001")
BO = uuid.UUID("00000000-0000-4000-8000-000000000002")
B1 = uuid.UUID("00000000-0000-4000-8000-0000000000b1")
B2 = uuid.UUID("00000000-0000-4000-8000-0000000000b2")
AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
LATER = datetime(2026, 9, 14, 14, 24, 10, tzinfo=UTC)
READY = datetime(2026, 9, 14, 14, 30, tzinfo=UTC)
EXPIRES = datetime(2026, 9, 21, 14, 30, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


# --- the stored scope and the grant digest -------------------------------------------------------


def test_scope_round_trips_through_its_stored_json() -> None:
    scope = exports.ExportScope((B1, B2), include_unaccepted=True, include_audit_trail=False)
    stored = scope.as_json()
    assert stored == {
        "binder_ids": [str(B1), str(B2)],
        "include_unaccepted": True,
        "include_audit_trail": False,
    }
    assert exports.ExportScope.of(stored) == scope
    other = exports.ExportScope.of(
        {"binder_ids": [], "include_unaccepted": 0, "include_audit_trail": 1}
    )
    assert other == exports.ExportScope((), include_unaccepted=False, include_audit_trail=True)
    assert other.include_audit_trail is True
    assert other.include_unaccepted is False


def test_grant_digest_is_the_sha256_of_the_canonical_binding() -> None:
    scope: dict[str, object] = {"include_audit_trail": False, "binder_ids": [str(B1)]}
    canonical = (
        '{"export_id":"'
        + str(EXPORT)
        + '","kind":"binder","scope":{"binder_ids":["'
        + str(B1)
        + '"],"include_audit_trail":false},"work_item_id":"'
        + str(WORK_ITEM)
        + '"}'
    )
    assert exports.grant_digest(EXPORT, WORK_ITEM, "binder", scope) == (
        hashlib.sha256(canonical.encode()).hexdigest()
    )


def test_grant_digest_changes_with_every_bound_part() -> None:
    base = exports.grant_digest(EXPORT, WORK_ITEM, "binder", {"a": 1})
    assert exports.grant_digest(ENGAGEMENT, WORK_ITEM, "binder", {"a": 1}) != base
    assert exports.grant_digest(EXPORT, ENGAGEMENT, "binder", {"a": 1}) != base
    assert exports.grant_digest(EXPORT, WORK_ITEM, "final_binder", {"a": 1}) != base
    assert exports.grant_digest(EXPORT, WORK_ITEM, "binder", {"a": 2}) != base


class _Tenant:
    def __init__(self, kind: str) -> None:
        self.actor_kind = kind


class _Ctx:
    def __init__(
        self, kind: str = "human", *, client: object = None, support: bool = False
    ) -> None:
        self.tenant = _Tenant(kind)
        self.client = client
        self.is_support = support


def test_human_lets_a_person_through() -> None:
    exports_human(_Ctx(), "export.create")  # type: ignore[arg-type] -- a stand-in context


@pytest.mark.parametrize(
    "ctx",
    [
        _Ctx("agent"),
        _Ctx("system"),
        _Ctx("human", client=object()),
        _Ctx("human", support=True),
    ],
    ids=["agent", "system", "client", "support"],
)
def test_human_refuses_everyone_else_at_the_role(ctx: _Ctx) -> None:
    with pytest.raises(Forbidden) as refused:
        exports_human(ctx, "export.create")  # type: ignore[arg-type] -- a stand-in context
    assert refused.value.action == "export.create"
    assert refused.value.layer == "role"


# --- the engagement export's contract shape ------------------------------------------------------


def _export_view(**over: object) -> exports.ExportView:
    fields: dict[str, Any] = {  # Any: the view's keyword arguments
        "id": EXPORT,
        "engagement_id": ENGAGEMENT,
        "work_item_id": WORK_ITEM,
        "kind": "final_binder",
        "scope": exports.ExportScope((B1,), include_unaccepted=True, include_audit_trail=True),
        "format_version": "ignored",
        "status": "ready",
        "requested_by": ANA,
        "requested_by_name": "Ana Alvarez",
        "requested_at": AT,
        "not_before": LATER,
        "ready_at": READY,
        "expires_at": EXPIRES,
        "request_count": 4,
        "file_count": 9,
        "size_bytes": 12345,
        "manifest_sha256": SHA_A,
        "bundle_sha256": SHA_B,
        "failure_code": None,
        "void_reason": "withdrawn_content",
        "allowed_actions": ["download"],
    }
    fields.update(over)
    return exports.ExportView(**fields)


def test_export_out_copies_every_field() -> None:
    out = export_contract_out(_export_view())
    assert out.model_dump() == {
        "id": EXPORT,
        "engagement_id": ENGAGEMENT,
        "work_item_id": WORK_ITEM,
        "kind": "final_binder",
        "scope": {"binder_ids": [B1], "include_unaccepted": True, "include_audit_trail": True},
        "format_version": "1.0",
        "status": "ready",
        "requested_by": {"user_id": ANA, "display_name": "Ana Alvarez"},
        "requested_at": AT,
        "not_before": LATER,
        "ready_at": READY,
        "expires_at": EXPIRES,
        "request_count": 4,
        "file_count": 9,
        "size_bytes": 12345,
        "manifest_sha256": SHA_A,
        "bundle_sha256": SHA_B,
        "failure_code": None,
        "void_reason": "withdrawn_content",
        "allowed_actions": ["download"],
    }


def test_export_out_of_a_queued_export() -> None:
    out = export_contract_out(
        _export_view(
            kind="binder",
            scope=exports.ExportScope((), include_unaccepted=False, include_audit_trail=False),
            status="failed",
            ready_at=None,
            expires_at=None,
            request_count=None,
            file_count=None,
            size_bytes=None,
            manifest_sha256=None,
            bundle_sha256=None,
            failure_code="build_error",
            void_reason=None,
            allowed_actions=["undo"],
        )
    )
    assert out.kind == "binder"
    assert out.status == "failed"
    assert out.scope.binder_ids == []
    assert out.scope.include_unaccepted is False
    assert out.scope.include_audit_trail is False
    assert out.failure_code == "build_error"
    assert out.void_reason is None
    assert out.allowed_actions == ["undo"]
    assert (out.ready_at, out.expires_at, out.size_bytes, out.manifest_sha256) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "no_store", [export_contract_no_store, firm_export_contract_no_store], ids=["export", "firm"]
)
def test_downloads_are_never_stored_or_sniffed(no_store: Callable[[Response], Response]) -> None:
    response = Response(b"x", headers={"X-Other": "kept"})
    assert no_store(response) is response
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Other"] == "kept"


# --- the firm export's contract shape ------------------------------------------------------------


def test_firm_export_out_copies_every_field() -> None:
    view = firm_exports.FirmExportView(
        id=EXPORT,
        status="ready",
        scope="all",
        origin="scheduled",
        requested_by=firm_exports.NamedUser(ANA, "Ana Alvarez"),
        requested_at=AT,
        approver=firm_exports.NamedUser(BO, "Bo Brandt"),
        decided_at=LATER,
        ready_at=READY,
        available_until=EXPIRES,
        size_bytes=999,
        manifest_sha256=SHA_A,
    )
    out = firm_export_contract_out(view)
    assert out.model_dump() == {
        "id": EXPORT,
        "status": "ready",
        "scope": "all",
        "origin": "scheduled",
        "requested_by": {"user_id": ANA, "display_name": "Ana Alvarez"},
        "requested_at": AT,
        "approver": {"user_id": BO, "display_name": "Bo Brandt"},
        "decided_at": LATER,
        "ready_at": READY,
        "available_until": EXPIRES,
        "size_bytes": 999,
        "manifest_sha256": SHA_A,
    }


def test_firm_export_gone_is_a_no_store_410() -> None:
    response = firm_export_contract_gone("export_expired")
    assert response.status_code == 410
    assert json.loads(bytes(response.body)) == {"detail": "export_expired"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# --- legal holds ---------------------------------------------------------------------------------


def _hold_row(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": EXPORT,
        "scope_kind": "client_tax_year",
        "client_id": CLIENT,
        "tax_year": 2025,
        "engagement_id": ENGAGEMENT,
        "work_item_id": WORK_ITEM,
        "reason_code": "litigation",
        "status": "active",
        "placed_by": ANA,
        "placed_at": AT,
        "released_by": BO,
        "released_at": READY,
        "objects_held": 7,
        "objects_applied": 5,
    }
    row.update(over)
    return row


def test_hold_view_reads_every_column() -> None:
    view = holds_to_view(_hold_row())
    assert view == holds.HoldView(
        id=EXPORT,
        scope_kind="client_tax_year",
        client_id=CLIENT,
        tax_year=2025,
        engagement_id=ENGAGEMENT,
        work_item_id=WORK_ITEM,
        reason_code="litigation",
        status="active",
        placed_by=ANA,
        placed_at=AT,
        released_by=BO,
        released_at=READY,
        objects_held=7,
        objects_applied=5,
    )


def test_hold_view_counts_are_ints() -> None:
    view = holds_to_view(_hold_row(objects_held=3.0, objects_applied="2"))
    assert view.objects_held == 3
    assert view.objects_applied == 2
    assert isinstance(view.objects_held, int)


def test_hold_system_context() -> None:
    ctx = holds_system(CLIENT)
    assert (ctx.tenant_id, ctx.actor_kind, ctx.actor_id) == (CLIENT, "system", "legal_holds")


def test_stored_object_names_key_and_version_only() -> None:
    stored = holds_stored("tenant/key", "v3")
    assert stored == holds.StoredObject("tenant/key", "v3", "", 0)


YEARS = frozenset({2024, 2025})


@pytest.mark.parametrize(
    ("hold", "covered"),
    [
        ({"scope_kind": "engagement", "engagement_id": ENGAGEMENT}, True),
        ({"scope_kind": "work_item", "engagement_id": ENGAGEMENT}, True),
        ({"scope_kind": "engagement", "engagement_id": WORK_ITEM}, False),
        ({"scope_kind": "work_item", "engagement_id": None, "client_id": CLIENT}, False),
        ({"scope_kind": "client", "client_id": CLIENT, "tax_year": None}, True),
        ({"scope_kind": "client", "client_id": ANA, "tax_year": None}, False),
        ({"scope_kind": "client_tax_year", "client_id": CLIENT, "tax_year": 2025}, True),
        ({"scope_kind": "client_tax_year", "client_id": CLIENT, "tax_year": 2023}, False),
        ({"scope_kind": "client_tax_year", "client_id": ANA, "tax_year": 2025}, False),
    ],
)
def test_covers(hold: dict[str, object], covered: bool) -> None:
    assert holds_covers(hold, ENGAGEMENT, CLIENT, YEARS) is covered


def test_counts_are_unreleased_objects_and_applied_ones() -> None:
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    held, applied = holds_counts()
    held_sql = str(select(held).compile(dialect=postgresql.dialect()))
    applied_sql = str(select(applied).compile(dialect=postgresql.dialect()))
    assert "count(*)" in held_sql
    assert "hold_objects.hold_id = legal_holds.id" in held_sql
    assert "hold_objects.released_at IS NULL" in held_sql
    assert "applied_at" not in held_sql
    assert "hold_objects.hold_id = legal_holds.id" in applied_sql
    assert "hold_objects.released_at IS NULL" in applied_sql
    assert "hold_objects.applied_at IS NOT NULL" in applied_sql
