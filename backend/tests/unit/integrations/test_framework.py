"""A-02-T12 (TASK-1339; SPEC-333 AC-49; A-02 AC-13.1): the fail-closed adapter registry, the
catalogue's honest listing and the load plan, without a database.

- An unregistered adapter is never listed as available on any surface; a registered one is only
  when its category and connection provider match the row (catalogue honesty).
- Registration refuses write-shaped adapters, bad hosts and scopes, duplicates.
- A load document with a write scope does not validate; the plan names adds and changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.modules.integrations.api import (
    AdapterRefused,
    CatalogDocument,
    CatalogRow,
    LoadPlan,
    listed,
    listing_of,
    plan_load,
    register_adapter,
    registered_adapter,
    registered_keys,
    unregister_adapter,
)
from abacus_tools.integration_catalog import LoadResult
from abacus_tools.release import OPS_COMMANDS


class Reader:
    """A read-only adapter: the port's members, its machinery private."""

    def __init__(
        self,
        key: str = "probe_ledger",
        category: str = "ledger",
        connector_provider: str | None = "probe_ledger",
        hosts: tuple[str, ...] = ("api.probe.example",),
        scopes: tuple[str, ...] = ("ledger.read",),
    ) -> None:
        self.key = key
        self.category = category
        self.connector_provider = connector_provider
        self._hosts = hosts
        self._scopes = scopes

    def read_scopes(self) -> tuple[str, ...]:
        return self._scopes

    def egress_hosts(self) -> tuple[str, ...]:
        return self._hosts


class DeclaredReader(Reader):
    """Declares its own read methods; they are allowed."""

    read_methods = ("read_trial_balance", "list_accounts")

    def read_trial_balance(self) -> None:
        return None

    def list_accounts(self) -> None:
        return None


class _Http:
    def get(self) -> None:
        return None

    def post(self) -> None:
        return None


class WithClient(Reader):
    """A public HTTP client: its `.post` would be reachable, so the adapter is refused."""

    def __init__(self) -> None:
        super().__init__()
        self.client = _Http()


# Write-capable names a word blocklist would miss (security review M1): each, added as a public
# method, makes the adapter unregistrable.
UNDECLARED = (
    "apply_payment",
    "make_payment",
    "record_bill",
    "commit",
    "save",
    "set_status",
    "approve_invoice",
    "mark_paid",
    "request",
    "execute",
    "call",
    "post_journal_entry",
)


def _noop(_self: object) -> None:
    return None


def _with_method(name: str) -> Reader:
    cls = type(f"With_{name}", (Reader,), {name: _noop})
    return cast(Reader, cls())


ROW = CatalogRow(
    key="probe_ledger",
    name="Probe ledger",
    category="ledger",
    ownership_mode="client_authorised",
    surfaces=("portal",),
    connector_provider="probe_ledger",
    adapter_key="probe_ledger",
    listing_status="available",
    consent_copy=None,
    consent_version=None,
    read_scopes=(("ledger.read", "Read ledger"),),
    icon="book-open",
    tone="olive",
    sort_order=1,
    revision=1,
    loaded_at=datetime(2026, 10, 26, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    before = registered_keys()
    yield
    for key in registered_keys() - before:
        unregister_adapter(key)


def test_ac49_an_unregistered_adapter_is_never_listed_as_available() -> None:
    assert registered_adapter("probe_ledger") is None
    assert listing_of(ROW) == "coming_soon"
    for surface in ("portal", "workbench"):
        for ownership in ("client_authorised", "firm", "personal"):
            row = replace(ROW, surfaces=("portal", "workbench"), ownership_mode=ownership)
            entries = listed([row], surface, ownership)
            assert all(e.listing != "available" for e in entries)


def test_ac49_a_registered_matching_adapter_is_available() -> None:
    register_adapter(Reader())
    assert listing_of(ROW) == "available"
    # Honest only when the adapter serves the row: another category or provider is not.
    assert listing_of(replace(ROW, category="bank_feed")) == "coming_soon"
    assert listing_of(replace(ROW, connector_provider="other_ledger")) == "coming_soon"
    # The row's own listing still rules: coming soon stays, hidden is never listed.
    assert listing_of(replace(ROW, listing_status="coming_soon")) == "coming_soon"
    assert listed([replace(ROW, listing_status="hidden")], "portal", "client_authorised") == []


def test_ac49_unregistering_takes_it_off_at_once() -> None:
    register_adapter(Reader())
    unregister_adapter("probe_ledger")
    assert listing_of(ROW) == "coming_soon"


@pytest.mark.parametrize("name", UNDECLARED)
def test_m1_any_undeclared_public_method_is_refused(name: str) -> None:
    with pytest.raises(AdapterRefused):
        register_adapter(_with_method(name))
    assert registered_adapter("probe_ledger") is None


def test_m1_a_public_client_attribute_is_refused() -> None:
    with pytest.raises(AdapterRefused):
        register_adapter(WithClient())
    assert registered_adapter("probe_ledger") is None


def test_m1_declared_read_methods_are_allowed_and_nothing_else() -> None:
    register_adapter(DeclaredReader())
    assert registered_adapter("probe_ledger") is not None
    unregister_adapter("probe_ledger")
    # A declared name outside the read grammar, or one the adapter doesn't have, is refused.
    for declared in (("post_entries",), ("read_missing",), "read_trial_balance"):
        bad = type("Bad", (DeclaredReader,), {"read_methods": declared})()
        with pytest.raises(AdapterRefused):
            register_adapter(bad)


@pytest.mark.parametrize(
    "adapter",
    [
        Reader(key="Bad-Key"),
        Reader(category="crm"),
        Reader(hosts=("https://api.probe.example",)),
        Reader(hosts=()),
        Reader(scopes=()),
        Reader(connector_provider="Bad Provider"),
    ],
    ids=["key", "category", "host", "no-host", "no-scope", "provider"],
)
def test_registration_fails_closed(adapter: Reader) -> None:
    with pytest.raises(AdapterRefused):
        register_adapter(adapter)
    assert registered_adapter(adapter.key) is None


def test_an_adapter_and_a_provider_register_once() -> None:
    register_adapter(Reader())
    with pytest.raises(AdapterRefused):
        register_adapter(Reader())
    with pytest.raises(AdapterRefused):
        register_adapter(Reader(key="probe_two"))  # same connection provider


def test_a_non_adapter_is_refused() -> None:
    with pytest.raises(AdapterRefused):
        register_adapter(object())


def _doc_row(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "key": "probe_ledger",
        "name": "Probe ledger",
        "category": "ledger",
        "ownership_mode": "client_authorised",
        "surfaces": ["portal"],
        "connector_provider": "probe_ledger",
        "adapter_key": "probe_ledger",
        "listing_status": "available",
        "scopes": {"read": [{"code": "ledger.read", "label": "Read ledger"}]},
        "icon": "book-open",
        "tone": "olive",
        "sort_order": 1,
    }
    row.update(over)
    return row


def test_a_document_with_a_write_scope_does_not_validate() -> None:
    with pytest.raises(ValidationError):
        CatalogDocument.model_validate(
            {
                "version": 1,
                "rows": [
                    _doc_row(
                        scopes={
                            "read": [{"code": "ledger.read", "label": "Read ledger"}],
                            "write": [{"code": "ledger.post", "label": "Post entries"}],
                        }
                    )
                ],
            }
        )


def test_a_document_repeats_no_key_or_provider() -> None:
    with pytest.raises(ValidationError):
        CatalogDocument.model_validate({"version": 1, "rows": [_doc_row(), _doc_row()]})
    with pytest.raises(ValidationError):
        CatalogDocument.model_validate(
            {"version": 1, "rows": [_doc_row(), _doc_row(key="probe_two")]}
        )


def test_ac50_the_plan_names_adds_and_changes_and_leaves_the_rest() -> None:
    document = CatalogDocument.model_validate(
        {
            "version": 1,
            "rows": [
                _doc_row(),
                _doc_row(
                    key="square",
                    connector_provider="square",
                    adapter_key="square",
                    category="sales",
                    name="Square",
                ),
                _doc_row(
                    key="shopify",
                    connector_provider="shopify",
                    adapter_key=None,
                    category="sales",
                    name="Shopify",
                ),
            ],
        }
    )
    current = [
        dict(document.rows[0].as_row()),  # unchanged
        {**document.rows[1].as_row(), "listing_status": "coming_soon"},  # changed
    ]
    plan = plan_load(current, document)
    assert plan.added == ("shopify",)
    assert plan.changed == (("square", ("listing_status",)),)
    assert plan.unchanged == ("probe_ledger",)
    assert plan.writes
    assert not plan_load([r.as_row() for r in document.rows], document).writes


def test_l5_a_load_that_differs_from_its_plan_is_a_mismatch() -> None:
    plan = LoadPlan(added=("shopify",), changed=(("square", ("listing_status",)),), unchanged=())
    assert LoadResult(plan, (("shopify", "added"), ("square", "changed"))).matches_plan
    assert not LoadResult(plan, (("shopify", "added"),)).matches_plan
    assert not LoadResult(plan, (("shopify", "changed"), ("square", "changed"))).matches_plan
    assert LoadResult(plan, (), dry_run=True).matches_plan


def test_m3_the_catalogue_load_is_not_an_allowlisted_ops_command() -> None:
    assert not any(c.startswith("abacus_tools.integration_catalog") for c in OPS_COMMANDS)
