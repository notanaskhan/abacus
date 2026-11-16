# ac-test-author: ayushkbhatia
"""A-08-T06 (TASK-8046; SPEC-657 AC-0.6, AC-6.8, AC-7.1, AC-7.4, AC-7.5; DEC-5031): the
confirmations stub. Firm routes carry one action each with 404 and 501; every field is
classified; no client principal holds a confirmation action; the public family is exactly the
ADR-152 amendment's five paths under the link-principal marker, answers the uniform expired view
for anything but a fixture token, and serves POR-17 a to f fixtures with code's figures.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import confirmations_contract as cc
from abacus.modules.assurance import confirmations_contract_models as cm
from abacus.modules.assurance import confirmations_fixtures as fx
from abacus.modules.identity.authz import _matrix
from abacus.modules.identity.routing import LINK_PRINCIPAL, LINK_PRINCIPAL_PATHS
from abacus_tools.quality.banned_patterns import PUBLIC_ROUTE_EXCEPTIONS

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
W = "/v1/work-items/{work_item_id}/confirmations"
C = "/v1/confirmations/{confirmation_id}"
FIRM: dict[tuple[str, str], str] = {
    ("get", W): "confirmation.read",
    ("get", f"{W}/summary"): "confirmation.read",
    ("post", W): "confirmation.create",
    ("post", f"{W}/authorization"): "confirmation.request_authorization",
    ("get", f"{W}/export.xlsx"): "confirmation.export",
    ("get", C): "confirmation.read",
    ("post", f"{C}/address-verifications"): "confirmation.verify_address",
    ("post", f"{C}/send"): "confirmation.send",
    ("post", f"{C}/second-request"): "confirmation.send",
    ("post", f"{C}/revoke-link"): "confirmation.send",
    ("post", f"{C}/record-response"): "confirmation.record_response",
    ("post", f"{C}/reconciliation"): "confirmation.reconcile",
    ("post", f"{C}/accept-reconciliation"): "confirmation.accept_reconciliation",
    ("post", f"{C}/alternative-procedures"): "confirmation.record_alternative",
    ("post", f"{C}/exception"): "finding.create",
    ("post", f"{C}/close"): "confirmation.close",
    ("get", f"{C}/respondent-preview"): "confirmation.read",
}
PUBLIC = {
    ("get", "/v1/confirm/{token}"),
    ("post", "/v1/confirm/{token}/code"),
    ("post", "/v1/confirm/{token}/code/verify"),
    ("post", "/v1/confirm/{token}/attachments"),
    ("post", "/v1/confirm/{token}/response"),
}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(FIRM))
def test_each_firm_route_declares_its_action_and_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == FIRM[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_ac0_6_the_public_family_is_exactly_the_amendments_five_paths() -> None:
    found = {(m, p) for p, ops in PATHS.items() if p.startswith("/v1/confirm/") for m in ops}
    assert found == PUBLIC
    assert {p for _, p in PUBLIC} == set(LINK_PRINCIPAL_PATHS)
    assert set(LINK_PRINCIPAL_PATHS) <= PUBLIC_ROUTE_EXCEPTIONS
    for method, path in PUBLIC:
        assert PATHS[path][method]["x-abacus-action"] == LINK_PRINCIPAL


def test_every_field_is_classified() -> None:
    models = [
        v
        for module in (cc, cm)
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__
    ]
    assert len(models) > 20
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_ac6_8_no_client_principal_holds_any_confirmation_action() -> None:
    for action, cells in _matrix.ACTIONS.items():
        if not action.startswith("confirmation."):
            continue
        for role in CLIENT_ROLES:
            assert cells.get(role, "deny") == "deny", (action, role)


@pytest.fixture
def fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cc, "CONFIRM_PAD_SECONDS", 0.0)
    monkeypatch.setattr(cc, "_fixture_mode", lambda: True)


async def test_ac7_1_the_summit_trail_page_foots_and_shows_one_confirmation(
    fixture_env: None,
) -> None:
    view = await cc.respondent_view(fx.TOKENS["a"])
    assert view.state == "open" and view.request is not None
    amounts = [i.amount for i in view.request.invoices]
    assert amounts == [Decimal("138200.00"), Decimal("151750.00"), Decimal("122650.00")]
    assert sum(amounts) == view.request.balance_per_client == Decimal("412600.00")
    dumped = view.model_dump_json()
    for other in ("Alpine Ridge", "Canyon Basecamp", "Front Range", "engagement", "portal"):
        assert other not in dumped


async def _no_link(*_: object) -> None:
    return None  # A-08-T15: a token outside the fixtures resolves to no link principal


async def test_ac7_4_unknown_expired_and_out_of_fixture_tokens_read_the_same(
    fixture_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cc, "resolve_link", _no_link)
    unknown = await cc.respondent_view("x" * 32)
    expired = await cc.respondent_view(fx.TOKENS["d"])
    assert unknown == expired == fx.EXPIRED
    assert unknown.model_dump() == {
        "state": "expired",
        "request": None,
        "receipt": None,
        "answered_on": None,
    }
    monkeypatch.setattr(cc, "_fixture_mode", lambda: False)
    assert await cc.respondent_view(fx.TOKENS["a"]) == fx.EXPIRED  # staging and production


async def test_the_bank_variant_lists_the_clients_accounts(fixture_env: None) -> None:
    view = await cc.respondent_view(fx.TOKENS["f"])
    assert view.request is not None and view.request.list_every_account
    assert [a.balance_per_client for a in view.request.client_accounts] == [
        Decimal("6500000.00"),
        Decimal("3200000.00"),
    ]


def _answer(agrees: bool, balance: str | None = None) -> cm.RespondentResponseIn:
    return cm.RespondentResponseIn(
        agrees=agrees,
        balances=[] if balance is None else [cm.RespondentBalanceIn(amount=Decimal(balance))],
        respondent_name="Respondent",
        respondent_company="Company",
        attestation=True,
    )


async def test_the_server_computes_the_difference(fixture_env: None) -> None:
    agree = await cc.submit_response(fx.TOKENS["a"], _answer(True))
    assert agree.difference == Decimal("0.00") and agree.reference == "C2"
    disagree = await cc.submit_response(fx.TOKENS["c"], _answer(False, "282600.00"))
    assert disagree.difference == Decimal("4300.00")  # 286,900 - 282,600


async def test_ac7_5_a_replayed_response_is_already_answered(fixture_env: None) -> None:
    with pytest.raises(cc.AlreadyAnswered):
        await cc.submit_response(fx.TOKENS["e"], _answer(True))


async def test_a_code_request_is_accepted_for_any_token(
    fixture_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cc, "resolve_link", _no_link)
    monkeypatch.setattr(cc, "request_link_code", _no_link)
    body = cm.CodeRequestIn(email="anyone@example.com")
    assert await cc.request_code("x" * 32, body) == await cc.request_code(fx.TOKENS["a"], body)
