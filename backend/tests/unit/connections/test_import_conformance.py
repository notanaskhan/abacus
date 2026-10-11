"""SPEC-028 AC-7 (TASK-052): the import connector passes the conformance suite, reads only the
latest clean import, and is registered as provider `import`."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from abacus.modules.connections.api import CONNECTORS, ConnectorError, Period
from abacus.modules.connections.connectors.import_file import ImportConnector
from abacus.modules.connections.models import LedgerImport
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.ledger_exports import qbo_trial_balance_csv

from .conformance import Check, Harness, HarnessFactory, conformance_params, run_check

PERIOD = Period(date(2025, 1, 1), date(2025, 12, 31))


def _row(*, scan_status: str = "clean", status: str = "received") -> LedgerImport:
    return LedgerImport(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        client_entity_id=uuid.uuid4(),
        format="qbo_tb_csv",
        period_start=PERIOD.start,
        period_end=PERIOD.end,
        storage_key="k",
        storage_version_id="v",
        fingerprint="0" * 64,
        size_bytes=1,
        scan_status=scan_status,
        status=status,
        failure_code=None,
        totals_from_lines=False,
        uploaded_by=uuid.uuid4(),
        on_behalf=False,
        created_at=datetime(2026, 1, 5, tzinfo=UTC),
    )


class _Stored(ImportConnector):
    """The connector with the database and the store replaced by one upload."""

    def __init__(self, row: LedgerImport | None, content: bytes) -> None:
        super().__init__(uuid.uuid4(), uuid.uuid4())
        self._row, self._bytes = row, content

    async def _latest(
        self, period: Period | None, *, clean_only: bool = True
    ) -> LedgerImport | None:
        row = self._row
        if row is None or (clean_only and row.scan_status != "clean"):
            return None
        if period is not None and row.period_end != period.end:
            return None
        return row

    async def _content(self, found: LedgerImport) -> bytes:
        return self._bytes


def import_harness(scratch: Path) -> Harness:
    entity = generate(7).client_entities[0]
    content = qbo_trial_balance_csv(entity.trial_balances[-1], as_of=PERIOD.end)
    return Harness(_Stored(_row(), content), {"trial_balance": (PERIOD, content)})


@pytest.mark.parametrize(("factory", "check"), conformance_params({"import": import_harness}))
async def test_ac7_import_connector_passes_the_conformance_suite(
    factory: HarnessFactory, check: Check, tmp_path: Path
) -> None:
    await run_check(check, factory, tmp_path)


def test_ac7_the_registry_knows_the_import_provider() -> None:
    assert "import" in CONNECTORS


async def test_ac7_the_source_names_the_format() -> None:
    raw = await _Stored(_row(), b"x").pull("trial_balance", PERIOD, None)
    assert raw.source == "import_qbo_tb_csv"
    assert raw.media_type == "text/csv"


async def test_ac7_no_clean_import_for_the_period_is_no_import() -> None:
    for connector in (
        _Stored(None, b""),
        _Stored(_row(scan_status="refused"), b"x"),
    ):
        with pytest.raises(ConnectorError) as raised:
            await connector.pull("trial_balance", PERIOD, None)
        assert raised.value.code == "no_import"
    other = Period(date(2024, 1, 1), date(2024, 12, 31))
    with pytest.raises(ConnectorError):
        await _Stored(_row(), b"x").pull("trial_balance", other, None)


async def test_ac7_health_follows_the_latest_import() -> None:
    assert await _Stored(_row(), b"x").health() is True
    assert await _Stored(_row(status="failed"), b"x").health() is False
    assert await _Stored(_row(scan_status="refused"), b"x").health() is False
    assert await _Stored(None, b"").health() is False
