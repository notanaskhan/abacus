"""Q-02-T08 (TASK-1210; SPEC-036 AC-5; 0158) against Postgres and the S3 gateway: a citation
written by an agent run that started in shadow is stored, and never read. The display answers
404, lists and stacks leave it out with no count, the viewer draws no region for it, relink
answers 404, and only an agent can write one."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    RecordedCitation,
    process_upload,
    record_citations,
)
from abacus.modules.evidence.audit_targets import audit_owners
from abacus.modules.evidence.citations.display import (
    CitationFilters,
    citation_display,
    citation_list,
)
from abacus.modules.evidence.citations.moved import NotMoved, relink
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.repository import verified_citations_of
from abacus.modules.evidence.viewer import viewer_regions
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import Forbidden, agent_context_for_run
from abacus.modules.identity.authz import recording_checks
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_version, make_firm, scanned

STATEMENT = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Net assets")],
    ]
)


async def _rendered(firm: Firm) -> uuid.UUID:
    version = await firm.version(STATEMENT)
    given = as_version(firm, version)
    await process_upload(given)
    await words_upload(given)
    await preview_upload(given)
    return version


async def _cite(
    firm: Firm, version: uuid.UUID, anchor_id: uuid.UUID, *, shadow: bool
) -> RecordedCitation:
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.upload_reviewer",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.user_id,
    )
    async with uow(agent.tenant) as tx:
        [cited] = await record_citations(
            tx,
            actor=agent,
            anchor=CitationAnchor("upload_review", anchor_id, "F1", None, firm.engagement_id),
            claims=[
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 2},
                    value="16,500,000.00",
                )
            ],
            shadow=shadow,
        )
    assert cited.verified
    return cited


async def test_ac5_a_shadow_runs_citation_is_stored_hidden(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    hidden = await _cite(firm, version, uuid.uuid4(), shadow=True)
    shown = await _cite(firm, version, uuid.uuid4(), shadow=False)
    rows = await seed.rows(
        "SELECT id, shadow FROM citations WHERE tenant_id = $1 ORDER BY created_at", firm.tenant_id
    )
    assert {(r["id"], r["shadow"]) for r in rows} == {(hidden.id, True), (shown.id, False)}


async def test_ac5_the_display_answers_404_and_lists_leave_it_out(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await scanned(seed, firm, [1, 2], version=version)
    host = uuid.uuid4()
    hidden = await _cite(firm, version, host, shadow=True)
    me = firm.person()
    with pytest.raises(NotFound):
        await citation_display(me, hidden.id)
    listed = await citation_list(
        me, CitationFilters(host_ref=f"upload_review:{host}"), cursor=None, limit=None
    )
    assert (listed.total, listed.items) == (0, [])
    everything = await citation_list(me, CitationFilters(), cursor=None, limit=None)
    assert hidden.id not in {v.id for v in everything.items}
    shown = await _cite(firm, version, host, shadow=False)
    assert (await citation_display(me, shown.id)).id == shown.id
    listed = await citation_list(
        me, CitationFilters(host_ref=f"upload_review:{host}"), cursor=None, limit=None
    )
    assert [v.id for v in listed.items] == [shown.id] and listed.total == 1


async def test_ac5_the_viewer_draws_no_region_for_it(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    hidden = await _cite(firm, version, uuid.uuid4(), shadow=True)
    me = firm.person()
    assert await viewer_regions(me, version, None) == []
    assert await viewer_regions(me, version, [str(hidden.match_id)]) == []
    shown = await _cite(firm, version, uuid.uuid4(), shadow=False)
    assert [r.citation_id for r in await viewer_regions(me, version, None)] == [shown.id]


async def test_ac5_stacks_composed_for_anchors_leave_it_out(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    anchor = uuid.uuid4()
    await _cite(firm, version, anchor, shadow=True)
    shown = await _cite(firm, version, anchor, shadow=False)
    async with tenant_session(firm.system) as session:
        stack = await verified_citations_of(session, "upload_review", [anchor])
    assert [c[0] for c in stack] == [shown.id]


async def test_ac5_relink_answers_404_before_anything_else(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    hidden = await _cite(firm, version, uuid.uuid4(), shadow=True)
    shown = await _cite(firm, version, uuid.uuid4(), shadow=False)
    with recording_checks(), pytest.raises(NotFound):  # a request the person is making
        await relink(firm.person(), hidden.id)
    # The same unmoved citation, not from a shadow run, gets past the lookup and is refused
    # later (the person's role, or not moved), never as missing.
    with recording_checks(), pytest.raises((Forbidden, NotMoved)):
        await relink(firm.person(), shown.id)


async def test_only_an_agent_run_writes_a_shadow_citation(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    me = firm.person()
    with pytest.raises(ValueError, match="only an agent run"):
        async with uow(me.tenant) as tx:
            await record_citations(
                tx,
                actor=me,
                anchor=CitationAnchor(
                    "workpaper_cell", uuid.uuid4(), "TB!C9", None, firm.engagement_id
                ),
                claims=[
                    CitationClaim(
                        "document_text",
                        {"evidence_version_id": str(version), "page": 2},
                        value="16,500,000.00",
                    )
                ],
                shadow=True,
            )


async def test_ac5_used_in_never_counts_a_shadow_runs_anchor(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await scanned(seed, firm, [1, 2], version=version)
    await _cite(firm, version, uuid.uuid4(), shadow=True)
    shown = await _cite(firm, version, uuid.uuid4(), shadow=False)
    assert (await citation_display(firm.person(), shown.id)).used_in == 1


async def test_ac5_its_audit_events_name_no_owner(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    hidden = await _cite(firm, version, uuid.uuid4(), shadow=True)
    shown = await _cite(firm, version, uuid.uuid4(), shadow=False)
    owners = await audit_owners(firm.system, "citation", [hidden.id, shown.id])
    assert owners == {shown.id: firm.engagement_id}


async def test_ac5_the_database_marks_a_shadow_runs_citation_the_writer_forgot(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    run = await seed.id(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, shadow) VALUES ($1, "
        "'evidence.upload_reviewer', 1, $2, $3, ARRAY['evidence.read'], 'running', true) "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run,
        agent_id="evidence.upload_reviewer",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.user_id,
    )
    async with uow(agent.tenant) as tx:
        [cited] = await record_citations(
            tx,
            actor=agent,
            anchor=CitationAnchor("upload_review", uuid.uuid4(), "F1", None, firm.engagement_id),
            claims=[
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 2},
                    value="16,500,000.00",
                )
            ],
            shadow=False,
        )
    assert await seed.value("SELECT shadow FROM citations WHERE id = $1", cited.id) is True
