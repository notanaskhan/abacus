"""Q-05-T16 part 1 (TASK-8820; SPEC-711 AC-7, AC-8): inspector access.

Row acceptance (part 1): "Thomas Whitcombe reads Bayside's archive and activity read-only during
INS-26-02 and loses access at conclusion, a walled inspector sees nothing." Here: the grant
expires at the conclusion or the due date + 30 days, whichever is first; it reaches reads only;
authorise checks walls before the inspector relationship (so a wall wins); visible() adds the
grant's engagements for an inspection read only.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import column

from abacus.modules.identity import authz
from abacus.modules.identity import inspection_grants as g


def test_expiry_is_the_conclusion_or_due_plus_30_days() -> None:
    due = datetime(2026, 10, 30, tzinfo=UTC)
    assert g.expiry(None, due) == datetime(2026, 11, 29, tzinfo=UTC)
    assert g.expiry(datetime(2026, 10, 20, tzinfo=UTC), due) == datetime(2026, 10, 20, tzinfo=UTC)


def test_a_grant_reaches_reads_only() -> None:
    assert "archive.read" in g.INSPECTION_READS and "audit_trail.read" in g.INSPECTION_READS
    assert not [a for a in g.INSPECTION_READS if not a.endswith(".read")]
    assert g.inspector_reach(uuid4(), "evidence.upload", column("engagement_id")) is None
    assert g.inspector_reach(uuid4(), "evidence.read", column("engagement_id")) is not None


def test_walls_are_checked_before_the_inspector_relationship() -> None:
    source = inspect.getsource(authz.authorise)
    assert source.index("_walled(ctx, resource)") < source.index("_roles(ctx, resource, rule)")
    roles = inspect.getsource(authz._roles)  # pyright: ignore[reportPrivateUsage]
    assert "inspector_of(" in roles and "not ctx.client" in roles
