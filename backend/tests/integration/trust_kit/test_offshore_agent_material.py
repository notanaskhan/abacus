"""TASK-1207 security review, item 2 (DEC-52; DEC-322's portal-drop rule): an agent acting for
an offshore member reads a document only as its masked projection.

The upload reviewer and the inbox matcher get a firm upload's extracted text when their run's
initiator is onshore. When the initiator is an offshore member, the material is the masked
projection of the PII-scanned pages (every detected region replaced by its token; no sheets), the
same rule a client's portal drop already has; before the scan has run there is no material, so the
run can't proceed (fail closed). Against Postgres and the S3 gateway, with the real extraction,
word layer and PII scan of the seeded W-2 (box a: SSN 000-00-6081).
"""

from __future__ import annotations

import uuid

from abacus.modules.agents.inbox_match import match_material_for
from abacus.modules.agents.upload_review import review_material_for
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import AgentContext, agent_context_for_run
from abacus_tools.synthetic.documents import w2_pdf

from .support import Firm, Seeder, as_inbox, as_version, make_firm

SSN = "000-00-6081"
MASKED = "•••-••-6081"


async def _agent(firm: Firm, agent_id: str) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id=agent_id,
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.user_id,
    )


async def _offshore(firm: Firm) -> None:
    await firm.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.user_id,
    )


async def _version(firm: Firm, *, scan: bool) -> uuid.UUID:
    version = await firm.version(w2_pdf())
    await extract_upload(as_version(firm, version))
    await words_upload(as_version(firm, version))
    if scan:
        await pii_scan_upload(as_version(firm, version))
    return version


async def _inbox(firm: Firm, *, scan: bool) -> uuid.UUID:
    inbox = await firm.inbox_file(w2_pdf())
    await extract_upload(as_inbox(firm, inbox))
    await words_upload(as_inbox(firm, inbox))
    if scan:
        await pii_scan_upload(as_inbox(firm, inbox))
    return inbox


def _text(pages: dict[int, str], excerpt: tuple[tuple[int, str], ...]) -> str:
    return " ".join(pages.values()) + " " + " ".join(t for _, t in excerpt)


async def test_review2_the_upload_reviewer_reads_the_w2_masked_for_an_offshore_initiator(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, scan=True)
    onshore = await review_material_for(await _agent(firm, "evidence.upload_reviewer"), version)
    assert onshore is not None
    assert SSN in _text(onshore.pages, onshore.excerpt_pages)  # the control: raw text onshore
    await _offshore(firm)
    material = await review_material_for(await _agent(firm, "evidence.upload_reviewer"), version)
    assert material is not None
    text = _text(material.pages, material.excerpt_pages)
    assert SSN not in text and MASKED in text
    assert material.sheets == {} and material.excerpt_tables == ()


async def test_review2_the_upload_reviewer_gets_nothing_before_the_scan(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, scan=False)
    await _offshore(firm)
    agent = await _agent(firm, "evidence.upload_reviewer")
    assert await review_material_for(agent, version) is None  # fail closed


async def test_review2_the_inbox_matcher_reads_a_firm_upload_masked_for_an_offshore_initiator(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    inbox = await _inbox(firm, scan=True)
    onshore = await match_material_for(await _agent(firm, "evidence.matcher"), inbox)
    assert onshore is not None
    assert SSN in _text(onshore.pages, onshore.excerpt_pages)  # the control
    await _offshore(firm)
    material = await match_material_for(await _agent(firm, "evidence.matcher"), inbox)
    assert material is not None
    text = _text(material.pages, material.excerpt_pages)
    assert SSN not in text and MASKED in text
    assert material.sheets == {}


async def test_review2_the_inbox_matcher_gets_nothing_before_the_scan(seed: Seeder) -> None:
    firm = await make_firm(seed)
    inbox = await _inbox(firm, scan=False)
    await _offshore(firm)
    agent = await _agent(firm, "evidence.matcher")
    assert await match_material_for(agent, inbox) is None  # fail closed
