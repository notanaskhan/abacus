"""W-01-T07 (SPEC-659 AC-1 to AC-6, AC-32): the Connect catalogue's pure parts.

The plan of a v2 import (adds, changes, unpublishes, what became available; a dry run writes
nothing because it never reaches the database), the document's content rules, and the read's
honesty, counts, category totals, filters and blocked reasons. The database half (the definers,
the HTTP route, Notify me) is the integration and security suites'.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations import adapters
from abacus.modules.integrations.catalog_import import CatalogDocumentV2, plan_import
from abacus.modules.integrations.connect_catalog import (
    Install,
    Tile,
    WorkbenchRow,
    honest_listing,
    published,
    tile_of,
)

T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _doc_row(key: str, **over: object) -> dict[str, Any]:  # Any: a document row as YAML gives it
    row: dict[str, Any] = {  # Any: as above
        "key": key,
        "name": key.title(),
        "categories": ["practice"],
        "ownership_mode": "firm",
        "surfaces": ["workbench"],
        "adapter_key": key,
        "listing_status": "available",
        "scopes": {"read": [{"code": "projects.read", "label": "Projects"}]},
        "icon": "briefcase",
        "tone": "olive",
        "sort_order": 1,
        "description": "Workflow and time.",
        "auth_line": "Firm connection",
        "published_at": "2026-01-01T00:00:00-06:00",
    }
    row.update(over)
    return row


def _doc(*rows: dict[str, Any]) -> CatalogDocumentV2:  # Any: as above
    return CatalogDocumentV2.model_validate({"version": 2, "rows": list(rows)})


def _current(key: str, **over: object) -> dict[str, object]:  # Any: as above
    row: dict[str, object] = {**_doc_row(key), "category": None, "consent_copy": None}
    row.update(over)
    return row


# --- the import plan ---------------------------------------------------------------------------


def test_ac32_a_new_key_is_added_and_counts_as_available() -> None:
    plan = plan_import([], _doc(_doc_row("karbon")))
    assert (plan.added, plan.changed, plan.unpublished) == (("karbon",), (), ())
    assert plan.became_available == ("karbon",) and plan.writes


def test_ac32_identical_content_writes_nothing() -> None:
    plan = plan_import([_current("karbon")], _doc(_doc_row("karbon")))
    assert plan.unchanged == ("karbon",) and not plan.writes


def test_ac32_the_same_instant_in_another_offset_is_unchanged() -> None:
    current = _current("karbon", published_at=datetime(2026, 1, 1, 6, 0, tzinfo=UTC))
    assert not plan_import([current], _doc(_doc_row("karbon"))).writes


def test_ac32_a_changed_row_names_its_columns_and_coming_soon_to_available_is_told() -> None:
    current = _current("drata", listing_status="coming_soon")
    plan = plan_import([current], _doc(_doc_row("drata", description="Controls.")))
    assert plan.changed == (("drata", ("listing_status", "description")),)
    assert plan.became_available == ("drata",)


def test_ac32_a_workbench_row_the_document_drops_is_unpublished_never_deleted() -> None:
    plan = plan_import(
        [_current("karbon"), _current("old"), _current("gone", listing_status="hidden")],
        _doc(_doc_row("karbon")),
    )
    assert plan.unpublished == ("old",)  # a row already hidden is left alone


def test_ac32_a_portal_only_row_is_not_unpublished_by_a_workbench_document() -> None:
    portal = _current("square", surfaces=["portal"], category="sales")
    assert plan_import([portal], _doc(_doc_row("karbon"))).unpublished == ()


@pytest.mark.parametrize(
    ("over", "why"),
    [
        ({"scopes": {"read": [], "write": []}}, "a write scope"),
        ({"surfaces": ["portal", "workbench"]}, "a portal row without its v1 category"),
        ({"categories": []}, "a tile without its category tags"),
        ({"description": "Start a free trial today"}, "payment copy (AC-5)"),
        ({"tone": "teal"}, "a brand colour (AC-5)"),
        ({"published_at": "2026-01-01T00:00:00"}, "an instant without its offset"),
        ({"ownership_mode": "client_authorised"}, "a firm app without its provider"),
    ],
)
def test_the_document_refuses(over: dict[str, Any], why: str) -> None:  # Any: as above
    with pytest.raises(ValidationError):
        _doc(_doc_row("karbon", **over))


def test_a_key_and_a_provider_appear_once() -> None:
    with pytest.raises(ValidationError):
        _doc(_doc_row("karbon"), _doc_row("karbon"))
    with pytest.raises(ValidationError):
        _doc(
            _doc_row("a1", ownership_mode="client_authorised", connector_provider="p"),
            _doc_row("a2", ownership_mode="client_authorised", connector_provider="p"),
        )


# --- the read ------------------------------------------------------------------------------------


_BASE = WorkbenchRow(
    key="base",
    name="Base",
    categories=("practice",),
    ownership_mode="firm",
    connector_provider=None,
    adapter_key="base",
    listing_status="available",
    consent_copy=None,
    consent_version=None,
    read_scopes=(("projects.read", "Projects"),),
    icon="briefcase",
    tone="olive",
    sort_order=1,
    description="Workflow and time.",
    auth_line="Firm connection",
    published_at=T0 - timedelta(days=30),
    prerequisite=None,
    revision=1,
)


def _row(key: str, **over: object) -> WorkbenchRow:
    return replace(_BASE, key=key, name=key.title(), adapter_key=key, **over)


class _Fake:
    read_methods: tuple[str, ...] = ()

    def __init__(self, key: str) -> None:
        self._key = key

    @property
    def key(self) -> str:
        return self._key

    @property
    def category(self) -> str:
        return "grc"

    @property
    def connector_provider(self) -> str | None:
        return None

    def read_scopes(self) -> tuple[str, ...]:
        return ("projects.read",)

    def egress_hosts(self) -> tuple[str, ...]:
        return ("api.example.com",)


@pytest.fixture
def karbon_registered() -> Iterator[None]:
    adapters.register_adapter(_Fake("karbon"))
    yield
    adapters.unregister_adapter("karbon")


def _ctx(role: str | None) -> AuthContext:
    tenant = TenantContext(uuid.uuid4(), "human", "u")
    return AuthContext(tenant, uuid.uuid4(), uuid.uuid4(), role, T0)  # type: ignore[arg-type] -- a role code from the matrix


def _tile(
    row: WorkbenchRow,
    role: str | None = "security_admin",
    *,
    firm: dict[str, Install] | None = None,
    mine: dict[str, Install] | None = None,
    names: dict[uuid.UUID, str] | None = None,
) -> Tile:
    return tile_of(
        row,
        ctx=_ctx(role),
        synthetic=False,
        firm=firm or {},
        mine=mine or {},
        names=names or {},
        manager="Felix Andersen",
    )


def test_ac4_without_a_registered_adapter_a_tile_is_coming_soon() -> None:
    assert honest_listing(_row("karbon"), synthetic=False) == "coming_soon"
    assert honest_listing(_row("karbon"), synthetic=True) == "coming_soon"  # no fakes yet


@pytest.mark.usefixtures("karbon_registered")
def test_ac4_a_registered_adapter_makes_it_available() -> None:
    assert honest_listing(_row("karbon"), synthetic=False) == "available"
    assert honest_listing(_row("karbon", listing_status="coming_soon"), synthetic=False) == (
        "coming_soon"
    )


def test_ac1_a_row_lists_only_once_published_and_never_hidden() -> None:
    rows = [
        _row("a"),
        _row("drata", published_at=T0 + timedelta(days=17)),
        _row("b", listing_status="hidden"),
        _row("c", published_at=None),
    ]
    assert [r.key for r in published(rows, T0)] == ["a"]
    assert [r.key for r in published(rows, T0 + timedelta(days=17))] == ["a", "drata"]


def test_the_install_decides_and_names_who_connected() -> None:
    felix = uuid.uuid4()
    install = Install(uuid.uuid4(), "needs_reauth", "token", felix, (), 3)
    tile = _tile(_row("cch"), firm={"cch": install}, names={felix: "Felix Andersen"})
    assert (tile.status, tile.bucket, tile.connected_by_label) == (
        "needs_reauth",
        "connected",
        "Felix Andersen",
    )
    bridge = _tile(
        _row("cch"), firm={"cch": Install(uuid.uuid4(), "connected", "file_bridge", felix, (), 1)}
    )
    assert bridge.kind == "file_bridge"


def test_a_personal_tile_reads_the_viewers_own_install() -> None:
    mine = {"box": Install(uuid.uuid4(), "connected", None, None, (), 1)}
    firm = {"box": Install(uuid.uuid4(), "connected", "token", None, (), 1)}
    assert _tile(_row("box", ownership_mode="personal"), firm=firm).status == "coming_soon"
    assert _tile(_row("box", ownership_mode="personal"), mine=mine).status == "connected"


def test_ac6_a_non_admin_reads_who_manages_firm_connections() -> None:
    tile = _tile(_row("karbon"), role="staff")
    assert not {"integration.connect_firm", "integration.disconnect_firm"} & set(
        tile.allowed_actions
    )
    assert tile.blocked_reason == "Felix Andersen manages firm connections."
    admin = _tile(_row("karbon"))
    assert admin.blocked_reason is None
    assert set(admin.allowed_actions) >= {
        "integration.connect_firm",
        "integration.disconnect_firm",
    }


def test_wb10_a_a_missing_prerequisite_scope_shows_the_rows_reason() -> None:
    reason = "Uses the CCH Axcess firm account, which does not yet grant the Workstream scope."
    row = _row("workstream", prerequisite={"key": "cch", "scope": "workstream", "reason": reason})
    granted = Install(uuid.uuid4(), "connected", "token", None, ("workstream",), 1)
    without = Install(uuid.uuid4(), "connected", "token", None, ("returns.read",), 1)
    assert _tile(row, firm={"cch": without}).blocked_reason == reason
    assert _tile(row).blocked_reason == reason  # CCH not connected at all
    assert _tile(row, firm={"cch": granted}).blocked_reason is None


def test_ac31_notify_me_is_offered_on_coming_soon_only() -> None:
    assert (
        "integration.interest" in _tile(_row("adp", listing_status="coming_soon")).allowed_actions
    )
    with_adapter = _tile(_row("adp"))
    assert "integration.interest" not in with_adapter.allowed_actions or with_adapter.status == (
        "coming_soon"
    )


def test_ac2_category_totals_count_a_tile_in_each_of_its_tags() -> None:
    rows = [_row("a", categories=("docs", "prod")), _row("b", categories=("docs",))]
    assert Counter(c for r in published(rows, T0) for c in r.categories) == {"docs": 2, "prod": 1}


def test_a_staff_member_with_no_firm_role_holds_notify_me_and_personal_actions() -> None:
    staff = _tile(_row("adp", listing_status="coming_soon"), role=None)
    assert staff.allowed_actions == ("integration.interest",)
    box = _tile(_row("box", ownership_mode="personal", listing_status="coming_soon"), role=None)
    assert {"integration.connect_personal", "integration.disconnect_personal"} <= set(
        box.allowed_actions
    )
