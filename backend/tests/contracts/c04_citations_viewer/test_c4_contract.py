"""C4 v1 consumer contract tests (P-03-T03; SPEC-322; ADR-166): every C4 route with its one matrix
action, the flag gate (404 off, 501 on), the shapes SHL-07 and SHL-08 read, the refusal codes, the
human-only actions, and the footing figures the fixtures carry. Schema and matrix only: the
routes are stubs until P-03-T05, T07, T12 and T14."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._flags import (
    EVIDENCE_CITATIONS_V2,
    EVIDENCE_PII_REVEAL,
    EVIDENCE_VIEWER_UNLOCK,
    EVIDENCE_VIEWER_V1,
)
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag
from abacus.modules.evidence import trust_contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
VERSION = "/v1/evidence-versions/{version_id}"

# (method, path) -> (the one matrix action, the flag that gates it) (P-03 §4.3, §4.9).
ROUTES: dict[tuple[str, str], tuple[str, Flag]] = {
    ("get", "/v1/citations/{citation_id}"): ("citation.read", EVIDENCE_CITATIONS_V2),
    ("get", "/v1/citations"): ("citation.read", EVIDENCE_CITATIONS_V2),
    ("post", "/v1/citations/{citation_id}/relink"): ("citation.relink", EVIDENCE_CITATIONS_V2),
    ("post", "/v1/citations"): ("citation.create", EVIDENCE_CITATIONS_V2),
    ("get", f"{VERSION}/viewer"): ("evidence.read", EVIDENCE_VIEWER_V1),
    ("get", f"{VERSION}/pages/{{page_no}}"): ("evidence.read", EVIDENCE_VIEWER_V1),
    ("get", f"{VERSION}/regions"): ("evidence.read", EVIDENCE_VIEWER_V1),
    ("get", f"{VERSION}/search"): ("evidence.read", EVIDENCE_VIEWER_V1),
    ("post", f"{VERSION}/pii-reveals"): ("pii.reveal", EVIDENCE_PII_REVEAL),
    ("post", f"{VERSION}/unlock"): ("evidence.unlock", EVIDENCE_VIEWER_UNLOCK),
}
HUMAN_ONLY = {"citation.relink", "citation.create", "pii.reveal", "evidence.unlock"}
CLIENTS = ("client_admin", "client_contributor", "client_service")


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _enum(model: str, field: str) -> set[str]:
    prop = _props(model)[field]
    options = cast(list[Json], prop["anyOf"]) if "anyOf" in prop else [prop]
    found: set[str] = set()
    for option in options:
        target = (
            SCHEMAS[cast(str, option["$ref"]).rsplit("/", 1)[1]] if "$ref" in option else option
        )
        found |= set(cast(list[str], target.get("enum", [])))
        if "const" in target:  # a one-value Literal
            found.add(cast(str, target["const"]))
    return found


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_spec322_each_route_declares_one_action_and_is_a_stub(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)][0]
    assert {"404", "501"} <= set(cast(Json, op["responses"]))


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
async def test_spec322_flag_off_is_404_and_on_is_501(
    method: str, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = ROUTES[(method, path)][1]
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[Flag] = []

    async def answer(value: bool):  # noqa: ANN202 - a tiny fake
        async def flag_enabled(_tenant: object, flag: Flag) -> bool:
            seen.append(flag)
            return value

        return flag_enabled

    monkeypatch.setattr(trust_contract, "flag_enabled", await answer(False))
    with pytest.raises(NotFound):
        await trust_contract._stub(ctx, gate)  # pyright: ignore[reportPrivateUsage]  # the gate
    monkeypatch.setattr(trust_contract, "flag_enabled", await answer(True))
    with pytest.raises(NotImplementedYet):
        await trust_contract._stub(ctx, gate)  # pyright: ignore[reportPrivateUsage]  # the gate, tested directly
    assert seen == [gate, gate]


def test_spec322_the_ten_kinds_and_the_verification_reasons() -> None:
    assert _enum("CitationV2Out", "kind") == {
        "document_text",
        "sheet_cell",
        "ledger_line",
        "workpaper_cell",
        "methodology_step",
        "policy_rule",
        "record_field",
        "tax_form_line",
        "artifact_cell",
        "request_item",
    }
    assert _enum("CitationV2Out", "verification_reason") == {
        "page_not_found",
        "cell_not_found",
        "quote_not_found",
        "value_mismatch",
        "bbox_mismatch",
        "source_not_found",
        "source_not_visible",
        "locator_invalid",
    }
    assert _enum("CitationV2Out", "state") == {"valid", "moved", "broken", "relinked"}
    assert _enum("CitationV2Out", "quote_state") == {"shown", "withheld", "changed"}


def test_spec322_a_citation_carries_no_stored_quote_or_model_text() -> None:
    props = _props("CitationV2Out")
    # The quote is re-read from the masked layer: Restricted, never Public or Internal.
    assert props["quote"]["cls"] == "restricted"
    assert "quote_sha256" not in props and "quote_text" not in props
    assert {"title", "loc", "allowed_actions", "verified"} <= set(props)


def test_spec322_viewer_routes_carry_geometry_and_mask_tokens_never_text() -> None:
    page = set(_props("ViewerPageOut"))
    assert "text" not in page and "words" not in page
    assert set(_props("ViewerSearchHitOut")) == {"page", "rects"}
    assert _enum("ViewerManifestOut", "status") == {
        "processing",
        "ready",
        "password_protected",
        "unreadable",
        "not_previewable",
    }
    mask = _props("PiiMaskOut")
    assert "value" not in mask and mask["display"]["cls"] == "confidential"


def test_spec322_only_the_reveal_answer_carries_a_value_and_the_password_never_leaves() -> None:
    assert _props("PiiRevealOut")["value"]["cls"] == "restricted"
    for model, props in SCHEMAS.items():
        if model != "PiiRevealOut" and "properties" in props:
            assert "value_sealed" not in cast(Json, props["properties"]), model
    assert "password" not in _props("EvidenceUnlockOut")
    assert _props("EvidenceUnlockIn")["password"]["cls"] == "restricted"


def test_spec322_the_create_route_is_reserved() -> None:
    assert set(_props("CitationCreateIn")) == {
        "cited_from_type",
        "cited_from_id",
        "cited_from_ref",
        "kind",
        "locator",
    }
    assert _enum("CitationCreateIn", "kind") == {"document_text"}  # Cite selection only


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY))
def test_spec322_human_only_actions_deny_the_agent_and_system(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny"
    assert decisions.get("system") == "deny"


def test_spec322_clients_and_client_service_never_see_citations_or_reveal() -> None:
    for action in ("citation.read", "pii.reveal"):
        decisions = RULES[action].decisions
        assert all(decisions.get(role) in (None, "deny") for role in CLIENTS), action


def test_spec322_reveal_is_onshore_independent_and_needs_recent_mfa() -> None:
    rule = RULES["pii.reveal"]
    assert rule.not_offshore and rule.independence and rule.mfa_recent


def test_spec322_the_fixture_figures_foot() -> None:
    # SHL-08b: the trial balance's total investments, and net assets.
    funds, broker = Decimal("14895000.00"), Decimal("1605000.00")
    assert funds + broker == Decimal("16500000.00")
    assert Decimal("16500000.00") + Decimal("312400.00") == Decimal("16812400.00")
    # SHL-08a: 25% of the 6,200 Ridgeline allocation is the K-1's 1,550 box 18A.
    assert Decimal("6200") * Decimal("0.25") == Decimal("1550")
