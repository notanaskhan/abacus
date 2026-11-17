# ac-test-author: ayushkbhatia
"""G-04-T16 (TASK-8540; ADR-078): AC suite 2 for N's console and support work (PLT-01, SHL-05).

Written from G-04 §4 and the console contract's acceptance criteria, not from the services' own
tests: staff-only routes (every platform action denies every firm and portal principal, the agent
and the system), metadata-only payloads (no console response carries a confidential or
restricted field, nor a client's name), the dual audit keeps only a reason fingerprint, region
refusal and two-person publish are typed conflicts, and no agent tool reads support messages.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from abacus.kernel.classification import level_of
from abacus.modules.agents.tools.catalogue import DECLARED
from abacus.modules.platform import console_contract
from abacus.modules.platform.console import reason_fingerprint
from abacus.modules.platform.console_contract import ApproverIsDrafter, RegionNotLive

MATRIX = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "permission-matrix"
FIRM_AND_PORTAL = (
    "firm_admin", "security_admin", "practice_leader", "client_admin", "client_contributor",
    "third_party", "link_principal", "agent", "system",
)  # fmt: skip


def _platform_actions() -> dict[str, dict[str, object]]:
    doc = yaml.safe_load((MATRIX / "platform.yaml").read_text(encoding="utf-8"))
    return {a: row for a, row in doc["actions"].items() if a.startswith("platform_")}


# ---- staff-only routes -----------------------------------------------------------------------


@pytest.mark.parametrize("action", sorted(_platform_actions()))
def test_a_firm_token_never_reaches_a_platform_action(action: str) -> None:
    row = _platform_actions()[action]
    for principal in FIRM_AND_PORTAL:
        assert row.get(principal) == "deny", (action, principal)
    assert any(row.get(r) == "allow" for r in ("platform_admin", "platform_support_desk"))


def test_the_console_router_serves_only_platform_actions() -> None:
    routes = console_contract.router.routes
    assert routes, "the console router has routes"
    for route in routes:
        path = getattr(route, "path", "")
        assert path.startswith("/v1/platform"), path


def test_only_the_platform_admin_publishes_or_reads_content() -> None:
    actions = _platform_actions()
    for action in ("platform_content.publish", "platform_content.read"):
        assert actions[action].get("platform_admin") == "allow"
        assert actions[action].get("platform_support_desk") in (None, "deny"), action


# ---- metadata-only payloads ------------------------------------------------------------------


# The support queue's chat (Queue*) carries the firm's own words to Accrued support, confidential
# by design and isolated per tenant (SHL-05); every other console payload is tenant metadata only.
CHAT_MODELS = ("Queue",)


def _out_models() -> list[type[BaseModel]]:
    return [
        obj
        for name, obj in inspect.getmembers(console_contract, inspect.isclass)
        if issubclass(obj, BaseModel)
        and name.endswith("Out")
        and not name.startswith(CHAT_MODELS)
        and obj.__module__ == console_contract.__name__
    ]


@pytest.mark.parametrize("model", _out_models(), ids=lambda m: m.__name__)
def test_no_console_payload_carries_confidential_or_restricted_data(
    model: type[BaseModel],
) -> None:
    for name, field in model.model_fields.items():
        level = level_of(field)
        assert (
            level is None
            or str(level) in ("internal", "public")
            or getattr(level, "value", level) in ("internal", "public")
        ), (model.__name__, name, level)


@pytest.mark.parametrize("model", _out_models(), ids=lambda m: m.__name__)
def test_no_console_payload_names_a_client(model: type[BaseModel]) -> None:
    for name in model.model_fields:
        assert not name.startswith(("client_name", "client_email", "contact_")), (
            model.__name__,
            name,
        )


# ---- dual audit: the platform trail keeps a fingerprint, never the reason --------------------


def test_the_platform_audit_keeps_a_fingerprint_of_the_reason() -> None:
    reason = "Seats for the October season (order form OF-2026-114)"
    fp = reason_fingerprint(reason)
    assert len(fp) == 16 and reason not in fp
    assert fp == reason_fingerprint(reason)
    assert fp != reason_fingerprint(reason + " ")


# ---- refusals are typed conflicts -------------------------------------------------------------


def test_region_refusal_and_two_person_publish_have_their_codes() -> None:
    assert RegionNotLive.code == "region_not_live"
    assert ApproverIsDrafter.code == "approver_is_drafter"


# ---- no agent tool reads support messages ----------------------------------------------------


def test_no_agent_tool_reads_support_messages_or_the_console() -> None:
    for tool in DECLARED:
        name = tool.name.lower()
        assert "support" not in name and "platform" not in name and "console" not in name, (
            tool.name
        )
        assert not str(tool.action).startswith("platform_"), tool.name
