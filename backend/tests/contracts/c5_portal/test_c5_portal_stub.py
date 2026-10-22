"""C5 v1.1 portal-half stub (P-08-T01; SPEC-320 AC-1 to AC-5): every served route exists with its
one matrix action and answers 404 with its flag off and 501 with it on; the firm-side recovery
actions are human-only; the client actions grant no firm role; every model field is classified;
`/v1/me` grows only optional fields; and the pre-session family is not served (DEC-139). The
consumers' own tests are P-08-T02's, in this directory."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.api.public_routes import PUBLIC_ROUTES
from abacus.kernel._flags import PORTAL_HOME_V2, PORTAL_SIGN_IN_V2
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.identity import portal_contract as identity_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import contract as portal_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
CONTACT = "/v1/clients/{client_id}/contacts/{contact_id}"

# (method, path) -> the one matrix action (P-08 §4.3; DEC-139 spelling).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/portal/home"): "portal_home.read",
    ("put", "/v1/portal/preferences"): "portal_preferences.update",
    ("post", f"{CONTACT}/portal-unlock"): "contact.unlock",
    ("post", f"{CONTACT}/mfa-reset"): "contact.mfa_reset",
}
HUMAN_ONLY = {"contact.unlock", "contact.mfa_reset"}
CLIENT_ONLY = {"portal_home.read", "portal_preferences.update"}
# Pre-session routes: answer before any session, so they wait for ADR-152's list (DEC-139).
PRE_SESSION = (
    "/v1/portal/branding",
    "/v1/portal/branding/logo",
    "/v1/portal/auth/start",
    "/v1/portal/auth/verify",
    "/v1/portal/auth/resend",
    "/v1/portal/auth/mfa",
    "/v1/portal/auth/mfa/setup",
    "/v1/portal/auth/mfa/setup/verify",
    "/v1/portal/auth/refresh",
    "/v1/portal/links/renew",
    "/v1/invitations/preview",
)


def _models(module: ModuleType) -> list[type[BaseModel]]:
    return [
        v
        for v in vars(module).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v is not BaseModel
        and v.__module__ == module.__name__
    ]


MODELS = _models(portal_contract) + _models(identity_contract)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_ac1_preferences_document_the_version_conflict() -> None:
    assert "409" in cast(Json, PATHS["/v1/portal/preferences"]["put"]["responses"])


def test_ac1_the_mfa_reset_emails_the_client_so_takes_an_idempotency_key() -> None:
    params = cast(list[Json], PATHS[f"{CONTACT}/mfa-reset"]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_ac2_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_ac2_branding_is_public_only_and_carries_no_tenant() -> None:
    def levels(model: type[BaseModel]) -> set[object]:
        return {level_of(f) for f in model.model_fields.values()}

    assert levels(portal_contract.PortalBrandingOut) == {"public"}
    assert levels(portal_contract.PortalSignInPolicyOut) == {"public"}
    assert not any("tenant" in name for name in portal_contract.PortalBrandingOut.model_fields)


def test_ac2_the_portal_status_is_the_invitation_registry_enum() -> None:
    prop = cast(dict[str, Json], SCHEMAS["ContactPortalStatusOut"]["properties"])
    assert prop["portal_status"]["$ref"] == "#/components/schemas/InvitationStatus"


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY | CLIENT_ONLY))
def test_ac3_every_portal_half_action_denies_the_agent_and_system(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny"
    assert decisions.get("system") == "deny"


@pytest.mark.parametrize("action", sorted(CLIENT_ONLY))
def test_ac3_client_actions_grant_no_firm_role(action: str) -> None:
    granted = {r for r, d in RULES[action].decisions.items() if d != "deny"}
    assert granted == {"client_admin", "client_contributor"}


def test_ac3_the_home_reads_one_covered_scope_and_recovery_is_firm_side() -> None:
    assert RULES["portal_home.read"].scope_only
    unlock = {r for r, d in RULES["contact.unlock"].decisions.items() if d == "allow"}
    assert unlock == {
        "firm_admin",
        "security_admin",
        "engagement_partner",
        "manager",
        "client_service",
    }
    reset = RULES["contact.mfa_reset"]
    assert {r for r, d in reset.decisions.items() if d == "allow"} == {"security_admin"}
    assert reset.mfa_recent


Stub = Callable[[AuthContext], Awaitable[object]]


@pytest.mark.parametrize(
    ("module", "flag"),
    [(portal_contract, PORTAL_HOME_V2), (identity_contract, PORTAL_SIGN_IN_V2)],
    ids=["portal.home_v2", "portal.sign_in_v2"],
)
async def test_ac4_flag_off_is_404_and_flag_on_is_501(
    module: ModuleType, flag: Flag, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = cast(Stub, module._stub)  # the stub gate, tested directly
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, asked: object) -> bool:
        seen.append(asked)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(module, "flag_enabled", off)
    with pytest.raises(NotFound):
        await stub(ctx)
    assert seen == [flag]
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(ctx)


@pytest.mark.parametrize("flag", [PORTAL_HOME_V2, PORTAL_SIGN_IN_V2], ids=lambda f: f.name)
def test_ac4_both_flags_are_boolean_and_default_off(flag: Flag) -> None:
    assert flag.kind == "boolean"
    assert flag.default == "false"


def test_ac5_me_gains_only_optional_portal_and_mfa_fields() -> None:
    me = SCHEMAS["MeOut"]
    props = cast(dict[str, Json], me["properties"])
    assert {"portal", "mfa"} <= set(props)
    assert not {"portal", "mfa"} & set(cast(list[str], me.get("required", [])))


@pytest.mark.parametrize("path", PRE_SESSION)
def test_ac5_the_pre_session_family_is_not_served_by_the_stub(path: str) -> None:
    assert path not in PATHS
    assert path not in PUBLIC_ROUTES
