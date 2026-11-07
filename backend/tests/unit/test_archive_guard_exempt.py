"""A-07-T13's end-pass review: what must still write after lock stays out of `archived_guard()`.
C13's projector runs on `archive.locked` itself; a guarded row would fail that event forever."""

from __future__ import annotations

import pytest

from abacus.kernel.db.archive_guard import EXEMPT


@pytest.mark.parametrize(
    "table",
    ["human_gates", "messages", "approval_grants", "agent_runs", "agent_run_records"],
)
def test_a_write_the_lock_itself_causes_stays_exempt(table: str) -> None:
    assert EXEMPT[table]


@pytest.mark.parametrize(
    "table", ["workpapers", "sign_offs", "evidence_versions", "review_decisions", "audit_reports"]
)
def test_documentation_is_never_exempt(table: str) -> None:
    assert table not in EXEMPT
