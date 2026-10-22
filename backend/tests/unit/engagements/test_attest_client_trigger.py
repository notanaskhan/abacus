"""F-03-T25 (DEC-128): the trigger that derives `clients.is_attest_client` (migration 0082), and
its backfill, use the attest family from `gate_policy` and only lifecycle statuses, so the SQL
and the code can't drift."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from abacus.modules.engagements.gate_policy import FAMILY
from abacus.modules.engagements.transitions import Status

_MIGRATION = Path(__file__).parents[3] / "migrations/versions/0082_client_record_contacts.py"


def _lists(column: str) -> list[set[str]]:
    source = _MIGRATION.read_text()
    found = re.findall(rf"e\.{column} IN \(([^)]*)\)", source)
    return [set(re.findall(r"'([a-z_0-9]+)'", body)) for body in found]


def test_the_trigger_and_backfill_read_the_attest_family() -> None:
    attest = {t for t, family in FAMILY.items() if family == "attest"}
    lists = _lists("type")
    assert len(lists) == 2
    assert all(types == attest for types in lists)


def test_a_client_is_attest_from_acceptance_to_delivery() -> None:
    lists = _lists("status")
    assert len(lists) == 2
    for live in lists:
        assert live <= set(get_args(Status))
        assert live == {"accepted", "contracted", "active", "on_hold", "delivered"}
