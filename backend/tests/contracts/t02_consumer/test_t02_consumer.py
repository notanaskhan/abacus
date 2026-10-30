# ac-test-author: ayushkbhatia
"""T-02-T05 (TASK-2119; SPEC-502 AC-6): what T-02 consumes, asserted where the providers' CI runs.

- C19 (T-01): the consent summary the TAX-02 chip reads, and TRI tags on return figures.
- C21 (K-02): `due_dates_for` with the period end as `as_of`, and BH-TAX-02 as a
  `return_approval_policy` standard naming its approver per client.
- C7 (N-02): the envelope summary's signer counts.
- C3 (P-04): the `final_approval` sign-off kind TAX-02's final approval records.
- T-01's `engine_sync.imported` payloads for the return summary and the K-1 set: owed by T-01's
  engine import (T-01-T24), held as a strict xfail citing this task.
"""

from __future__ import annotations

import dataclasses
import inspect
from typing import get_args

import pytest

from abacus.modules.methodology import standards_contract as c21b
from abacus.modules.organisations import consents_contract as c19
from abacus.modules.practice import api as practice_api
from abacus.modules.review import contract as review_contract
from abacus.modules.signatures import api as signatures


def test_ac6_c19_the_consent_summary_has_the_counts_the_chip_reads() -> None:
    fields = set(c19.ConsentSummaryOut.model_fields)
    assert {"signed", "expiring", "requested", "declined", "ai_use_signed"} <= fields


def test_ac6_c19_return_figures_are_tri() -> None:
    schema = c19.TaxElectionOut.model_json_schema()["properties"]["amount"]
    assert schema.get("x-tri") is True


def test_ac6_c21_due_dates_take_the_period_end_and_name_their_rules() -> None:
    params = list(inspect.signature(practice_api.due_dates_for).parameters)
    assert params[:3] == ["form", "tax_year", "period_end"]
    fields = {f.name for f in dataclasses.fields(practice_api.DueDates)}
    assert {"original_due_on", "extended_due_on", "reference_set_version_ids"} <= fields


def test_ac6_c21_bh_tax_02_names_an_approver_per_client() -> None:
    entry = c21b.ReturnApprovalAssignment.model_fields
    assert {"client_id", "approver_user_id"} == set(entry)
    assert "return_approval_policy" in get_args(c21b.FirmStandardKind)


def test_ac6_c7_the_envelope_summary_counts_signers() -> None:
    fields = {f.name for f in dataclasses.fields(signatures.EnvelopeSummary)}
    assert {"status", "signed", "total"} <= fields


def test_ac6_c3_final_approval_is_a_sign_off_kind_and_an_issue_block() -> None:
    assert "final_approval" in get_args(review_contract.SignOffKind)
    assert "final_approval" in get_args(review_contract.IssueBlock)


@pytest.mark.xfail(
    strict=True,
    reason="TASK-2119: T-01's engine import (T-01-T24) has not shipped engine_sync.imported",
)
def test_ac6_t01_engine_sync_imported_carries_the_summary_and_k1_set() -> None:
    from abacus.modules.integrations import api as integrations_api

    assert hasattr(integrations_api, "EngineSyncImported")
