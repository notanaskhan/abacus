"""SPEC-644 AC-5 (A-07-T05; TASK-3250): the AUD-21 to AUD-25 contract stub. Every operation is
in the OpenAPI document answering 501, each route declares one matrix action, the five final
verbs deny the agent and the system, the new human-only approvals need fresh MFA, and the
contract doc lists report.release, archive.lock and archive_addition.approve as human-only with
fresh MFA (A-07 §4.3, §4.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.assurance.release_contract import router
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.routing import ACTION_KEY

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "docs" / "contracts" / "audit-completion.md"
FRESH_MFA = ROOT / "docs" / "architecture" / "fresh-mfa-actions.yaml"
FINAL_VERBS = (
    "rep_letter.approve",
    "rep_letter.send",
    "governance_comm.approve_send",
    "report.release",
    "archive.lock",
    "archive_addition.approve",
)
NEW_FRESH_MFA = ("rep_letter.approve", "governance_comm.approve_send", "archive_addition.approve")
CLIENTS = ("client_admin", "client_contributor", "third_party")


def _declared() -> dict[tuple[str, str], str]:
    return {
        (m.lower(), r.path): r.openapi_extra[ACTION_KEY]  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
        for r in router.routes
        for m in r.methods  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
    }


def test_ac5_every_operation_is_in_the_openapi_document_answering_501() -> None:
    paths = json.loads(document())["paths"]
    declared = _declared()
    assert len(declared) == 41
    for method, path in declared:
        assert "501" in paths[path][method]["responses"], (method, path)


def test_ac5_routes_cover_every_aud21_to_aud25_family() -> None:
    paths = {p for _, p in _declared()}
    for family in (
        "/representation-letter",
        "/governance-communications",
        "/governance-recipients",
        "/report",
        "/release",
        "/filings",
        "/archive",
        "/archive/manifest",
        "/archive/additions",
        "/archive/verify",
    ):
        assert f"/v1/audits/{{work_item_id}}{family}" in paths, family


@pytest.mark.parametrize("action", FINAL_VERBS)
def test_ac5_agent_system_and_clients_never_hold_a_final_verb(action: str) -> None:
    rule = RULES[action]
    for principal in ("agent", "system", *CLIENTS):
        assert rule.decisions.get(principal) == "deny", (action, principal)


def test_ac5_release_and_addition_approval_are_the_engagement_partners_alone() -> None:
    for action in ("report.release", "archive_addition.approve", "rep_letter.approve"):
        allowed = {r for r, d in RULES[action].decisions.items() if d == "allow"}
        assert allowed == {"engagement_partner"}, action


def test_ac5_new_human_only_approvals_need_a_fresh_second_factor() -> None:
    listed = {e["action"] for e in yaml.safe_load(FRESH_MFA.read_text())["actions"]}
    for action in NEW_FRESH_MFA:
        assert action in listed
        assert RULES[action].mfa_recent, action


def test_ac5_contract_doc_lists_the_three_human_only_fresh_mfa_actions() -> None:
    text = CONTRACT.read_text()
    for action in ("report.release", "archive.lock", "archive_addition.approve"):
        row = next(line for line in text.splitlines() if line.startswith(f"| `{action}`"))
        assert "| yes" in row, action
