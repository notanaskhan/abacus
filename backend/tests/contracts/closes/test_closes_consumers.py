"""C-01-T06 (TASK-8006; C-01 §8; SPEC-655): consumer contract tests for the closes stubs.

Written on behalf of the downstream epics that read the closes contract: C-02 (the CLS-07, 08,
11, 12 and 13 hosts and the Approved, Delivered and Locked guards), K-04 (the close board
provider), I-01 (the HOME-01 count and HOME-02 gates), P-08 (the portal home source), P-02
(search) and W-02 (WB-01c close-run rows). Row acceptance: "The suite runs in AY's CI and fails
on any rename or removal of a field a downstream consumer reads."
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.modules.closes import contract as c1
from abacus.modules.closes import contract_work as c2
from abacus.modules.closes.api import (
    CloseFacts,
    TransitionNotAvailable,
    register_status_guard,
    status_guard,
)
from abacus.modules.identity.api import AuthContext

ROOT = Path(__file__).resolve().parents[4]

# What each consumer reads, by model: a rename or removal fails here first.
CONSUMERS: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "C-02 CLS-07/08 host (record)": (
        c1.CloseSummaryOut,
        ("close_id", "engagement_id", "client_entity_id", "period", "status", "on_hold",
         "attest", "allowed_actions", "row_version", "planned_links"),
    ),
    "C-02 CLS-08 commentary (flux)": (
        c2.FluxLineOut, ("line_key", "caption", "status", "explanation", "accepted_by")
    ),
    "C-02 CLS-11 sync line": (c1.CloseSyncOut, ("state", "last_synced_at", "next_sync_at")),
    "C-02 CLS-07 entries": (c2.ProposalRefOut, ("proposed_entry_id", "entry_number")),
    "C-02 CLS-04 recordings": (
        c2.EntryRecordingOut, ("proposed_entry_id", "external_txn_id", "found_at")
    ),
    "K-04 board rows": (
        c1.CloseRowOut,
        ("close_id", "status", "on_hold", "accounts_reconciled", "accounts_total", "running"),
    ),
    "K-04 procedure statuses": (
        c1.CloseProcedureOut, ("procedure_id", "run_step_id", "status", "open_count")
    ),
    "I-01 HOME-01 count": (
        c1.CloseTilesOut, ("not_started", "in_progress", "in_review", "delivered")
    ),
    "I-01 HOME-01 summary": (c1.CloseSummaryLineOut, ("open_issues", "past_due", "running")),
    "P-08 portal home (questions)": (
        c2.PortalQuestionOut, ("question_id", "client_wording", "context_line", "status")
    ),
    "P-02 search (rows)": (c1.CloseRowOut, ("close_id", "client_name", "period")),
    "W-02 WB-01c run rows": (
        c1.CloseRunOut, ("run_id", "run_no", "status", "done", "total", "groups")
    ),
}  # fmt: skip

# CloseFacts: the Python facts C-02, K-04, I-01 and P-08 read (C-01 §4.4).
FACTS = (
    "close_id", "engagement_id", "client_entity_id", "period", "status", "on_hold",
    "plan_version", "accounts_reconciled", "accounts_total", "open_issues", "attest",
)  # fmt: skip

# Firm-only words that never reach a portal DTO (QC-9, AC-47, INV-4).
FIRM_ONLY = {
    "issue_id",
    "severity",
    "why_surfaced",
    "issue_class",
    "run_id",
    "agent",
    "drafted_by",
}


@pytest.mark.parametrize("consumer", sorted(CONSUMERS))
def test_every_field_a_consumer_reads_exists(consumer: str) -> None:
    model, fields = CONSUMERS[consumer]
    assert [f for f in fields if f not in model.model_fields] == [], consumer


def test_close_facts_keep_their_fields() -> None:
    names = [f.name for f in dataclasses.fields(CloseFacts)]
    assert [f for f in FACTS if f not in names] == []


def test_the_canonical_statuses_are_six_and_none_is_closed() -> None:
    schema = json.dumps(c1.CloseRowOut.model_json_schema()["properties"]["status"])
    for status in ("not_started", "in_progress", "in_review", "approved", "delivered", "locked"):
        assert f'"{status}"' in schema
    assert '"closed"' not in schema


def test_the_portal_dto_carries_no_firm_only_field() -> None:
    for model in (c2.PortalQuestionOut, c2.PortalQuestionsOut):
        assert FIRM_ONLY.isdisjoint(model.model_fields), model


def _paths() -> dict[str, dict[str, dict[str, object]]]:
    return cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])


def _routes() -> Iterator[tuple[str, str]]:
    for router in (c1.closes_router, c2.close_work_router, c2.portal_close_router):
        for route in router.routes:
            for method in getattr(route, "methods", ()):
                yield route.path, method.lower()  # type: ignore[attr-defined]


def test_every_route_is_published_with_one_action_and_a_501_until_built() -> None:
    paths = _paths()
    seen = list(_routes())
    for path, method in seen:
        op = paths[path][method]
        assert "501" in cast(dict[str, object], op["responses"]), (method, path)
        assert op.get("x-abacus-action"), (method, path)
    assert len(seen) == 46  # 23 in part 1, 23 in part 2


def test_portal_routes_live_under_the_portal_prefix_only() -> None:
    for route in c2.portal_close_router.routes:
        assert route.path.startswith("/v1/portal/")  # type: ignore[attr-defined]
    for router in (c1.closes_router, c2.close_work_router):
        for route in router.routes:
            assert not route.path.startswith("/v1/portal/")  # type: ignore[attr-defined]


async def _guard(ctx: AuthContext, close_id: object) -> None:
    return None


def test_the_status_guard_slot_fails_closed_until_c02_registers() -> None:
    for status in ("approved", "delivered", "locked"):
        c1._guards.pop(status, None)  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(TransitionNotAvailable):
            status_guard(status)
    try:
        register_status_guard("approved", _guard)
        assert status_guard("approved") is _guard
        with pytest.raises(ValueError):
            register_status_guard("approved", _guard)  # one guard per status
        with pytest.raises(ValueError):
            register_status_guard("in_review", _guard)  # type: ignore[arg-type]
    finally:
        c1._guards.pop("approved", None)  # pyright: ignore[reportPrivateUsage]


def test_the_contract_doc_lists_every_route() -> None:
    doc = (ROOT / "docs/contracts/closes.md").read_text()
    for path, _ in _routes():
        tail = path.removeprefix("/v1").split("{")[0].rstrip("/")
        assert tail.split("/")[-1] in doc, path


def test_refusal_codes_are_catalogued() -> None:
    catalogue = (ROOT / "docs/architecture/error-codes.yaml").read_text()
    for error in (
        c1.AccountsNotReconciled, c1.CloseRunInProgress, c1.TransitionNotAvailable,
        c1.PlanVersionPinned, c1.UnadoptedRows, c2.OpenItems, c2.StatementNotAvailable,
        c2.QuestionTemplateRequired,
    ):  # fmt: skip
        assert f"  {error.code}:" in catalogue, error.code
