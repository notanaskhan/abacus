"""R-02-T08 (TASK-6102; chapter 10 §10.7.2; R-02 §8.1): C10's provider suite.

Written against the stub, from R-02 §3.5 to §3.7, §3.15 and §4.2, never from the implementation. It
holds the shapes consumers bind to (A-06's send-draft, A-07's release, C-02, T-02, X-01), the
refusal codes, the client-only actions, and the seed figures the screens draw. When R-02-T09's
service lands these stay green unchanged (frozen S29; additive in place, chapter 01 §1.3.2).
"""

from __future__ import annotations

import dataclasses
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import get_args

import pytest
import yaml

from abacus.kernel.errors import DomainInvalid
from abacus.modules.portal import deliverables_contract as dc
from abacus.modules.reporting import deliverables as svc

REPO = Path(__file__).resolve().parents[4]
FIGURES = json.loads(
    (REPO / "backend/tests/golden/scenario/brightwater_hale/portal_figures.json").read_text()
)
MIGRATION = (REPO / "backend/migrations/versions/0710_r02_deliverables_governance.py").read_text()


def _check_list(name: str) -> set[str]:
    """The quoted values of a CHECK list constant in migration 0710."""
    block = re.search(rf"^{name} = (\(\n.*?\n\)|\"[^\n]*\")$", MIGRATION, re.S | re.M)
    assert block, name
    return set(re.findall(r"'([a-z_0-9]+)'", block.group(1)))


def _fields(cls: type) -> list[str]:
    return [f.name for f in dataclasses.fields(cls)]


# --- shapes ---------------------------------------------------------------------------------


def test_ac17_publish_spec_carries_what_r02_needs() -> None:
    assert _fields(svc.DeliverableSpec) == [
        "client_id",
        "kind",
        "title",
        "source_module",
        "source_ref",
        "evidence_version_id",
        "render_hash",
        "page_count",
        "audiences",
        "published_by_user_id",
        "actor_kind",
        "on_behalf_of_user_id",
        "client_entity_id",
        "engagement_id",
        "work_item_id",
        "generated_document_id",
        "is_draft",
        "page_comments",
        "restricted_use",
        "legend_kind",
        "approval_kind",
        "approval_item_id",
    ]
    assert _fields(svc.PublishedDeliverable) == [
        "deliverable_id",
        "version_id",
        "version_no",
        "created",  # False on a repeat with the same source version (AC-17 no-op)
    ]


def test_ac17_kinds_and_audiences_match_the_schema() -> None:
    assert set(get_args(dc.DeliverableKind)) == _check_list("_DELIVERABLE_KINDS")
    assert set(get_args(svc.AudienceScope)) == _check_list("_SCOPE_KINDS")
    assert "governance_room" in get_args(svc.AudienceScope)


def test_ac19_withdraw_reasons_match_the_schema() -> None:
    assert set(get_args(svc.WithdrawReason)) == {"wrong_file", "reissued", "other"}
    assert "reason_code text NULL CHECK (reason_code IN ('wrong_file', 'reissued', 'other'))" in (
        MIGRATION
    )


def test_ac20_delivery_states_per_audience_contact() -> None:
    assert get_args(svc.DeliveryState) == ("not_opened", "delivered", "viewed", "downloaded")
    assert _fields(svc.AudienceReceipt) == [
        "contact_id",
        "state",
        "first_viewed_at",
        "first_downloaded_at",
        "download_count",
    ]
    assert "receipts" in _fields(svc.WorkItemDeliverable)


def test_status_words_are_the_registry_s() -> None:
    vocabulary = yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())
    codes = set(vocabulary["objects"]["deliverable"]["codes"])
    assert set(get_args(dc.DeliverableStatus)) == codes
    labels = {k: v["label"] for k, v in vocabulary["objects"]["deliverable"]["codes"].items()}
    assert labels["for_your_review"] == "For your review"
    assert labels["approved_by_you"] == "Approved by you"
    assert labels["final"] == "Final"


def test_client_dtos_carry_no_firm_only_field() -> None:
    allowed_actions = set(get_args(dc.DeliverableAction))
    assert allowed_actions == {"download", "approve", "comment"}
    for model in (dc.DeliverableOut, dc.DeliverableVersionOut, dc.DeliverableRowOut):
        assert not {"evidence_version_id", "render_hash", "source_ref", "source_module"} & set(
            model.model_fields
        ), model.__name__


def test_comments_are_bounded_restricted_client_text() -> None:
    body = dc.PageCommentIn.model_fields["body"]
    assert any(getattr(m, "max_length", None) == 1000 for m in body.metadata)
    with pytest.raises(ValueError):
        dc.PageCommentIn(page=0, body="x")


# --- refusal codes --------------------------------------------------------------------------


def test_ac18_a_draft_without_watermark_is_422() -> None:
    assert issubclass(svc.DraftWithoutWatermark, DomainInvalid)
    assert svc.DraftWithoutWatermark.code == "draft_without_watermark"


def test_ac18_the_schema_refuses_a_draft_that_is_not_a_generated_document() -> None:
    assert "CHECK (NOT is_draft OR generated_document_id IS NOT NULL)" in MIGRATION
    assert "CHECK (NOT page_comments OR is_draft)" in MIGRATION


@pytest.mark.parametrize(
    "name",
    [
        "publish_deliverable",
        "supersede_deliverable",
        "withdraw_deliverable",
        "deliverables_for_work_item",
        "expected_deliverables",
        "DraftWithoutWatermark",
    ],
)
def test_every_service_is_public_on_reporting_api(name: str) -> None:
    from abacus.modules.reporting import api

    assert getattr(api, name) is getattr(svc, name)


# --- client-only actions --------------------------------------------------------------------


@pytest.mark.parametrize(
    "action", ["deliverable.read", "deliverable.download", "deliverable.comment"]
)
def test_ac38_deliverables_are_client_reads_never_agent_or_firm(action: str) -> None:
    matrix = yaml.safe_load((REPO / "docs/architecture/permission-matrix/portal.yaml").read_text())
    row = matrix["actions"][action]
    assert (row["agent"], row["system"]) == ("deny", "deny")
    assert not {"firm_admin", "engagement_partner", "manager", "client_service"} & set(row)


def test_ac23_management_approval_is_a_person_s_with_a_fresh_second_factor() -> None:
    matrix = yaml.safe_load((REPO / "docs/architecture/permission-matrix/portal.yaml").read_text())
    row = matrix["actions"]["statement.client_approve"]
    assert row["mfa_recent"] == "required"
    from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS

    assert "statement.approved_by_management" in HUMAN_ONLY_ACTIONS


# --- seed figures ---------------------------------------------------------------------------


def _d(value: str) -> Decimal:
    return Decimal(value)


def test_ac22_page_two_foots() -> None:
    page = FIGURES["fs_draft"]["page_2"]
    for key in ("investments", "receivables", "prior_year"):
        assert sum(map(_d, page[key]["parts"])) == _d(page[key]["total"]), key
    assert _d(page["investments"]["total"]) + _d(page["receivables"]["total"]) == _d(
        page["net_assets"]
    )


def test_ac22_page_two_agrees_with_the_completion_figures() -> None:
    completion = json.loads(
        (
            REPO / "backend/tests/golden/scenario/brightwater_hale/completion_figures.json"
        ).read_text()
    )
    page = FIGURES["fs_draft"]["page_2"]
    assert page["net_assets"] == completion["net_assets"]["total"]
    assert completion["net_assets"]["receivable"] in page["receivables"]["parts"]


def test_ac21_ac24_draft_and_final_page_counts() -> None:
    assert FIGURES["fs_draft"]["pages"] == 14
    finals = {f["title"]: f["pages"] for f in FIGURES["release"]["files"]}
    assert finals["Financial statements and supplemental schedules.pdf"] == 14
    assert finals["Independent auditor's report.pdf"] == 3
