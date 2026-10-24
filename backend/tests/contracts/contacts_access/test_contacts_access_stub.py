"""The contacts and portal-access contract stub, v1 (P-07-T17; `docs/contracts/contacts-access.md`;
DEC-226): every route exists with its one matrix action and answers 404 with `contacts.v2` off
(501 with it on until P-07-T25 made every route live); the list is the P-36 envelope with the
CLI-04 header counts and the delegated-requests footer; grants carry ADR-146's role and scope
codes and delegated request ids; the invitation never returns its token; every write is a
person's (the agent and the system are denied, no client role holds any action); no model has a
wall count. The consumer suite is P-07-T18's."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import CONTACTS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import contacts_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
CONTACT = "/v1/contacts/{contact_id}"
INVITATION = "/v1/invitations/{invitation_id}"

# (method, path) -> the one matrix action (P-07 §4.3, contacts and portal access).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/clients/{client_id}/contacts"): "contact.read",
    ("post", "/v1/clients/{client_id}/contacts"): "contact.manage",
    ("get", CONTACT): "contact.read",
    ("patch", CONTACT): "contact.manage",
    ("post", f"{CONTACT}/invitations"): "client_access.grant",
    ("post", f"{INVITATION}/resend"): "client_access.grant",
    ("post", f"{INVITATION}/revoke"): "client_access.revoke",
    ("put", f"{CONTACT}/access"): "client_access.grant",
    ("post", f"{CONTACT}/unlock"): "contact.unlock",
}
WRITES = {"contact.manage", "client_access.grant", "client_access.revoke", "contact.unlock"}
CLIENT_ROLES = {"client_admin", "client_contributor"}


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema]["properties"])


def _enum(schema: str, field: str) -> set[str]:
    prop = _props(schema)[field]
    if "$ref" in prop:
        ref = cast(str, prop["$ref"]).rsplit("/", 1)[-1]
        return set(cast(list[str], SCHEMAS[ref]["enum"]))
    return set(cast(list[str], prop["enum"]))


# Live since P-07-T25 (TASK-1123): no route here is a stub any more.
STUBBED: set[tuple[str, str]] = set()


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) in STUBBED)


def test_the_invitation_takes_an_idempotency_key_and_never_returns_its_token() -> None:
    op = PATHS[f"{CONTACT}/invitations"]["post"]
    headers = {p["name"] for p in cast(list[Json], op["parameters"]) if p["in"] == "header"}
    assert "Idempotency-Key" in headers
    assert not {f for f in _props("InvitationOut") if "token" in f or "link" in f}
    assert _props("InvitationIn")["expires_in_days"]["const"] == 14


def test_the_list_is_the_envelope_with_header_counts_and_the_delegated_footer() -> None:
    page = _props("ContactsPage")
    assert {"items", "next_cursor", "total", "counts", "summary", "delegated"} <= set(page)
    assert set(_props("ContactCountsOut")) == {"active", "invited", "not_invited", "locked"}
    assert set(_props("DelegatedFooterOut")) == {"parts", "total", "received"}
    assert {"active", "invited", "not_invited", "locked"} <= _enum(
        "ContactRowOut", "portal_status"
    )


def test_grants_carry_scope_kinds_and_delegated_requests() -> None:
    grant = _props("GrantIn")
    assert {"role", "scope_kind", "scope_id", "request_item_ids"} == set(grant)
    assert {"client", "client_entity", "engagement", "request_item", "intake"} <= _enum(
        "GrantIn", "scope_kind"
    )
    assert {"owner", "delegate", "third_party"} <= _enum("GrantIn", "role")
    assert {"client", "client_entity"} == _enum("ContactRoleIn", "scope_kind")


def test_every_field_is_classified_and_no_model_has_a_wall_count() -> None:
    for name, schema in SCHEMAS.items():
        if name.startswith(("Contact", "Grant", "Invitation", "Delegated", "SignInEvent")):
            props = cast(dict[str, Json], schema.get("properties", {}))
            assert all("cls" in p for p in props.values()), name
            assert not {p for p in props if "wall" in p or "hidden" in p}, name


@pytest.mark.parametrize("action", sorted(WRITES | {"contact.read"}))
def test_the_agent_and_the_system_are_denied_and_no_client_role_holds_it(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent", "deny") == "deny"
    assert rule.decisions.get("system", "deny") == "deny"
    assert not {r for r, d in rule.decisions.items() if d != "deny"} & CLIENT_ROLES


def test_contact_manage_is_the_firm_admin_partners_and_the_team_leads() -> None:
    granted = {r for r, d in RULES["contact.manage"].decisions.items() if d != "deny"}
    assert granted == {
        "firm_admin",
        "firm_partner",
        "engagement_partner",
        "manager",
        "client_service",
    }


async def test_flag_off_is_404_and_flag_on_passes_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contacts_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await contacts_contract._gate(ctx)  # pyright: ignore[reportPrivateUsage] -- the flag gate
    assert seen == [CONTACTS_V2]
    monkeypatch.setattr(contacts_contract, "flag_enabled", on)
    await contacts_contract._gate(ctx)  # pyright: ignore[reportPrivateUsage] -- the flag gate


def test_the_new_codes_are_in_the_catalogue() -> None:
    from pathlib import Path

    import yaml

    catalogue = Path(__file__).resolve().parents[4] / "docs/architecture/error-codes.yaml"
    codes = cast(dict[str, Json], yaml.safe_load(catalogue.read_text())["codes"])
    assert codes["invitation_expired"]["status"] == 409
    assert codes["invitation_used"]["status"] == 409
    assert codes["scope_outside_client"]["status"] == 422
