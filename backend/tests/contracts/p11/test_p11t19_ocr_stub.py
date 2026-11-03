"""C4 v1.1, the OCR and box-extraction stub (P-11-T19; docs/contracts/c04-citations-viewer.md
§v1.1 additive; DEC-2204).

The three routes exist with their one action and document 404 and 501; the viewer page gains its
two optional facts without moving a v1 field; every field is classified and a TIN box never
carries its value; the gate answers clients 404, authorises, then reads its flag (variant `off` is
404); retry is a person's act.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.evidence import ocr_contract as contract
from abacus.modules.evidence import trust_contract
from abacus.modules.evidence.events import (
    EvidenceTextReady,
    ExtractedFieldsRecorded,
    OcrRunRefused,
)
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], cast(Json, json.loads(document()))["paths"])
V = "/v1/evidence-versions/{version_id}"
ROUTES = {
    ("get", f"{V}/fields"): "evidence.read",
    ("get", f"{V}/tables"): "evidence.read",
    ("post", f"{V}/text/retry"): "evidence.ocr_retry",
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


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac11_2_each_route_declares_its_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_ac11_2_the_viewer_page_is_additive_only() -> None:
    fields = trust_contract.ViewerPageOut.model_fields
    for v1 in ("n", "width_pt", "height_pt", "rotation", "image_w", "image_h", "text_layer"):
        assert fields[v1].is_required(), v1
    assert not fields["text_source"].is_required()
    assert not fields["ocr"].is_required()


def test_ac11_2_every_field_is_classified_and_a_tin_never_travels_whole() -> None:
    for model in (
        contract.ExtractedFieldOut,
        contract.ExtractedFieldsOut,
        contract.ExtractedTableOut,
        contract.TextRetryOut,
        trust_contract.PageOcrOut,
        EvidenceTextReady,
        ExtractedFieldsRecorded,
        OcrRunRefused,
    ):
        assert unclassified_fields(model) == [], model.__name__
    assert "mask_token" in contract.ExtractedFieldOut.model_fields
    assert "tin" not in contract.ExtractedFieldOut.model_fields
    for event in (EvidenceTextReady, ExtractedFieldsRecorded, OcrRunRefused):
        assert not set(event.model_fields) & {"text", "value", "value_text", "words"}


def test_ac10_3_retry_is_a_persons_act() -> None:
    rule = RULES["evidence.ocr_retry"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system", "deny") == "deny"
    for role in ("client_admin", "client_contributor", "third_party"):
        assert rule.decisions.get(role, "deny") == "deny"


async def test_ac11_2_client_404_then_authorise_then_the_flag_then_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(NotFound):
        await contract.extracted_fields_route(uuid.uuid4(), _ctx(client=True))
    calls: list[str] = []
    variant = {"value": "off"}

    async def authorise(_ctx: AuthContext, action: str, _resource: object) -> None:
        calls.append(action)

    async def flag_variant(_tenant: object, _flag: object) -> str:
        return variant["value"]

    async def flag_enabled(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contract, "authorise", authorise)
    monkeypatch.setattr(contract, "flag_variant", flag_variant)
    monkeypatch.setattr(contract, "flag_enabled", flag_enabled)
    with pytest.raises(NotFound):
        await contract.extracted_fields_route(uuid.uuid4(), _ctx())
    variant["value"] = "notices"
    with pytest.raises(NotImplementedYet):
        await contract.extracted_fields_route(uuid.uuid4(), _ctx())
    with pytest.raises(NotImplementedYet):
        await contract.text_retry_route(uuid.uuid4(), _ctx())
    assert calls == ["evidence.read", "evidence.read", "evidence.ocr_retry"]
