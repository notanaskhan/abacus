"""A-02-T27 (TASK-1613; A-02 §5.3): the tooling fakes and the `connections` slice.

"make seed-demo shows POR-16a for Tess Moreno at 9:24 AM, the fakes are refused outside synthetic
environments, and the Granite Peak TB balances with total assets 26,410,000" (A-02-T27
acceptance). Here: the fakes refuse a production environment; the fake QuickBooks Online runs the
real connector over a recorded report to a balanced trial balance; the fake NetSuite serves an
export the import format parses; the Granite Peak FY2026 export balances at 71,910,000 with total
assets 26,410,000 and FY2025's total assets are 23,200,000; Northwind's template foots at net
assets 16,812,400; the slice seeds Copperleaf's four POR-16a connections and the `copperleaf`
holdout drops them. The seed-demo walk itself is the batch pass's (it needs the stack).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus.modules.connections.api import CONNECTORS, Period, is_networkless
from abacus.modules.connections.import_parse import parse_export
from abacus.modules.connections.models import Connection
from abacus.modules.connections.qbo_format import parse_qbo_trial_balance
from abacus_tools.fakes import ledgers as fakes
from abacus_tools.synthetic.scenarios.brightwater_hale import ledgers
from abacus_tools.synthetic.scenarios.brightwater_hale.connections import connections_events
from abacus_tools.synthetic.scenarios.brightwater_hale.holdouts import held_out

FIXTURE = Path(__file__).parent / "fixtures" / "qbo_trial_balance_synthetic.json"
PERIOD = Period(date(2026, 1, 1), date(2026, 8, 31))


@pytest.fixture
def installed(tmp_path: Path) -> Iterator[Path]:
    fakes.install_fake_ledgers(tmp_path)
    yield tmp_path
    fakes.uninstall_fake_ledgers()


def _connection(provider: str) -> Connection:
    return Connection(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), client_entity_id=uuid.uuid4(), provider=provider
    )


def test_ac_the_fakes_are_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    production = settings().model_copy(update={"environment": "production"})
    monkeypatch.setattr(fakes, "settings", lambda: production)
    with pytest.raises(fakes.FakeLedgersRefused):
        fakes.install_fake_ledgers(tmp_path)
    assert fakes.FAKE_QBO not in CONNECTORS


def test_the_fakes_reach_no_host(installed: Path) -> None:
    for name in (fakes.FAKE_QBO, fakes.FAKE_NETSUITE, *fakes.FAKE_FEEDS):
        assert name in CONNECTORS and is_networkless(name)


async def test_the_fake_qbo_runs_the_real_connector_to_a_balanced_tb(installed: Path) -> None:
    connection = _connection(fakes.FAKE_QBO)
    folder = installed / str(connection.id)
    folder.mkdir()
    name = f"qbo-trial_balance-{PERIOD.start.isoformat()}_{PERIOD.end.isoformat()}.json"
    (folder / name).write_bytes(FIXTURE.read_bytes())
    connector = CONNECTORS[fakes.FAKE_QBO](connection, None)
    payload = await connector.pull("trial_balance", PERIOD, None)
    assert payload.source == "quickbooks_online"  # the pipeline's QuickBooks normaliser
    tb = parse_qbo_trial_balance(payload.content)
    assert tb.total_debit == tb.total_credit == Decimal("274715.35")


async def test_the_fake_netsuite_serves_an_export_the_import_format_parses(
    installed: Path,
) -> None:
    connection = _connection(fakes.FAKE_NETSUITE)
    folder = installed / str(connection.id)
    folder.mkdir()
    period = Period(date(2025, 7, 1), date(2026, 6, 30))
    name = f"netsuite-trial_balance-{period.start.isoformat()}_{period.end.isoformat()}.csv"
    (folder / name).write_bytes(
        (ledgers.FILES / "granite-peak-fy2026-netsuite-tb.csv").read_bytes()
    )
    payload = await CONNECTORS[fakes.FAKE_NETSUITE](connection, None).pull(
        "trial_balance", period, None
    )
    assert payload.source == "import_netsuite_tb_csv"
    parsed = parse_export(payload.content, "netsuite_tb_csv", period.start, period.end)
    assert parsed.trial_balance.total_debit == parsed.trial_balance.total_credit


def test_ac_granite_peak_balances_with_total_assets_26_410_000() -> None:
    fy26, fy25 = ledgers.GRANITE_PEAK_FY2026, ledgers.GRANITE_PEAK_FY2025
    assert fy26.total_debits == fy26.total_credits == Decimal("71910000")
    assert ledgers.total_assets(fy26) == Decimal("26410000")
    assert fy25.total_debits == fy25.total_credits
    assert ledgers.total_assets(fy25) == Decimal("23200000")
    content = (ledgers.FILES / "granite-peak-fy2026-netsuite-tb.csv").read_bytes()
    parsed = parse_export(content, "netsuite_tb_csv", date(2025, 7, 1), date(2026, 6, 30))
    assets = sum(
        (x.debit - x.credit for x in parsed.trial_balance.lines if x.account_code < "2000"),
        Decimal(0),
    )
    assert assets == Decimal("26410000.00")


def test_northwind_template_foots_at_unadjusted_net_assets() -> None:
    content = (ledgers.FILES / "northwind-py2025-tb-template.xlsx").read_bytes()
    parsed = parse_export(content, "accrued_template", date(2025, 1, 1), date(2025, 12, 31))
    assert parsed.trial_balance.total_credit == Decimal("16812400.00")
    assert parsed.trial_balance.total_debit == parsed.trial_balance.total_credit


def test_the_slice_seeds_copperleafs_four_por16a_connections() -> None:
    events = connections_events()
    assert [e.data["provider"] for e in events] == [
        "fake_quickbooks_online",
        "fake_bank_feed",
        "fake_card_feed",
        "fake_sales_feed",
    ]
    amex = next(e for e in events if e.data["provider"] == "fake_card_feed")
    assert (amex.data["status"], amex.data["reason"]) == ("needs_attention", "token_expired")
    assert all(e.data["connected_by"] == "Tess Moreno" for e in events)


def test_the_copperleaf_holdout_drops_the_slice() -> None:
    dropped = held_out({"copperleaf"})
    assert all(e.client in dropped for e in connections_events())


def test_the_files_are_the_rendered_ones(tmp_path: Path) -> None:
    for written in ledgers.write_files(tmp_path):
        committed = ledgers.FILES / written.name
        if written.suffix == ".csv":
            assert written.read_bytes() == committed.read_bytes(), written.name
