"""C20 v1 stub, the POR-16 family and the integrations framework's ports (A-02-T06;
docs/contracts/c20-integrations.md; SPEC-333 AC-35 to AC-44, AC-49).

Every route exists with its one matrix action and answers 404 with its flag off and 501 with it
on; client-visible effects take an `Idempotency-Key`; every field is classified; statuses are
C2's `integration` codes; scopes never offer a write (DF-19); an empty write-capability registry
validates and no write can be enabled. Expectations come from A-02 §4.3 and §4.4. The consumers'
own tests are A-02-T08's, in this directory.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._flags import CONNECTIONS_LIVE_LEDGER, CONNECTIONS_PORTAL_V2
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.integrations import contract
from abacus.modules.integrations.api import (
    IntegrationAdapter,
    WriteCapabilityRegistry,
)

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ENTITY = "/v1/portal/entities/{entity_id}/connections"
CONN = "/v1/portal/connections/{connection_id}"

# (method, path) -> (the one matrix action, the flag that gates it)
ROUTES: dict[tuple[str, str], tuple[str, Flag]] = {
    ("get", ENTITY): ("connection.read", CONNECTIONS_PORTAL_V2),
    ("post", f"{ENTITY}/{{catalog_key}}/start"): ("connection.create", CONNECTIONS_PORTAL_V2),
    ("get", CONN): ("connection.read", CONNECTIONS_PORTAL_V2),
    ("post", f"{CONN}/retry"): ("connection.retry", CONNECTIONS_PORTAL_V2),
    ("post", f"{CONN}/disconnect"): ("connection.disconnect", CONNECTIONS_PORTAL_V2),
    ("post", "/v1/connections/{connection_id}/reconnect-requests"): (
        "connection.reconnect_request",
        CONNECTIONS_PORTAL_V2,
    ),
    ("post", "/v1/engagements/{engagement_id}/connection/pulls"): (
        "ledger.pull",
        CONNECTIONS_LIVE_LEDGER,
    ),
}
IDEMPOTENT = {path for (method, path) in ROUTES if method == "post"}
MODELS: tuple[type[BaseModel], ...] = (
    contract.PortalConnectionsOut,
    contract.PortalConnectionCardOut,
    contract.PortalConnectionDetailOut,
    contract.ConnectionStartIn,
    contract.ConnectionStartOut,
    contract.ConnectionDisconnectIn,
    contract.SyncRunRefOut,
    contract.ReconnectRequestOut,
    contract.LedgerPullIn,
    WriteCapabilityRegistry,
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_answers_404_and_501(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize("path", sorted(IDEMPOTENT))
def test_client_visible_effects_take_an_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_the_sign_in_url_is_restricted_and_the_status_is_the_registrys() -> None:
    start = cast(dict[str, Json], SCHEMAS["ConnectionStartOut"]["properties"])
    assert start["authorise_url"]["cls"] == "restricted"
    card = cast(dict[str, Json], SCHEMAS["PortalConnectionCardOut"]["properties"])
    assert card["status"].get("$ref") == "#/components/schemas/IntegrationStatus"


def test_the_start_needs_fresh_mfa_and_only_a_client_owner_may_start() -> None:
    rule = RULES["connection.create"]
    assert rule.mfa_recent
    assert {r for r, d in rule.decisions.items() if d != "deny"} == {"client_admin"}


def test_the_disconnect_is_the_owners_on_a_covered_entity_with_fresh_mfa() -> None:
    """DEC-379 (security review M3): a client admin whose grant covers entity A can't disconnect
    entity B's ledger, and destroying the secret needs a fresh second factor."""
    rule = RULES["connection.disconnect"]
    assert {r for r, d in rule.decisions.items() if d == "allow"} == {"client_admin"}
    assert rule.scope_only and rule.independence and rule.mfa_recent
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


@pytest.mark.parametrize("flag", [CONNECTIONS_PORTAL_V2, CONNECTIONS_LIVE_LEDGER])
async def test_flag_off_is_404_and_flag_on_is_501(
    flag: Flag, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []

    async def off(_tenant: object, f: object) -> bool:
        seen.append(f)
        return False

    async def on(_tenant: object, _f: object) -> bool:
        return True

    monkeypatch.setattr(contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await contract._stub(_ctx(), flag)  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == [flag]
    monkeypatch.setattr(contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await contract._stub(_ctx(), flag)  # pyright: ignore[reportPrivateUsage] -- the gate


def test_both_flags_are_off_by_default() -> None:
    assert CONNECTIONS_PORTAL_V2.default == CONNECTIONS_LIVE_LEDGER.default == "false"


# --- the write-capability registry schema (A-02 §2.2 item 6) -------------------------------------


def test_an_empty_registry_validates() -> None:
    registry = WriteCapabilityRegistry.model_validate({"version": 1})
    assert (registry.read_connectors, registry.writes) == ([], [])
    assert registry.egress_hosts() == frozenset()


def test_a_reserved_write_validates_but_can_never_be_enabled() -> None:
    reserved = {
        "key": "ledger_post_entries",
        "adapter_key": "quickbooks_online",
        "shape": "W1",
        "owner_epic": "C-02",
    }
    registry = WriteCapabilityRegistry.model_validate({"version": 1, "writes": [reserved]})
    assert registry.writes[0].enabled is False
    with pytest.raises(ValidationError):
        WriteCapabilityRegistry.model_validate(
            {"version": 1, "writes": [{**reserved, "enabled": True}]}
        )


def test_read_connectors_declare_hosts_and_scopes_once() -> None:
    entry = {
        "adapter_key": "quickbooks_online",
        "category": "ledger",
        "egress_hosts": ["quickbooks.api.intuit.com", "oauth.platform.intuit.com"],
        "read_scopes": ["ledger.read"],
    }
    registry = WriteCapabilityRegistry.model_validate({"version": 1, "read_connectors": [entry]})
    assert "oauth.platform.intuit.com" in registry.egress_hosts()
    with pytest.raises(ValidationError):
        WriteCapabilityRegistry.model_validate({"version": 1, "read_connectors": [entry, entry]})
    for bad_host in ("https://quickbooks.api.intuit.com", "localhost", "*.intuit.com"):
        with pytest.raises(ValidationError):
            WriteCapabilityRegistry.model_validate(
                {"version": 1, "read_connectors": [{**entry, "egress_hosts": [bad_host]}]}
            )
    with pytest.raises(ValidationError):
        WriteCapabilityRegistry.model_validate({"version": 2})


def test_the_adapter_port_has_no_write_method() -> None:
    members = {m for m in dir(IntegrationAdapter) if not m.startswith("_")}
    assert members == {"key", "category", "connector_provider", "read_scopes", "egress_hosts"}
