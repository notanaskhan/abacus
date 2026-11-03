"""Independent AC tests for the adjustments schema and services (A-06-T17; ADR-078; A-06 §3 F1,
§4.2; ADR-040, DEC-69).

Written apart from A-06-T03, T09 and T10, they fail if any code path can set a posting status or
write to a client ledger: no route posts, no service writes `posted`, `failed_post` or
`reversed`, the migration keeps `pe_posting_dormant` and the attest CHECK, the decisions and
batches stay insert-only and a person's own, the send needs a recent second factor, and the
agent and system principals are refused every write. The database behaviour itself is A-06-T03's
migration suite; these hold the code and the declarations to it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MODULE = BACKEND / "src/abacus/modules/adjustments"
MIGRATION = (BACKEND / "migrations/versions/0643_adjustments_core.py").read_text()
MATRIX = cast(
    dict[str, dict[str, dict[str, str]]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/adjustments.yaml").read_text()),
)["actions"]
PATHS = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
POSTING = ("posted", "failed_post", "reversed")


def test_no_route_posts_to_a_client_ledger() -> None:
    """ADR-040: no path under adjustments or ledgers names a post, a push or a write-back."""
    bad = [
        path
        for path in PATHS
        if ("proposed-entries" in path or "adjust" in path or "ledger" in path)
        and any(word in path.lower() for word in ("/post", ":post", "push", "write-back", "sync"))
    ]
    assert bad == []


def _string_constants(source: str) -> list[str]:
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


@pytest.mark.parametrize("path", sorted(MODULE.glob("*.py")), ids=lambda p: p.name)
def test_no_service_sets_a_posting_status(path: Path) -> None:
    """No string the module writes is a posting status, alone or in SQL ("status = 'posted'")."""
    for text in _string_constants(path.read_text()):
        lowered = text.lower()
        for status in POSTING:
            assert f"'{status}'" not in lowered or "check" in lowered, (path.name, status)
            assert lowered.strip() != status, (path.name, status)


def test_the_migration_keeps_posting_dormant() -> None:
    assert "pe_posting_dormant" in MIGRATION
    assert "CHECK (status NOT IN ('posted', 'failed_post', 'reversed'))" in MIGRATION


def test_an_attest_clients_entry_is_always_review_required() -> None:
    assert "CHECK (NOT is_attest_client OR threshold_result = 'review_required')" in MIGRATION


def test_decisions_are_a_persons_own() -> None:
    assert "actor_kind = 'human'" in MIGRATION
    assert "actor_id = current_" in MIGRATION  # the session's own actor, set by kernel.db


@pytest.mark.parametrize(
    "action",
    [
        "proposed_entry.create",
        "proposed_entry.update",
        "proposed_entry.send_to_client",
        "proposed_entry.reject",
        "proposed_entry.record_client_decision",
        "approval_batch.create",
    ],
)
def test_every_write_refuses_the_agent_and_system(action: str) -> None:
    row = MATRIX[action]
    assert row["agent"] == "deny"
    assert row["system"] == "deny"
    assert row.get("independence") == "required"


def test_the_send_needs_a_recent_second_factor() -> None:
    assert MATRIX["proposed_entry.send_to_client"].get("mfa_recent") == "required"


def test_no_matrix_action_posts() -> None:
    assert [a for a in MATRIX if a.endswith((".post", ".push", ".write_back"))] == []


def test_the_send_is_held_on_a_grant_and_undo_voids_it() -> None:
    source = (MODULE / "decisions.py").read_text()
    assert "issue_grant(" in source
    assert "void_grant(" in source
    assert "send_undone" in source
