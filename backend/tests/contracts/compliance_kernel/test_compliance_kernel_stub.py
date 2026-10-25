"""Compliance-kernel v1.1 stub (Q-02-T38; `docs/contracts/compliance-kernel.md`): the firm-export
family exists with one matrix action per route, documents 404 and 501 (and its 409/410 answers),
the request takes an `Idempotency-Key`, every field is classified, the writes need fresh MFA and
deny the agent and system, and the gate answers 404 with `compliance.firm_export` off and 501
with it on. The live halves the contract indexes (incident create with its clock, retention
policies read, legal holds read) keep their actions and shapes."""

from __future__ import annotations

import json
import uuid
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import COMPLIANCE_FIRM_EXPORT
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.evidence import firm_export_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
EXPORTS = "/v1/firm/data-exports"
ONE = f"{EXPORTS}/{{export_id}}"

STUBBED: dict[tuple[str, str], tuple[str, set[str]]] = {
    ("get", EXPORTS): ("firm_export.read", {"404", "501"}),
    ("post", EXPORTS): ("firm_export.request", {"404", "422", "501"}),
    ("post", f"{ONE}/approve"): ("firm_export.approve", {"404", "409", "501"}),
    ("post", f"{ONE}/decline"): ("firm_export.approve", {"404", "409", "501"}),
    ("post", f"{ONE}/link"): ("firm_export.download", {"404", "409", "410", "501"}),
}
# Live before this stub; the contract indexes them for G-02 and Q-05 (§2, §3, §5).
LIVE: dict[tuple[str, str], str] = {
    ("post", "/v1/firm/security/incidents"): "incident.manage",
    ("get", "/v1/retention/policies"): "retention_policy.read",
    ("get", "/v1/legal-holds"): "legal_hold.read",
}
WRITES = ("firm_export.request", "firm_export.approve", "firm_export.download")


def _models(module: ModuleType) -> list[type[BaseModel]]:
    return [
        v
        for v in vars(module).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v is not BaseModel
        and v.__module__ == module.__name__
    ]


@pytest.mark.parametrize(("method", "path"), sorted(STUBBED))
def test_each_export_route_declares_its_action_and_the_stub_answers(
    method: str, path: str
) -> None:
    action, answers = STUBBED[(method, path)]
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert answers <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize(("method", "path"), sorted(LIVE))
def test_the_indexed_live_routes_keep_their_actions(method: str, path: str) -> None:
    assert PATHS[path][method]["x-abacus-action"] == LIVE[(method, path)]


def test_the_request_takes_an_idempotency_key_and_answers_202() -> None:
    op = PATHS[EXPORTS]["post"]
    params = cast(list[Json], op.get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True
    assert "202" in cast(Json, op["responses"])


def test_the_incident_create_carries_the_clock_fields() -> None:
    props = cast(Json, SCHEMAS["IncidentOut"]["properties"])
    assert {"ftc_notify_by", "clock_day", "clock_days", "notification_event"} <= set(props)


@pytest.mark.parametrize("model", _models(firm_export_contract), ids=lambda m: m.__name__)
def test_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_the_download_link_is_restricted() -> None:
    url = firm_export_contract.FirmExportLinkOut.model_fields["url"]
    assert level_of(url) == "restricted"


@pytest.mark.parametrize("action", WRITES)
def test_the_export_writes_need_fresh_mfa_and_deny_the_agent_and_system(action: str) -> None:
    rule = RULES[action]
    assert rule.mfa_recent
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


def test_the_request_is_the_security_admins_and_the_approval_a_partners() -> None:
    allow = {r for r, d in RULES["firm_export.request"].decisions.items() if d == "allow"}
    assert allow == {"security_admin"}
    approve = {r for r, d in RULES["firm_export.approve"].decisions.items() if d == "allow"}
    assert approve == {"security_admin", "firm_partner"}


async def test_flag_off_is_404_and_flag_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), "security_admin", None
    )
    seen: list[object] = []

    async def off(_tenant: object, asked: object) -> bool:
        seen.append(asked)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(firm_export_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await firm_export_contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == [COMPLIANCE_FIRM_EXPORT]
    monkeypatch.setattr(firm_export_contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await firm_export_contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate
    assert COMPLIANCE_FIRM_EXPORT.default == "false"
