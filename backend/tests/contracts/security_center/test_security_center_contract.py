"""The security-center contract stub, v1 (G-02-T11; `docs/contracts/security-center.md`): every
route declares exactly one matrix action and answers 404 with `security_center.v1` off and 501
with it on, after the matrix (security review L1); the family is exactly these routes and repeats
none of Q-02's; no input can turn a locked floor off; the bounds are the service's refusal, not a
validation error; every field is classified; request context and the pack link are personal or
Restricted; the schedule is mounted before Q-02's export router."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.evidence import api as evidence_api
from abacus.modules.evidence import firm_export_schedule_contract as schedule
from abacus.modules.identity import security_center_contract as identity_contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.platform import security_center_contract as platform_contract

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
CONTRACT_DOC = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "security-center.md"

ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/firm/security"): "security.read",
    ("put", "/v1/firm/security/sign-in"): "security.manage",
    ("put", "/v1/firm/security/portal-sign-in"): "security.manage",
    ("put", "/v1/firm/security/sso-exempt-account"): "security.manage",
    ("get", "/v1/firm/security/sessions"): "security.read",
    ("post", "/v1/firm/security/sessions/{session_id}/sign-out"): "session.end",
    ("get", "/v1/firm/security/posture"): "security.read",
    ("post", "/v1/firm/staff/{user_id}/unlock"): "staff.unlock",
    ("get", "/v1/firm/support-access"): "support_session.read",
    ("put", "/v1/firm/support-access"): "support_session.manage",
    ("get", "/v1/firm/security/incidents"): "incident.read",
    ("get", "/v1/firm/security/incidents/{incident_id}"): "incident.read",
    ("post", "/v1/firm/security/incidents/{incident_id}/timeline"): "incident.manage",
    ("post", "/v1/firm/security/incidents/{incident_id}/decisions"): "incident.decide",
    ("get", "/v1/firm/data-exports/schedule"): "firm_export.read",
    ("put", "/v1/firm/data-exports/schedule"): "firm_export.schedule",
    ("post", "/v1/firm/data-exports/schedule/approve"): "firm_export.approve",
    ("get", "/v1/firm/safeguards"): "security.read",
    ("put", "/v1/firm/safeguards"): "security.manage",
    ("put", "/v1/firm/safeguards/controls/{control_key}"): "security.manage",
    ("post", "/v1/firm/safeguards/wisp-pack"): "security.manage",
}
# Q-02's routes in the same paths: incident create and the on-demand export (unchanged here).
Q02: frozenset[tuple[str, str]] = frozenset(
    {
        ("post", "/v1/firm/security/incidents"),
        ("get", "/v1/firm/data-exports"),
        ("post", "/v1/firm/data-exports"),
        ("post", "/v1/firm/data-exports/{export_id}/approve"),
        ("post", "/v1/firm/data-exports/{export_id}/decline"),
        ("post", "/v1/firm/data-exports/{export_id}/link"),
    }
)
PREFIXES = (
    "/v1/firm/security",
    "/v1/firm/support-access",
    "/v1/firm/safeguards",
    "/v1/firm/data-exports",
)
CONTRACTS: tuple[ModuleType, ...] = (identity_contract, platform_contract, schedule)
NAMED = (
    "SecurityOverviewOut",
    "SignInPolicyOut",
    "MfaSummaryOut",
    "PortalSignInFloorOut",
    "SecuritySessionPageOut",
    "SecurityIncidentDetailOut",
    "SafeguardsOut",
    "FirmExportScheduleOut",
    "PostureOut",
)
# The write actions of the family (AC-45, INV-1).
WRITES = (
    "security.manage",
    "session.end",
    "staff.unlock",
    "support_session.manage",
    "incident.manage",
    "incident.decide",
    "firm_export.schedule",
    "firm_export.approve",
)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_g02t11_each_route_declares_its_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


def test_g02t11_the_family_is_these_routes_and_q02s_untouched() -> None:
    served = {
        (method, path)
        for path, ops in PATHS.items()
        if path.startswith(PREFIXES) or path == "/v1/firm/staff/{user_id}/unlock"
        for method in ops
    }
    assert served == set(ROUTES) | Q02


@pytest.mark.parametrize("action", sorted(set(ROUTES.values())))
def test_g02t02_every_action_is_in_the_matrix(action: str) -> None:
    assert action in RULES


@pytest.mark.parametrize("name", NAMED)
def test_g02t11_the_named_models_are_published(name: str) -> None:
    assert name in SCHEMAS


MODELS = [
    m
    for contract in CONTRACTS
    for m in vars(contract).values()
    if isinstance(m, type) and issubclass(m, BaseModel) and m.__module__ == contract.__name__
]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_ac20_a_sessions_ip_and_device_are_personal_data_and_the_pack_link_restricted() -> None:
    for name in ("ip", "device_label"):
        assert level_of(identity_contract.SecuritySessionOut.model_fields[name]) == "confidential"
    assert level_of(platform_contract.WispPackOut.model_fields["download_url"]) == "restricted"
    assert level_of(platform_contract.SecurityIncidentOut.model_fields["title"]) == "confidential"


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (
            identity_contract.SignInPolicyIn,
            {
                "require_sso": True,
                "session_absolute_minutes": 720,
                "session_idle_minutes": 30,
                "version": 1,
                "mfa_required": False,
            },
        ),
        (
            identity_contract.PortalSignInFloorIn,
            {"session_minutes": 480, "version": 1, "passwordless_email_code": False},
        ),
        (
            identity_contract.PortalSignInFloorIn,
            {"session_minutes": 480, "version": 1, "failed_code_limit": 5},
        ),
    ],
)
def test_ac16_ac19_no_input_turns_a_locked_floor_off(
    model: type[BaseModel], body: dict[str, object]
) -> None:
    """DEC-22, DEC-34, DEC-35: MFA, the portal's passwordless code and lockout have no field."""
    with pytest.raises(ValidationError):
        model.model_validate(body)


def test_ac17_ac19_a_longer_limit_reaches_the_service_to_be_refused_with_its_code() -> None:
    """The models bound nothing above, so 780 minutes is the service's 422
    `policy_loosening_refused` (AC-17), not a validation error the SPA can't name."""
    identity_contract.SignInPolicyIn(
        require_sso=False, session_absolute_minutes=780, session_idle_minutes=45, version=0
    )
    identity_contract.PortalSignInFloorIn(session_minutes=600, version=0)
    assert identity_contract.PLATFORM_MAX_SESSION_MINUTES == 720
    assert identity_contract.PLATFORM_MAX_IDLE_MINUTES == 30
    assert identity_contract.PLATFORM_MAX_PORTAL_SESSION_MINUTES == 480


def test_ac23_no_route_edits_or_removes_a_timeline_entry() -> None:
    for path, ops in PATHS.items():
        if "/timeline" in path:
            assert set(ops) == {"post"}, path


def test_ac26_retention_is_read_only_here() -> None:
    assert not [path for path in PATHS if path.startswith("/v1/firm/security/retention")]


def test_ac25_the_schedule_is_mounted_before_q02s_export_router() -> None:
    """Q-02's `POST /{export_id}/approve` would otherwise take `schedule/approve`."""
    routers = list(evidence_api.ROUTERS)
    assert routers.index(schedule.schedule_router) < routers.index(evidence_api.firm_export_router)


@pytest.mark.parametrize("action", WRITES)
def test_ac45_no_agent_system_or_client_holds_a_write(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


def test_the_contract_doc_names_every_route() -> None:
    text = CONTRACT_DOC.read_text("utf-8")
    for method, path in ROUTES:
        assert f"`{method.upper()} {path}`" in text, (method, path)


# --- The gate: matrix first, then the flag (security review L1) ---------------------------------


def _ctx(firm_role: str | None, *, client: bool = False, kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # pyright: ignore[reportArgumentType] -- an actor kind code
        user,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- a firm role code
        None,
        client=client,
    )


def _flags(monkeypatch: pytest.MonkeyPatch, contract: ModuleType, value: bool) -> list[Flag]:
    seen: list[Flag] = []

    async def flag_enabled(_tenant: object, flag: Flag) -> bool:
        seen.append(flag)
        return value

    monkeypatch.setattr(contract, "flag_enabled", flag_enabled)
    return seen


def _authorise(monkeypatch: pytest.MonkeyPatch, contract: ModuleType, *, allow: bool) -> None:
    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        if not allow:
            raise Forbidden(action, "role")

    monkeypatch.setattr(contract, "authorise", authorise)


Gate = Callable[[AuthContext, str], Coroutine[object, object, None]]


def _stub_of(contract: ModuleType) -> Gate:
    return cast(Gate, contract._stub)


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__.split(".")[2])
async def test_g02t11_flag_off_is_404_and_on_is_501(
    monkeypatch: pytest.MonkeyPatch, contract: ModuleType
) -> None:
    _authorise(monkeypatch, contract, allow=True)
    stub = _stub_of(contract)
    _flags(monkeypatch, contract, False)
    with pytest.raises(NotFound):
        await stub(_ctx("security_admin"), "security.read")
    seen = _flags(monkeypatch, contract, True)
    with pytest.raises(NotImplementedYet):
        await stub(_ctx("security_admin"), "security.read")
    assert seen == [SECURITY_CENTER_V1]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__.split(".")[2])
async def test_l1_the_matrix_answers_before_the_flag_is_read(
    monkeypatch: pytest.MonkeyPatch, contract: ModuleType
) -> None:
    stub = _stub_of(contract)
    seen = _flags(monkeypatch, contract, True)
    _authorise(monkeypatch, contract, allow=False)
    with pytest.raises(Forbidden):  # the agent, a person without the action, a stale factor
        await stub(_ctx(None, kind="agent"), "security.manage")
    _authorise(monkeypatch, contract, allow=True)
    with pytest.raises(NotFound):  # INV-4: a client principal learns nothing, not even a 403
        await stub(_ctx(None, client=True), "security.read")
    assert seen == []
