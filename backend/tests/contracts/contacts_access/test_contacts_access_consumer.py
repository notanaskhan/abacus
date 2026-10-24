"""Contacts and portal-access consumer contract tests (P-07-T18; SPEC-321 AC-26 to AC-29;
`docs/contracts/contacts-access.md`): what CLI-04 relies on, read from the OpenAPI document as a
consumer reads the generated client, plus CLI-04 a's frame validated by the contract's models.
Schema shape only: they run against the stub and keep holding once P-07-T25 makes the routes live.

Brightwater Hale, synthetic: Northwind's six contacts and their delegated requests from the screen
contract (`docs/screens/CLI-04.md`) and the contract's §8; ids are placeholders.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import cast, get_args

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.identity.api import GrantRole, ScopeKind
from abacus.modules.organisations.contacts_contract import ContactsPage, InvitationIn

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VOCABULARY = Path(__file__).resolve().parents[4] / "docs" / "product" / "status-vocabulary.yaml"
INVITATION_CODES = set(
    cast(
        dict[str, object], yaml.safe_load(VOCABULARY.read_text())["objects"]["invitation"]["codes"]
    )
)
GRANT_ROLES = set(get_args(GrantRole))
SCOPE_KINDS = set(get_args(ScopeKind))
WALL_NAME = re.compile(r"(hidden|walled|wall_count|by_wall)")
SECRET_NAME = re.compile(r"(token|link|url|secret)")
CONTACT_SCHEMAS = (
    "ContactsPage",
    "ContactRowOut",
    "ContactRoleOut",
    "ContactCountsOut",
    "DelegatedFooterOut",
    "ContactDetailOut",
    "GrantOut",
    "SignInEventOut",
    "ContactOut",
    "InvitationOut",
    "InvitationRevokedOut",
    "ContactAccessOut",
    "ContactUnlockedOut",
)
CONTACT_PATHS = (
    "/v1/clients/{client_id}/contacts",
    "/v1/contacts/{contact_id}",
    "/v1/contacts/{contact_id}/invitations",
    "/v1/invitations/{invitation_id}/resend",
    "/v1/invitations/{invitation_id}/revoke",
    "/v1/contacts/{contact_id}/access",
    "/v1/contacts/{contact_id}/unlock",
)


def _id(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _row(n: int, name: str, status: str, delegated: int, **extra: object) -> Json:
    return {
        "id": _id(n),
        "name": name,
        "party_kind": extra.pop("party_kind", "person"),
        "portal_status": status,
        "delegated_request_count": delegated,
        **extra,
    }


# CLI-04 a, Mon Sep 14, 2026, 9:24 AM CT, for Grace Holloway on Northwind Robotics, Inc.
NORTHWIND = _id(900)
CLI04_A: Json = {
    "items": [
        _row(
            1,
            "Dana Kowalski",
            "active",
            10,
            email="dana.kowalski@northwindrobotics.com",
            mfa_enrolled=True,
            last_seen_at="2026-09-14T13:02:00Z",
            roles=[
                {
                    "role": "plan_sponsor_officer",
                    "scope_kind": "client",
                    "scope_id": NORTHWIND,
                    "scope_name": "Northwind Robotics, Inc.",
                    "title_text": "HR Director",
                },
            ],
        ),
        _row(
            2, "Northwind benefits committee", "active", 0, party_kind="group", mfa_enrolled=True
        ),
        _row(
            3,
            "Sam Ortiz",
            "active",
            9,
            email="sam.ortiz@keystoneretirement.com",
            mfa_enrolled=True,
            roles=[
                {
                    "role": "recordkeeper",
                    "scope_kind": "client",
                    "scope_id": NORTHWIND,
                    "scope_name": "Northwind Robotics, Inc.",
                },
            ],
        ),
        _row(
            4,
            "Summit Plan Administrators",
            "invited",
            2,
            party_kind="organisation",
            invited_on="2026-09-10",
            expires_on="2026-09-24",
        ),
        _row(5, "Harborline Trust Company", "not_invited", 2, party_kind="organisation"),
        _row(6, "PayGrid Payroll", "not_invited", 1, party_kind="organisation"),
    ],
    "total": 6,
    "counts": {"active": 3, "invited": 1, "not_invited": 2},
    "summary": {"active": 3, "invited": 1, "not_invited": 2, "locked": 0},
    "delegated": {"parts": [10, 9, 2, 2, 1], "total": 24, "received": 11},
}


# --- AC-26: the envelope and the row ------------------------------------------------------------


def test_ac26_the_list_is_the_p36_envelope_with_the_header_and_the_footer() -> None:
    page = _props("ContactsPage")
    assert {"items", "next_cursor", "total", "counts", "facets"} <= set(page)
    assert {"summary", "delegated"} <= set(page)
    assert set(_props("ContactCountsOut")) == {"active", "invited", "not_invited", "locked"}
    assert set(_props("DelegatedFooterOut")) == {"parts", "total", "received"}
    params = cast(list[Json], PATHS["/v1/clients/{client_id}/contacts"]["get"]["parameters"])
    assert {"portal_status", "sort", "cursor", "limit"} <= {cast(str, p["name"]) for p in params}


def test_ac26_the_row_carries_cli04s_columns() -> None:
    assert {
        "name",
        "party_kind",
        "email",
        "roles",
        "portal_status",
        "invited_on",
        "expires_on",
        "mfa_enrolled",
        "last_seen_at",
        "delegated_request_count",
        "allowed_actions",
    } <= set(_props("ContactRowOut"))
    assert {"role", "scope_kind", "scope_id", "scope_name", "title_text"} <= set(
        _props("ContactRoleOut")
    )


def test_ac26_portal_status_is_exactly_the_registry_invitation_codes() -> None:
    assert set(cast(list[str], SCHEMAS["InvitationStatus"]["enum"])) == INVITATION_CODES
    assert _props("ContactRowOut")["portal_status"]["$ref"] == (
        "#/components/schemas/InvitationStatus"
    )


# --- AC-27: CLI-04 a foots ----------------------------------------------------------------------


def test_ac27_cli04_a_is_a_valid_page() -> None:
    page = ContactsPage.model_validate(CLI04_A)
    assert len(page.items) == page.total == 6


def test_ac27_the_header_counts_sum_to_the_rows_and_agree_with_counts() -> None:
    page = ContactsPage.model_validate(CLI04_A)
    summary = page.summary
    assert (summary.active, summary.invited, summary.not_invited) == (3, 1, 2)
    assert summary.active + summary.invited + summary.not_invited + summary.locked == page.total
    by_status: dict[str, int] = {}
    for row in page.items:
        by_status[row.portal_status] = by_status.get(row.portal_status, 0) + 1
    assert by_status == page.counts
    assert {k: v for k, v in summary.model_dump().items() if v} == page.counts


def test_ac27_the_footer_is_the_non_zero_row_counts_in_order_summing_to_24() -> None:
    page = ContactsPage.model_validate(CLI04_A)
    parts = [row.delegated_request_count for row in page.items if row.delegated_request_count]
    assert page.delegated.parts == parts == [10, 9, 2, 2, 1]
    assert sum(page.delegated.parts) == page.delegated.total == 24
    assert 0 <= page.delegated.received <= page.delegated.total
    assert page.delegated.received == 11  # "PBC received 11 of 24"; 13 open = 24 - 11


# --- AC-28: grants, expiry and no token ---------------------------------------------------------


def test_ac28_grants_carry_adr146s_codes_and_delegated_request_ids() -> None:
    for schema in ("GrantIn", "GrantOut"):
        grant = _props(schema)
        assert {"role", "scope_kind", "scope_id", "request_item_ids"} <= set(grant)
        assert set(cast(list[str], grant["role"]["enum"])) == GRANT_ROLES
        assert set(cast(list[str], grant["scope_kind"]["enum"])) == SCOPE_KINDS
    assert set(cast(list[str], _props("GrantOut")["status"]["enum"])) == {
        "pending",
        "active",
        "revoked",
    }


def test_ac28_an_invitation_expires_in_14_days_and_nothing_else() -> None:
    assert InvitationIn.model_validate({"grants": [_grant()]}).expires_in_days == 14
    with pytest.raises(ValueError):
        InvitationIn.model_validate({"grants": [_grant()], "expires_in_days": 7})
    with pytest.raises(ValueError):
        InvitationIn.model_validate({"grants": []})


def _grant() -> Json:
    return {
        "role": "third_party",
        "scope_kind": "request_item",
        "scope_id": _id(77),
        "request_item_ids": [_id(77), _id(78)],
    }


@pytest.mark.parametrize("path", CONTACT_PATHS)
def test_ac28_no_contacts_response_carries_a_token_or_link(path: str) -> None:
    seen: set[str] = set()
    for op in PATHS[path].values():
        for ref in re.findall(r'"#/components/schemas/([A-Za-z_]+)"', json.dumps(op["responses"])):
            seen.add(ref)
    assert seen, path
    for schema in seen:
        if schema in ("HTTPValidationError", "ValidationError", "ErrorOut"):
            continue
        assert not [p for p in _props(schema) if SECRET_NAME.search(p)], schema


# --- AC-29: no wall field, no Restricted field --------------------------------------------------


@pytest.mark.parametrize("schema", CONTACT_SCHEMAS)
def test_ac29_no_contacts_schema_has_a_wall_or_restricted_field(schema: str) -> None:
    props = _props(schema)
    assert not [p for p in props if WALL_NAME.search(p)], schema
    assert all(p.get("cls") != "restricted" for p in props.values()), schema
