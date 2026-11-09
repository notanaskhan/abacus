"""T-04-T06 (TASK-6321; ADR-078; SPEC-649; DEC-3021): RW-1 and WS-1 consumer contract tests.

Written from the screens' needs (the eight screen contracts and T-04 §3), not the stub: each
artboard's fields must exist on the models it reads, every route answers through exactly one
matrix action, the decisions are a person's, and the figures the artboards draw foot.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.modules.tax import workspace_contract as rw

Schema = dict[str, object]

# What each screen reads from which model (fields named by the screen contracts).
NEEDS: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "TAX-04 a/b tabs": (
        rw.WorkspaceSummaryOut,
        ("review_count", "viewer_level", "issues_open", "allowed_actions"),
    ),
    "TAX-04 tree": (
        rw.ReviewDocumentOut,
        (
            "evidence_version_id",
            "title",
            "category",
            "approval",
            "approvals_count",
            "flagged",
            "mismatch_field_key",
            "version",
        ),
    ),
    "TAX-04 c mismatch": (
        rw.LeadsheetLineOut,
        ("line_key", "amount", "contributing_field_keys", "mismatch"),
    ),
    "TAX-04 lighting": (
        rw.FieldLinkOut,
        ("match_id", "evidence_version_id", "page", "bbox", "field_key", "line_key"),
    ),
    "TAX-05 a matrix": (
        rw.K1MatrixRowOut,
        ("activity_id", "current_year", "prior_year", "status"),
    ),
    "TAX-05 e request": (rw.FinalApprovalRequestIn, ("assignee_user_id",)),
    "TAX-08 availability": (rw.WorkspaceSummaryOut, ("assistant",)),
    "TXI-01 fields": (
        rw.WorksheetFieldOut,
        ("field_key", "value", "state", "provenance", "citations", "signed_off_by", "seen_seq"),
    ),
    "TXI-01 tree": (rw.WorksheetNodeOut, ("title", "group", "tsj", "new_this_year", "edited")),
    "TXI-02 treatments": (
        rw.K1TreatmentOut,
        ("line", "treatment", "status", "changed_vs_year", "decided_by_name", "version"),
    ),
    "TXI-02 e released": (
        rw.K1ActivityOut,
        ("status", "released_on", "treatments", "pending_proposal_id"),
    ),
    "TXI-02 d override": (rw.K1OverrideIn, ("value", "reason", "seen_version")),
    "TXI-03 residency": (
        rw.ReturnResidencyOut,
        ("status", "facts", "options", "confirmed_by_name", "confirmed_at"),
    ),
    "TXI-03 allocation": (
        rw.AllocationRowOut,
        ("jurisdiction", "income", "credits", "derivation"),
    ),
}


@pytest.mark.parametrize("need", sorted(NEEDS))
def test_every_artboard_field_exists(need: str) -> None:
    model, fields = NEEDS[need]
    missing = [f for f in fields if f not in model.model_fields]
    assert missing == [], f"{need}: {missing}"


def _paths() -> dict[str, dict[str, dict[str, object]]]:
    return cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])


ROUTES = {
    ("get", "/v1/tax/returns/{return_id}/workspace"),
    ("get", "/v1/tax/returns/{return_id}/review-tree"),
    ("post", "/v1/tax/returns/{return_id}/document-approvals"),
    ("post", "/v1/tax/document-approvals/{approval_id}/reverse"),
    ("get", "/v1/tax/returns/{return_id}/leadsheets"),
    ("get", "/v1/tax/returns/{return_id}/matrices/sch-e-k1"),
    ("get", "/v1/tax/returns/{return_id}/links"),
    ("post", "/v1/tax/returns/{return_id}/final-approval-requests"),
    ("post", "/v1/tax/returns/{return_id}/draft-runs"),
    ("get", "/v1/tax/returns/{return_id}/worksheets"),
    ("get", "/v1/tax/worksheets/{worksheet_id}/fields"),
    ("get", "/v1/tax/returns/{return_id}/k1-activities"),
    ("get", "/v1/tax/k1-activities/{activity_id}"),
    ("post", "/v1/tax/k1-activities/{activity_id}/treatment-runs"),
    ("post", "/v1/tax/k1-treatments/{treatment_id}/override"),
    ("get", "/v1/tax/returns/{return_id}/residency"),
    ("post", "/v1/tax/returns/{return_id}/residency/proposal-runs"),
    ("get", "/v1/tax/returns/{return_id}/state-allocation"),
}


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_every_route_is_published_and_answers_501_until_built(method: str, path: str) -> None:
    op = _paths()[path][method]
    assert "501" in cast(dict[str, object], op["responses"])


def test_decisions_deny_the_agent() -> None:
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[4]
    actions = yaml.safe_load((root / "docs/architecture/permission-matrix/tax.yaml").read_text())[
        "actions"
    ]
    for action in (
        "document.approve", "tax_return.request_approval", "tax_return.draft_run",
        "k1_treatment.approve", "k1_treatment.override", "residency.confirm",
        "residency.request_proposal",
    ):  # fmt: skip
        assert (actions[action]["agent"], actions[action]["system"]) == ("deny", "deny"), action


def test_values_are_tax_return_information() -> None:
    for model, name in ((rw.LeadsheetLineOut, "amount"), (rw.WorksheetFieldOut, "value"),
                        (rw.K1MatrixRowOut, "current_year")):  # fmt: skip
        schema = json.dumps(model.model_json_schema()["properties"][name])
        assert '"cls": "restricted"' in schema, (model, name)


# --- the figures the artboards draw (screen contracts' Figures) ---------------------------------


def test_feld_line_8_foots_598_030_plus_1_550_plus_16_025() -> None:
    assert Decimal("598030") + Decimal("1550") + Decimal("16025") == Decimal("615605")


def test_ridgeline_box_2_shares_foot_to_307_900() -> None:
    assert Decimal("141634") + Decimal("96989") + Decimal("69277") == Decimal("307900")


def test_review_count_is_41_minus_4() -> None:
    """DF-34: TAX-05's Review 37 = 41 documents - 4 approved, then 36 after one more."""
    assert 41 - 4 == 37
    assert 37 - 1 == 36
