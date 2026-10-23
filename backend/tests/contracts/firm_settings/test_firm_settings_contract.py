"""The firm-settings family contract stub, v1 (G-01-T02) and its consumer tests (G-01-T03):
every new route declares exactly one matrix action and answers 404 with `firm_settings.v2` off
and 501 with it on; no schema carries a hidden or hidden-count field or any field derived from
walled rows (DEC-43, AC8.7); statuses are the registry's codes; the role grid carries a locked
row's shape; every write denies the agent and the system (INV-1); region is never writable."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import FIRM_SETTINGS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.identity import settings_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.organisations import settings_contract as org_settings

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

# (method, path) -> the one matrix action (G-01 section 4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/firm/settings/overview"): "firm.read_settings",
    ("get", "/v1/firm/settings/{section}"): "firm.read_settings",
    ("patch", "/v1/firm/settings/{section}"): "firm.manage_settings",
    ("get", "/v1/firm/staff/{user_id}"): "firm.read_people",
    ("patch", "/v1/firm/staff/{user_id}"): "firm.manage_users",
    ("put", "/v1/firm/staff/{user_id}/security-role"): "security_role.assign",
    ("post", "/v1/firm/staff/{user_id}/deactivate"): "firm.manage_users",
    ("get", "/v1/firm/role-templates"): "firm.read_people",
    ("get", "/v1/firm/independence/annual"): "independence.annual_read",
    ("post", "/v1/me/independence/annual"): "independence.annual_confirm",
    ("get", "/v1/firm/service-lines"): "firm.read_settings",
    ("put", "/v1/firm/service-lines/{line}"): "service_line_policy.manage",
    ("get", "/v1/firm/offshore"): "firm.read_settings",
    ("get", "/v1/walls/preview"): "wall.create",
    ("post", "/v1/walls/{wall_id}/approve"): "wall.approve",
    ("get", "/v1/walls/{wall_id}/events"): "wall.list",
    ("get", "/v1/firm/offices"): "org_structure.read",
    ("post", "/v1/firm/offices"): "org_structure.manage",
    ("patch", "/v1/firm/offices/{office_id}"): "org_structure.manage",
    ("get", "/v1/firm/teams"): "org_structure.read",
    ("post", "/v1/firm/teams"): "org_structure.manage",
    ("patch", "/v1/firm/teams/{team_id}"): "org_structure.manage",
    ("put", "/v1/firm/teams/{team_id}/members"): "org_structure.manage",
    ("put", "/v1/firm/groups/seasonal/access-ends"): "firm.manage_users",
}
NEW_ACTIONS = (
    "firm.read_people",
    "security_role.assign",
    "service_line_policy.manage",
    "wall.approve",
    "independence.annual_read",
    "independence.annual_confirm",
    "org_structure.read",
    "org_structure.manage",
)
FRESH_MFA = ("security_role.assign", "service_line_policy.manage", "wall.approve")
MODELS = sorted(
    name
    for module in (settings_contract, org_settings)
    for name in dir(module)
    if name.endswith(("Out", "In")) and name in SCHEMAS
)
HIDDEN = re.compile(r"(hidden|walled|wall_count|by_wall)")


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_g01t02_each_route_declares_its_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize("module", [settings_contract, org_settings])
async def test_g01t02_flag_off_is_404_and_on_is_501(
    monkeypatch: pytest.MonkeyPatch, module: object
) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[Flag] = []

    def fake(value: bool):  # noqa: ANN202 - a tiny fake
        async def flag_enabled(_tenant: object, flag: Flag) -> bool:
            seen.append(flag)
            return value

        return flag_enabled

    gate = cast(Callable[[AuthContext], Awaitable[None]], getattr(module, "_stub"))  # noqa: B009
    monkeypatch.setattr(module, "flag_enabled", fake(False))
    with pytest.raises(NotFound):
        await gate(ctx)
    monkeypatch.setattr(module, "flag_enabled", fake(True))
    with pytest.raises(NotImplementedYet):
        await gate(ctx)
    assert seen == [FIRM_SETTINGS_V2, FIRM_SETTINGS_V2]


@pytest.mark.parametrize("schema", MODELS)
def test_g01t03_no_schema_has_a_hidden_or_wall_derived_field(schema: str) -> None:
    assert not [p for p in _props(schema) if HIDDEN.search(p)], schema


@pytest.mark.parametrize("action", NEW_ACTIONS)
def test_g01t02_every_new_action_denies_the_agent_and_the_system(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions["agent"] == rule.decisions["system"] == "deny"
    assert not {"client_admin", "client_contributor"} & {
        r for r, d in rule.decisions.items() if d != "deny"
    }


@pytest.mark.parametrize("action", FRESH_MFA)
def test_g01t02_security_writes_need_fresh_mfa(action: str) -> None:
    assert RULES[action].mfa_recent


def test_g01t02_region_is_never_writable() -> None:
    writes = ("SettingsPatchIn", "PersonPatchIn", "FirmOfficeIn", "ServiceLinePolicyIn")
    for schema in writes:
        assert "region" not in _props(schema), schema


def test_g01t03_statuses_are_the_registry_codes() -> None:
    def enum(schema: str, field: str) -> set[str]:
        ref = cast(str, _props(schema)[field].get("$ref", ""))
        return set(cast(list[str], SCHEMAS[ref.rsplit("/", 1)[-1]]["enum"]))

    assert enum("StaffRowV2Out", "status") == {"active", "invited", "deactivated"}
    assert enum("WallV2Out", "approval_status") == {"awaiting", "approved"}
    assert enum("AnnualRowOut", "status") == {"confirmed", "not_yet", "declined"}


def test_g01t03_the_grid_carries_cells_a_source_and_a_lock() -> None:
    assert {"key", "actions", "cells", "source", "locked"} <= set(_props("GridRowOut"))
    assert {"templates", "grid"} <= set(_props("RoleTemplatesOut"))


def test_g01t03_the_annual_confirmation_takes_no_user_id() -> None:
    assert "user_id" not in _props("AnnualConfirmIn")  # AC6.3: oneself only, structurally


def test_g01t03_offshore_policy_toggles_are_locked_on() -> None:
    props = _props("OffshoreOut")
    for toggle in ("block_without_consent", "mask_tins"):
        assert props[toggle].get("const") is True or props[toggle].get("enum") == [True]
