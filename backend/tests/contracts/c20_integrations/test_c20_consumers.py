"""POR-16's consumer view of C20 v1 (A-02-T08; TASK-1263; SPEC-333 AC-35, AC-36, AC-38, AC-41,
AC-42), run against the A-02-T06 stub, on the handoff's facts: Tess Moreno (Owner) on Copperleaf
Coffee Roasters, Inc. at Mon Sep 14, 2026, 9:24 AM CT; QuickBooks Online connected by Tess on Mar
4, 2026, last sync 9:15 AM; American Express ••1009 needs reauth; Shopify not connected. The cards
fit the models with the registry's words, the documented refusals are declared, the agent holds
no C20 action, and nothing offers a write (DF-19). The fixture half is
`apps/web/src/fixtures/contracts/c20-integrations.contract.test.ts`."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._statuses import IntegrationStatus
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.integrations.contract import (
    ConnectionPersonOut,
    ConnectionScopeOut,
    ConnectionStartIn,
    ConsentCopyOut,
    ExportInsteadOut,
    PortalConnectionCardOut,
    PortalConnectionsOut,
    PortalEntityOut,
)

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
REPO = Path(__file__).resolve().parents[4]
VOCABULARY = REPO / "docs" / "product" / "status-vocabulary.yaml"
START = "/v1/portal/entities/{entity_id}/connections/{catalog_key}/start"
ACTIONS = (
    "connection.read",
    "connection.create",
    "connection.retry",
    "connection.disconnect",
    "connection.reconnect_request",
    "ledger.pull",
)
TESS = ConnectionPersonOut(user_id=uuid.uuid4(), display_name="Tess Moreno", kind="client")
AUTHORIZATION = (
    "I authorize Brightwater Hale LLP to access this account for the services in our "
    "engagement letter"
)


def _words() -> dict[str, dict[str, str]]:
    data = cast(dict[str, object], yaml.safe_load(VOCABULARY.read_text(encoding="utf-8")))
    objects = cast(dict[str, object], data.get("objects", data))
    integration = cast(dict[str, object], objects["integration"])
    return cast(dict[str, dict[str, str]], integration["codes"])


def _por16a() -> PortalConnectionsOut:
    quickbooks = PortalConnectionCardOut(
        catalog_key="quickbooks_online",
        name="QuickBooks Online",
        category="ledger",
        icon="BookOpen",
        tone="olive",
        status=IntegrationStatus.CONNECTED,
        connection_id=uuid.uuid4(),
        connected_by=TESS,
        connected_at=datetime(2026, 3, 4, 15, 0, tzinfo=UTC),
        last_sync_at=datetime(2026, 9, 14, 14, 15, tzinfo=UTC),
        scopes=[ConnectionScopeOut(code="ledger.read", label="Read ledger")],
        export_instead=ExportInsteadOut(),
        version=1,
        allowed_actions=["details", "disconnect", "export_instead"],
    )
    amex = PortalConnectionCardOut(
        catalog_key="american_express",
        name="American Express",
        category="card_feed",
        icon="CreditCard",
        tone="clay",
        status=IntegrationStatus.NEEDS_REAUTH,
        status_reason="token_expired",
        connection_id=uuid.uuid4(),
        display_label="American Express ••1009",
        reauth_requested_at=datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
        consent=ConsentCopyOut(
            version=1,
            title="Reconnect American Express",
            will=[
                "Read statements and transactions for card ••1009",
                "Use them for your monthly close",
            ],
            wont=["Make payments or change your account", "See other cards on your login"],
            authorization=AUTHORIZATION,
            continue_label="Continue to American Express",
        ),
        version=3,
        allowed_actions=["reconnect", "details"],
    )
    shopify = PortalConnectionCardOut(
        catalog_key="shopify",
        name="Shopify",
        category="sales",
        icon="ShoppingBag",
        tone="ochre",
        status=IntegrationStatus.AVAILABLE,
        helper="You upload payout reports each month instead.",
        allowed_actions=["connect"],
    )
    return PortalConnectionsOut(
        entity=PortalEntityOut(
            client_entity_id=uuid.uuid4(), display_name="Copperleaf Coffee Roasters, Inc."
        ),
        firm_display_name="Brightwater Hale",
        items=[quickbooks, amex, shopify],
    )


def test_ac35_the_cards_fit_and_read_the_registrys_words() -> None:
    page = _por16a()
    words = _words()
    shown = {
        c.name: words[c.status.value].get("client_label", words[c.status.value]["label"])
        for c in page.items
    }
    assert shown == {
        "QuickBooks Online": "Connected",
        "American Express": "Needs reauth",
        "Shopify": "Not connected",
    }
    assert PortalConnectionsOut.model_validate(page.model_dump(mode="json")) == page


def test_ac35_the_connected_by_line_names_the_client() -> None:
    quickbooks = _por16a().items[0]
    assert quickbooks.connected_by is not None
    assert (quickbooks.connected_by.display_name, quickbooks.connected_by.kind) == (
        "Tess Moreno",
        "client",
    )
    assert quickbooks.connected_at is not None
    assert quickbooks.connected_at.date().isoformat() == "2026-03-04"


def test_ac36_a_start_states_the_authorization_and_nothing_else() -> None:
    assert ConnectionStartIn(consent_version=1, authorized=True).authorized
    with pytest.raises(ValidationError):
        ConnectionStartIn.model_validate({"consent_version": 1})
    with pytest.raises(ValidationError):
        ConnectionStartIn.model_validate(
            {"consent_version": 1, "authorized": True, "password": "x"}
        )
    responses = cast(Json, PATHS[START]["post"]["responses"])
    assert {"409", "422"} <= set(responses)  # live since A-02-T16: no longer 501
    assert RULES["connection.create"].mfa_recent


def test_ac38_no_scope_or_copy_offers_a_write() -> None:
    dumped = json.dumps(_por16a().model_dump(mode="json")).lower()
    for word in ("post entries", "post approved", "posts only", "accept entries"):
        assert word not in dumped
    for card in _por16a().items:
        assert all(s.code.endswith(".read") for s in card.scopes)


def test_ac38_the_portal_never_names_accrued() -> None:
    assert "accrued" not in json.dumps(_por16a().model_dump(mode="json")).lower()


@pytest.mark.parametrize("action", ACTIONS)
def test_ac41_the_agent_holds_no_c20_action(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent", "deny") == "deny"


def test_ac41_only_the_client_starts_a_connection() -> None:
    granted = {r for r, d in RULES["connection.create"].decisions.items() if d != "deny"}
    assert granted == {"client_admin"}
    assert RULES["connection.read"].scope_only
