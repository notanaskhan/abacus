"""I-02-T04 (TASK-7611; SPEC-654; DEC-4610): the Today brief's protected bundle. Every firm role
holds `briefing.read`, `briefing.rebuild` and `briefing.ask`; client roles, platform support, the
agent and the system hold none; `today_brief.enabled` defaults off within its lifetime; practice
may read review, agents and requests, and none of them may import practice."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from abacus.kernel import _flags
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus_tools.quality.banned_patterns import MODULE_DEPENDENCIES

ACTIONS_I02 = ("briefing.read", "briefing.rebuild", "briefing.ask")
FIRM = (
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
DENIED = (
    "client_admin",
    "client_contributor",
    "third_party",
    "platform_support",
    "platform_support_content",
    "agent",
    "system",
)
ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("action", ACTIONS_I02)
def test_every_firm_role_holds_its_own_brief(action: str) -> None:
    for role in FIRM:
        assert ACTIONS[action].get(role) == "allow", (action, role)


@pytest.mark.parametrize("action", ACTIONS_I02)
def test_an_agent_client_or_support_principal_holds_nothing(action: str) -> None:
    for role in DENIED:
        assert ACTIONS[action].get(role, "deny") == "deny", (action, role)


def test_the_flag_defaults_off_within_its_lifetime() -> None:
    flag = _flags.FLAGS["today_brief.enabled"]
    assert flag.default is False
    rows = yaml.safe_load((ROOT / "docs/architecture/feature-flags/practice.yaml").read_text())
    row = next(r for r in rows["flags"] if r["name"] == "today_brief.enabled")
    created = date.fromisoformat(str(row["created"]))
    expires = date.fromisoformat(str(row["expires"]))
    assert row["override"] == "DEC-137" and expires <= created + timedelta(days=180)


def test_practice_reads_review_agents_and_requests_and_nothing_reads_practice() -> None:
    assert {"review", "agents", "requests"} <= MODULE_DEPENDENCIES["practice"]
    for module, allowed in MODULE_DEPENDENCIES.items():
        if module != "practice":
            assert "practice" not in allowed, module
    pyproject = (ROOT / "backend/pyproject.toml").read_text()
    assert 'name = "Nothing practice reads imports practice (I-02)"' in pyproject
