"""C5 v1.1 portal-half consumer tests (P-08-T02; SPEC-320 AC-6, AC-7, AC-15, AC-16 shapes): what
R-01, P-07 and G-02 rely on. Sign-in never tells one account from another (one shape for every
input); the lock and try facts are identifier-only; the home carries no firm status code, amount
or agent reference, and every to-do opens a manifest screen; branding is Public and names no
tenant and never "Accrued". Schema, matrix and documents only: the routes are stubs (or not
served yet, DEC-139). The TypeScript half is
`apps/web/src/fixtures/contracts/portal.contract.test.ts`."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast, get_args

import pytest
import yaml
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _statuses
from abacus.kernel.errors import check_facts
from abacus.modules.identity import portal_contract as identity
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.portal import contract as portal

Json = dict[str, object]
REPO = Path(__file__).resolve().parents[4]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VOCABULARY = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())["objects"],
)
CONTRACT = (REPO / "docs/contracts/portal-identity.md").read_text()
MANIFEST = (REPO / "apps/web/src/routes/manifest/por.ts").read_text()
STATUS_ENUMS = {
    name for name, value in vars(_statuses).items() if isinstance(value, type) and name[0] != "_"
}
FIRM_ROLES = {
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "security_admin",
    "firm_partner",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
}


def _schema_tree(name: str) -> dict[str, Json]:
    """`name` and every component schema it reaches, by name."""
    seen: dict[str, Json] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ref = cast(Json, node).get("$ref")
            if isinstance(ref, str):
                target = ref.rsplit("/", 1)[1]
                if target not in seen:
                    seen[target] = SCHEMAS[target]
                    walk(SCHEMAS[target])
            for value in cast(Json, node).values():
                walk(value)
        elif isinstance(node, list):
            for value in cast(list[object], node):
                walk(value)

    seen[name] = SCHEMAS[name]
    walk(SCHEMAS[name])
    return seen


def _properties(tree: dict[str, Json]) -> dict[str, Json]:
    """`Schema.field` to its property schema, over a schema tree."""
    return {
        f"{schema}.{field}": prop
        for schema, body in tree.items()
        for field, prop in cast(dict[str, Json], body.get("properties", {})).items()
    }


def _enum_values(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in cast(Json, node).items():
            if key == "enum":
                found |= {str(v) for v in cast(list[object], value)}
            elif key == "const":
                found.add(str(value))
            else:
                found |= _enum_values(value)
    elif isinstance(node, list):
        for value in cast(list[object], node):
            found |= _enum_values(value)
    return found


HOME = _schema_tree("PortalHomeOut")
HOME_FIELDS = _properties(HOME)


# ---- R-01 and POR-01: sign-in without enumeration (AC-6, AC-7) ---------------------------------


@pytest.mark.parametrize(
    "model",
    [identity.PortalSignInStartOut, identity.PortalLinkRenewOut],
    ids=lambda m: m.__name__,
)
def test_start_and_renew_answer_one_shape_for_any_input(model: type[BaseModel]) -> None:
    """Every field is either required or a constant: no field is present for one email or token
    and absent for another, and nothing in the body says whether an account exists."""
    for name, field in model.model_fields.items():
        assert field.is_required() or get_args(field.annotation) == (True,), name
    names = set(model.model_fields)
    assert not names & {"exists", "eligible", "contact_id", "user_id", "email", "tenant_id"}
    assert not any(n.startswith(("is_", "has_")) or "status" in n for n in names)


def test_start_carries_exactly_the_challenge_and_its_two_clocks() -> None:
    assert set(identity.PortalSignInStartOut.model_fields) == {
        "challenge_id",
        "code_expires_at",
        "resend_available_at",
    }
    assert set(identity.PortalLinkRenewOut.model_fields) == {"accepted"}


def test_preview_names_no_failure_reason_so_every_failure_is_the_same_404() -> None:
    names = set(identity.InvitationPreviewOut.model_fields)
    assert not names & {"status", "reason", "error", "expired", "revoked", "used"}
    assert "same 404" in (identity.InvitationPreviewOut.__doc__ or "")


@pytest.mark.parametrize(
    ("code", "facts"),
    [
        ("code_mismatch", {"tries_left": 2}),
        ("sign_in_locked", {"locked_until": "2026-09-14T14:37:00Z"}),
        ("resend_too_soon", {"resend_available_at": "2026-09-14T14:22:42Z"}),
        ("mfa_mismatch", {"tries_left": 1}),
        ("mfa_locked", {"locked_until": "2026-09-14T14:37:00Z"}),
    ],
)
def test_try_and_lock_facts_are_identifier_only_and_documented(
    code: str, facts: dict[str, object]
) -> None:
    assert check_facts(facts) == facts
    key = next(iter(facts))
    rows = [line for line in CONTRACT.splitlines() if f"`{code}" in line or f'"{code}"' in line]
    assert rows, f"{code} is not in the contract's error table"
    assert any(key in row for row in rows), f"{code} does not document `{key}`"


def test_the_lock_applies_to_an_email_that_matches_no_one() -> None:
    row = next(line for line in CONTRACT.splitlines() if '"sign_in_locked"' in line)
    assert "matches no one" in row


def test_verify_states_are_the_three_por01_branches() -> None:
    state = identity.PortalSignInVerifyOut.model_fields["state"].annotation
    assert set(get_args(state)) == {"signed_in", "mfa_required", "mfa_setup_required"}


def test_codes_tokens_and_secrets_are_restricted() -> None:
    restricted = {
        (identity.PortalSignInVerifyIn, "code"),
        (identity.PortalSignInVerifyOut, "access_token"),
        (identity.PortalSignInVerifyOut, "mfa_token"),
        (identity.PortalSignInStartIn, "link_token"),
        (identity.PortalSignInStartIn, "invitation_token"),
        (identity.PortalMfaIn, "totp"),
        (identity.PortalMfaIn, "backup_code"),
        (identity.PortalMfaSetupOut, "manual_key"),
        (identity.PortalMfaSetupVerifyOut, "backup_codes"),
        (identity.PortalLinkRenewIn, "link_token"),
        (identity.InvitationPreviewIn, "token"),
    }
    for model, field in restricted:
        extra = cast(Json, model.model_fields[field].json_schema_extra)
        assert extra["cls"] == "restricted", f"{model.__name__}.{field}"


# ---- R-01 and POR-02: the home carries no firm status, amount or agent (AC-15, AC-16) ----------


def test_the_home_references_no_status_registry_enum() -> None:
    reached = set(HOME) & STATUS_ENUMS
    assert not reached, f"the home reaches firm status enums {sorted(reached)}"


def test_no_home_field_is_a_status_field() -> None:
    named = [k for k in HOME_FIELDS if re.search(r"\.(status|\w+_status)$", k)]
    assert not named


# Client stage words that are also some firm object's code. The field is a client stage or a card
# position, never that object's status; any other overlap fails (a firm code leaking in).
COINCIDENT = {
    "open": "a to-do card's state, not an issue or note status",
    "overdue": "the request's derived overdue, the one status a to-do reflects (contract §4)",
    "done": "a stage position, not a close task's status",
    "current": "a stage position, not a checkpoint's status",
    "planning": "an audit client stage (POR-02 g), not the engagement's status",
    "fieldwork": "an audit client stage (POR-02 g), not the engagement's status",
    "testing": "a SOC 2 client stage (POR-02 h), not the control board's status",
    "scoping": "a SOC 2 client stage (POR-02 h), not the project's status",
    "review": "a client stage position, not F-06's derived `signing_step` (S14 batch)",
    "sign": "a client stage position, not F-06's derived `signing_step` (S14 batch)",
}


def test_home_codes_are_client_codes_not_firm_status_codes() -> None:
    firm_codes = {
        str(code)
        for body in VOCABULARY.values()
        for code in cast(dict[str, object], body.get("codes") or {})
    }
    leaked = (_enum_values(HOME) & firm_codes) - set(COINCIDENT)
    assert not leaked, f"firm status codes in the home: {sorted(leaked)}"


def test_the_firm_only_words_never_reach_the_home() -> None:
    values = _enum_values(HOME)
    # "In review · Manager" and "Draft K-1 · pre-release" (POR-02 AVOID) as codes.
    assert not values & {"in_review", "draft", "pre_release", "not_prepared", "released"}


_AMOUNT = re.compile(r"amount|balance|materiality|currency|price|fee|cents|usd|dollar")
_AGENT = re.compile(r"agent|run_id|model|confidence|suggest|draft|ai_|_ai$|citation")


def test_the_home_carries_no_amount() -> None:
    for key, prop in HOME_FIELDS.items():
        field = key.split(".", 1)[1]
        assert not _AMOUNT.search(field), key
        assert prop.get("type") != "number", key
        assert '"type": "number"' not in json.dumps(prop), key
        assert prop.get("format") != "decimal", key


def test_the_home_carries_no_agent_reference() -> None:
    for key in HOME_FIELDS:
        assert not _AGENT.search(key.split(".", 1)[1]), key
    assert not any("Agent" in name for name in HOME), sorted(HOME)


def test_every_home_target_is_a_portal_manifest_screen() -> None:
    for screen in get_args(portal.PortalScreen):
        assert f'"{screen}"' in MANIFEST, screen


def test_the_binder_card_is_counts_only_and_firm_attributed() -> None:
    fields = set(portal.PortalHomeBinderOut.model_fields)
    assert fields == {"binder_id", "done", "total", "sorted_count"}


def test_k1s_say_only_whether_released() -> None:
    assert "status" not in portal.PortalHomeK1Out.model_fields
    assert portal.PortalHomeK1Out.model_fields["released"].annotation is bool


def test_a_scope_is_read_through_its_grant_and_no_firm_role_reads_a_home() -> None:
    rule = RULES["portal_home.read"]
    assert rule.scope_only
    assert not {r for r, d in rule.decisions.items() if d != "deny"} & FIRM_ROLES
    params = cast(list[Json], PATHS["/v1/portal/home"]["get"].get("parameters", []))
    assert [p["name"] for p in params if p["in"] == "query"] == ["scope_id"]


def test_preferences_are_versioned_per_scope() -> None:
    assert set(portal.PortalPreferencesIn.model_fields) == {
        "scope_id",
        "welcome_dismissed",
        "version",
    }
    assert "portal_preferences_stale" in CONTRACT


# ---- R-01 and ADM-10: branding is Public and white-label (ADR-163) -----------------------------

NEUTRAL = portal.PortalBrandingOut(
    firm_name=None,
    portal_name=None,
    logo_url=None,
    address_line=None,
    help_url=None,
    privacy_url=None,
    support_contact_name=None,
    sign_in=portal.PortalSignInPolicyOut(methods=["email_code"], mfa_floor=[]),
)
BRIGHTWATER = portal.PortalBrandingOut(
    firm_name="Brightwater Hale LLP",
    portal_name="Brightwater Hale",
    logo_url="/v1/portal/branding/logo",
    address_line="Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL",
    help_url="https://brightwaterhale.example/help",
    privacy_url="https://brightwaterhale.example/privacy",
    support_contact_name="Grace Holloway",
    sign_in=portal.PortalSignInPolicyOut(
        methods=["email_code"], mfa_floor=["owner", "signer", "approver"]
    ),
)


def test_an_unknown_host_gets_the_same_shape_with_neutral_values() -> None:
    assert set(NEUTRAL.model_dump()) == set(BRIGHTWATER.model_dump())
    assert NEUTRAL.secured_footer is False and BRIGHTWATER.secured_footer is False


def test_branding_names_no_tenant_and_is_public_only() -> None:
    for model in (portal.PortalBrandingOut, portal.PortalSignInPolicyOut):
        for name, field in model.model_fields.items():
            assert "tenant" not in name and not name.endswith("_id"), name
            assert cast(Json, field.json_schema_extra)["cls"] == "public", name


def test_the_logo_is_served_same_origin() -> None:
    assert BRIGHTWATER.logo_url is not None and BRIGHTWATER.logo_url.startswith("/v1/")


# ---- White label across the portal half (AGENTS frontend rule 7, DEC-01) -----------------------

PORTAL_SCHEMAS = [
    "PortalHomeOut",
    "PortalPreferencesIn",
    "PortalPreferencesOut",
    "ContactPortalStatusOut",
    "ContactMfaResetOut",
    "MePortalOut",
    "MeMfaOut",
]


@pytest.mark.parametrize("name", PORTAL_SCHEMAS)
def test_no_portal_half_schema_says_accrued(name: str) -> None:
    for schema, body in _schema_tree(name).items():
        assert "accrued" not in json.dumps(body).lower(), schema


def _own_models() -> list[type[BaseModel]]:
    return [
        m
        for module in (identity, portal)
        for m in vars(module).values()
        if isinstance(m, type) and issubclass(m, BaseModel) and m.__module__ == module.__name__
    ]


@pytest.mark.parametrize("model", _own_models(), ids=lambda m: m.__name__)
def test_no_unserved_shape_says_accrued(model: type[BaseModel]) -> None:
    assert "accrued" not in json.dumps(model.model_json_schema()).lower()
    assert "accrued" not in BRIGHTWATER.model_dump_json().lower()


# ---- R-01 shell, P-07 (CLI-04) and G-02 (ADM-06) ---------------------------------------------


def test_the_shell_routes_every_landing_of_story_2_3_and_has_no_bell() -> None:
    assert set(get_args(identity.PortalLanding)) >= {
        "home",
        "requests",
        "k1s",
        "governance",
        "intake",
        "component_room",
    }
    nav = set(get_args(identity.PortalNavItem))
    assert "approvals" in nav
    assert not nav & {"notifications", "bell", "agent"}


def test_the_contact_portal_status_uses_the_invitation_words() -> None:
    codes = set(cast(dict[str, object], VOCABULARY["invitation"]["codes"]))
    assert {s.value for s in _statuses.InvitationStatus} == codes
    assert {"locked", "active"} <= codes


def test_recovery_is_a_named_firm_person_and_reset_needs_fresh_mfa() -> None:
    for action in ("contact.unlock", "contact.mfa_reset"):
        decisions = RULES[action].decisions
        assert decisions["agent"] == "deny" and decisions["system"] == "deny"
        granted = {r for r, d in decisions.items() if d != "deny"}
        assert granted and granted <= FIRM_ROLES
        assert not granted & {"client_admin", "client_contributor"}
    assert RULES["contact.mfa_reset"].mfa_recent
    assert "client_service" in RULES["contact.unlock"].decisions


def test_mfa_on_me_never_carries_the_factor() -> None:
    assert set(identity.MeMfaOut.model_fields) == {"enrolled", "required", "trusted_until"}
