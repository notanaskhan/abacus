"""The notices v1 contract stub (N-04-T02; docs/contracts/notices.md; DEC-2051).

Every N-04 §4.3 route exists with its one matrix action and documents 404 and 501; every create
takes an Idempotency-Key and every edit an If-Match; the gate answers clients 404, authorises
and then serves (`notices.workspace` retired at N-04-T27, DEC-2602); every model
field is classified, amounts and letter text are tax return information, and TINs and
confirmation numbers never come back whole.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import tri_paths, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Resource
from abacus.modules.notices import contract, sending

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
N = "/v1/notices/{notice_id}"
I = "/v1/notice-intakes/{intake_id}"  # noqa: E741
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/notices"): "notice.read",
    ("get", "/v1/notices/summary"): "notice.read",
    ("post", "/v1/notice-intakes"): "notice_intake.create",
    ("get", I): "notice_intake.read",
    ("put", I): "notice_intake.update",
    ("post", f"{I}/create"): "notice_intake.confirm",
    ("post", f"{I}/attach"): "notice_intake.confirm",
    ("post", f"{I}/discard"): "notice_intake.confirm",
    ("get", N): "notice.read",
    ("patch", N): "notice.update",
    ("post", f"{N}:start"): "notice.start",
    ("put", f"{N}/return-as-filed"): "notice.record_as_filed",
    ("put", f"{N}/proposed-items"): "notice.record_as_filed",
    ("get", f"{N}/analysis"): "notice.read",
    ("post", f"{N}/analysis/run"): "notice.analyze",
    ("post", f"{N}/decision-requests"): "notice.request_decision",
    ("post", f"{N}/notes"): "notice.note",
    ("get", f"{N}/activity"): "notice.read",
    ("post", f"{N}/response"): "notice_response.draft",
    ("get", f"{N}/response"): "notice.read",
    ("put", f"{N}/response"): "notice_response.edit",
    ("post", f"{N}/response/regenerate"): "notice_response.edit",
    ("post", f"{N}/response/send-for-signature"): "notice_response.send_for_signature",
    ("post", f"{N}/response/mark-sent"): "notice_response.mark_sent",
    ("post", f"{N}/agency-replies"): "notice.agency_reply",
}
IF_MATCH = {
    ("put", I),
    ("patch", N),
    ("put", f"{N}/response"),
    ("post", f"{N}/response/regenerate"),
}


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
    return {
        cast(str, p["name"]) for p in cast(list[Json], PATHS[path][method].get("parameters", []))
    }


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_one_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_ac1_the_stub_owns_exactly_these_routes() -> None:
    mine = {
        (m, p)
        for p, ops in PATHS.items()
        if p.startswith(("/v1/notices", "/v1/notice-intakes"))
        for m in ops
    }
    assert mine == set(ROUTES)


def test_ac1_creates_take_an_idempotency_key_and_edits_an_if_match() -> None:
    for method, path in ROUTES:
        if method == "get":
            continue
        names = _params(method, path)
        if (method, path) in IF_MATCH:
            assert "If-Match" in names, (method, path)
        else:
            assert "Idempotency-Key" in names, (method, path)


def test_ac1_there_is_no_notices_decide_route() -> None:
    assert not [p for p in PATHS if p.startswith("/v1/notices") and "decide" in p]


def test_ac1_every_field_is_classified_and_amounts_are_tri() -> None:
    models = [
        v
        for v in vars(contract).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
    ]
    assert len(models) > 30
    for model in models:
        assert unclassified_fields(model) == [], model.__name__
    assert "tax" in tri_paths(contract.AmountsOut)
    assert "text" in tri_paths(contract.BlockOut)
    assert "confirmation_no" in tri_paths(contract.MarkSentIn)


def test_ac1_no_out_model_carries_a_whole_tin_or_confirmation_number() -> None:
    # P-12 (the repo's rule, tests/contracts/clients): a TIN travels only as MaskedTinOut.
    for model, field in (
        (contract.IntakeFieldOut, "tin"),
        (contract.NoticeOut, "taxpayer_tin"),
        (contract.MatchCandidateOut, "tin"),
    ):
        assert contract.MaskedTinOut | None == model.model_fields[field].annotation, model.__name__
    assert "confirmation_no" not in contract.SentOut.model_fields
    assert "confirmation_last4" in contract.SentOut.model_fields


async def test_ac1_a_client_principal_gets_404_before_anything_else() -> None:
    with pytest.raises(NotFound):
        await contract.notices_summary_route(_ctx(client=True))
    with pytest.raises(NotFound):
        await contract.notice_route(uuid.uuid4(), _ctx(client=True))


async def test_ac1_the_gate_authorises_then_serves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def engagement(_tenant: object, _wid: uuid.UUID) -> uuid.UUID:
        return uuid.uuid4()

    async def get_ref(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        # The gate scopes the check to the notice's work item (DEC-2089), so a real Resource.
        return SimpleNamespace(resource=lambda: Resource.firm(uuid.uuid4()))

    async def authorise(_ctx: AuthContext, action: str, resource: object) -> None:
        calls.append(f"authorise:{action}")

    monkeypatch.setattr(contract, "work_item_engagement", engagement)
    monkeypatch.setattr(contract, "get_ref", get_ref)
    monkeypatch.setattr(contract, "authorise", authorise)
    # N-04-T16 serves sending for signature: the gate still comes first.
    envelope = uuid.uuid4()

    async def sent(_ctx: AuthContext, _notice_id: uuid.UUID) -> uuid.UUID:
        return envelope

    async def no_item(_ctx: AuthContext, _notice_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(sending, "send_for_signature", sent)
    monkeypatch.setattr(sending, "confirmation_item_of", no_item)
    served = await contract.send_for_signature_route(uuid.uuid4(), _ctx(), "key")
    assert served.envelope_id == envelope
    assert calls == ["authorise:notice_response.send_for_signature"]
    # N-04-T06 serves the patch; the assignee alone is still `notice.assign`.
    assert contract._assign_only(contract.NoticePatchIn(assignee_id=uuid.uuid4()))  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert not contract._assign_only(  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        contract.NoticePatchIn(assignee_id=uuid.uuid4(), client_visible=True)
    )
