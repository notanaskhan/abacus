"""C16 v1.1 stub, the POR-20 and ADM-10 family (R-01-T16; SPEC-345 AC-1 to AC-5; R-01 §4.3).

Every route exists with its one matrix action. Writes answer 404 with their flag off and 501 with
it on; reads and the onboarding import are never flag-gated and answer 501 until built. Client-
visible effects carry an `Idempotency-Key`; publish, import and the settings writes need a fresh
second factor; the agent and system hold none of the actions; every field is classified. The
`register_email_template` slot refuses what the whitelist does not allow, and `send_templated`
refuses to run until R-01-T19. C16 v1 stays frozen (`test_c16_frozen.py`)."""

from __future__ import annotations

import inspect
import json
import typing
import uuid
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import (
    COMMUNICATIONS_FIRM_SENDER_DOMAIN,
    FOLLOW_UPS_SCHEDULED_SEND,
    PORTAL_SETTINGS_EDITOR,
)
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.communications import template_registry, templates_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import settings_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
T = "/v1/firm/email-templates"
D = "/v1/firm/sending-domains"
S = "/v1/firm/portal-settings"
EDITOR, SENDER = PORTAL_SETTINGS_EDITOR, COMMUNICATIONS_FIRM_SENDER_DOMAIN

# (method, path) -> (the one matrix action, the flag that gates it or None)
ROUTES: dict[tuple[str, str], tuple[str, Flag | None]] = {
    ("get", T): ("email_template.read", None),
    ("post", f"{T}/import"): ("email_template.import", None),
    ("get", f"{T}/{{key}}"): ("email_template.read", None),
    ("put", f"{T}/{{key}}/draft"): ("email_template.edit", EDITOR),
    ("delete", f"{T}/{{key}}/draft"): ("email_template.edit", EDITOR),
    ("post", f"{T}/{{key}}/preview"): ("email_template.read", None),
    ("post", f"{T}/{{key}}/test-send"): ("email_template.test_send", EDITOR),
    ("post", f"{T}/{{key}}/publish"): ("email_template.publish", EDITOR),
    ("get", D): ("sending_domain.read", None),
    ("post", D): ("sending_domain.manage", SENDER),
    ("post", f"{D}/{{domain_id}}/check"): ("sending_domain.manage", SENDER),
    ("delete", f"{D}/{{domain_id}}"): ("sending_domain.manage", SENDER),
    ("get", "/v1/firm/follow-up-policy"): ("portal_settings.read", None),
    ("get", S): ("portal_settings.read", None),
    ("put", f"{S}/draft"): ("portal_settings.manage", EDITOR),
    ("delete", f"{S}/draft"): ("portal_settings.manage", EDITOR),
    ("post", f"{S}/publish"): ("portal_settings.manage", EDITOR),
    ("post", f"{S}/logo"): ("portal_settings.manage", EDITOR),
    ("get", f"{S}/preview"): ("portal.preview", None),
}
IDEMPOTENT = {f"{T}/{{key}}/test-send", f"{T}/{{key}}/publish", D, f"{S}/publish"}
FRESH_MFA = {"email_template.publish", "email_template.import", "sending_domain.manage"} | {
    "portal_settings.manage",
    "email_template.test_send",  # DEC-379: a sample contact's titles leave the firm
}
ACTIONS = sorted({action for action, _ in ROUTES.values()})
MODELS: tuple[type[BaseModel], ...] = (
    templates_contract.EmailTemplateListOut,
    templates_contract.EmailTemplateOut,
    templates_contract.EmailTemplateDraftIn,
    templates_contract.EmailPreviewIn,
    templates_contract.EmailPreviewOut,
    templates_contract.EmailTestSendOut,
    templates_contract.FirmEmailTemplateImportIn,
    templates_contract.FirmEmailTemplateImportOut,
    templates_contract.SendingDomainIn,
    templates_contract.SendingDomainListOut,
    templates_contract.FollowUpPolicyOut,
    settings_contract.PortalSettingsOut,
    settings_contract.PortalSettingsDraftIn,
    settings_contract.PortalPreviewOut,
    settings_contract.PortalLogoOut,
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize("path", sorted(IDEMPOTENT))
def test_ac1_client_visible_effects_take_an_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_ac2_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_ac2_the_v1_import_model_is_untouched() -> None:
    schemas = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
    assert {"EmailTemplateImportIn", "FirmEmailTemplateImportIn"} <= set(schemas)


@pytest.mark.parametrize("action", ACTIONS)
def test_ac3_the_agent_and_system_hold_none(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny" and decisions.get("system") == "deny"
    for client in ("client_admin", "client_contributor"):
        assert decisions.get(client, "deny") == "deny"


@pytest.mark.parametrize("action", ACTIONS)
def test_ac3_fresh_mfa_where_the_plan_says(action: str) -> None:
    assert RULES[action].mfa_recent == (action in FRESH_MFA)


def test_ac3_a_test_send_needs_an_onshore_member() -> None:
    """DEC-379 (security review L1): a test send with a sample contact emails that client's
    request titles out of the firm."""
    assert RULES["email_template.test_send"].not_offshore


def test_ac3_who_holds_what() -> None:
    def holders(action: str) -> set[str]:
        return {r for r, d in RULES[action].decisions.items() if d == "allow"}

    assert holders("email_template.read") == {"firm_admin", "practice_leader"}
    assert holders("email_template.publish") == {"firm_admin"}
    assert holders("sending_domain.manage") == {"firm_admin", "security_admin"}
    assert holders("portal_settings.read") == {"firm_admin", "practice_leader"}
    assert holders("portal.preview") == {"firm_admin"}


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


@pytest.mark.parametrize("module", [templates_contract, settings_contract])
@pytest.mark.parametrize("flag", [EDITOR, SENDER, None])
async def test_ac4_flag_off_is_404_and_on_is_501(
    module: ModuleType, flag: Flag | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def off(_tenant: object, _f: object) -> bool:
        return False

    async def on(_tenant: object, _f: object) -> bool:
        return True

    stub = module._stub  # the stub gate, tested directly
    monkeypatch.setattr(module, "flag_enabled", off)
    if flag is None:  # ungated reads and the import: 501 whatever the flags say
        with pytest.raises(NotImplementedYet):
            await stub(_ctx(), flag)
    else:
        with pytest.raises(NotFound):
            await stub(_ctx(), flag)
    monkeypatch.setattr(module, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await stub(_ctx(), flag)


def test_ac4_every_new_flag_is_off_by_default() -> None:
    for flag in (EDITOR, SENDER, FOLLOW_UPS_SCHEDULED_SEND):
        assert flag.default == "false"


async def test_ac4_a_scheduled_policy_sends_only_with_its_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    async def off(_tenant: object, f: object) -> bool:
        seen.append(f)
        return False

    monkeypatch.setattr(template_registry, "flag_enabled", off)
    assert await template_registry.scheduled_send_enabled(_ctx().tenant) is False
    assert seen == [FOLLOW_UPS_SCHEDULED_SEND]


# --- AC-5 the slot and send_templated ------------------------------------------------------------


def test_ac5_the_slot_registers_a_whitelisted_key_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(template_registry, "_REGISTERED", {})
    register = template_registry.register_email_template
    reg = register(
        "reconnect_request",
        ("client",),
        ("client_first_name", "firm_name", "portal_link", "connection_name"),
        ("connections",),
        ("POR-16", "AUD-06"),
        firm_editable=True,
    )
    assert reg.key == "reconnect_request"
    assert [r.key for r in template_registry.registered_templates()] == ["reconnect_request"]
    invalid = template_registry.TemplateRegistrationInvalid
    with pytest.raises(invalid):  # twice
        register("reconnect_request", ("client",), (), (), (), firm_editable=True)
    with pytest.raises(invalid):  # not whitelisted
        register("x_amount", ("client",), ("balance_due",), (), (), firm_editable=True)
    with pytest.raises(invalid):  # two buttons for one audience
        register("two_ctas", ("client",), (), ("documents", "sign"), (), firm_editable=True)
    with pytest.raises(invalid):  # not a screen id
        register("bad_used_by", ("client",), (), (), ("reminders",), firm_editable=True)
    with pytest.raises(invalid):  # staff templates are platform-locked
        register("staff_note", ("staff",), (), (), (), firm_editable=True)


async def test_ac5_send_templated_refuses_to_run_until_built() -> None:
    scope = template_registry.SendScope(engagement_id=uuid.uuid4())
    recipient = template_registry.RecipientRef("contact", uuid.uuid4())
    with pytest.raises(NotImplementedYet):
        await template_registry.send_templated(
            _ctx(),
            "reminder",
            recipient,
            {"client_first_name": "Claire"},
            scope=scope,
            idempotency_key="k",
        )
    system = template_registry.SystemSendContext(_ctx().tenant, "scheduled_follow_up", 1)
    with pytest.raises(NotImplementedYet):
        await template_registry.send_templated(
            system, "reminder", recipient, {}, scope=scope, idempotency_key="k"
        )


def test_ac5_send_templated_takes_the_callers_context_and_an_engagement() -> None:
    """DEC-379 (security review M1): no caller-asserted actor; `message.send` is authorised
    inside, on the engagement the message is about, and the scope check can refuse."""
    signature = inspect.signature(template_registry.send_templated)
    first = next(iter(signature.parameters.values()))
    assert first.name == "ctx"
    assert "AuthContext" in str(first.annotation) and "SystemSendContext" in str(first.annotation)
    assert "scope" in signature.parameters and "actor" not in signature.parameters
    assert "out_of_scope" in typing.get_args(template_registry.SendRefusal)
    assert RULES["message.send"].independence
