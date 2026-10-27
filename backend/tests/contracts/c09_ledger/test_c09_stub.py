"""C9 v1 stub, AUD-06 family (A-02-T03; docs/contracts/c09-ledger.md; SPEC-333 AC-26 to AC-28).

Every C9 v1 route exists with its one matrix action. The SPEC-309 to SPEC-311 routes stay live
(DEC-314); the new ones authorise first, then answer 404 with `ledger.tb_workpaper` off and 501
with it on. Every model field is classified, the issue link takes an `Idempotency-Key`, and the
writes and the export are human only. Expectations come from A-02 §4.3 and §4.4. The consumers'
own tests are A-02-T08's, in this directory.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import LEDGER_TB_WORKPAPER
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.assurance import tb_contract
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
TBS = "/v1/engagements/{engagement_id}/trial-balances"
TB = f"{TBS}/{{tb_id}}"

# The new C9 v1 operations, stubbed behind the flag (method, path) -> the one matrix action. None
# since A-02-T22 (TASK-1470) made Open in Excel live.
STUBS: dict[tuple[str, str], str] = {}
# C9 v1's operations already live (SPEC-309, SPEC-310, SPEC-311, SPEC-313; DEC-314).
LIVE: dict[tuple[str, str], str] = {
    ("get", TBS): "trial_balance.read",
    ("post", TBS): "trial_balance.adopt",
    ("get", TB): "trial_balance.read",
    ("get", f"{TB}/candidates"): "trial_balance.read",
    ("post", f"{TB}/versions"): "trial_balance.adopt",
    ("get", f"{TB}/leadsheets"): "trial_balance.read",
    ("post", f"{TB}/annotations"): "trial_balance.annotate",
    ("get", f"{TB}/checks"): "trial_balance.read",
    ("post", f"{TB}/checks"): "tie_out_check.define",
    ("put", f"{TB}/checks/{{check_id}}"): "tie_out_check.define",
    ("post", f"{TB}/sign-offs/prepare"): "sign_off.prepare",
    ("post", f"{TB}/sign-offs/review"): "sign_off.review",
    ("post", f"{TB}/sign-offs/manager"): "sign_off.manager",
    ("post", f"{TB}/sign-offs/partner"): "sign_off.partner",
    ("post", f"{TB}/sign-offs/eqr"): "sign_off.eqr",
    # A-02-T10 (TASK-1336): the view by layer and the leadsheet by area are live.
    ("get", f"{TB}/layers/{{layer}}"): "trial_balance.read",
    ("get", f"{TB}/leadsheets/{{area}}"): "trial_balance.read",
    # A-02-T17 (TASK-1417): the issue link is live.
    ("post", f"{TB}/checks/{{check_id}}/issue-link"): "tie_out_check.define",
    # A-02-T22 (TASK-1470): Open in Excel is live, behind the flag.
    ("get", f"{TB}/export.xlsx"): "trial_balance.export",
}
CLIENT_ROLES = {"client_admin", "client_contributor", "client_service"}


# The routes' shared gate, read from the module as the audits stub test reads its own.
_STUB = cast(
    Callable[[AuthContext, str, uuid.UUID], Awaitable[object]], vars(tb_contract)["stub_gate"]
)


def _models() -> list[type[BaseModel]]:
    return [
        v
        for v in vars(tb_contract).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v is not BaseModel
        and v.__module__ == tb_contract.__name__
    ]


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


@pytest.mark.parametrize(("method", "path"), sorted(STUBS | LIVE))
def test_ac26_each_c9_route_declares_its_one_action(method: str, path: str) -> None:
    assert PATHS[path][method]["x-abacus-action"] == (STUBS | LIVE)[(method, path)]


def test_ac26_each_stub_documents_404_and_501() -> None:
    for method, path in sorted(STUBS):
        assert {"404", "501"} <= set(cast(Json, PATHS[path][method]["responses"]))
    # A-02-T22: the live export keeps the flag's 404 and the view's 409s.
    export = cast(Json, PATHS[f"{TB}/export.xlsx"]["get"]["responses"])
    assert {"404", "409"} <= set(export)


# A-03's half of C9 (SPEC-316): the account mapping and the draft statements.
A03 = (f"{TB}/mapping", f"{TB}/statements")


def test_ac26_the_family_has_exactly_these_routes_besides_a03s_half() -> None:
    family = {
        (m, p)
        for p, ops in PATHS.items()
        if p.startswith(TBS) and not p.startswith(A03)
        for m in ops
    }
    assert family == set(STUBS) | set(LIVE)


async def test_ac26_a_stub_authorises_then_answers_404_off_and_501_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    engagement_id = uuid.uuid4()

    async def get_ref(_ctx: AuthContext, asked: uuid.UUID) -> object:
        assert asked == engagement_id
        calls.append("ref")
        return SimpleNamespace(resource=lambda: "engagement")

    async def authorise(_ctx: AuthContext, action: str, resource: object) -> None:
        assert resource == "engagement"
        calls.append(f"authorise:{action}")

    async def off(_tenant: object, flag: object) -> bool:
        calls.append(f"flag:{getattr(flag, 'name', flag)}")
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(tb_contract, "get_ref", get_ref)
    monkeypatch.setattr(tb_contract, "authorise", authorise)
    monkeypatch.setattr(tb_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await _STUB(_ctx(), "trial_balance.export", engagement_id)
    assert calls == ["ref", "authorise:trial_balance.export", f"flag:{LEDGER_TB_WORKPAPER.name}"]
    monkeypatch.setattr(tb_contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await _STUB(_ctx(), "trial_balance.read", engagement_id)


async def test_ac26_a_refused_principal_never_learns_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_ref(_ctx: AuthContext, _asked: uuid.UUID) -> object:
        return SimpleNamespace(resource=lambda: "engagement")

    async def authorise(_ctx: AuthContext, action: str, _resource: object) -> None:
        raise Forbidden(action, "role")

    async def flag(_tenant: object, _flag: object) -> bool:
        raise AssertionError("the flag is read only after authorise")

    monkeypatch.setattr(tb_contract, "get_ref", get_ref)
    monkeypatch.setattr(tb_contract, "authorise", authorise)
    monkeypatch.setattr(tb_contract, "flag_enabled", flag)
    with pytest.raises(Forbidden):
        await _STUB(_ctx(), "tie_out_check.define", uuid.uuid4())


def test_ac26_the_flag_is_boolean_and_default_off() -> None:
    assert LEDGER_TB_WORKPAPER.kind == "boolean"
    assert LEDGER_TB_WORKPAPER.default == "false"


@pytest.mark.parametrize("model", _models(), ids=lambda m: m.__name__)
def test_ac27_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


@pytest.mark.parametrize("model", _models(), ids=lambda m: m.__name__)
def test_ac27_no_model_carries_a_hidden_count(model: type[BaseModel]) -> None:
    assert not [f for f in model.model_fields if "hidden" in f or "walled" in f]


def test_ac27_labels_and_layers_are_the_registry_enums() -> None:
    schemas = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
    view = cast(dict[str, Json], schemas["TbLayerViewOut"]["properties"])
    assert view["label"]["$ref"] == "#/components/schemas/TrialBalanceLabelStatus"
    assert view["layer"]["$ref"] == "#/components/schemas/TrialBalanceLayerStatus"
    assert schemas["TrialBalanceLabelStatus"]["enum"] == [
        "standard",
        "interim",
        "prior",
        "budget",
        "preliminary",
    ]
    assert schemas["TrialBalanceLayerStatus"]["enum"] == ["unadjusted", "aje", "rje", "final"]


def test_ac28_the_issue_link_takes_an_idempotency_key_creates_and_documents_conflicts() -> None:
    op = PATHS[f"{TB}/checks/{{check_id}}/issue-link"]["post"]
    params = cast(list[Json], op.get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True
    assert {"201", "409"} <= set(cast(Json, op["responses"]))


def test_ac28_open_in_excel_is_the_only_route_under_trial_balance_export() -> None:
    routes = [
        (m, p)
        for p, ops in PATHS.items()
        for m, op in ops.items()
        if op.get("x-abacus-action") == "trial_balance.export"
    ]
    assert routes == [("get", f"{TB}/export.xlsx")]


@pytest.mark.parametrize(
    "action", ["trial_balance.adopt", "trial_balance.export", "tie_out_check.define"]
)
def test_ac28_writes_and_the_export_are_human_and_firm_only(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system", "deny") == "deny"
    assert not CLIENT_ROLES & {r for r, d in rule.decisions.items() if d == "allow"}
    assert rule.independence is True


def test_no_route_of_the_family_is_unauthenticated() -> None:
    for method, path in STUBS | LIVE:
        assert PATHS[path][method]["x-abacus-action"] not in ("PUBLIC", "PORTAL_PUBLIC")
