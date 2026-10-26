# ac-test-author: ayushkbhatia
"""I-01-T03 (TASK-1304; ADR-078): the C13 gate half on the wire and in the matrix, written before
I-01-T04 and T07 open (`docs/contracts/home-and-gates.md` §2, §6; I-01 §4.2, §4.3).

Holds on main now: no agent, system or client principal reads gates (INV-1, INV-4). Strict xfails
citing TASK-1304 name what T04 and T07 add: the counts route and its shape, the list's filters
and presentation facts, snooze and reassign with their actions (human-only) and error codes, and
the two insert-only tables, the reassignments one human-only at the database. The DB-backed half
is `tests/integration/backfill/test_i01t03_c13_gate_half_ac.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review import registry

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS = ROOT / "backend" / "migrations" / "versions"
NEVER: Final = ("agent", "system", "client_admin", "client_contributor")
GATE_HALF = pytest.mark.xfail(
    strict=True, reason="TASK-1304: the C13 gate half lands in I-01-T04 and I-01-T07"
)


def _params(path: str, method: str = "get") -> set[str]:
    return {
        cast(str, p["name"]) for p in cast(list[Json], PATHS[path][method].get("parameters", []))
    }


def _schema_of(path: str, method: str = "get", status: str = "200") -> Json:
    content = cast(
        Json, cast(Json, cast(Json, PATHS[path][method]["responses"])[status])["content"]
    )
    ref = cast(str, cast(Json, cast(Json, content["application/json"])["schema"])["$ref"])
    return SCHEMAS[ref.rsplit("/", 1)[1]]


def test_inv1_inv4_no_agent_system_or_client_reads_gates() -> None:
    decisions = RULES["human_gate.read"].decisions
    for role in NEVER:
        assert decisions.get(role, "deny") == "deny", role


@GATE_HALF
def test_f1_the_counts_route_is_the_one_count_source() -> None:
    op = PATHS["/v1/human-gates/counts"]["get"]
    assert op["x-abacus-action"] == "human_gate.read"
    assert "office_id" in _params("/v1/human-gates/counts")
    props = cast(Json, _schema_of("/v1/human-gates/counts")["properties"])
    assert set(props) == {"total", "bands", "overdue", "snoozed"}


@GATE_HALF
def test_f6_the_list_filters_by_state_band_office_and_sorts_by_deadline() -> None:
    assert {"state", "band", "office_id", "sort"} <= _params("/v1/human-gates")


@GATE_HALF
@pytest.mark.parametrize("action", ["human_gate.snooze", "human_gate.reassign"])
def test_inv1_snooze_and_reassign_are_a_persons_acts(action: str) -> None:
    decisions = RULES[action].decisions
    for role in (*NEVER, "platform_support", "platform_support_content"):
        assert decisions.get(role, "deny") == "deny", role
    assert any(d == "allow" for d in decisions.values())


@GATE_HALF
@pytest.mark.parametrize(
    ("method", "path", "action"),
    [
        ("post", "/v1/human-gates/{gate_id}/snooze", "human_gate.snooze"),
        ("post", "/v1/human-gates/{gate_id}/unsnooze", "human_gate.snooze"),
        ("get", "/v1/human-gates/{gate_id}/reassign-candidates", "human_gate.reassign"),
        ("post", "/v1/human-gates/{gate_id}/reassign", "human_gate.reassign"),
    ],
)
def test_f8_snooze_and_reassign_routes_declare_their_action(
    method: str, path: str, action: str
) -> None:
    assert PATHS[path][method]["x-abacus-action"] == action


@GATE_HALF
def test_s6_the_gate_half_error_codes_are_catalogued() -> None:
    codes = cast(Json, yaml.safe_load((ROOT / "docs/architecture/error-codes.yaml").read_text()))
    catalogued = set(cast(Json, codes["codes"]))
    assert {
        "snooze_past_due",
        "snooze_in_past",
        "gate_not_open",
        "gate_overdue",
        "not_reassignable",
        "stale_version",
        "candidate_not_eligible",
    } <= catalogued


@GATE_HALF
def test_s42_snoozes_and_reassignments_are_insert_only_and_reassignment_is_human_only() -> None:
    assert {"human_gate_snoozes", "human_gate_reassignments"} <= registry.TABLES
    assert {"human_gate_snoozes", "human_gate_reassignments"} <= registry.INSERT_ONLY
    text = "\n".join(p.read_text() for p in MIGRATIONS.glob("*.py"))
    assert "CREATE TABLE human_gate_reassignments" in text
    block = text.split("CREATE TABLE human_gate_reassignments", 1)[1].split(")\n", 1)[0]
    assert "actor_kind" in block and "'human'" in block


@GATE_HALF
def test_s42_gates_carry_the_home_columns() -> None:
    props = cast(Json, SCHEMAS["HumanGateOut"]["properties"])
    assert {"subkind", "band", "blocked", "bulk_eligible", "proposed_by", "version"} <= set(props)
