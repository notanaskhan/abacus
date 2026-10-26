"""The audit-log contract stub, v1 (G-02-T04; `docs/contracts/audit-log.md`): every route
declares exactly one matrix action and answers 404 with `audit_log.explorer` off and 501 with it
on; no route can change or remove an event (AC-8); no shape carries a hidden or hidden-count field
(DEC-43); the actor grammar has no agent-as-actor slot (INV-5); request context and values are
classified as personal data; amounts are decimal strings; the link is Restricted."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import AUDIT_LOG_EXPLORER
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.audit_trail import audit_log_contract as contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/audit-events"): "audit_event.read",
    ("get", "/v1/audit-events/{seq}"): "audit_event.read",
    ("post", "/v1/audit-events/exports"): "audit_event.export",
    ("get", "/v1/audit-events/exports/{export_id}"): "audit_export.read",  # L5: no fresh MFA
    ("post", "/v1/audit-events/exports/{export_id}/link"): "audit_event.export",
}
NAMED = ("AuditEventRow", "AuditEventDetail", "ValueRow", "AuditExport")
CONTRACT_DOC = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "audit-log.md"
HIDDEN = re.compile(r"(hidden|walled|wall_count|by_wall|omitted)")


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _enum(schema: str, field: str) -> set[str]:
    prop = _props(schema)[field]
    for option in cast(list[Json], prop.get("anyOf", [prop])):
        if "enum" in option:
            return set(cast(list[str], option["enum"]))
        ref = option.get("$ref")
        if isinstance(ref, str):
            return set(cast(list[str], SCHEMAS[ref.rsplit("/", 1)[1]]["enum"]))
    raise AssertionError(f"{schema}.{field} has no enum")


# G-02-T08 (TASK-1329): the list and the detail are live; the export family stays the stub's
# until G-02-T17.
LIVE = frozenset({("get", "/v1/audit-events"), ("get", "/v1/audit-events/{seq}")})


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_g02t04_each_route_declares_its_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    if (method, path) in LIVE:
        assert "501" not in responses
    else:
        assert "501" in responses


def test_g02t04_the_family_is_exactly_these_routes() -> None:
    served = {
        (method, path)
        for path, ops in PATHS.items()
        if path.startswith("/v1/audit-events")
        for method in ops
    }
    assert served == set(ROUTES)


def test_ac8_no_route_changes_or_removes_an_audit_event() -> None:
    for path, ops in PATHS.items():
        if "audit-events" in path and not path.startswith("/v1/audit-events/exports"):
            assert set(ops) <= {"get"}, path


@pytest.mark.parametrize("name", NAMED)
def test_g02t04_the_named_models_are_published(name: str) -> None:
    assert name in SCHEMAS


def test_dec43_no_shape_counts_or_flags_what_walls_left_out() -> None:
    for name in (*NAMED, "AuditEventPageOut", "AuditValuesOut", "AuditTargetOut"):
        for prop in _props(name):
            assert not HIDDEN.search(prop), f"{name}.{prop}"


def test_inv5_the_actor_grammar_names_people_policies_or_the_system_never_the_agent() -> None:
    assert _enum("AuditActorOut", "kind") == {"person", "via_agent", "policy", "system", "support"}
    actor = _props("AuditActorOut")
    assert "display_name" not in actor and "agent_name" not in actor
    assert {"person", "on_behalf_of", "agent_id", "policy_ref"} <= set(actor)


def test_ac9_request_context_and_values_are_personal_data() -> None:
    for model, fields in (
        (contract.AuditEventRow, ("ip", "labels")),
        (contract.AuditEventDetail, ("ip", "device_label")),
        (contract.ValueRow, ("item_label", "before", "after", "amount")),
    ):
        for name in fields:
            assert level_of(model.model_fields[name]) == "confidential", (model, name)
    assert level_of(contract.AuditExportLinkOut.model_fields["url"]) == "restricted"


def test_m4_facts_are_codes_and_ids_and_values_live_under_values() -> None:
    """Security review M4: a metadata-only reader gets `detail_facts`, so they carry no value."""
    assert level_of(contract.AuditEventRow.model_fields["detail_facts"]) == "internal"
    assert "values" in contract.AuditEventDetail.model_fields
    assert "values" not in contract.AuditEventRow.model_fields
    text = CONTRACT_DOC.read_text("utf-8")
    assert "codes and identifiers only" in text
    assert "searches labels only" in text


def test_m2_request_context_is_for_three_roles_and_null_for_everyone_else() -> None:
    """DEC-420 (security review M2): the projection (G-02-T08) nulls request context for every
    reader outside these roles, so every request-context field must be nullable."""
    assert frozenset({"firm_admin", "security_admin", "quality_partner"}) == (
        contract.REQUEST_CONTEXT_READERS
    )
    readers = set(RULES["audit_event.read"].decisions) - {"agent", "system"}
    assert readers - contract.REQUEST_CONTEXT_READERS, "some readers must get request context null"
    for name in ("ip", "device_label", "user_agent_family", "session"):
        assert not contract.AuditEventDetail.model_fields[name].is_required(), name
    for name in ("session_id", "auth_method", "mfa_at"):
        assert not contract.AuditSessionOut.model_fields[name].is_required(), name
    assert "firm_admin, security_admin and quality_partner" in CONTRACT_DOC.read_text("utf-8")
    # G-02-T08: the projection asks the matrix (AUTHZ-002); its row names exactly these roles.
    allowed = {
        role
        for role, decision in RULES["audit_event.read_request_context"].decisions.items()
        if decision == "allow"
    }
    assert allowed == contract.REQUEST_CONTEXT_READERS


MODELS = [
    m
    for m in vars(contract).values()
    if isinstance(m, type) and issubclass(m, BaseModel) and m.__module__ == contract.__name__
]


@pytest.mark.parametrize("model", MODELS)
def test_adr031_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_ac10_amounts_are_decimal_strings_and_values_have_three_states() -> None:
    row = contract.ValueRow(item_label="Payroll accrual", field="status", amount="11860.00")
    assert row.amount == "11860.00"
    with pytest.raises(ValueError):
        contract.ValueRow(item_label="Payroll accrual", field="status", amount="11860")
    assert _enum("AuditValuesOut", "status") == {"resolved", "withheld", "unavailable"}


def test_ac14_ac45_the_export_is_a_fresh_second_factor_and_no_agent_or_client_holds_it() -> None:
    rule = RULES["audit_event.export"]
    assert rule.mfa_recent
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert rule.decisions.get(principal, "deny") == "deny"
        assert RULES["audit_event.read"].decisions.get(principal, "deny") == "deny"


def _ctx(firm_role: str | None, *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- a firm role code
        None,
        client=client,
    )


def _flags(monkeypatch: pytest.MonkeyPatch, value: bool) -> list[Flag]:
    seen: list[Flag] = []

    async def flag_enabled(_tenant: object, flag: Flag) -> bool:
        seen.append(flag)
        return value

    monkeypatch.setattr(contract, "flag_enabled", flag_enabled)
    return seen


def _authorise(monkeypatch: pytest.MonkeyPatch, *, allow: bool) -> None:
    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        if not allow:
            raise Forbidden(action, "role")

    monkeypatch.setattr(contract, "authorise", authorise)


async def test_g02t04_flag_off_is_404_and_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorise(monkeypatch, allow=True)
    seen = _flags(monkeypatch, False)
    with pytest.raises(NotFound):
        await contract._stub(_ctx("security_admin"), "audit_event.read")  # pyright: ignore[reportPrivateUsage] -- the route gate
    seen = _flags(monkeypatch, True)
    with pytest.raises(NotImplementedYet):
        await contract._stub(_ctx("security_admin"), "audit_event.read")  # pyright: ignore[reportPrivateUsage] -- the route gate
    assert seen == [AUDIT_LOG_EXPLORER]


async def test_l1_the_matrix_answers_before_the_flag_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _authorise(monkeypatch, allow=False)
    seen = _flags(monkeypatch, True)
    with pytest.raises(Forbidden):  # no role the export row names
        await contract._stub(_ctx(None), "audit_event.export")  # pyright: ignore[reportPrivateUsage] -- the route gate
    agent = _ctx(None)
    agent = AuthContext(
        TenantContext(agent.tenant_id, "agent", "agent:probe:run", agent.user_id),
        agent.user_id,
        agent.membership_id,
        None,
        None,
    )
    with pytest.raises(Forbidden):  # INV-1: the agent never reads the log
        await contract._stub(agent, "audit_event.read")  # pyright: ignore[reportPrivateUsage] -- the route gate
    with pytest.raises(NotFound):  # INV-4: a client principal learns nothing, not even a 403
        await contract._stub(_ctx(None, client=True), "audit_event.read")  # pyright: ignore[reportPrivateUsage] -- the route gate
    assert seen == []
    # An in-scope or engagement-role reader passes to the gate; the live route narrows per event
    # with visible().
    for role in ("quality_partner", None):
        with pytest.raises(NotImplementedYet):
            await contract._stub(_ctx(role), "audit_event.read")  # pyright: ignore[reportPrivateUsage] -- the route gate
