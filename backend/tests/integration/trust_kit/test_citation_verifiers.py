"""P-03-T06 against Postgres and the S3 gateway (SPEC-322 AC-1 to AC-3; ADR-166 §§1-4;
DEC-218, DEC-219): `record_citations` verifies every claim with its kind's registered verifier,
on the word layer or the extraction, and writes one insert-only row each. A fabricated page, box,
quote or value is stored unverified with its reason; no citation fails only for a missing box; no
quote text is stored anywhere."""

from __future__ import annotations

import hashlib
import uuid

from abacus.kernel.uow import uow
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    RecordedCitation,
    process_upload,
    record_citations,
)
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import Actor, AgentContext, agent_context_for_run
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_version, engagement, make_firm

STATEMENT = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 600.0, "Opening balance 14,895,000.00")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Net assets")],
    ]
)
LINE = [70.0, 82.0, 300.0, 96.0]  # page 3's first line, in page points from the top


async def _agent(firm: Firm, engagement_id: uuid.UUID | None = None) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.screen",
        engagement_id=engagement_id or firm.engagement_id,
        task_scope=frozenset({"evidence.read", "request_item.read"}),
        initiator_user_id=firm.user_id,
    )


async def _record(
    firm: Firm,
    claims: list[CitationClaim],
    *,
    agent: bool = False,
    actor: Actor | None = None,
    engagement_id: uuid.UUID | None = None,
    anchored: bool = True,
) -> list[RecordedCitation]:
    acting = actor or (await _agent(firm) if agent else firm.person())
    anchor = CitationAnchor(
        "workpaper_cell",
        uuid.uuid4(),
        "RA!C14",
        None,
        (engagement_id or firm.engagement_id) if anchored else None,
    )
    async with uow(acting.tenant) as tx:
        return await record_citations(tx, actor=acting, anchor=anchor, claims=claims)


async def _layered(firm: Firm) -> uuid.UUID:
    version = await firm.version(STATEMENT)
    await words_upload(as_version(firm, version))
    return version


def _doc(version: uuid.UUID, page: int, bbox: list[float] | None = None) -> dict[str, object]:
    return {"evidence_version_id": str(version), "page": page, "bbox": bbox}


async def _row(seed: Seeder, citation_id: uuid.UUID) -> dict[str, object]:
    [row] = await seed.rows("SELECT * FROM citations WHERE id = $1", citation_id)
    return dict(row)


async def test_ac1_an_agents_quote_is_one_verified_row_with_the_layers_hash(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _record(
        firm,
        [
            CitationClaim(
                "document_text", _doc(version, 3), quote="Total investments 16,500,000.00"
            )
        ],
        agent=True,
    )
    assert (cited.verified, cited.verification_reason, cited.n) == (True, None, 1)
    row = await _row(seed, cited.id)
    assert (row["kind"], row["created_by_kind"], row["source_type"]) == (
        "document_text",
        "agent",
        "evidence_version",
    )
    assert row["created_by_run_id"] is not None
    assert row["on_behalf_of_user_id"] == firm.user_id
    assert row["quote_sha256"] == hashlib.sha256(b"total investments 16,500,000.00").digest()
    assert row["source_id"] == version
    locator = row["locator"]
    assert isinstance(locator, str) and '"bbox": [72.0' in locator  # the quote's words
    assert str(row["match_id"]).startswith(f"ev:{version}#p3:72,")
    assert row["verifier_version"] == "v1"


async def test_ac1_no_quote_text_is_stored_anywhere(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    await _record(firm, [CitationClaim("document_text", _doc(version, 3), quote="Net assets")])
    columns = [
        r["column_name"]
        for r in await seed.rows(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'citations'"
        )
    ]
    assert not [c for c in columns if "quote" in c and c != "quote_sha256"]
    dumped = await seed.value(
        "SELECT string_agg(c::text, '') FROM citations c WHERE tenant_id = $1", firm.tenant_id
    )
    assert "net assets" not in str(dumped).casefold()


async def test_ac2_fabrications_are_stored_unverified_with_their_reason(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    claims = [
        CitationClaim("document_text", _doc(version, 9), quote="Total investments"),
        CitationClaim("document_text", _doc(version, 3, [400.0, 400.0, 500.0, 500.0])),
        CitationClaim("document_text", _doc(version, 3), quote="Total liabilities 1.00"),
        CitationClaim("document_text", _doc(version, 3, LINE), quote="Net assets"),
        CitationClaim("document_text", _doc(version, 3, LINE), value="16,812,400.00"),
    ]
    found = await _record(firm, claims, agent=True)
    assert [(c.verified, c.verification_reason) for c in found] == [
        (False, "page_not_found"),
        (False, "bbox_mismatch"),
        (False, "quote_not_found"),
        (False, "bbox_mismatch"),
        (False, "value_mismatch"),
    ]
    assert [c.n for c in found] == [1, 2, 3, 4, 5]
    rows = [await _row(seed, c.id) for c in found]
    assert all(r["match_id"] is None and r["quote_sha256"] is None for r in rows)
    assert [r["verification_reason"] for r in rows] == [c.verification_reason for c in found]


async def test_ac2_a_cited_value_is_kept_as_the_source_prints_it(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _record(
        firm, [CitationClaim("document_text", _doc(version, 3, LINE), value="16500000")]
    )
    assert cited.verified
    assert (await _row(seed, cited.id))["value_text"] == "16,500,000.00"


async def test_ac3_without_a_layer_the_page_text_verifies_and_no_box_fails_it(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await firm.version(STATEMENT)
    assert await process_upload(as_version(firm, version)) == "extracted"  # no word layer
    found = await _record(
        firm,
        [
            CitationClaim("document_text", _doc(version, 3, LINE), quote="Total investments"),
            CitationClaim("document_text", _doc(version, 7), quote="Total investments"),
        ],
    )
    assert [(c.verified, c.verification_reason) for c in found] == [
        (True, None),
        (False, "page_not_found"),
    ]
    row = await _row(seed, found[0].id)
    # No region; the hash is of the quote as matched on the page text (security review #2).
    assert (row["match_id"], row["quote_sha256"]) == (
        f"ev:{version}#p3",
        hashlib.sha256(b"total investments").digest(),
    )


async def test_ac2_sheet_cells_check_the_quote_and_the_value(seed: Seeder) -> None:
    firm = await make_firm(seed)
    sheet = await firm.version(b'Account,Balance\nCash,"1,650.00"\n', "text/csv")
    assert await process_upload(as_version(firm, sheet)) == "extracted"
    cell = {"evidence_version_id": str(sheet), "cell": "B2"}
    found = await _record(
        firm,
        [
            CitationClaim("sheet_cell", cell, quote="1,650.00", value="1650"),
            CitationClaim("sheet_cell", cell, value="1600"),
            CitationClaim("sheet_cell", {**cell, "cell": "D9"}),
        ],
    )
    assert [(c.verified, c.verification_reason) for c in found] == [
        (True, None),
        (False, "value_mismatch"),
        (False, "cell_not_found"),
    ]
    assert found[0].match_id == f"{sheet}!B2"


async def test_a_source_outside_the_anchors_engagement_reads_as_absent(seed: Seeder) -> None:
    """Security review (#3): a version in another engagement answers exactly as a missing one,
    so verification is no oracle for what other engagements hold."""
    firm = await make_firm(seed)
    [row] = await seed.rows(
        "SELECT client_id, client_entity_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    other = await engagement(
        seed, firm.tenant_id, row["client_id"], row["client_entity_id"], firm.user_id
    )
    elsewhere = await firm.version(STATEMENT, engagement_id=other)
    await words_upload(as_version(firm, elsewhere))
    [cited] = await _record(
        firm, [CitationClaim("document_text", _doc(elsewhere, 3), quote="Total investments")]
    )
    assert (cited.verified, cited.verification_reason) == (False, "source_not_found")
    [missing] = await _record(
        firm, [CitationClaim("document_text", _doc(uuid.uuid4(), 3), quote="Total investments")]
    )
    assert missing.verification_reason == "source_not_found"


async def test_adr166_kinds_without_a_verifier_and_bad_locators_are_locator_invalid(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    step = uuid.uuid4()
    found = await _record(
        firm,
        [
            CitationClaim("methodology_step", {"template_version_id": str(step), "step_key": "a"}),
            CitationClaim("document_text", {"page": "three"}),
            CitationClaim("request_item", {"request_item_id": str(uuid.uuid4())}),
        ],
    )
    assert [(c.verified, c.verification_reason) for c in found] == [
        (False, "locator_invalid"),
        (False, "locator_invalid"),
        (False, "source_not_found"),
    ]
    row = await _row(seed, found[0].id)
    assert (row["source_type"], row["source_id"], row["verifier_version"]) == (
        "methodology_template_version",
        step,
        "none",
    )


async def test_adr007_each_citation_is_audited_and_a_stack_keeps_counting(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    anchor = CitationAnchor("workpaper_cell", uuid.uuid4(), None, None, firm.engagement_id)
    human = firm.person()
    for quote in ("Total investments", "Net assets"):
        async with uow(human.tenant) as tx:
            await record_citations(
                tx,
                actor=human,
                anchor=anchor,
                claims=[CitationClaim("document_text", _doc(version, 3), quote=quote)],
            )
    rows = await seed.rows(
        "SELECT n, created_by_kind, created_by_user_id FROM citations WHERE cited_from_id = $1 "
        "ORDER BY n",
        anchor.id,
    )
    assert [(r["n"], r["created_by_kind"], r["created_by_user_id"]) for r in rows] == [
        (1, "human", firm.user_id),
        (2, "human", firm.user_id),
    ]
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'citation.created'",
        firm.tenant_id,
    )
    assert audited == 2


async def test_review_verification_authorises_the_acting_person(seed: Seeder) -> None:
    """Security review (#3): verifying reads the source, so the actor must be allowed
    `evidence.read` on its engagement; otherwise it answers as if nothing were there."""
    firm = await make_firm(seed)
    version = await _layered(firm)
    outsider = firm.person(await firm.outsider())
    claim = CitationClaim("document_text", _doc(version, 3), quote="Total investments")
    [cited] = await _record(firm, [claim], actor=outsider)
    assert (cited.verified, cited.verification_reason) == (False, "source_not_visible")
    [cited] = await _record(firm, [claim])
    assert cited.verified


async def test_review_an_anchor_without_an_engagement_cannot_verify_evidence(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    found = await _record(
        firm,
        [
            CitationClaim("document_text", _doc(version, 3), quote="Total investments"),
            CitationClaim("request_item", {"request_item_id": str(uuid.uuid4())}),
        ],
        anchored=False,
    )
    assert [(c.verified, c.verification_reason) for c in found] == [
        (False, "source_not_visible"),
        (False, "source_not_visible"),
    ]


async def test_review_an_agent_verifies_only_inside_its_runs_engagement(seed: Seeder) -> None:
    firm = await make_firm(seed)
    [row] = await seed.rows(
        "SELECT client_id, client_entity_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    other = await engagement(
        seed, firm.tenant_id, row["client_id"], row["client_entity_id"], firm.user_id
    )
    elsewhere = await firm.version(STATEMENT, engagement_id=other)
    await words_upload(as_version(firm, elsewhere))
    claim = CitationClaim("document_text", _doc(elsewhere, 3), quote="Total investments")
    # The anchor names the other engagement, but the run is confined to its own.
    [cited] = await _record(firm, [claim], agent=True, engagement_id=other)
    assert (cited.verified, cited.verification_reason) == (False, "source_not_visible")


async def test_review_an_overlong_quote_is_never_searched(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _record(
        firm, [CitationClaim("document_text", _doc(version, 3), quote="Total " * 400)]
    )
    assert (cited.verified, cited.verification_reason) == (False, "quote_not_found")
