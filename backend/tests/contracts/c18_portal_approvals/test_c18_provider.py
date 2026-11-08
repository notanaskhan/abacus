"""R-02-T08 (TASK-6102; chapter 10 §10.7.2; R-02 §8.1): C18's provider suite.

Written against the stub, from R-02 §3.1 to §3.4 and §4.3 to §4.7, not the implementation. It
holds the protocol every provider implements (A-06 entries and drafts, A-07's acknowledgement,
C-02 and A-08 packages), the refusal codes, the human-only decisions, the decision vocabulary and
the seed figures POR-08 draws. Frozen S30; additive in place (chapter 01 §1.3.2).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from decimal import Decimal
from pathlib import Path
from typing import get_args

import pytest
import yaml

from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.kernel.errors import DomainConflict, DomainForbidden
from abacus.modules.engagements import client_approvals as ca
from abacus.modules.portal import approvals_contract as ac

REPO = Path(__file__).resolve().parents[4]
FIGURES = json.loads(
    (REPO / "backend/tests/golden/scenario/brightwater_hale/portal_figures.json").read_text()
)
MINUS = "\u2212"  # the artboard's minus sign
MATRIX = yaml.safe_load((REPO / "docs/architecture/permission-matrix/portal.yaml").read_text())


# --- the protocol ---------------------------------------------------------------------------


def test_ac1_kinds_are_the_four_r02_names() -> None:
    assert {
        "proposed_entry",
        "uncorrected_misstatements",
        "fs_draft",
        "fs_package",
    } == ca.CLIENT_APPROVAL_KINDS


def test_ac1_a_provider_implements_items_item_decide_and_facts() -> None:
    members = {
        name
        for name, value in vars(ca.ClientApprovalProvider).items()
        if inspect.isfunction(value) and not name.startswith("_")
    }
    assert {"items", "item", "decide", "facts"} <= members


def test_ac6_every_provider_gets_the_client_s_attribution() -> None:
    names = [f.name for f in dataclasses.fields(ca.ClientDecisionContext)]
    assert names[:6] == [
        "contact_id",
        "user_id",
        "grant_id",
        "designation_basis",
        "mfa_verified_at",
        "session_id",
    ]
    assert {"channel", "ip", "device"} <= set(names)
    field = {f.name: f for f in dataclasses.fields(ca.ClientDecisionContext)}["channel"]
    assert field.default == "portal"


def test_decision_vocabulary_and_reasons() -> None:
    assert set(get_args(ca.ClientDecisionWord)) == {"accept", "decline", "approve", "acknowledge"}
    assert list(get_args(ca.DeclineReason)) == FIGURES["decline_reasons"]
    assert set(get_args(ca.DesignationBasis)) == {"owner", "approver_of_record", "ske_designee"}


def test_status_words_are_the_registry_s() -> None:
    vocabulary = yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())
    codes = vocabulary["objects"]["client_approval_item"]["codes"]
    assert set(get_args(ca.ClientApprovalState)) == set(codes)
    assert codes["waiting"]["label"] == "Waiting for you"


# --- refusal codes --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "base", "code"),
    [
        (ca.ApprovalKindNotRegistered, DomainConflict, "approval_kind_not_registered"),  # 409
        (ca.ItemChanged, DomainConflict, "item_changed"),  # 409, AC-4
        (ca.NotDecider, DomainForbidden, "not_decider"),  # 403, AC-2
    ],
)
def test_refusal_codes(error: type[DomainConflict], base: type, code: str) -> None:
    assert issubclass(error, base)
    assert error.code == code


def test_ac4_every_decision_carries_what_the_client_saw() -> None:
    for model in (ac.ProposedEntryDecideIn, ac.ApprovalAcknowledgeIn, ac.PackageDecideIn):
        assert model.model_fields["seen_hash"].is_required(), model.__name__
    assert "seen_hash" in ac.ApprovalItemDetailOut.model_fields


def test_ac14_a_package_decline_needs_its_reason() -> None:
    field = ac.PackageDecideIn.model_fields["reason_code"]
    assert set(get_args(get_args(field.annotation)[0])) == set(FIGURES["decline_reasons"])


# --- human-only decisions -------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "proposed_entry.client_decide",
        "uncorrected_misstatements.acknowledge",
        "statement.client_approve",
        "close_package.client_decide",
    ],
)
def test_ac5_decisions_are_a_client_s_never_an_agent_s(action: str) -> None:
    row = MATRIX["actions"][action]
    assert (row["agent"], row["system"]) == ("deny", "deny")
    assert row["mfa_recent"] == "required"
    assert not {"firm_admin", "engagement_partner", "manager", "client_service"} & set(row)


@pytest.mark.parametrize(
    "event",
    [
        "uncorrected_misstatements.acknowledged",
        "proposed_entry.client_decided",
        "statement.approved_by_management",
    ],
)
def test_ac5_the_decision_events_are_human_only_at_the_data_layer(event: str) -> None:
    assert event in HUMAN_ONLY_ACTIONS


def test_ac12_the_acknowledgement_table_binds_the_session_actor() -> None:
    migration = (
        REPO / "backend/migrations/versions/0710_r02_deliverables_governance.py"
    ).read_text()
    assert "principal_kind text NOT NULL CHECK (principal_kind = 'client')" in migration
    assert "actor_id = actor_user_id::text" in migration


# --- seed figures ---------------------------------------------------------------------------


def _total(values: list[str]) -> Decimal:
    return sum((Decimal(v) for v in values), Decimal(0))


def test_ac11_the_uncorrected_sentence_is_built_from_the_figures() -> None:
    um = FIGURES["uncorrected_misstatements"]
    net = Decimal(um["would_increase"]) - Decimal(um["would_decrease"])
    assert net == Decimal(um["net_effect"])
    assert f"${net:,.2f}" in um["sentence"]
    assert (
        f"(${Decimal(um['would_increase']):,.2f} {MINUS} ${Decimal(um['would_decrease']):,.2f})"
        in (um["sentence"])
    )


def test_ac11_the_figures_agree_with_the_completion_book() -> None:
    completion = json.loads(
        (
            REPO / "backend/tests/golden/scenario/brightwater_hale/completion_figures.json"
        ).read_text()
    )
    um = FIGURES["uncorrected_misstatements"]
    assert Decimal(um["net_effect"]) == Decimal(completion["sum"]["iron_curtain"])
    assert Decimal(um["would_increase"]) == Decimal(completion["sum"]["projected"])
    assert Decimal(um["would_decrease"]) == Decimal(completion["sum"]["accrued"])


def test_ac8_entry_sublines_foot() -> None:
    entries = FIGURES["attest_entries"]
    for key in ("receivable", "accrued"):
        assert _total(entries[key]["lines"]) == Decimal(entries[key]["total"]), key


def test_ac15_posted_entries_foot() -> None:
    posted = FIGURES["posted_entries"]
    assert _total(posted["list"]) == Decimal(posted["total"])
    accrued = posted["accrued_expenses"]
    assert _total(accrued["lines"]) == Decimal(accrued["total"])
    assert accrued["total"] in posted["list"]
