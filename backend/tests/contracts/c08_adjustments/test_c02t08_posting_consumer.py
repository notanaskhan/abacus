"""CLS-07's consumer view of C8 v2 posting (C-02-T08; SPEC-700 AC-3, AC-4; DEC-5507), run against
the C-02-T06 stub on the handoff's facts: Copperleaf Coffee Roasters, August 2026, Raj Malhotra
(CAS Senior) under BH AJE thresholds v2. Each artboard state a-g fits the models with code's
sums, every operation is declared with its one action and its 501, the agent holds none, and the
batch reads QBO 48213-48218. A breaking change to a posting schema fails here first. The fixture
half is `apps/web/src/fixtures/contracts/c08-posting.contract.test.ts`."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._statuses import PostingBatchStatus, ProposedEntryStatus
from abacus.modules.adjustments.posting_contract import (
    PostingApproverContextOut,
    PostingBatchEntryOut,
    PostingBatchOut,
    PostingClassLimitOut,
    PostingCloseEntriesOut,
    PostingCloseEntryRowOut,
    PostingDryRunOut,
    PostingPreflightResultOut,
    PostingTalliesOut,
    PostingTallyOut,
)
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
WI = "/v1/work-items/{work_item_id}"
OPERATIONS = {
    ("get", f"{WI}/proposed-entries:close"): "proposed_entry.read",
    ("post", "/v1/proposed-entries/{entry_id}/approve"): "proposed_entry.approve",
    (
        "post",
        "/v1/proposed-entries/{entry_id}/request-approval",
    ): "proposed_entry.request_approval",
    ("post", "/v1/proposed-entry-decisions/{decision_id}/undo"): "proposed_entry.undo_approval",
    (
        "post",
        "/v1/proposed-entries/{entry_id}/withdraw-approval",
    ): "proposed_entry.withdraw_approval",
    ("post", "/v1/proposed-entries/{entry_id}/reject-close"): "proposed_entry.reject_close",
    ("post", "/v1/proposed-entries/{entry_id}/record-external"): "proposed_entry.record_external",
    ("get", f"{WI}/proposed-entries.xlsx"): "proposed_entry.export",
    ("post", f"{WI}/posting-batches:dry-run"): "posting_batch.dry_run",
    ("post", f"{WI}/posting-batches"): "posting_batch.post",
    ("post", "/v1/posting-batches/{batch_id}/undo"): "posting_batch.post",
    ("post", "/v1/posting-batches/{batch_id}/entries/{entry_id}/retry"): "posting_batch.post",
    (
        "post",
        "/v1/closing-date-conflicts/{conflict_id}/ask-client",
    ): "closing_date_conflict.resolve",
    ("post", "/v1/closing-date-conflicts/{conflict_id}/redate"): "closing_date_conflict.resolve",
}
# AJE-01..06 (C-02-T09's seed): within threshold 4 · $20,020.00; review 1 · $14,900.00; AJE-06
# (bank adjustments, no threshold class) $380.00 arrives at 10:12 AM (CLS-07c).
ENTRIES = (
    ("AJE-01", "11860.00", "payroll_accruals", "15000.00", ProposedEntryStatus.WITHIN_THRESHOLD),
    ("AJE-02", "700.00", "prepaids", "10000.00", ProposedEntryStatus.WITHIN_THRESHOLD),
    ("AJE-03", "2140.00", "depreciation", "10000.00", ProposedEntryStatus.WITHIN_THRESHOLD),
    ("AJE-04", "5320.00", "deferred_revenue", "10000.00", ProposedEntryStatus.WITHIN_THRESHOLD),
    ("AJE-05", "14900.00", "other_accruals", "10000.00", ProposedEntryStatus.REVIEW_REQUIRED),
)


def _rows(status: ProposedEntryStatus | None = None) -> list[PostingCloseEntryRowOut]:
    return [
        PostingCloseEntryRowOut(
            entry_id=uuid.uuid4(),
            ref=ref,
            amount=Decimal(amount),
            status=status or initial,
            class_limit=PostingClassLimitOut(account_class=cls, limit=Decimal(limit)),
            version=1,
        )
        for ref, amount, cls, limit, initial in ENTRIES
    ]


def _tally(rows: list[PostingCloseEntryRowOut], *statuses: ProposedEntryStatus) -> PostingTallyOut:
    picked = [r for r in rows if r.status in statuses] if statuses else rows
    return PostingTallyOut(
        count=len(picked), amount=sum((r.amount for r in picked), Decimal("0.00"))
    )


def _cls07a() -> PostingCloseEntriesOut:
    rows = _rows()
    return PostingCloseEntriesOut(
        items=rows,
        total=len(rows),
        tallies=PostingTalliesOut(
            proposed=_tally(rows),
            within_threshold=_tally(rows, ProposedEntryStatus.WITHIN_THRESHOLD),
            review_required=_tally(rows, ProposedEntryStatus.REVIEW_REQUIRED),
            approved=0,
            of=len(rows),
        ),
        approver=PostingApproverContextOut(
            user_id=uuid.uuid4(),
            display_name="Raj Malhotra",
            role_label="CAS Senior",
            policy_label="BH AJE thresholds v2",
            policy_version_id=uuid.uuid4(),
            may_batch_within_threshold=True,
        ),
        posting_enabled=True,
        is_attest_client=False,
    )


def test_cls07a_tallies_foot_by_code() -> None:
    tallies = _cls07a().tallies
    assert (tallies.proposed.count, tallies.proposed.amount) == (5, Decimal("34920.00"))
    assert (tallies.within_threshold.count, tallies.within_threshold.amount) == (
        4,
        Decimal("20020.00"),
    )
    assert (tallies.review_required.count, tallies.review_required.amount) == (
        1,
        Decimal("14900.00"),
    )
    assert tallies.within_threshold.amount + tallies.review_required.amount == Decimal("34920.00")
    assert (tallies.approved, tallies.of, tallies.posted_batch_code) == (0, 5, None)


def test_cls07c2_the_dry_run_names_six_entries_and_the_closing_date() -> None:
    total = Decimal("20020.00") + Decimal("14900.00") + Decimal("380.00")
    dry = PostingDryRunOut(
        entry_count=6,
        total_amount=total,
        ledger_label="QuickBooks Online",
        client_entity_name="Copperleaf Coffee Roasters",
        closing_date_target=date(2026, 8, 31),
        results=[PostingPreflightResultOut(entry_id=uuid.uuid4(), ok=True) for _ in range(6)],
    )
    assert dry.total_amount == Decimal("35300.00")
    assert all(r.ok for r in dry.results)


def test_cls07d_batch_2026_08_a_reads_qbo_48213_to_48218() -> None:
    entries = [
        PostingBatchEntryOut(
            entry_id=uuid.uuid4(),
            ref=f"AJE-0{i + 1}",
            status=ProposedEntryStatus.POSTED,
            external_txn_ref=str(48213 + i),
        )
        for i in range(6)
    ]
    batch = PostingBatchOut(
        batch_id=uuid.uuid4(),
        batch_code="2026-08-A",
        period="2026-08",
        status=PostingBatchStatus.POSTED,
        entry_count=6,
        total_amount=Decimal("35300.00"),
        first_external_ref="48213",
        last_external_ref="48218",
        closing_date_target=date(2026, 8, 31),
        entries=entries,
        version=3,
    )
    assert [e.external_txn_ref for e in batch.entries] == [str(n) for n in range(48213, 48219)]


def test_cls07e_a_failed_entry_fails_alone_with_its_reason() -> None:
    failed = PostingBatchEntryOut(
        entry_id=uuid.uuid4(),
        ref="AJE-03",
        status=ProposedEntryStatus.FAILED_POST,
        failure="inactive_account",
        provider_message="QuickBooks Online: account 'Accumulated Depreciation' is inactive",
    )
    assert failed.failure == "inactive_account"


def test_cls07g_an_attest_client_offers_no_post() -> None:
    page = _cls07a().model_copy(update={"is_attest_client": True, "posting_enabled": False})
    for row in page.items:
        assert "posting_batch.post" not in row.allowed_actions


def test_cls07f_policy_acceptance_is_not_a_status() -> None:
    """The dormant policy actor (DEC-53): no status or action reads "Accepted by Policy"."""
    assert "accepted_by_policy" not in {s.value for s in ProposedEntryStatus}


def test_a_breaking_change_to_a_row_is_refused() -> None:
    with pytest.raises(ValidationError):
        PostingCloseEntryRowOut.model_validate({"entry_id": str(uuid.uuid4()), "ref": "AJE-01"})
    with pytest.raises(ValidationError):
        PostingBatchOut.model_validate(
            {
                "batch_id": str(uuid.uuid4()),
                "batch_code": "Aug-A",
                "period": "2026-08",
                "status": "posted",
                "entry_count": 6,
                "total_amount": "35300.00",
                "version": 1,
            }
        )


@pytest.mark.parametrize(("op", "action"), sorted(OPERATIONS.items()), ids=str)
def test_every_operation_is_declared_with_its_action_and_501(
    op: tuple[str, str], action: str
) -> None:
    method, path = op
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])
    rule = RULES[action]
    # The agent holds no write; a read stays in its task scope (proposed_entry.read on main).
    agent = rule.decisions.get("agent", "deny")
    assert agent == "deny" or (rule.reads and agent == "task_scope"), (action, agent)
