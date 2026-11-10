# ac-test-author: notanaskhan
"""R-02-T20 (TASK-6619; ADR-078 independent): the AC suite for R-02's amber migration and services
(T05, T09, T11, T12, T15, T16), written from the R-02 epic (§3, AC-4, §5 tables, §6 routes) and the
rows, not from their diffs.

Row acceptance: "Suites headed ac-test-author notanaskhan pass and fail if any portal DTO carries a
materiality, threshold, policy or agent field." Covered here:

- the pack-rule DTO scan over every `/v1/portal` request and response schema in the OpenAPI, with
  a planted field proving the scan bites;
- INV-4's scope matrix: a grant covers its own work item, engagement or client and nothing else;
- I-AGENT-NEVER and MFA on every client decision action in the portal matrix;
- the decider rule (owner grant or approver of record; SKE designee on an attest package);
- `Idempotency-Key` on every portal decision route;
- the seen-hash and latest-draft rules (409 `item_changed`);
- 22,250 from the frozen snapshot, and no amount in the acknowledge body.

The insert-only and human-only migration properties (T05) run against Postgres in
`tests/integration/test_r02t05_deliverables_governance_migration.py`; the governance room's
per-member privacy (T12, T16) in the assurance unit suites. This file adds no database case.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.modules.engagements.client_approvals import (
    DECIDER_RULES,
    ApprovalScope,
    scope_covered,
)
from abacus.modules.identity.api import ScopeFacts

REPO = Path(__file__).resolve().parents[4]
MATRIX = REPO / "docs" / "architecture" / "permission-matrix" / "portal.yaml"
# The pack rule (R-02 §3: the client sees amounts, never the firm's judgement or its tooling).
BANNED = re.compile(r"materiality|threshold|policy|agent", re.IGNORECASE)
DECISIONS = (
    "statement.client_approve",
    "tcwg.acknowledge",
    "proposed_entry.client_decide",
    "uncorrected_misstatements.acknowledge",
    "close_package.client_decide",
)
FIRM_ROLES = (
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "firm_partner",
    "firm_manager",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
)

# --- the pack-rule DTO scan ----------------------------------------------------------------------


@cache
def _openapi() -> dict[str, Any]:
    from abacus.api import create_app

    spec: dict[str, Any] = create_app().openapi()
    return spec


def _resolve(spec: Mapping[str, Any], node: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str):
        found: Any = spec
        for part in ref.removeprefix("#/").split("/"):
            found = found[part]
        return cast(Mapping[str, Any], found)
    return node


def _fields(spec: Mapping[str, Any], node: object, seen: set[str]) -> Iterator[tuple[str, str]]:
    """(schema, property) for every property reachable from `node`, through refs and unions."""
    if not isinstance(node, Mapping):
        return
    node = cast(Mapping[str, Any], node)
    ref = node.get("$ref")
    if isinstance(ref, str):
        if ref in seen:
            return
        seen.add(ref)
    schema = _resolve(spec, node)
    title = str(schema.get("title", ref or "?"))
    for name, prop in cast(Mapping[str, Any], schema.get("properties", {})).items():
        yield title, name
        yield from _fields(spec, prop, seen)
    for key in ("items", "additionalProperties"):
        yield from _fields(spec, schema.get(key), seen)
    for key in ("anyOf", "oneOf", "allOf"):
        for part in cast(list[object], schema.get(key, [])):
            yield from _fields(spec, part, seen)


def _bodies(op: Mapping[str, Any]) -> Iterator[object]:
    body: dict[str, Any] = op.get("requestBody") or {}
    contents: dict[str, Any] = body.get("content", {})
    for content in contents.values():
        yield content.get("schema")
    for response in op.get("responses", {}).values():
        for content in response.get("content", {}).values():
            yield content.get("schema")


def portal_fields(spec: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """(path, schema, property) for every DTO the portal API reads or answers."""
    out: list[tuple[str, str, str]] = []
    for path, ops in cast(Mapping[str, Mapping[str, Any]], spec["paths"]).items():
        if not path.startswith("/v1/portal"):
            continue
        for op in ops.values():
            seen: set[str] = set()
            for body in _bodies(op):
                out += [(path, s, p) for s, p in _fields(spec, body, seen)]
    return out


def banned_fields(spec: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    return [f for f in portal_fields(spec) if BANNED.search(f[2])]


def test_ac_the_scan_reaches_the_r02_routes() -> None:
    """The scan is not vacuous: approvals, deliverables and the governance room are all read."""
    paths = {p for p, _, _ in portal_fields(_openapi())}
    for route in (
        "/v1/portal/approvals",
        "/v1/portal/approvals/{kind}/{item_id}",
        "/v1/portal/deliverables",
        "/v1/portal/governance/rooms",
        "/v1/portal/governance/communications/{communication_id}",
    ):
        assert route in paths, route


def test_ac_no_portal_dto_carries_a_materiality_threshold_policy_or_agent_field() -> None:
    assert banned_fields(_openapi()) == []


def test_ac_the_scan_fails_on_a_planted_field() -> None:
    spec: dict[str, Any] = {
        "paths": {
            "/v1/portal/approvals": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Planted"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Planted": {
                    "title": "Planted",
                    "properties": {
                        "rows": {"type": "array", "items": {"$ref": "#/components/schemas/Row"}}
                    },
                },
                "Row": {"title": "Row", "properties": {"performance_materiality": {}}},
            }
        },
    }
    assert banned_fields(spec) == [("/v1/portal/approvals", "Row", "performance_materiality")]


# --- the matrix: I-AGENT-NEVER, MFA, no firm cell ------------------------------------------------


def _portal_actions() -> dict[str, dict[str, object]]:
    data = cast(dict[str, object], yaml.safe_load(MATRIX.read_text()))
    actions: dict[str, dict[str, object]] = {}
    for section in data.values():
        if isinstance(section, dict):
            for name, cells in cast(dict[str, object], section).items():
                if isinstance(cells, dict):
                    actions[name] = cast(dict[str, object], cells)
    return actions


@pytest.mark.parametrize("action", DECISIONS)
def test_ac_every_client_decision_is_human_scoped_and_mfa_fresh(action: str) -> None:
    cells = _portal_actions()[action]
    assert cells["agent"] == "deny"
    assert cells["system"] == "deny"
    assert cells["mfa_recent"] == "required"
    assert cells["scope_only"] == "required"


@pytest.mark.parametrize(
    "action",
    [
        *DECISIONS,
        "client_approval.read",
        "client_approval.ask",
        "deliverable.read",
        "deliverable.download",
        "tcwg.read",
        "tcwg.ask",
    ],
)
def test_ac_a_firm_person_holds_no_cell_on_the_portal_half(action: str) -> None:
    """Firms act through A-06's record mode, never in the portal (R-02 §3)."""
    cells = _portal_actions()[action]
    assert not [r for r in FIRM_ROLES if cells.get(r) == "allow"]


# --- INV-4: a grant covers its own scope only ----------------------------------------------------


CLIENT, OTHER_CLIENT = uuid.uuid4(), uuid.uuid4()
ENGAGEMENT, OTHER_ENGAGEMENT = uuid.uuid4(), uuid.uuid4()
WORK_ITEM, OTHER_WORK_ITEM = uuid.uuid4(), uuid.uuid4()
AT = ApprovalScope(CLIENT, ENGAGEMENT, WORK_ITEM)


@pytest.mark.parametrize(
    ("grant", "covered"),
    [
        (ScopeFacts(CLIENT), True),
        (ScopeFacts(CLIENT, ENGAGEMENT), True),
        (ScopeFacts(CLIENT, ENGAGEMENT, WORK_ITEM), True),
        (ScopeFacts(OTHER_CLIENT), False),
        (ScopeFacts(CLIENT, OTHER_ENGAGEMENT), False),
        (ScopeFacts(CLIENT, ENGAGEMENT, OTHER_WORK_ITEM), False),
        (ScopeFacts(OTHER_CLIENT, ENGAGEMENT, WORK_ITEM), False),
    ],
)
def test_ac_inv4_scope_matrix(grant: ScopeFacts, covered: bool) -> None:
    assert scope_covered(grant, AT) is covered


def test_ac_a_work_item_grant_never_covers_its_engagements_other_items() -> None:
    sibling = ApprovalScope(CLIENT, ENGAGEMENT, OTHER_WORK_ITEM)
    assert not scope_covered(ScopeFacts(CLIENT, ENGAGEMENT, WORK_ITEM), sibling)


# --- the decider rule ----------------------------------------------------------------------------


def test_ac_the_decider_is_an_owner_or_the_approver_of_record() -> None:
    for kind in ("proposed_entry", "uncorrected_misstatements", "fs_draft"):
        rule = DECIDER_RULES[kind]
        assert rule.any_of == {"owner", "approver_of_record"}, kind
        assert not rule.attest_also, kind


def test_ac_an_attest_package_also_needs_the_ske_designee() -> None:
    rule = DECIDER_RULES["fs_package"]
    assert rule.any_of == {"owner", "approver_of_record"}
    assert rule.attest_also == {"ske_designee"}


# --- Idempotency-Key on every decision route -----------------------------------------------------


DECISION_ROUTES = (
    "/v1/portal/approvals/proposed-entries/{entry_id}/decide",
    "/v1/portal/approvals/uncorrected-misstatements/{item_id}/acknowledge",
    "/v1/portal/approvals/packages/{package_id}/decide",
    "/v1/portal/deliverables/{deliverable_id}/versions/{version_no}/approve",
    "/v1/portal/governance/communications/{communication_id}/acknowledge",
)


@pytest.mark.parametrize("path", DECISION_ROUTES)
def test_ac_every_decision_route_takes_an_idempotency_key(path: str) -> None:
    op = _openapi()["paths"][path]["post"]
    params = {p["name"]: p for p in op.get("parameters", [])}
    assert "Idempotency-Key" in params, path


@pytest.mark.parametrize("path", DECISION_ROUTES[:4])
def test_ac4_every_approval_decision_binds_what_was_seen(path: str) -> None:
    spec = _openapi()
    op = spec["paths"][path]["post"]
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    assert "seen_hash" in {p for _, p in _fields(spec, schema, set())}, path


def test_ac_the_acknowledge_body_carries_no_amount() -> None:
    """The net effect is the snapshot's; the client never sends a figure (no client arithmetic)."""
    spec = _openapi()
    path = "/v1/portal/approvals/uncorrected-misstatements/{item_id}/acknowledge"
    schema = spec["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"]
    names = {p for _, p in _fields(spec, schema, set())}
    assert not [n for n in names if re.search(r"amount|net|effect|total|value", n)], names


# --- seen-hash, latest draft, 22,250 -------------------------------------------------------------


def test_ac_22250_is_the_snapshots_frozen_total() -> None:
    from abacus.modules.assurance.uncorrected_ack import net_effect

    # Northwind PY2025, R-02 §2: 35,300.00 overstatement less 13,050.00 understatement.
    frozen = {"rollover": "34150", "iron_curtain": "22250.00", "aggregate": "34150"}
    assert net_effect(frozen) == Decimal("22250.00")


def test_ac4_the_seen_hash_moves_with_whatever_the_client_read() -> None:
    from abacus.modules.assurance.uncorrected_ack import seen_hash as sum_hash
    from abacus.modules.reporting.client_approvals import seen_hash as fs_hash

    snapshot, version = uuid.uuid4(), uuid.uuid4()
    base = sum_hash(snapshot, "a" * 64, Decimal("22250.00"))
    assert base == sum_hash(snapshot, "a" * 64, Decimal("22250.00"))
    assert base != sum_hash(snapshot, "a" * 64, Decimal("22250.01"))
    assert base != sum_hash(snapshot, "b" * 64, Decimal("22250.00"))
    assert base != sum_hash(uuid.uuid4(), "a" * 64, Decimal("22250.00"))
    assert fs_hash(version, 3, "c" * 64) != fs_hash(version, 4, "c" * 64)
    assert fs_hash(version, 4, "c" * 64) != fs_hash(version, 4, "d" * 64)


@dataclass
class _Result:
    row: Mapping[str, object] | None

    def mappings(self) -> _Result:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self.row


@dataclass
class _Session:
    """Answers the provider's three reads: the version, already approved, a newer version."""

    approved: bool = False
    newer: bool = False
    writes: list[str] = field(default_factory=list[str])

    async def execute(self, statement: object, params: object = None) -> _Result:
        sql = str(statement)
        if sql.lstrip().upper().startswith("INSERT") or "UPDATE " in sql.upper():
            self.writes.append(sql)
            return _Result(None)
        if "FOR UPDATE" in sql:
            return _Result(
                {
                    "id": VERSION,
                    "tenant_id": uuid.uuid4(),
                    "engagement_id": ENGAGEMENT,
                    "work_item_id": WORK_ITEM,
                    "statement_document_id": uuid.uuid4(),
                }
            )
        if "approved_by_management" in sql:
            return _Result({"x": 1} if self.approved else None)
        if "version_no >" in sql:
            return _Result({"x": 1} if self.newer else None)
        return _Result(None)


@dataclass
class _Tx:
    session: _Session


VERSION = uuid.uuid4()


def _decision(kind: str = "approve") -> object:
    from abacus.modules.engagements.api import ClientDecision

    return ClientDecision(decision=kind, seen_hash="x" * 64)  # type: ignore[arg-type]


def _context() -> object:
    from abacus.modules.engagements.api import ClientDecisionContext

    fields = ClientDecisionContext.__dataclass_fields__
    return ClientDecisionContext(**{n: uuid.uuid4() for n in fields})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_ac_an_older_draft_answers_item_changed_and_writes_nothing() -> None:
    from abacus.modules.engagements.api import ItemChanged
    from abacus.modules.reporting.client_approvals import FsDraftApprovals

    session = _Session(newer=True)
    with pytest.raises(ItemChanged):
        await FsDraftApprovals().decide(_Tx(session), VERSION, _decision(), _context())  # type: ignore[arg-type]
    assert session.writes == []


@pytest.mark.asyncio
async def test_ac_an_approved_draft_cannot_be_approved_again() -> None:
    from abacus.modules.engagements.api import ItemChanged
    from abacus.modules.reporting.client_approvals import FsDraftApprovals

    session = _Session(approved=True)
    with pytest.raises(ItemChanged):
        await FsDraftApprovals().decide(_Tx(session), VERSION, _decision(), _context())  # type: ignore[arg-type]
    assert session.writes == []


@pytest.mark.asyncio
async def test_ac_a_draft_is_only_ever_approved() -> None:
    from abacus.modules.engagements.api import ItemChanged
    from abacus.modules.reporting.client_approvals import FsDraftApprovals

    session = _Session()
    with pytest.raises(ItemChanged):
        await FsDraftApprovals().decide(_Tx(session), VERSION, _decision("decline"), _context())  # type: ignore[arg-type]
    assert session.writes == []
