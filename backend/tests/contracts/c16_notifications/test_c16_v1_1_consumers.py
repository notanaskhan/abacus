"""C16 v1.1 consumer contract tests on behalf of R-01, P-06, N-02, A-02, A-08 and R-02 (R-01-T17;
TASK-1265; SPEC-345 AC-6, AC-7), run against the R-01-T16 stub.

Each consumer's template keys and the variables its emails need are whitelisted and register
through the slot. No variable can resolve to an amount, an account number or a TIN: the kinds are
a closed list without them, no variable is Restricted, and no variable is named like one. The
refusal reasons, the lint finding shape, the settings draft and publish shapes and the read-only
preview shape carry what POR-20 and ADM-10 need (docs/screens/POR-20.md, ADM-10.md) and nothing
more. Brightwater Hale, synthetic: Grace Holloway, Mon Sep 14, 2026."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import cast, get_args

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.modules.communications import template_registry
from abacus.modules.communications.api import (
    TEMPLATE_VARIABLES,
    FollowUpPolicyFields,
    SendRefusal,
)
from abacus.modules.communications.templates_contract import LintFindingOut
from abacus.modules.portal.settings_contract import (
    ClientExperienceFields,
    PortalBrandFields,
    PortalBrandOut,
    PortalPreviewOut,
    PortalSettingsDraftIn,
    PortalSettingsPersonOut,
    PortalSettingsVersionOut,
)

Json = dict[str, object]
SCHEMAS = cast(dict[str, Json], cast(Json, json.loads(document())["components"])["schemas"])
GRACE = PortalSettingsPersonOut(user_id=uuid.uuid4(), display_name="Grace Holloway")

# consumer -> {key: (audience, the variables its email uses, its call-to-action target)}
CONSUMERS: dict[str, dict[str, tuple[tuple[str, ...], tuple[str, ...], str]]] = {
    "R-01": {
        "invitation": (
            ("client", "third_party"),
            (
                "client_first_name",
                "firm_name",
                "inviter_name",
                "organisation_name",
                "scope_summary",
                "portal_link",
            ),
            "portal_home",
        ),
        "reminder": (
            ("client", "third_party"),
            (
                "client_first_name",
                "firm_name",
                "work_item",
                "open_items",
                "due_date",
                "portal_link",
                "staff_name",
            ),
            "documents",
        ),
    },
    "P-06": {
        "request_sent": (
            ("client",),
            ("client_first_name", "firm_name", "work_item", "open_items", "portal_link"),
            "documents",
        ),
        "request_returned": (
            ("client",),
            ("client_first_name", "firm_name", "work_item", "portal_link", "staff_name"),
            "request",
        ),
    },
    "N-02": {
        "signature_request": (
            ("client",),
            ("client_first_name", "firm_name", "document_title", "due_date", "portal_link"),
            "sign",
        ),
    },
    "A-02": {
        "reconnect_request": (
            ("client",),
            ("client_first_name", "firm_name", "portal_link", "connection_name"),
            "connections",
        ),
    },
    "A-08": {
        "confirmation_request": (
            ("respondent",),
            ("respondent_org", "firm_name", "organisation_name", "due_date", "portal_link"),
            "confirm",
        ),
    },
    "R-02": {
        "deliverable_ready": (
            ("client",),
            ("client_first_name", "firm_name", "deliverable_title", "portal_link"),
            "deliverables",
        ),
    },
}
FORBIDDEN_KINDS = {"amount", "money", "balance", "account_number", "account", "tin", "ssn", "ein"}
FORBIDDEN_NAME = re.compile(r"amount|balance|total|account|acct|tin\b|ssn|ein\b|iban|routing")


# --- AC-7 the whitelist can never carry an amount, an account number or a TIN --------------------


def test_ac7_the_kind_list_has_no_amount_account_or_tin() -> None:
    kinds = set(get_args(template_registry.VariableKind))
    assert kinds == {
        "person_name",
        "organisation_name",
        "title",
        "item_list",
        "date",
        "secure_link",
        "summary",
    }
    assert not kinds & FORBIDDEN_KINDS


@pytest.mark.parametrize("name", sorted(TEMPLATE_VARIABLES))
def test_ac7_no_variable_resolves_to_an_amount_an_account_or_a_tin(name: str) -> None:
    variable = TEMPLATE_VARIABLES[name]
    assert variable.name == name
    assert variable.kind not in FORBIDDEN_KINDS
    assert variable.classification != "restricted"
    assert not FORBIDDEN_NAME.search(name)


def test_ac7_the_editor_shows_the_same_closed_kinds() -> None:
    kind = cast(dict[str, Json], SCHEMAS["TemplateVariableOut"]["properties"])["kind"]
    assert set(cast(list[str], kind["enum"])) == set(get_args(template_registry.VariableKind))


def test_ac7_the_whitelist_is_r01s() -> None:
    assert set(template_registry.GENERAL_VARIABLES) <= set(TEMPLATE_VARIABLES)
    assert set(TEMPLATE_VARIABLES) == set(template_registry.GENERAL_VARIABLES) | {
        "inviter_name",
        "organisation_name",
        "scope_summary",
        "document_title",
        "deliverable_title",
        "respondent_org",
        "connection_name",
    }
    assert [n for n, v in TEMPLATE_VARIABLES.items() if v.block] == ["open_items"]


# --- AC-6 each consumer's keys ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("consumer", "key"), [(c, k) for c, keys in CONSUMERS.items() for k in keys]
)
def test_ac6_each_consumers_key_registers_with_whitelisted_variables(
    consumer: str, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(template_registry, "_REGISTERED", {})
    audience, variables, target = CONSUMERS[consumer][key]
    assert set(variables) <= set(TEMPLATE_VARIABLES), consumer
    registration = template_registry.register_email_template(
        key,
        cast(tuple[template_registry.TemplateAudience, ...], audience),
        variables,
        (cast(template_registry.CtaTarget, target),),
        (),
        firm_editable=True,
    )
    assert registration.variables == variables
    assert "portal_link" in variables  # every client email links to the portal, never a file


def test_ac6_the_refusal_reasons_are_the_four() -> None:
    assert set(get_args(SendRefusal)) == {
        "template_missing",
        "template_lint_failed",
        "firm_not_client_facing",
        "suppressed",
    }


def test_ac6_a_lint_finding_names_where_never_what() -> None:
    props = set(cast(dict[str, Json], SCHEMAS["LintFindingOut"]["properties"]))
    assert props == {"code", "block_id", "variable"}
    codes = set(get_args(template_registry.LintCode))
    assert {"amount", "tin_shape", "account_number", "platform_name"} <= codes
    finding = LintFindingOut(code="amount", block_id="body-2")
    assert finding.model_dump() == {"code": "amount", "block_id": "body-2", "variable": None}


# --- AC-6 the settings draft and publish, and the preview ---------------------------------------


def _policy(cadence: int = 7) -> FollowUpPolicyFields:
    return FollowUpPolicyFields(cadence_days=cadence)


def test_ac6_adm10_b_saves_a_five_day_cadence() -> None:
    draft = PortalSettingsDraftIn(
        brand=PortalBrandFields(
            portal_name="Brightwater Hale", sender_display_name="Brightwater Hale"
        ),
        client_experience=ClientExperienceFields(),
        follow_up_policy=_policy(5),
        expected_version=1,
    )
    assert draft.follow_up_policy.cadence_days == 5
    assert draft.follow_up_policy.mode == "draft_for_person"  # DEC-74: a person sends
    assert draft.client_experience.allow_upload_something_else is False
    assert draft.brand.secured_footer is False  # DEC-59


@pytest.mark.parametrize(
    "change",
    [
        {"follow_up_policy": {"cadence_days": 31}},
        {"follow_up_policy": {"max_reminders": 5}},
        {"follow_up_policy": {"send_local_time": "9am"}},
        {"brand": {"portal_name": "x", "sender_display_name": "x", "accent": "teal"}},
    ],
)
def test_ac6_the_draft_refuses_what_adm10_never_offers(change: dict[str, object]) -> None:
    base: dict[str, object] = {
        "brand": {"portal_name": "Brightwater Hale", "sender_display_name": "Brightwater Hale"},
        "client_experience": {},
        "follow_up_policy": {},
        "expected_version": 1,
    }
    with pytest.raises(ValidationError):
        PortalSettingsDraftIn.model_validate({**base, **change})


def test_ac6_a_published_version_keeps_the_accent_and_host_fixed() -> None:
    version = PortalSettingsVersionOut(
        version=2,
        brand=PortalBrandOut(
            portal_name="Brightwater Hale",
            sender_display_name="Brightwater Hale",
            portal_host="brightwaterhale.portal.example",
        ),
        client_experience=ClientExperienceFields(),
        follow_up_policy=_policy(),
        content_sha256="0" * 64,
        published_at=datetime(2026, 9, 14, 14, 30, tzinfo=UTC),
        published_by=GRACE,
    )
    assert version.brand.accent == "espresso"
    brand = cast(dict[str, Json], SCHEMAS["PortalBrandOut"]["properties"])
    assert brand["accent"].get("const") == "espresso" or brand["accent"].get("enum") == [
        "espresso"
    ]
    assert "accrued" not in json.dumps(version.model_dump(mode="json")).lower()


def test_ac6_the_preview_is_read_only_and_offers_no_action() -> None:
    props = cast(dict[str, Json], SCHEMAS["PortalPreviewOut"]["properties"])
    assert props["read_only"].get("const") is True or props["read_only"].get("enum") == [True]
    assert "allowed_actions" not in props
    assert "session" not in json.dumps(props).lower()
    with pytest.raises(ValidationError):
        PortalPreviewOut.model_validate({"read_only": False})
