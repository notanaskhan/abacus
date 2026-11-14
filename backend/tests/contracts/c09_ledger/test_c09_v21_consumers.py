"""C-01-T08 (TASK-8008; C-01 §8; SPEC-655 F5, F6, F9): C9 v2.1 consumer contract tests, written
for the closes consumer (CLS-04, CLS-05, CLS-10) against the ledger and connections provider.

Row acceptance: "The suite fails on any field drift that CLS-04, CLS-05 or CLS-10 reads." Also the
refusal codes (`stale_source`, `period_not_available`; a walled entity is 404, never its own
code), the sync-status facts, read-only (no route writes to a client system) and the Copperleaf
August fixture footing in code: assets 539,055.45 = liabilities 163,543.05 + equity 375,512.40."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.modules.connections import ledger_sync_contract as sync
from abacus.modules.ledger import api as ledger
from abacus.modules.ledger import cas_contract as cas

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).parent / "fixtures" / "copperleaf_2026_08_tree.json"

READS: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "CLS-04 tree": (
        cas.LedgerAccountOut,
        ("external_id", "number", "name", "classification", "account_type", "account_subtype",
         "parent_external_id", "mask", "is_contra", "active"),
    ),
    "CLS-04 balances": (cas.MonthlyBalanceOut, ("external_id", "period", "balance", "activity")),
    "CLS-04 totals": (
        cas.AccountTreeOut, ("snapshot_id", "period", "accounts", "balances", "totals")
    ),
    "CLS-04/05 register": (
        cas.RegisterLineOut,
        ("line_ref", "external_txn_id", "txn_date", "txn_type", "offset_account_ref", "payee",
         "memo", "amount"),
    ),
    "CLS-10 compare": (cas.PeriodComparisonLineOut, ("external_id", "prior", "current")),
    "CLS-02/04 sync line": (
        sync.LedgerSyncStatusOut,
        ("state", "last_synced_at", "next_sync_at", "retry_at", "failure_code", "meter"),
    ),
    "QC-5 meter": (sync.MeterOut, ("month", "calls", "budget", "state")),
}  # fmt: skip


@pytest.mark.parametrize("reader", sorted(READS))
def test_every_field_a_close_screen_reads_exists(reader: str) -> None:
    model, fields = READS[reader]
    assert [f for f in fields if f not in model.model_fields] == [], reader


def test_the_ledger_api_exports_the_four_reads() -> None:
    for name in ("account_tree", "monthly_balances", "register_lines", "compare_periods"):
        assert callable(getattr(ledger, name)), name


def test_refusal_codes() -> None:
    assert cas.StaleSource.code == "stale_source"
    assert cas.PeriodNotAvailable.code == "period_not_available"
    assert sync.LedgerNotConnected.code == "ledger_not_connected"
    assert sync.MeterBudgetExhausted.code == "meter_budget_exhausted"
    catalogue = (ROOT / "docs/architecture/error-codes.yaml").read_text()
    for code in ("stale_source", "period_not_available", "ledger_not_connected"):
        assert f"  {code}:" in catalogue, code


def test_money_is_decimal_and_confidential() -> None:
    for model, name in ((cas.MonthlyBalanceOut, "balance"), (cas.RegisterLineOut, "amount")):
        schema = json.dumps(model.model_json_schema()["properties"][name])
        assert '"cls": "confidential"' in schema, (model, name)
        assert model.model_fields[name].annotation is Decimal, (model, name)


def test_the_copperleaf_fixture_foots_in_code() -> None:
    raw = json.loads(FIXTURE.read_text())
    raw.pop("_note")
    tree = cas.AccountTreeOut.model_validate(raw)
    totals = tree.totals
    assert totals["asset"] == totals["liability"] + totals["equity"]
    assert totals["asset"] == Decimal("539055.45")
    assert all(isinstance(v, Decimal) for v in totals.values())


def _paths() -> dict[str, dict[str, dict[str, object]]]:
    return cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])


def test_sync_routes_are_published_with_one_action_and_a_501() -> None:
    paths = _paths()
    routes = [
        (route.path, m.lower())  # type: ignore[attr-defined]
        for route in sync.ledger_sync_router.routes
        for m in getattr(route, "methods", ())
    ]
    assert sorted(routes) == [
        ("/v1/client-entities/{client_entity_id}/ledger-sync", "get"),
        ("/v1/client-entities/{client_entity_id}/ledger-sync", "post"),
    ]
    for path, method in routes:
        op = paths[path][method]
        assert "501" in cast(dict[str, object], op["responses"])
    assert paths[routes[0][0]]["get"]["x-abacus-action"] == "ledger.read"
    assert paths[routes[0][0]]["post"]["x-abacus-action"] == "ledger.sync_now"


def test_no_c9_v21_name_is_a_write_to_the_ledger() -> None:
    """CONN-001: C9 has no write method; v2.1 adds only reads and the sync facts."""
    names = [n for n in dir(cas) if not n.startswith("_")]
    assert not [n for n in names if n.startswith(("post_", "write_", "push_", "update_"))]
