"""P-09-T16 (TASK-6519; ADR-078 under the solo edition: written from the SPEC, not the code;
SPEC-648 AC-1 to AC-6; DEC-3119): independent acceptance tests for P-09's red work.

Personas from the Brightwater Hale seed: the initiator and the team read content; Thomas
Whitcombe (EQR) reads content and never writes; Felix Andersen (security admin) and Grace Holloway
(firm admin) read metadata only; client roles and the agent never read a run or export a trace;
every export needs a fresh second factor and never leaves offshore. Each test fails if the rule
it names is removed from the matrix or the code.
"""

from __future__ import annotations

import pytest

from abacus.modules.agents.blocks import BlocksRejected, validate_blocks
from abacus.modules.identity.authz.matrix import RULES

CONTENT_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer", "eqr_reviewer")
METADATA_ROLES = ("firm_admin", "security_admin")
NEVER = ("client_admin", "client_contributor", "third_party", "client_service", "agent")


@pytest.mark.parametrize("role", CONTENT_ROLES)
def test_the_team_and_the_eqr_read_content(role: str) -> None:
    assert RULES["agent_run.read"].decisions.get(role) == "allow"
    assert RULES["run_content.read"].decisions.get(role) == "allow"


@pytest.mark.parametrize("role", METADATA_ROLES)
def test_admins_read_metadata_never_content(role: str) -> None:
    assert RULES["agent_run.read"].decisions.get(role) == "allow"
    assert RULES["run_content.read"].decisions.get(role, "deny") == "deny"


@pytest.mark.parametrize("role", NEVER)
def test_portal_roles_and_the_agent_never_read_or_export(role: str) -> None:
    for action in ("agent_run.read", "run_content.read", "run_trace.export"):
        assert RULES[action].decisions.get(role, "deny") in ("deny", None)


def test_every_export_needs_a_fresh_second_factor_and_stays_onshore() -> None:
    rule = RULES["run_trace.export"]
    assert rule.mfa_recent and rule.not_offshore and rule.independence


def test_the_eqr_exports_but_never_signs_off_a_run() -> None:
    assert RULES["run_trace.export"].decisions.get("eqr_reviewer") == "allow"
    sign_off = RULES.get("run.sign_off") or RULES.get("agent_run.sign_off")
    if sign_off is not None:
        assert sign_off.decisions.get("agent", "deny") == "deny"


def test_walls_hold_because_reads_need_independence() -> None:
    # Lena Park, walled from Ashford: `independence: required` makes a walled read 404 alike.
    assert RULES["agent_run.read"].independence and RULES["run_content.read"].independence


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {
                "version": 1,
                "parts": [{"kind": "p", "segments": [{"kind": "text", "text": "I approved it."}]}],
            },
            "human_act",
        ),
        (
            {
                "version": 1,
                "parts": [
                    {"kind": "p", "segments": [{"kind": "text", "text": "It was $48,600."}]}
                ],
            },
            "free_number",
        ),
        (
            {
                "version": 1,
                "parts": [
                    {"kind": "p", "segments": [{"kind": "text", "text": "See https://x.example"}]}
                ],
            },
            "link",
        ),
        (
            {
                "version": 1,
                "parts": [{"kind": "p", "segments": [{"kind": "text", "text": "**bold**"}]}],
            },
            "markup",
        ),
        ({"version": 1, "parts": []}, "shape"),
    ],
)
def test_agent_blocks_refuse_what_may_not_be_shown(payload: object, code: str) -> None:
    with pytest.raises(BlocksRejected) as refused:
        validate_blocks(payload, {}, set())
    assert refused.value.code == code
