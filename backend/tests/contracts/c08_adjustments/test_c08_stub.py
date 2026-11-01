# ac-test-author: ayushkbhatia
"""A-06-T06 (TASK-2919; SPEC-642 AC-3; DEC-1965): AY's consumer tests for N's C8 stub.

Every C8 operation AUD-16 b, b2, c, d and EBP-06 call exists with its one action, documents 404
and (writes) 501 and takes an Idempotency-Key; every model field is classified; the matrix gives
client principals nothing and the agent no write; the flag defaults off; no route can post.
"""

from __future__ import annotations

import json
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _flags
from abacus.kernel.classification import unclassified_fields
from abacus.modules.adjustments import contract as c8
from abacus.modules.identity.authz import _matrix

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
W = "/v1/work-items/{work_item_id}"
ROUTES: dict[tuple[str, str], str] = {
    ("get", f"{W}/proposed-entries"): "proposed_entry.read",
    ("post", f"{W}/proposed-entries"): "proposed_entry.create",
    ("post", f"{W}/proposed-entries:approve-and-send"): "proposed_entry.send_to_client",
    ("post", "/v1/proposed-entries/{entry_id}/reject"): "proposed_entry.reject",
    ("post", "/v1/proposed-entries/{entry_id}/client-decision:record"): (
        "proposed_entry.record_client_decision"
    ),
    ("post", "/v1/approval-batches"): "approval_batch.create",
    ("get", f"{W}/adjusted-tb"): "adjusted_tb.read",
}
READS = {"proposed_entry.read", "adjusted_tb.read"}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_documents_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert {"404", "501"} <= responses


def test_every_write_takes_an_idempotency_key() -> None:
    for (method, path), _ in ROUTES.items():
        if method == "get":
            continue
        names = {p["name"] for p in cast(list[Json], PATHS[path][method].get("parameters", []))}
        assert "Idempotency-Key" in names, (method, path)


def test_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(c8).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == c8.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


@pytest.mark.parametrize("action", sorted(set(ROUTES.values())))
def test_clients_hold_nothing_and_the_agent_never_writes(action: str) -> None:
    cells = _matrix.ACTIONS[action]
    for role in CLIENT_ROLES:
        assert cells.get(role, "deny") == "deny", (action, role)
    assert cells.get("system", "deny") == "deny"
    if action not in READS:
        assert cells.get("agent", "deny") == "deny", action


def test_send_needs_a_fresh_second_factor() -> None:
    assert _matrix.ACTIONS["proposed_entry.send_to_client"].get("mfa_recent") == "required"


def test_the_flag_defaults_off() -> None:
    flag = _flags.FLAGS["adjustments.entries"]
    assert flag.kind == "boolean" and str(flag.default).lower() == "false"


def test_no_route_can_post_book_or_write_to_a_client_system() -> None:
    words = ("post-entry", "/post", "book", "posting", "push")
    for path in PATHS:
        if "proposed-entries" in path or "adjusted-tb" in path or "approval-batches" in path:
            assert not any(w in path for w in words), path
    # The posting states are not in the contract's status words (pe_posting_dormant).
    assert not {"posted", "failed_post", "reversed"} & set(c8.EntryStatus.__args__)  # type: ignore[attr-defined]
