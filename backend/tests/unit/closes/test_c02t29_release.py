"""C-02-T29 (TASK-8815; SPEC-701 F7 US-7.3, US-7.4): release, client approval, lock, reopen.

Row acceptance: "Priya's release at 4:25 PM publishes to POR-09 with an approval item for Tess
Moreno and Ben Ashby, a manager's release is refused, and Lock is refused before the client
approves." Here, at the module seams: release is a partner's only (matrix), needs a live human
with a fresh MFA, and refuses unmet preconditions; Lock before the client's approval answers
409 `client_approval_required`; the final render's approval holds only during the release; the
fs_package provider is the C18 kind.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from abacus.modules.closes import release

MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"


def test_ac_a_managers_release_is_refused_at_the_matrix() -> None:
    actions = yaml.safe_load((MATRIX / "closes.yaml").read_text())["actions"]
    row = actions["close_package.release"]
    assert row.get("engagement_partner") == "allow"
    assert row.get("manager", "deny") != "allow"
    assert row.get("agent") == "deny" and row.get("system") == "deny"


async def test_release_needs_a_live_human_with_a_fresh_mfa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def now(_: object) -> datetime:
        return datetime.now(UTC)

    monkeypatch.setattr(release.clock, "now", now)
    stale = SimpleNamespace(
        tenant=SimpleNamespace(actor_kind="human"), is_support=False,
        mfa_at=datetime.now(UTC) - timedelta(hours=1),
    )  # fmt: skip
    with pytest.raises(release.MfaRequired):
        await release._fresh(stale)  # type: ignore[arg-type] -- a context double
    agent = SimpleNamespace(
        tenant=SimpleNamespace(actor_kind="agent"), is_support=False, mfa_at=None
    )
    with pytest.raises(release.Forbidden):
        await release._fresh(agent)  # type: ignore[arg-type] -- a context double


async def test_the_final_render_approval_holds_only_inside_the_release() -> None:
    ref = SimpleNamespace(kind="close_release", id=uuid4(), content_hash="a" * 64)
    assert await release.release_approval(ref) is None
    token = release._approving.set((ref, uuid4()))  # pyright: ignore[reportPrivateUsage] -- the module under test or its own sibling
    try:
        found = await release.release_approval(ref)
        assert found is not None and found[1] == "a" * 64
    finally:
        release._approving.reset(token)  # pyright: ignore[reportPrivateUsage] -- the module under test or its own sibling


def test_lock_before_client_approval_is_a_conflict_code() -> None:
    assert release.ClientApprovalRequired.code == "client_approval_required"
    assert release.PreconditionsUnmet.code == "release_preconditions_unmet"
    assert release.APPROVAL_KIND == "fs_package"
