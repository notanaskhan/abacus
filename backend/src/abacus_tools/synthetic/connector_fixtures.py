"""Fake-connector fixtures from synthetic trial balances (TASK-010 design §3).

The fake connector (product code) can't import this package (ADR-101), so it reads the files
written here. The JSON is shaped like a provider's response: amounts as decimal strings, provider
line IDs, and declared control totals.

    write_trial_balance(directory, connection_id, tb, period_start=..., entity_name=...)
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from abacus.modules.connections.api import Period, fixture_path
from abacus_tools.synthetic.model import TrialBalance


def _amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def trial_balance_document(
    tb: TrialBalance,
    *,
    period_start: date,
    entity_name: str,
    control_totals: tuple[Decimal, Decimal] | None = None,
) -> dict[str, object]:
    """`control_totals` overrides the declared totals (to simulate a provider mismatch)."""
    debit = sum((line.debit for line in tb.lines), Decimal(0))
    credit = sum((line.credit for line in tb.lines), Decimal(0))
    declared = control_totals or (debit, credit)
    return {
        "provider": "fake",
        "dataset": "trial_balance",
        "entity": {"name": entity_name},
        "period": {"start": period_start.isoformat(), "end": tb.as_of.isoformat()},
        "currency": "USD",
        "lines": [
            {
                "id": f"acct-{line.account_code}",
                "code": line.account_code,
                "name": line.account_name,
                "debit": _amount(line.debit),
                "credit": _amount(line.credit),
            }
            for line in tb.lines
        ],
        "control_totals": {"debit": _amount(declared[0]), "credit": _amount(declared[1])},
    }


def write_trial_balance(
    directory: Path,
    connection_id: UUID,
    tb: TrialBalance,
    *,
    period_start: date,
    entity_name: str,
    control_totals: tuple[Decimal, Decimal] | None = None,
) -> Path:
    path = fixture_path(directory, connection_id, "trial_balance", Period(period_start, tb.as_of))
    path.parent.mkdir(parents=True, exist_ok=True)
    document = trial_balance_document(
        tb, period_start=period_start, entity_name=entity_name, control_totals=control_totals
    )
    path.write_text(json.dumps(document, indent=2, sort_keys=True))
    return path


def write_fault(directory: Path, connection_id: UUID, period: Period) -> Path:
    path = fixture_path(directory, connection_id, "trial_balance", period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fault": "unavailable"}))
    return path


def write_raw(directory: Path, connection_id: UUID, period: Period, content: bytes) -> Path:
    """Arbitrary bytes (malformed provider responses)."""
    path = fixture_path(directory, connection_id, "trial_balance", period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
