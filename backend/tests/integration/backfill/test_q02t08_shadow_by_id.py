"""Q-02-T08 (TASK-1210; SPEC-036 AC-5): reads that reach agent output by id, or feed the human
gates, leave out a shadow run's output.

- A guidance draft written by a shadow run is not there to approve by id (it was never shown).
- The gates' screening reader takes per-version results only, and the firm having a shadow run
  never changes what it returns: a request batch's aggregate (no run) is never a version's gate.

Boundary: the migrated Postgres (superuser seeding), the agents repository in a firm session.
"""

from __future__ import annotations

import uuid
from typing import cast

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.repository import get_guidance_draft, latest_screenings_for_gates

from .support import Seeder, Site


async def _run(seed: Seeder, site: Site, by: uuid.UUID, agent: str, *, shadow: bool) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, task_scope, status, finished_at, shadow) "
            "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'], 'completed', now(), $6) "
            "RETURNING id",
            site.tenant_id,
            agent,
            site.engagement_id,
            site.version_id,
            by,
            shadow,
        ),
    )


async def _draft(seed: Seeder, site: Site, run: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO guidance_drafts (tenant_id, engagement_id, request_item_id, "
            "agent_run_id, prompt_ref, why, good_looks_like, passed_checks, check_reasons) "
            "VALUES ($1, $2, $3, $4, 'requests.guidance_drafter@v1', 'Why', 'Good', true, '{}') "
            "RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.item_id,
            run,
        ),
    )


async def _screening(seed: Seeder, site: Site, run: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
            "($1, $2, $3, $4, 'needs_revision', 0.5, 'Totals differ', '[]', '[]') RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.version_id,
            run,
        ),
    )


async def _aggregate(seed: Seeder, site: Site, source: uuid.UUID) -> uuid.UUID:
    """A request batch's aggregate, seeded past the guard that leaves composing it to code."""
    made = uuid.uuid4()
    await seed.run_untriggered(
        "INSERT INTO screening_results (id, tenant_id, engagement_id, subject_kind, "
        "request_item_id, batch_no, source_result_ids, source_review_ids, "
        "evidence_version_ids, checks, file_flags, verdict, created_by_kind, citations, "
        "unverified) VALUES ($1, $2, $3, 'request_batch', $4, 1, ARRAY[$5::uuid], '{}', "
        "ARRAY[$6::uuid], '[]', '[]', 'flagged', 'system', '[]', '[]')",
        made,
        site.tenant_id,
        site.engagement_id,
        site.item_id,
        source,
        site.version_id,
    )
    return made


def _system(site: Site) -> TenantContext:
    return TenantContext(site.tenant_id, "system", "q02t08-test")


async def test_ac5_a_shadow_draft_is_not_there_to_approve_by_id(seed: Seeder) -> None:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Granite")
    hidden = await _draft(
        seed, site, await _run(seed, site, admin.user_id, "requests.guidance_drafter", shadow=True)
    )
    shown = await _draft(
        seed,
        site,
        await _run(seed, site, admin.user_id, "requests.guidance_drafter", shadow=False),
    )
    async with tenant_session(_system(site)) as session:
        assert await get_guidance_draft(session, hidden) is None
        found = await get_guidance_draft(session, shown)
    assert found is not None and found.id == shown


async def test_ac5_gates_read_per_version_results_whatever_the_firms_shadow_runs(
    seed: Seeder,
) -> None:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Granite")
    live = await _screening(
        seed, site, await _run(seed, site, admin.user_id, "evidence.screener", shadow=False)
    )
    await _aggregate(seed, site, live)
    async with tenant_session(_system(site)) as session:
        before = await latest_screenings_for_gates(session, site.engagement_id)
    assert before == [(live, site.engagement_id, site.version_id)]
    # A shadow run elsewhere in the firm: its result is left out, and nothing else changes.
    other = await seed.site(tenant_id, admin.user_id, "Ashford")
    await _screening(
        seed, other, await _run(seed, other, admin.user_id, "evidence.screener", shadow=True)
    )
    async with tenant_session(_system(site)) as session:
        assert await latest_screenings_for_gates(session, site.engagement_id) == before
        assert await latest_screenings_for_gates(session, other.engagement_id) == []
