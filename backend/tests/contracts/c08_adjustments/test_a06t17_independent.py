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


# A-09-T20 (DEC-5313; migration 0896): an approved elimination posts to Accrued's own
# consolidation layer, never a client ledger. That file alone may name `posted`, never
# `failed_post` or `reversed`, and the database admits it only for that kind and target (below).
CONSOLIDATION_LAYER = {"eliminations.py": ("posted",)}
# C-02-T18 (ADR-344 W1; DEC-5704; S51 rows end pass DEC-5734): the one client-ledger write path,
# dark behind write-capabilities.yaml `enabled: false`, marks an entry posted or failed after the
# provider answers; `reversed` stays banned everywhere, and no route names a post (test above).
W1_POSTING = {"posting.py": ("posted", "failed_post")}
MIGRATION_0896 = (BACKEND / "migrations/versions/0896_adjustments_eliminations.py").read_text()


@pytest.mark.parametrize("path", sorted(MODULE.glob("*.py")), ids=lambda p: p.name)
def test_no_service_sets_a_posting_status(path: Path) -> None:
    """No string the module writes is a posting status, alone or in SQL ("status = 'posted'")."""
    allowed = CONSOLIDATION_LAYER.get(path.name, ()) + W1_POSTING.get(path.name, ())
    for text in _string_constants(path.read_text()):
        lowered = text.lower()
        for status in POSTING:
            if status in allowed:
                continue
            assert f"'{status}'" not in lowered or "check" in lowered, (path.name, status)
            assert lowered.strip() != status, (path.name, status)


def test_only_an_elimination_on_the_consolidation_layer_may_be_posted() -> None:
    """The one exception is held by the database: 0896's CHECK keeps every other entry dormant."""
    assert "CHECK (status NOT IN ('posted', 'failed_post', 'reversed') " in MIGRATION_0896
    assert "OR (kind = 'elimination' AND posting_target IS NOT NULL))" in MIGRATION_0896
    source = (MODULE / "eliminations.py").read_text()
    assert "'failed_post'" not in source and "'reversed'" not in source


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
    """ADR-344 (P-16; C-02-T08, DEC-5507) opens exactly one posting action, `posting_batch.post`:
    a person's, with a fresh second factor, under the W1 registry entry, which stays off, refuses
    attest clients and never admits the policy principal. Any other posting action still fails."""
    from abacus.modules.integrations import _capabilities as caps

    assert [a for a in MATRIX if a.endswith((".post", ".push", ".write_back"))] == [
        "posting_batch.post"
    ]
    row = MATRIX["posting_batch.post"]
    assert row["agent"] == "deny" and row["system"] == "deny"
    assert row.get("mfa_recent") == "required" and row.get("independence") == "required"
    w1 = next(w for w in caps.WRITES if w["key"] == "ledger_post_journal_entries")
    assert w1["enabled"] is False
    assert w1["attest_clients"] == "refused" and w1["policy_principal"] == "never"


def test_the_send_is_held_on_a_grant_and_undo_voids_it() -> None:
    source = (MODULE / "decisions.py").read_text()
    assert "issue_grant(" in source
    assert "void_grant(" in source
    assert "send_undone" in source
