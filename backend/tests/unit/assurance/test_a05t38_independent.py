"""Independent AC tests for A-05-T26, T27, T28, T35 and T36 (A-05-T38; ADR-078; ADR P-58).

Written apart from those builds: a document trial balance becomes a snapshot only when code foots
it and every line's citation is verified (P-58 refusals: unbalanced, unverified line), the
snapshot carries its provenance and is never adopted here (adoption is a person's: the agent is
denied), and the migrations keep every new table tenant-scoped with the human-only CHECKs on
corrections and certification evaluations. Errors carry identifiers only, never amounts.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
import yaml

from abacus.modules.ledger import service as ledger

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
VERSIONS = BACKEND / "migrations/versions"
M0658 = (VERSIONS / "0658_ebp_contributions.py").read_text()
M0659 = (VERSIONS / "0659_ledger_document_snapshots.py").read_text()
M0665 = (VERSIONS / "0665_ebp_investments_5500.py").read_text()


def _tb(debit: str, credit: str, refs: list[str]) -> SimpleNamespace:
    lines = [SimpleNamespace(account_code=f"10{n}", source_ref=ref) for n, ref in enumerate(refs)]
    return SimpleNamespace(total_debit=Decimal(debit), total_credit=Decimal(credit), lines=lines)


def _call(
    tb: SimpleNamespace,
    citations: dict[str, Any],  # Any: test doubles and JSON
    supported: object | None = None,  # Any: test doubles and JSON
) -> object:
    async def everything(ids: object) -> set[Any]:  # Any: test doubles and JSON
        return set(cast(Any, ids))  # Any: test doubles and JSON

    return asyncio.run(
        ledger.record_document_snapshot(
            cast(Any, SimpleNamespace()),  # Any: test doubles and JSON
            client_entity_id=uuid4(),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            tb=cast(Any, tb),  # Any: test doubles and JSON
            line_citations=citations,
            source_evidence_version_id=uuid4(),
            extraction_run_id=uuid4(),
            pulled_at=datetime(2026, 9, 21, tzinfo=UTC),
            supported=cast(Any, supported or everything),  # Any: test doubles and JSON
        )
    )


def _no_problems(*_a: object, **_k: object) -> list[str]:
    return []


def test_p58_refuses_a_footing_difference_without_naming_an_amount() -> None:
    with pytest.raises(ledger.DocumentUnbalanced) as refused:
        _call(_tb("100.00", "99.00", ["a"]), {"a": uuid4()})
    assert "100" not in str(refused.value) and "99" not in str(refused.value)


def test_p58_refuses_a_line_without_a_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ledger, "validate", _no_problems)
    with pytest.raises(ledger.LineUnverified) as refused:
        _call(_tb("100.00", "100.00", ["a", "b"]), {"a": uuid4()})
    assert refused.value.facts == {"account_code": "101"}


def test_p58_refuses_a_citation_c4_does_not_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ledger, "validate", _no_problems)

    async def none(_ids: object) -> set[Any]:  # Any: test doubles and JSON
        return set()

    with pytest.raises(ledger.LineUnverified):
        _call(_tb("100.00", "100.00", ["a"]), {"a": uuid4()}, supported=none)


def test_the_snapshot_names_its_document_and_is_never_adopted_here() -> None:
    source = inspect.getsource(ledger.record_document_snapshot)
    assert "source_evidence_version_id" in source and "extraction_run_id" in source
    assert "adopt" not in source.split('"""')[-1]  # the body, after the docstring


def test_the_agent_never_adopts_a_trial_balance() -> None:
    matrix = yaml.safe_load(
        (ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text()
    )["actions"]
    assert matrix["trial_balance.adopt"]["agent"] == "deny"


def test_document_snapshots_must_carry_provenance() -> None:
    assert "ledger_snapshots_document_provenance" in M0659
    assert "source <> 'document_extraction'" in M0659


@pytest.mark.parametrize(
    ("migration", "tables"),
    [
        (M0658, ("ebp_payrolls", "ebp_late_remittances", "ebp_late_remittance_events")),
        (M0665, ("ebp_certification_evaluations",)),
    ],
)
def test_every_new_table_is_tenant_scoped(migration: str, tables: tuple[str, ...]) -> None:
    assert "tenant_table(" in migration
    for table in tables:
        assert table in migration


def test_a_correction_is_a_persons_record() -> None:
    assert "ebp_late_remittance_events_human_correction" in M0658
    assert "actor_kind = 'human' AND actor_user_id IS NOT NULL" in M0658
    assert "insert_only(" in M0658


def test_a_certification_evaluation_is_a_persons() -> None:
    """The CHECK's binding to the session's actor is exercised against the database in
    `tests/integration/test_a05t35_ebp_investments_migration.py` (an agent cannot write one)."""
    assert "ebp_certification_evaluations_by_a_person" in M0665
