"""P-03-T10 against Postgres and the S3 gateway (SPEC-322 AC-1; ADR-166; DEC-267): the agents'
citations become v2 rows through `record_citations`, as the agent, in its handoff's unit of work.
A reviewer's quote resolves to a box on the word layer; the matcher cites an inbox file; a
fabricated quote is written unverified; a rolled-back handoff leaves no rows."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.handoff import Citation, DocumentCitation
from abacus.modules.agents.v2_citations import (
    cell_claims,
    document_claims,
    record_agent_citations,
)
from abacus.modules.evidence.api import process_upload
from abacus.modules.evidence.citations.display import citation_display
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import AgentContext, agent_context_for_run
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_inbox, as_version, make_firm

STATEMENT = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Net assets")],
    ]
)


async def _agent(firm: Firm, agent_id: str) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id=agent_id,
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.user_id,
    )


async def test_ac1_a_reviewers_quotes_become_agent_rows_that_resolve_to_a_region(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await firm.version(STATEMENT)
    await words_upload(as_version(firm, version))
    agent = await _agent(firm, "evidence.upload_reviewer")
    review = uuid.uuid4()
    claims = document_claims(
        [
            DocumentCitation(page=2, quote="Total investments 16,500,000.00"),
            DocumentCitation(page=2, quote="Total liabilities 1.00"),
        ],
        evidence_version_id=version,
    )
    async with uow(agent.tenant) as tx:
        found = await record_agent_citations(
            tx, agent, anchor_type="upload_review", anchor_id=review, ref="F1", claims=claims
        )
    assert [(c.verified, c.verification_reason) for c in found] == [
        (True, None),
        (False, "quote_not_found"),
    ]
    rows = await seed.rows(
        "SELECT created_by_kind, created_by_run_id, on_behalf_of_user_id, cited_from_type, "
        "cited_from_id, cited_from_ref, engagement_id, locator::text AS locator FROM citations "
        "WHERE tenant_id = $1 ORDER BY n",
        firm.tenant_id,
    )
    assert {(r["created_by_kind"], r["created_by_run_id"]) for r in rows} == {
        ("agent", agent.agent_run_id)
    }
    assert rows[0]["on_behalf_of_user_id"] == firm.user_id
    assert (rows[0]["cited_from_type"], rows[0]["cited_from_id"], rows[0]["cited_from_ref"]) == (
        "upload_review",
        review,
        "F1",
    )
    assert rows[0]["engagement_id"] == firm.engagement_id
    assert '"bbox": [72.0' in rows[0]["locator"]  # a lit region
    assert str(found[0].match_id).startswith(f"ev:{version}#p2:72,")
    view = await citation_display(firm.person(), found[0].id)
    assert view.created_by.label == "Test person via Agent"
    assert view.quote == "Total investments 16,500,000.00"


async def test_ac1_the_matcher_cites_an_inbox_file(seed: Seeder) -> None:
    firm = await make_firm(seed)
    inbox = await firm.inbox_file(STATEMENT)
    await words_upload(as_inbox(firm, inbox))
    agent = await _agent(firm, "evidence.matcher")
    async with uow(agent.tenant) as tx:
        [cited] = await record_agent_citations(
            tx,
            agent,
            anchor_type="inbox_match",
            anchor_id=uuid.uuid4(),
            ref="R1",
            claims=document_claims(
                [DocumentCitation(page=1, quote="Harborline statement")], inbox_file_id=inbox
            ),
        )
    assert cited.verified and str(cited.match_id).startswith(f"inbox:{inbox}#p1:")
    [row] = await seed.rows("SELECT source_type, source_id FROM citations WHERE id = $1", cited.id)
    assert (row["source_type"], row["source_id"]) == ("inbox_file", inbox)
    view = await citation_display(firm.person(), cited.id)
    assert (view.title, view.quote) == ("dropped.pdf", "Harborline statement")


async def test_an_inbox_file_of_another_engagement_is_not_found(seed: Seeder) -> None:
    firm = await make_firm(seed)
    other = await make_firm(seed)
    inbox = await other.inbox_file(STATEMENT)
    agent = await _agent(firm, "evidence.matcher")
    async with uow(agent.tenant) as tx:
        [cited] = await record_agent_citations(
            tx,
            agent,
            anchor_type="inbox_match",
            anchor_id=uuid.uuid4(),
            ref="R1",
            claims=document_claims(
                [DocumentCitation(page=1, quote="Harborline statement")], inbox_file_id=inbox
            ),
        )
    assert (cited.verified, cited.verification_reason) == (False, "source_not_found")


async def test_the_screeners_cells_are_sheet_cell_rows(seed: Seeder) -> None:
    firm = await make_firm(seed)
    sheet = await firm.version(b'Account,Balance\nCash,"1,650.00"\n', "text/csv")
    assert await process_upload(as_version(firm, sheet)) == "extracted"
    agent = await _agent(firm, "evidence.screener")
    async with uow(agent.tenant) as tx:
        found = await record_agent_citations(
            tx,
            agent,
            anchor_type="screening_result",
            anchor_id=uuid.uuid4(),
            ref=None,
            claims=cell_claims(sheet, [Citation(cell="B2", value=None, quote="1,650.00")]),
        )
    assert [(c.kind, c.verified) for c in found] == [("sheet_cell", True)]


async def test_a_rolled_back_handoff_leaves_no_citation_rows(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(STATEMENT)
    await words_upload(as_version(firm, version))
    agent = await _agent(firm, "evidence.upload_reviewer")
    with pytest.raises(RuntimeError):
        async with uow(agent.tenant) as tx:
            await record_agent_citations(
                tx,
                agent,
                anchor_type="upload_review",
                anchor_id=uuid.uuid4(),
                ref="F1",
                claims=document_claims(
                    [DocumentCitation(page=1, quote="Harborline")], evidence_version_id=version
                ),
            )
            tx.record(
                "upload_review.created", target=Target("evidence_version", version), after=Ref()
            )
            raise RuntimeError("the handoff failed after its citations")
    count = await seed.value("SELECT count(*) FROM citations WHERE tenant_id = $1", firm.tenant_id)
    assert count == 0
