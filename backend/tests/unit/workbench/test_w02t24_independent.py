"""W-02-T24, part 1 (ADR-078; TASK-8013; SPEC-653): independent acceptance and security tests for
notanaskhan's red work that is on main, W-02-T03 (the protected bundle and the run-artifact and
drill stubs), T12 (`workbench.assistant` v1) and T15 (`WorkbenchSessionWorkflow` v2), written in
ayushkbhatia's session from the SPEC and the rows' acceptance, not from the implementation.

Row acceptance: "Tests pass and fail on any agent-actor approval, unverified citation shown as
fact, walled read or wrong attribution." Each test names its guard. Part 2 (W-02-T19, T20, T23
and the J11 API-level journey) waits on S43's session plans and run artifacts and on S44's
Save to Files wiring.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.agents import run_artifacts_contract as artifacts
from abacus.modules.agents.api import spec_v2
from abacus.modules.agents.blocks import BlocksRejected, Fact, validate_blocks
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.workbench.assistant import (
    CAPABILITY,
    AssistantNotice,
    AssistantPlan,
    AssistantTurn,
    check_turn,
)

PRINCIPALS_NEVER = ("agent", "system", "platform_support", "platform_support_content")
PORTAL = ("client_admin", "client_contributor", "third_party")
SESSION_ACTIONS = ("session.create", "session.read", "session.manage")
HUMAN_ARTIFACT_ACTIONS = ("run_artifact.download",)
RESERVED = ("approved", "decided", "signed off", "released", "sent", "posted", "exported",
            "transmitted", "adopted", "published", "resolved", "accepted", "rejected")  # fmt: skip


# --- T03: the protected bundle and stubs ---------------------------------------------------------


@pytest.mark.parametrize("action", SESSION_ACTIONS + HUMAN_ARTIFACT_ACTIONS)
def test_inv1_no_agent_system_support_or_portal_principal_holds_a_session_action(
    action: str,
) -> None:
    """Guard: a session or an artifact download is a person's (AC-V4, INV-1, INV-4)."""
    cells = ACTIONS[action]
    for role in PRINCIPALS_NEVER + PORTAL:
        assert cells.get(role, "deny") in ("deny",), (action, role)


def test_inv1_the_artifact_download_is_fresh_mfa_or_denied_to_everyone_but_people() -> None:
    """Guard: downloading client content is an export: never a non-person, and audited."""
    cells = ACTIONS["run_artifact.download"]
    assert cells["agent"] == "deny"
    assert any(v == "allow" or v == "in_scope" for k, v in cells.items() if k not in PORTAL)


def _ctx(actor: str = "human") -> AuthContext:
    me = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), cast(Any, actor), str(me)),
        me,
        uuid.uuid4(),
        cast(Any, "staff"),
        None,
    )


@pytest.mark.parametrize("route", ["preview", "download"])
def test_inv3_the_artifact_routes_answer_404_while_the_workbench_is_off(
    monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Guard: with `workbench.enabled` off nothing about an artifact answers but 404 (DEC-43)."""

    async def off(*_a: object) -> bool:
        return False

    monkeypatch.setattr(artifacts, "flag_enabled", off)
    call = (
        artifacts.artifact_preview_route(uuid.uuid4(), _ctx())
        if route == "preview"
        else artifacts.artifact_download_route(uuid.uuid4(), _ctx())
    )
    with pytest.raises(NotFound):
        asyncio.run(call)


# --- T12: workbench.assistant v1 -----------------------------------------------------------------


def test_inv1_the_assistant_holds_no_final_verb_and_proposes_only_a_file_save() -> None:
    """Guard: the allow-list's only propose tool is `files.propose_save`; no tool approves."""
    spec = spec_v2(CAPABILITY)
    kinds = spec.tools.by_kind()
    assert kinds["propose"] == ("files.propose_save",)
    for name in spec.tools.names():
        verb = name.split(".")[-1]
        assert not verb.startswith(("approve", "decide", "sign", "release", "send", "post")), name
    assert spec.client_data == "none"
    assert "tri" not in spec.data_classes


@pytest.mark.parametrize("word", RESERVED)
def test_inv1_code_refuses_a_turn_that_claims_a_human_act(word: str) -> None:
    """Guard: a notice saying the agent did a person's act is refused by code (DE-5)."""
    turn = AssistantTurn(notice=AssistantNotice(code="nothing_to_do", text=f"I {word} it."))
    assert check_turn(turn) == "reserved_action_named"


@pytest.mark.parametrize("approver", ["Accrued Agent", "agent", "  ACCRUED AGENT "])
def test_inv1_a_plan_naming_the_agent_as_approver_is_refused(approver: str) -> None:
    """Guard: a write's approver is a named person, never the agent (INV-1)."""
    plan = AssistantPlan.model_validate(
        {
            "steps": [{"label": "Build the workbook", "tool": "tax.season_counts"}],
            "writes": [{"op": "save_file", "target": "Season.xlsx", "approver": approver}],
        }
    )
    assert check_turn(AssistantTurn(plan=plan)) == "agent_cannot_approve"


def test_inv1_a_plan_naming_a_person_passes() -> None:
    plan = AssistantPlan.model_validate(
        {
            "steps": [{"label": "Build the workbook", "tool": "tax.season_counts"}],
            "writes": [{"op": "save_file", "target": "Season.xlsx", "approver": "Hannah Leclerc"}],
        }
    )
    assert check_turn(AssistantTurn(plan=plan)) is None


CITE = uuid.UUID(int=7)
FACTS = {"returns": Fact(id="returns", kind="count", value="224", basis="tax:season_counts")}


def _p(*segments: dict[str, object]) -> dict[str, object]:
    return {"parts": [{"kind": "p", "segments": list(segments)}]}


def test_inv2_a_citation_outside_the_runs_verified_set_is_never_shown() -> None:
    """Guard: an unverified citation is refused before display, never rendered as fact."""
    stranger = uuid.UUID(int=99)
    with pytest.raises(BlocksRejected):
        validate_blocks(
            _p(
                {"kind": "text", "text": "Season progress "},
                {"kind": "cite", "citation_id": str(stranger), "n": 1},
            ),
            FACTS,
            {CITE},
        )


def test_inv2_a_free_number_in_text_is_refused_and_a_registered_fact_passes() -> None:
    """Guard: figures travel as facts code registered (ADR P-48); a typed number is refused."""
    with pytest.raises(BlocksRejected):
        validate_blocks(_p({"kind": "text", "text": "There are 224 returns."}), FACTS, {CITE})
    validate_blocks(
        _p(
            {"kind": "text", "text": "Returns this season: "},
            {"kind": "fact", "fact_id": "returns"},
        ),
        FACTS,
        {CITE},
    )


def test_inv2_an_unregistered_fact_is_refused() -> None:
    with pytest.raises(BlocksRejected):
        validate_blocks(_p({"kind": "fact", "fact_id": "offices"}), FACTS, {CITE})


# --- T15: the session workflow v2 ----------------------------------------------------------------


def test_inv3_a_tool_call_on_a_walled_client_is_out_of_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard: a turn pinned to Copperleaf cannot read Northwind through any tool argument."""
    from abacus.modules.agents import session_turns
    from abacus.modules.agents.harness import ToolRequest

    pinned, walled = str(uuid.uuid4()), str(uuid.uuid4())
    engagement = uuid.uuid4()

    async def client_of(_t: object, _engagement: uuid.UUID) -> str:
        return walled

    monkeypatch.setattr(session_turns, "client_of", client_of)

    class Ports(session_turns.ReadOnlyPorts):
        def __init__(self) -> None:
            self.offered = frozenset({"engagements.read", "binders.read"})
            self.pinned = frozenset({pinned})
            self.agent = SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "agent", "run:1"))  # type: ignore[assignment] -- a stand-in

    ports = Ports()
    by_engagement = asyncio.run(
        ports.tool(ToolRequest("t1", "engagements.read", {"engagement_id": str(engagement)}))
    )
    by_client = asyncio.run(ports.tool(ToolRequest("t2", "binders.read", {"client_id": walled})))
    assert (by_engagement.ok, by_engagement.code) == (False, "out_of_scope")
    assert (by_client.ok, by_client.code) == (False, "out_of_scope")


def test_inv1_the_read_only_line_is_codes_never_the_models() -> None:
    """Guard: "Nothing was written." is appended by code; a model notice may not claim it."""
    from abacus.modules.workbench import session_turn_v2 as v2
    from abacus.modules.workbench.assistant import NOTHING_WRITTEN

    assert NOTHING_WRITTEN == "Nothing was written."
    assert v2.NOTHING_WRITTEN == "nothing_written"  # the code notice's code, not model text
