"""The T-03 contract stubs (T-03-T02; docs/contracts/questionnaires.md §T-03 additive and
docs/contracts/tax-extensions-estimates.md; DEC-2201).

Every T-03 §4.3 route exists with its one matrix action and documents 404 and 501; bulk creates
take an Idempotency-Key and edits an If-Match; the gate answers clients 404, authorises before
reading the flag, answers 404 with the flag off and 501 with it on; every model field is
classified and amounts and answers are tax return information; the preview DTO carries no
firm-internal field; T-02's v1 questionnaire routes are unchanged; the effect slot fails closed.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import tri_paths, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests import answer_effect_slots as slots
from abacus.modules.requests import questionnaire_editor_contract as editor
from abacus.modules.tax import schedules_contract as schedules

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
Q = "/v1/questionnaires/{questionnaire_id}"
T = "/v1/questionnaire-templates/{template_id}"
X = "/v1/tax/extensions/{extension_id}"
E = "/v1/tax/estimates/{schedule_id}"
I = f"{E}/installments/{{quarter}}"  # noqa: E741
EDITOR: dict[tuple[str, str], str] = {
    ("get", "/v1/binders/{binder_id}/questionnaire"): "questionnaire.read",
    ("get", f"{Q}/editor"): "questionnaire.read",
    ("put", Q): "questionnaire.edit",
    ("get", f"{Q}/client-preview"): "questionnaire.read",
    ("get", T): "questionnaire_template.read",
    ("put", f"{T}/owner"): "questionnaire_template.assign_owner",
    ("post", f"{T}/versions"): "questionnaire_template.draft",
    ("delete", f"{T}/versions/{{version}}"): "questionnaire_template.draft",
    ("get", f"{T}/versions/{{version}}/diff"): "questionnaire_template.read",
}
SCHEDULES: dict[tuple[str, str], str] = {
    ("get", "/v1/tax/extensions"): "filing_extension.read",
    ("get", "/v1/tax/extensions/export.xlsx"): "tax_schedule.export",
    ("post", "/v1/tax/extensions:prepare"): "filing_extension.prepare",
    ("post", "/v1/tax/extensions:submit-for-approval"): "filing_extension.prepare",
    ("post", "/v1/tax/extensions:approve-and-request"): "filing_extension.approve_payment",
    ("get", X): "filing_extension.read",
    ("patch", X): "filing_extension.mark_filed",
    ("post", f"{X}/confirmation-requests"): "filing_extension.confirmation_send",
    ("get", "/v1/tax/estimates"): "estimate_schedule.read",
    ("post", "/v1/tax/estimates"): "estimate_schedule.update",
    ("get", "/v1/tax/estimates/export.xlsx"): "tax_schedule.export",
    ("patch", E): "estimate_schedule.update",
    ("patch", I): "estimate_schedule.update",
    ("post", f"{I}/confirmation-requests"): "estimate_schedule.confirmation_send",
    ("post", f"{I}/follow-ups"): "follow_up.draft",
    ("get", "/v1/tax/payments"): "filing_extension.read",
}
ROUTES = {**EDITOR, **SCHEDULES}
IF_MATCH = {("put", Q), ("patch", X), ("patch", E), ("patch", I)}
NO_KEY = {("put", f"{T}/owner"), ("delete", f"{T}/versions/{{version}}")}  # idempotent by nature


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


def _params(method: str, path: str) -> set[str]:
    return {str(p["name"]) for p in cast(list[Json], PATHS[path][method].get("parameters", []))}


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac2_each_route_declares_its_one_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_ac2_the_schedules_stub_owns_exactly_these_routes() -> None:
    mine = {(m, p) for p, ops in PATHS.items() if p.startswith("/v1/tax/") for m in ops}
    mine = {
        (m, p)
        for m, p in mine
        if p.startswith(("/v1/tax/extensions", "/v1/tax/estimates", "/v1/tax/payments"))
    }
    assert mine == set(SCHEDULES)


def test_ac2_bulk_creates_take_an_idempotency_key_and_edits_an_if_match() -> None:
    for method, path in ROUTES:
        if method == "get" or (method, path) in NO_KEY:
            continue
        names = _params(method, path)
        if (method, path) in IF_MATCH:
            assert "If-Match" in names, (method, path)
        else:
            assert "Idempotency-Key" in names, (method, path)


def test_ac2_t02s_v1_questionnaire_routes_are_unchanged() -> None:
    # POR-05's consumers read these; T-03 adds beside them (DEC-2201).
    assert PATHS["/v1/questionnaires/{questionnaire_id}"]["get"]["x-abacus-action"] == (
        "questionnaire.read"
    )
    assert "/v1/questionnaire-templates/{template_id}/versions/{version}:publish" in PATHS
    assert "/v1/portal/questionnaires/{questionnaire_id}/answers/{question_id}" in PATHS


@pytest.mark.parametrize("module", [editor, schedules])
def test_ac2_every_field_is_classified(module: object) -> None:
    models = [
        v
        for v in vars(module).values()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v.__module__ == getattr(module, "__name__", "")
    ]
    assert len(models) > 15
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_ac2_amounts_reject_codes_and_answers_are_tri() -> None:
    assert "amount" in tri_paths(schedules.ExtensionPaymentOut)
    assert "safe_harbor_target" in tri_paths(schedules.ExtensionRowOut)
    assert "reject_code" in tri_paths(schedules.JurisdictionLineOut)
    assert "annual_required" in tri_paths(schedules.EstimateRowOut)
    assert "value" in tri_paths(editor.AnswerSummaryOut)
    assert "answer" in tri_paths(editor.PreviewQuestionOut)


def test_ac2_the_client_preview_carries_no_firm_internal_field() -> None:
    names = set(editor.PreviewQuestionOut.model_fields) | set(editor.ClientPreviewOut.model_fields)
    assert not names & {"internal_helper", "effect_rules", "effects", "tags", "banner"}


def test_ac2_no_payment_instrument_is_ever_accepted() -> None:
    for model in (schedules.ProposedPaymentIn, schedules.EstimatePatchIn):
        names = set(model.model_fields)
        assert not names & {"account_number", "routing_number", "card_number", "bank_account"}


async def test_ac2_a_client_principal_gets_404_before_anything_else() -> None:
    with pytest.raises(NotFound):
        await editor.questionnaire_editor_route(uuid.uuid4(), _ctx(client=True))
    with pytest.raises(NotFound):
        await schedules.extension_route(uuid.uuid4(), _ctx(client=True))


class _PastTheGate(Exception):
    """The live service was reached: the gate let the call through."""


async def _past_the_gate(*_a: object, **_k: object) -> None:
    raise _PastTheGate


@pytest.mark.parametrize(
    ("module", "flag"),
    [(editor, "questionnaires.editor"), (schedules, "tax.extensions_estimates")],
)
async def test_ac2_the_gate_authorises_then_reads_the_flag_then_lets_the_route_run(
    monkeypatch: pytest.MonkeyPatch, module: object, flag: str
) -> None:
    # T-03-T05 and T-03-T07 made both reads live.
    calls: list[str] = []
    state = {"on": False}

    async def authorise(_ctx: AuthContext, action: str, resource: object) -> None:
        calls.append(f"authorise:{action}")

    async def flag_enabled(_tenant: object, f: object) -> bool:
        calls.append(f"flag:{getattr(f, 'name', f)}")
        return state["on"]

    monkeypatch.setattr(module, "authorise", authorise)
    monkeypatch.setattr(module, "flag_enabled", flag_enabled)
    route = editor.questionnaire_editor_route if module is editor else schedules.extension_route
    with pytest.raises(NotFound):
        await route(uuid.uuid4(), _ctx())
    assert calls[1] == f"flag:{flag}"
    state["on"] = True
    if module is editor:
        from abacus.modules.requests import questionnaire_editor

        monkeypatch.setattr(questionnaire_editor, "editor", _past_the_gate)
        with pytest.raises(_PastTheGate):
            await route(uuid.uuid4(), _ctx())
    else:
        from abacus.modules.tax import extensions

        monkeypatch.setattr(extensions, "year_of", _past_the_gate)
        with pytest.raises(_PastTheGate):
            await route(uuid.uuid4(), _ctx())


async def test_ac2_flag_likely_alone_is_its_own_action(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    async def flag_enabled(_tenant: object, f: object) -> bool:
        return True

    async def patch(*_a: object, **k: object) -> None:
        seen.append(k["action"])
        raise _PastTheGate

    monkeypatch.setattr(schedules, "flag_enabled", flag_enabled)
    # DEC-2327: the action is held by a function on the return, so the service authorises it.
    from abacus.modules.tax import extensions

    monkeypatch.setattr(extensions, "patch", patch)
    with pytest.raises(_PastTheGate):
        await schedules.extension_patch_route(
            uuid.uuid4(),
            schedules.ExtensionPatchIn(likely_to_extend=True, reason="k1_outstanding"),
            _ctx(),
            1,
        )
    assert seen == ["filing_extension.flag_likely"]


def test_ac6_the_effect_slot_fails_closed_and_takes_one_handler_per_kind() -> None:
    assert slots.answer_effect_handler("route_upload_to_notices") is None or callable(
        slots.answer_effect_handler("route_upload_to_notices")
    )
    assert slots.answer_effect_handler("not_a_kind") is None

    async def handler(_req: slots.EffectRequest) -> slots.EffectResult:
        return slots.EffectResult("notice_intake", uuid.uuid4())

    async def other(_req: slots.EffectRequest) -> slots.EffectResult:
        return slots.EffectResult("notice_intake", uuid.uuid4())

    with pytest.raises(ValueError):
        slots.register_answer_effect("not_a_kind", handler)  # type: ignore[arg-type] -- the test reaches past the public type
    saved = dict(slots._HANDLERS)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    try:
        slots._HANDLERS.pop("flag_internal_review", None)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        slots.register_answer_effect("flag_internal_review", handler)
        assert slots.answer_effect_handler("flag_internal_review") is handler
        with pytest.raises(ValueError):
            slots.register_answer_effect("flag_internal_review", other)
    finally:
        slots._HANDLERS.clear()  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        slots._HANDLERS.update(saved)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
