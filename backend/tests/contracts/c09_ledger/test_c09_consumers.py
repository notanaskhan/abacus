"""AUD-06's consumer view of C9 v1 (A-02-T08; TASK-1263; SPEC-333 AC-5, AC-17, AC-18, AC-29,
AC-30), run against the A-02-T03 stub. The seed's figures at E0 (Mon Sep 14, 2026; blueprint
§9.4; `tests/golden/scenario/brightwater_hale/northwind.yaml`): Northwind's unadjusted net assets
16,812,400.00 EOY and 14,228,500.00 BOY, investments 16,500,000.00 and 13,940,000.00, debits =
credits 17,663,450.00, and the Investments leadsheet 13,940,000 · 16,500,000 · 2,560,000 · 18.4 %.
They fit the stub's models, amounts travel as decimal strings (ADR-050), labels and layers are the
registry's, the documented refusal codes are the catalogue's, and the agent holds no C9 action.
The fixture half is `apps/web/src/fixtures/contracts/c09-ledger.contract.test.ts`."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.kernel._statuses import TrialBalanceLabelStatus, TrialBalanceLayerStatus
from abacus.modules.assurance.tb_contract import (
    TbChecksSummaryOut,
    TbLayerBalanceOut,
    TbLayerViewOut,
    TbLeadsheetAreaOut,
    TbLeadsheetRowOut,
    TbNamedTotalOut,
    TbProvenanceOut,
)
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
REPO = Path(__file__).resolve().parents[4]
GOLDEN = REPO / "backend" / "tests" / "golden" / "scenario" / "brightwater_hale" / "northwind.yaml"
CATALOGUE = REPO / "docs" / "architecture" / "error-codes.yaml"
TB = "/v1/engagements/{engagement_id}/trial-balances/{tb_id}"

NET_ASSETS = (Decimal("16812400.00"), Decimal("14228500.00"))  # EOY, BOY
INVESTMENTS = (Decimal("16500000.00"), Decimal("13940000.00"))
DEBITS = CREDITS = Decimal("17663450.00")
# The C9 actions AUD-06 drives (A-02 §4.4); the agent holds none (INV-1).
ACTIONS = (
    "trial_balance.read",
    "trial_balance.adopt",
    "trial_balance.annotate",
    "trial_balance.export",
    "tie_out_check.define",
    "ledger.pull",
    "connection.reconnect_request",
)
# The refusals C9 v1 documents (docs/contracts/c09-ledger.md §6) that are live today; AUD-06's
# messages map each one. `layer_unbalanced` registers with A-02-T07.
LIVE_REFUSALS = (
    "snapshot_entity_mismatch",
    "trial_balance_exists",
    "no_assurance_item",
    "tb_version_stale",
    "tb_same_snapshot",
    "layer_unavailable",
    "citation_required",
    "tie_out_check_stale",
)


def _view() -> TbLayerViewOut:
    eoy, boy = NET_ASSETS
    return TbLayerViewOut(
        trial_balance_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        label=TrialBalanceLabelStatus.STANDARD,
        layer=TrialBalanceLayerStatus.UNADJUSTED,
        layers_available=[TrialBalanceLayerStatus.UNADJUSTED],
        display_unit="cents",
        period_start=date(2025, 7, 1),
        period_end=date(2026, 6, 30),
        prior_period_end=date(2025, 6, 30),
        version_no=1,
        current_version_no=1,
        provenance=TbProvenanceOut(
            source_kind="import",
            source="import_netsuite",
            pulled_at=datetime(2026, 9, 11, 15, 2, tzinfo=UTC),
            adopted_by_user_id=uuid.uuid4(),
            adopted_by_name="Simone Baptiste",
            adopted_at=datetime(2026, 9, 11, 15, 2, tzinfo=UTC),
        ),
        groups=[],
        totals=[
            TbNamedTotalOut(
                key="investments",
                label="Total investments",
                boy=INVESTMENTS[1],
                eoy=INVESTMENTS[0],
            ),
            TbNamedTotalOut(key="net_assets", label="Net assets", boy=boy, eoy=eoy),
        ],
        balance=TbLayerBalanceOut(
            layer=TrialBalanceLayerStatus.UNADJUSTED,
            debit=DEBITS,
            credit=CREDITS,
            difference=DEBITS - CREDITS,
            balanced=DEBITS == CREDITS,
        ),
        checks=TbChecksSummaryOut(tie=3, off=0, pending=0, worst=None),
        newer_snapshots=0,
        allowed_actions=["trial_balance.adopt", "trial_balance.export"],
    )


def test_ac5_the_seed_figures_are_the_goldens() -> None:
    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    text = json.dumps(golden)
    assert '"unadjusted_net_assets": 16812400' in text
    assert '"prior_year_net_assets": -14228500' in text


def test_ac29_northwind_at_e0_fits_the_view_and_balances() -> None:
    view = _view()
    totals = {t.key: (t.eoy, t.boy) for t in view.totals}
    assert totals == {"investments": INVESTMENTS, "net_assets": NET_ASSETS}
    assert (view.balance.debit, view.balance.credit, view.balance.balanced) == (
        DEBITS,
        CREDITS,
        True,
    )
    assert view.balance.difference == Decimal("0.00")


def test_ac5_amounts_travel_as_decimal_strings() -> None:
    view = _view()
    dumped = view.model_dump(mode="json")
    balance = cast(dict[str, object], dumped["balance"])
    assert (balance["debit"], balance["difference"]) == ("17663450.00", "0.00")
    assert TbLayerViewOut.model_validate(dumped) == view


def test_ac18_the_investments_leadsheet_reads_18_4_percent() -> None:
    cy, py = INVESTMENTS
    change = cy - py
    pct = (change / py * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
    assert (change, pct) == (Decimal("2560000.00"), Decimal("18.4"))
    sheet = TbLeadsheetAreaOut(
        trial_balance_id=uuid.uuid4(),
        version_no=1,
        area="Investments",
        unassigned=False,
        layer=TrialBalanceLayerStatus.UNADJUSTED,
        display_unit="cents",
        rows=[
            TbLeadsheetRowOut(
                account_code="1200",
                account_name="Investments",
                py=py,
                cy=cy,
                change=change,
                change_pct=pct,
            )
        ],
        py=py,
        cy=cy,
        change=change,
        change_pct=pct,
    )
    assert sheet.model_dump(mode="json")["change_pct"] == "18.4"


def test_ac17_labels_and_layers_are_the_registrys() -> None:
    props = cast(dict[str, Json], SCHEMAS["TbLayerViewOut"]["properties"])
    assert props["label"].get("$ref") == "#/components/schemas/TrialBalanceLabelStatus"
    assert props["layer"].get("$ref") == "#/components/schemas/TrialBalanceLayerStatus"
    assert {m.value for m in TrialBalanceLabelStatus} == {
        "standard",
        "interim",
        "prior",
        "budget",
        "preliminary",
    }
    assert [m.value for m in TrialBalanceLayerStatus] == ["unadjusted", "aje", "rje", "final"]


def test_ac17_the_layer_view_documents_its_conflicts() -> None:
    responses = cast(Json, PATHS[f"{TB}/layers/{{layer}}"]["get"]["responses"])
    # Live since A-02-T10 (TASK-1336): 404 (walls, flag off) and 409, no longer 501.
    assert {"404", "409"} <= set(responses)
    assert "501" not in responses


@pytest.mark.parametrize("code", LIVE_REFUSALS)
def test_the_documented_refusals_are_catalogued(code: str) -> None:
    catalogue = cast(dict[str, object], yaml.safe_load(CATALOGUE.read_text(encoding="utf-8")))
    codes = cast(dict[str, object], catalogue.get("codes", catalogue))
    assert code in codes


@pytest.mark.parametrize("action", ACTIONS)
def test_ac30_the_agent_holds_no_c9_action(action: str) -> None:
    assert RULES[action].decisions.get("agent", "deny") == "deny"
    assert RULES[action].decisions.get("system", "deny") == "deny"


def test_no_c9_model_counts_hidden_rows() -> None:
    for name in ("TbLayerViewOut", "TbLeadsheetAreaOut", "TbGroupOut", "TbChecksSummaryOut"):
        props = cast(dict[str, Json], SCHEMAS[name]["properties"])
        assert not [p for p in props if "hidden" in p or "walled" in p]
