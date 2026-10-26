"""P-08-T28 (TASK-1359; DEC-456): the repository side of the portal rollout.

- Both rollout flags are on for every synthetic firm the seeds build (the Brightwater Hale
  `portal` slice, which `make seed-staging` loads, and the load profiles).
- C5 v1.1's portal half is frozen: a snapshot exists and today's schemas break nothing in it.
- The lockout and pause runbooks exist, are indexed, are linked from RB-22, and name controls and
  routes that exist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from abacus_tools import contracts
from abacus_tools.synthetic import fleet
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import FLAGS, SLICE
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

REPO = Path(__file__).resolve().parents[4]
RUNBOOKS = REPO / "docs" / "runbooks"
PORTAL_FLAGS = {"portal.sign_in_v2", "portal.home_v2"}


def test_ac_the_portal_slice_turns_both_rollout_flags_on() -> None:
    assert set(FLAGS) == PORTAL_FLAGS
    events = build("E0", (), ("audit_core", *loader.expand_slices((SLICE,)))).events
    flags = {str(e.data["flag"]) for e in events if e.kind == "platform.flag_set"}
    assert flags >= PORTAL_FLAGS
    assert all(loader.HANDLERS.get(e.kind) for e in events if e.kind == "platform.flag_set")


def test_ac_every_load_profile_firm_has_them_on_too() -> None:
    assert set(fleet.FLEET_FLAGS) >= PORTAL_FLAGS


def test_ac_the_flags_are_not_retired_before_the_canary_walk() -> None:
    """DEC-456: retirement is one later PR, after the production canary signs in with a second
    factor; until then both flags keep their registry rows and an expiry."""
    for module, name in (("identity", "portal.sign_in_v2"), ("portal", "portal.home_v2")):
        text = (REPO / "docs" / "architecture" / "feature-flags" / f"{module}.yaml").read_text()
        block = text.split(f"- name: {name}", 1)[1].split("\n  - name:", 1)[0]
        assert re.search(r"expires: 20\d\d-\d\d-\d\d", block)


def test_ac_c5_portal_is_frozen_at_v1_1_and_today_breaks_nothing() -> None:
    frozen = contracts.snapshots()["c5_portal"]
    assert [p.stem for p in frozen] == ["v1.1"]
    snapshot = json.loads(frozen[0].read_text())
    assert set(snapshot) == set(contracts.MODELS["c5_portal"])
    assert {"PortalSignInStartIn", "PortalHomeOut", "MePortalOut"} <= set(snapshot)
    assert contracts.check() == []
    register = (REPO / "docs" / "contracts" / "portal-identity.md").read_text()
    assert "**Frozen at v1.1 on 2026-10-27**" in register


def _frontmatter_id(path: Path) -> str:
    found = re.search(r"^id: (RB-\d+)$", path.read_text(), re.M)
    assert found, path
    return found.group(1)


def test_ac_the_lockout_and_pause_runbooks_are_written_indexed_and_linked() -> None:
    lockout = RUNBOOKS / "RB-35-portal-sign-in-lockout.md"
    pause = RUNBOOKS / "RB-36-portal-sign-in-pause.md"
    assert (_frontmatter_id(lockout), _frontmatter_id(pause)) == ("RB-35", "RB-36")
    index = (RUNBOOKS / "README.md").read_text()
    assert "| RB-35 |" in index and "| RB-36 |" in index
    rb22 = (RUNBOOKS / "RB-22-identity-provider-outage.md").read_text()
    assert "RB-35" in rb22 and "RB-36" in rb22
    for runbook in (lockout, pause):
        text = runbook.read_text()
        assert "## Rehearsal log" in text  # rehearsed once before the flags retire


def test_ac_the_runbooks_name_controls_and_routes_that_exist() -> None:
    pause = (RUNBOOKS / "RB-36-portal-sign-in-pause.md").read_text()
    assert "--control portal_sign_in --scope firm" in pause
    tool = (REPO / "backend" / "src" / "abacus_tools" / "platform_control.py").read_text()
    assert "portal_sign_in" in tool
    lockout = (RUNBOOKS / "RB-35-portal-sign-in-lockout.md").read_text()
    paths = json.loads((REPO / "packages" / "api-client" / "openapi.json").read_text())["paths"]
    for route in re.findall(r"`POST (/v1/clients/\{client_id\}/contacts/[^`]+)`", lockout):
        assert route in paths, route
    assert "/portal-unlock" in lockout and "/mfa-reset" in lockout
