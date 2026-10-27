"""I-01-T08: the wedge's C13 and home-count registrations (DEC-647).

- SPEC-004's review queue is an `evidence_review` gate (band Approvals & sends) on the uploaded
  item's newest version: unassigned it waits on the engagement's reviewers, taken it waits on the
  reviewer alone, and the counts endpoint and the list agree (P-01's one number).
- A shadow run's proposal is never a gate (AC1.6; the agents' sources already leave shadow runs
  out, SPEC-036 AC-5).
- The home counts `agent_runs_running`, `audits` and `binders` are registered and count what the
  viewer may read, narrowed by office.

Built on P-04-T17's firm (Ashford and Bayside; Daniel the EP, Hannah the manager, Lena staff).
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import member_context
from abacus.modules.platform.api import home_count, home_count_keys
from abacus.modules.review.gates import gate_sources

from .support import Json, Site
from .test_p04t17_human_gates_independent import (
    Firm,
    _deliver,  # pyright: ignore[reportPrivateUsage] -- the projector, driven as the worker drives it
    firm,
)

__all__ = ["firm"]
pytestmark = pytest.mark.asyncio
COUNTS = "/v1/human-gates/counts"


async def _uploaded(f: Firm, site: Site) -> None:
    """A client's upload fulfils the site's item (as `fulfil_by_upload` writes it)."""
    await f.net.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        f.tenant_id,
        site.engagement_id,
        site.item_id,
        site.version_id,
    )
    await f.net.seed.run(
        "UPDATE request_items SET status = 'uploaded' WHERE id = $1", site.item_id
    )
    await _deliver(
        OutboxEvent(
            uuid.uuid4(),
            f.tenant_id,
            "evidence.uploaded",
            {
                "engagement_id": str(site.engagement_id),
                "request_item_id": str(site.item_id),
                "evidence_version_id": str(site.version_id),
                "uploaded_by": str(uuid.uuid4()),
            },
        )
    )


def test_the_review_queue_is_a_registered_evidence_review_source() -> None:
    sources = {s.subject_type: s for s in gate_sources()}
    assert sources["evidence_version"].kind == "evidence_review"
    assert {"evidence.uploaded", "review.assigned"} <= sources["evidence_version"].events


async def test_an_upload_waits_on_the_reviewers_and_the_counts_agree(firm: Firm) -> None:
    await _uploaded(firm, firm.bayside)
    for who in (firm.hannah, firm.daniel):
        status, page = await firm.gates(who)
        assert status == 200, page
        rows = [r for r in cast(list[Json], page["items"]) if r["kind"] == "evidence_review"]
        assert [r["subject"] for r in rows] == [
            {"type": "evidence_version", "id": str(firm.bayside.version_id)}
        ]
        assert rows[0]["band"] == "approvals_sends"
        counts = cast(Json, (await firm.net.call("GET", COUNTS, who)).json())
        assert counts["total"] == page["total"]
        assert cast(dict[str, int], counts["bands"])["approvals_sends"] >= 1


async def test_a_taken_review_waits_on_its_reviewer_alone(firm: Firm) -> None:
    await _uploaded(firm, firm.bayside)
    await firm.net.seed.run(
        "INSERT INTO review_assignments (tenant_id, evidence_version_id, engagement_id, "
        "assignee_user_id, assigned_by, assigned_at) VALUES ($1, $2, $3, $4, $4, now())",
        firm.tenant_id,
        firm.bayside.version_id,
        firm.bayside.engagement_id,
        firm.hannah.user_id,
    )
    await _deliver(
        OutboxEvent(
            uuid.uuid4(),
            firm.tenant_id,
            "review.assigned",
            {
                "engagement_id": str(firm.bayside.engagement_id),
                "evidence_version_id": str(firm.bayside.version_id),
                "assignee_user_id": str(firm.hannah.user_id),
            },
        )
    )
    _status, hannah = await firm.gates(firm.hannah)
    _status, daniel = await firm.gates(firm.daniel)
    kinds = [r["kind"] for r in cast(list[Json], hannah["items"])]
    assert kinds.count("evidence_review") == 1
    assert "evidence_review" not in [r["kind"] for r in cast(list[Json], daniel["items"])]


async def test_home_counts_are_registered_and_count_what_the_viewer_reads(firm: Firm) -> None:
    assert {"agent_runs_running", "audits", "binders"} <= set(home_count_keys())
    hannah = await member_context(firm.tenant_id, firm.hannah.user_id)
    assert hannah is not None
    binders = await home_count(hannah, "binders", None)
    assert binders is not None and binders.total == 2  # one draft binder on each site
    running = await home_count(hannah, "agent_runs_running", None)
    assert running is not None and running.total == 0
    # An office nobody files under narrows to nothing (DEC-30): a filter, never a boundary.
    nowhere = await home_count(hannah, "binders", uuid.uuid4())
    assert nowhere is not None and nowhere.total == 0
