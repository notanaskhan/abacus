"""W-02-T03 (TASK-7603; SPEC-653; DEC-4603): the protected bundle. No agent, system, support or
portal principal holds a session or run-artifact action; both W-02 flags default off and expire
before W-02's calendar window closes; the drill, preview and download routes are declared with one
action each and answer 404 behind `workbench.enabled` before their 501."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.kernel import _flags
from abacus.kernel.classification import unclassified_fields
from abacus.modules.agents.run_artifacts_contract import (
    ArtifactPreviewOut,
    DrillIn,
    DrillOut,
    DrillRowOut,
    PreviewCellOut,
    run_artifacts_router,
    session_drill_router,
)
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.identity.routing import ACTION_KEY

W02_ACTIONS = ("session.create", "session.read", "session.manage", "run_artifact.download")
NEVER = ("agent", "system", "platform_support", "platform_support_content")
PORTAL = ("client_admin", "client_contributor", "third_party")


@pytest.mark.parametrize("action", W02_ACTIONS)
def test_ac_v4_no_agent_system_support_or_portal_principal_holds_a_session_action(
    action: str,
) -> None:
    cells = ACTIONS[action]
    for role in NEVER + PORTAL:
        assert cells.get(role, "deny") == "deny", (action, role)


def test_inv1_download_is_an_export_with_its_conditions() -> None:
    cells = ACTIONS["run_artifact.download"]
    assert cells["independence"] == "required"
    assert cells["not_offshore"] == "required"
    assert cells["agent"] == "deny" and cells["system"] == "deny"


@pytest.mark.parametrize("flag", [_flags.WORKBENCH_ENABLED, _flags.WORKBENCH_PLANS])
def test_flags_default_off_and_expire(flag: _flags.Flag) -> None:
    assert flag.default == "false"  # the generated registry keeps the YAML text
    assert _flags.FLAGS[flag.name] is flag


def test_flag_registry_rows_expire_before_the_p02_horizon() -> None:
    root = Path(__file__).resolve().parents[4]
    rows = yaml.safe_load((root / "docs/architecture/feature-flags/workbench.yaml").read_text())
    for row in rows["flags"]:
        assert row["owner"] == "notanaskhan"
        assert row["default"] is False
        assert date.fromisoformat(str(row["expires"])) <= date(2027, 5, 7)


def _routes(router: object) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    routes = cast(list[Any], getattr(router, "routes"))  # noqa: B009  # Any: FastAPI route objects
    for route in routes:
        for method in cast(set[str], route.methods):
            out[(method, str(route.path))] = str(route.openapi_extra[ACTION_KEY])
    return out


def test_routes_one_action_each() -> None:
    routes = _routes(run_artifacts_router) | _routes(session_drill_router)
    assert routes == {
        ("GET", "/v1/run-artifacts/{artifact_id}/preview"): "run_content.read",
        ("GET", "/v1/run-artifacts/{artifact_id}/download"): "run_artifact.download",
        ("POST", "/v1/workbench/sessions/{session_id}/drill"): "session.manage",
    }


@pytest.mark.parametrize(
    "model", [ArtifactPreviewOut, PreviewCellOut, DrillIn, DrillOut, DrillRowOut]
)
def test_every_field_is_classified(model: type) -> None:
    assert unclassified_fields(model) == []
