"""P-03-T08 against Postgres and the S3 gateway (SPEC-322 AC-5, AC-12; C4 §3.2; ADR-166;
DEC-265): the citations read API. Walls answer 404 and lists carry no hidden count; a client
principal is refused; an unverified citation is never returned as verified; the quote is re-read
from the word layer, hash-checked and masked, and never stored."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    RecordedCitation,
    record_citations,
)
from abacus.modules.evidence.citations.display import (
    CitationFilters,
    citation_display,
    citation_list,
)
from abacus.modules.evidence.pii import DETECTOR_VERSION
from abacus.modules.evidence.repository import pages_of
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer, words_upload
from abacus.modules.identity.api import AuthContext, Forbidden, agent_context_for_run
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_version, engagement, make_firm, scanned

STATEMENT = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 700.0, "Employee SSN 000-00-6081 on file")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Net assets")],
    ]
)


async def _layered(firm: Firm, engagement_id: uuid.UUID | None = None) -> uuid.UUID:
    version = await firm.version(STATEMENT, engagement_id=engagement_id)
    await words_upload(as_version(firm, version))
    return version


def _doc(version: uuid.UUID, page: int) -> dict[str, object]:
    return {"evidence_version_id": str(version), "page": page}


async def _cite(
    firm: Firm,
    claims: list[CitationClaim],
    *,
    anchor_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
    agent: bool = False,
    ref: str = "RA!C14",
) -> list[RecordedCitation]:
    acting = (
        await agent_context_for_run(
            tenant_id=firm.tenant_id,
            run_id=uuid.uuid4(),
            agent_id="evidence.screen",
            engagement_id=engagement_id or firm.engagement_id,
            task_scope=frozenset({"evidence.read"}),
            initiator_user_id=firm.user_id,
        )
        if agent
        else firm.person()
    )
    anchor = CitationAnchor(
        "workpaper_cell",
        anchor_id or uuid.uuid4(),
        ref,
        {"section_id": "service-orgs"},
        engagement_id or firm.engagement_id,
    )
    async with uow(acting.tenant) as tx:
        return await record_citations(tx, actor=acting, anchor=anchor, claims=claims)


async def _second_engagement(firm: Firm) -> tuple[uuid.UUID, uuid.UUID]:
    """Another client's engagement with the same person on it, and that client."""
    client_id = await firm.seed.id(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Walled client') RETURNING id",
        firm.tenant_id,
    )
    entity_id = await firm.seed.id(
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, 'Walled entity') RETURNING id",
        firm.tenant_id,
        client_id,
    )
    return await engagement(firm.seed, firm.tenant_id, client_id, entity_id, firm.user_id), (
        client_id
    )


async def test_ac1_the_display_is_rendered_by_code_and_the_quote_re_read(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(
        firm,
        [
            CitationClaim(
                "document_text", _doc(version, 3), quote="Total investments 16,500,000.00"
            )
        ],
        agent=True,
    )
    await scanned(seed, firm, [1, 2, 3], version=version)
    view = await citation_display(firm.person(), cited.id)
    assert (view.kind, view.n, view.state, view.verified) == ("document_text", 1, "valid", True)
    assert view.title.startswith("Upload ") and view.loc == "p. 3"  # the item, by code
    assert (view.quote, view.quote_state) == ("Total investments 16,500,000.00", "shown")
    assert view.created_by.kind == "agent"
    assert view.created_by.label == "Test person via Agent"
    assert view.source.evidence_version_id == version and view.source.page == 3
    assert view.used_in == 1 and view.moved is None and view.allowed_actions == []
    assert str(view.match_id).startswith(f"ev:{version}#p3:")


async def test_ac1_no_quote_text_is_stored_in_the_database(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    await _cite(firm, [CitationClaim("document_text", _doc(version, 3), quote="Net assets")])
    dumped = await seed.value(
        "SELECT string_agg(c::text, '') FROM citations c WHERE tenant_id = $1", firm.tenant_id
    )
    assert "net assets" not in str(dumped).casefold()


async def test_ac5_a_walled_citation_is_404_and_omitted_from_stacks_with_no_count(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    other, walled_client = await _second_engagement(firm)
    mine = await _layered(firm)
    theirs = await _layered(firm, other)
    anchor = uuid.uuid4()
    [shown] = await _cite(
        firm, [CitationClaim("document_text", _doc(mine, 1), quote="Harborline")]
    )
    await _cite(
        firm,
        [CitationClaim("document_text", _doc(theirs, 1), quote="Harborline")],
        anchor_id=anchor,
        engagement_id=other,
    )
    [hidden] = await _cite(
        firm,
        [CitationClaim("document_text", _doc(theirs, 3), quote="Net assets")],
        anchor_id=anchor,
        engagement_id=other,
    )
    lena = await firm.outsider()
    for engagement_id in (firm.engagement_id, other):
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'staff')",
            firm.tenant_id,
            engagement_id,
            lena,
        )
        await seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
            "clock_timestamp())",
            firm.tenant_id,
            engagement_id,
            lena,
        )
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant_id,
        lena,
        walled_client,
        firm.user_id,
    )
    walled = firm.person(lena)
    with pytest.raises(Forbidden) as refused:
        await citation_display(walled, hidden.id)
    assert refused.value.layer == "wall"  # answered 404 (DEC-43)
    stack = await citation_list(
        walled, CitationFilters("workpaper_cell", anchor), cursor=None, limit=None
    )
    assert (stack.items, stack.total, stack.counts) == ([], 0, {})
    everything = await citation_list(walled, CitationFilters(), cursor=None, limit=None)
    assert [v.id for v in everything.items] == [shown.id] and everything.total == 1
    # The person who isn't walled reads the stack, by n.
    full = await citation_list(
        firm.person(), CitationFilters("workpaper_cell", anchor), cursor=None, limit=None
    )
    assert [v.n for v in full.items] == [1, 2] and full.total == 2


async def test_ac5_a_client_principal_is_refused_every_citation_read(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(firm, [CitationClaim("document_text", _doc(version, 1))])
    client = dataclasses.replace(firm.person(), client=True)
    with pytest.raises(Forbidden) as one:
        await citation_display(client, cited.id)
    with pytest.raises(Forbidden) as listed:
        await citation_list(client, CitationFilters(), cursor=None, limit=None)
    assert one.value.layer == listed.value.layer == "role"  # 403


async def test_ac5_unknown_and_other_firm_citations_are_404(seed: Seeder) -> None:
    firm = await make_firm(seed)
    elsewhere = await make_firm(seed)
    version = await _layered(elsewhere)
    [theirs] = await _cite(elsewhere, [CitationClaim("document_text", _doc(version, 1))])
    for citation_id in (uuid.uuid4(), theirs.id):
        with pytest.raises(NotFound):
            await citation_display(firm.person(), citation_id)


async def test_ac12_an_unverified_citation_is_never_returned_as_verified(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [fake] = await _cite(
        firm, [CitationClaim("document_text", _doc(version, 3), quote="Total liabilities 1.00")]
    )
    view = await citation_display(firm.person(), fake.id)
    assert (view.verified, view.verification_reason) == (False, "quote_not_found")
    assert view.quote is None and view.value_text is None


async def test_ac12_a_hash_the_layer_no_longer_holds_reads_changed_and_unverified(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(
        firm, [CitationClaim("document_text", _doc(version, 3), quote="Net assets")]
    )
    # A forged row: the same box with a digest no run of its words has.
    row = await seed.rows("SELECT * FROM citations WHERE id = $1", cited.id)
    forged = await seed.id(
        "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
        "kind, source_type, source_id, locator, match_id, quote_sha256, verified, "
        "verifier_version, created_by_kind, created_by_user_id) VALUES ($1, $2, "
        "'workpaper_cell', $3, 1, 'document_text', 'evidence_version', $4, $5::jsonb, $6, "
        "$7, true, 'v1', 'human', $8) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        uuid.uuid4(),
        version,
        row[0]["locator"],
        row[0]["match_id"],
        b"\x00" * 32,
        firm.user_id,
    )
    view = await citation_display(firm.person(), forged)
    assert (view.quote, view.quote_state) == (None, "changed")
    assert (view.verified, view.verification_reason) == (False, "quote_not_found")


async def test_a_re_read_quote_is_masked_where_pii_was_detected(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(
        firm,
        [CitationClaim("document_text", _doc(version, 2), quote="Employee SSN 000-00-6081")],
    )
    locator = await seed.value("SELECT locator::text FROM citations WHERE id = $1", cited.id)
    assert "bbox" in str(locator)
    # The SSN's word, where the layer put it on page 2 (T13 writes these; seeded here).
    async with tenant_session(firm.system) as session:
        pages = await pages_of(
            session, evidence_version_id=version, extractor_version=WORDS_VERSION
        )
    layer = await read_page_layer(firm.tenant_id, pages[1])
    [ssn] = [w for w in layer.words if w.text == "000-00-6081"]
    await seed.run(
        "INSERT INTO pii_regions (tenant_id, evidence_version_id, page_no, bbox, kind, "
        "value_sealed, last4, label_anchored, detector_version) VALUES ($1, $2, 2, "
        "$3::numeric[], 'ssn', '\\x00'::bytea, '6081', true, $4)",
        firm.tenant_id,
        version,
        [ssn.x0, ssn.top, ssn.x1, ssn.bottom],
        DETECTOR_VERSION,
    )
    await scanned(seed, firm, [1, 2, 3], version=version)
    view = await citation_display(firm.person(), cited.id)
    assert view.quote_state == "shown"
    assert view.quote == "Employee SSN •••-••-6081"
    assert "000-00" not in str(view)


async def test_state_is_computed_from_events_and_relink_offered_when_held(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    [moved, broken] = await _cite(
        firm,
        [
            CitationClaim("document_text", _doc(version, 3), quote="Net assets"),
            CitationClaim("document_text", _doc(version, 1), quote="Harborline"),
        ],
    )
    for citation_id, kind in ((moved.id, "moved"), (broken.id, "broken")):
        await seed.run(
            "INSERT INTO citation_events (tenant_id, citation_id, kind, cause_ref, actor_kind) "
            "VALUES ($1, $2, $3, 'evidence_version:next', 'system')",
            firm.tenant_id,
            citation_id,
            kind,
        )
    view = await citation_display(firm.person(), moved.id)
    assert view.state == "moved" and view.moved is not None
    assert view.moved.successor_ref == "evidence_version:next"
    assert view.allowed_actions == ["citation.relink"]
    other = await citation_display(firm.person(), broken.id)
    assert (other.state, other.allowed_actions, other.moved) == ("broken", [], None)


async def test_used_in_counts_the_anchors_citing_the_same_match(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    claim = CitationClaim("document_text", _doc(version, 3), quote="Net assets")
    [first] = await _cite(firm, [claim])
    await _cite(firm, [claim])
    assert (await citation_display(firm.person(), first.id)).used_in == 2


async def test_lists_filter_by_host_section_source_and_kind(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _layered(firm)
    other = await _layered(firm)
    host = uuid.uuid4()
    await _cite(
        firm,
        [
            CitationClaim("document_text", _doc(version, 3), quote="Net assets"),
            CitationClaim("document_text", _doc(other, 1), quote="Harborline"),
        ],
        anchor_id=host,
    )
    me: AuthContext = firm.person()
    by_host = await citation_list(
        me,
        CitationFilters(host_ref=f"workpaper_cell:{host}", section_id="service-orgs"),
        cursor=None,
        limit=None,
    )
    assert by_host.total == 2
    into = await citation_list(
        me,
        CitationFilters(host_ref=f"workpaper_cell:{host}", source_version_id=version),
        cursor=None,
        limit=None,
    )
    assert [v.source.evidence_version_id for v in into.items] == [version]
    none = await citation_list(me, CitationFilters(kind="sheet_cell"), cursor=None, limit=None)
    assert none.total == 0
    bad = await citation_list(me, CitationFilters(host_ref="nonsense"), cursor=None, limit=None)
    assert bad.total == 0
    paged = await citation_list(
        me, CitationFilters(host_ref=f"workpaper_cell:{host}"), cursor=None, limit=1
    )
    assert len(paged.items) == 1 and paged.next_cursor is not None
    rest = await citation_list(
        me, CitationFilters(host_ref=f"workpaper_cell:{host}"), cursor=paged.next_cursor, limit=1
    )
    assert [v.n for v in rest.items] == [2] and rest.next_cursor is None


async def test_a_quote_on_a_page_never_scanned_for_pii_is_withheld(seed: Seeder) -> None:
    """Security review #1: a page no PII scan covers is never quoted raw (fail closed)."""
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(
        firm,
        [CitationClaim("document_text", _doc(version, 2), quote="Employee SSN 000-00-6081")],
    )
    view = await citation_display(firm.person(), cited.id)
    assert (view.quote, view.quote_state, view.verified) == (None, "withheld", True)
    await scanned(seed, firm, [1, 3], version=version)  # page 2 still not scanned
    assert (await citation_display(firm.person(), cited.id)).quote_state == "withheld"
    events = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    assert events == 0  # nothing shown, nothing logged as read


async def test_a_shown_quote_leaves_an_access_event_first(seed: Seeder) -> None:
    """Security review #2: a re-read quote is content (Restricted): its read is logged."""
    firm = await make_firm(seed)
    version = await _layered(firm)
    [cited] = await _cite(
        firm, [CitationClaim("document_text", _doc(version, 3), quote="Net assets")]
    )
    await scanned(seed, firm, [1, 2, 3], version=version)
    view = await citation_display(firm.person(), cited.id)
    assert view.quote == "Net assets"
    [event] = await seed.rows(
        "SELECT kind, subject_type, subject_id, engagement_id, actor_id FROM access_events "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert (event["kind"], event["subject_type"], event["subject_id"]) == (
        "evidence_content.read",
        "evidence_version",
        version,
    )
    assert event["engagement_id"] == firm.engagement_id
    listed = await citation_list(firm.person(), CitationFilters(), cursor=None, limit=None)
    assert [v.quote for v in listed.items] == ["Net assets"]
    count = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    assert count == 2  # the list's quote is logged too


async def test_a_title_never_names_a_file_outside_the_citations_engagement(seed: Seeder) -> None:
    """Security review #3: an unverified row, or one whose source isn't in its engagement, is
    titled by its kind; the file is never looked up."""
    firm = await make_firm(seed)
    other, _ = await _second_engagement(firm)
    theirs = await _layered(firm, other)
    [refused] = await _cite(
        firm, [CitationClaim("document_text", _doc(theirs, 1), quote="Harborline")]
    )
    view = await citation_display(firm.person(), refused.id)
    assert (view.verified, view.verification_reason) == (False, "source_not_found")
    assert (view.title, view.loc) == ("Document", "")
    forged = await seed.id(
        "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
        "kind, source_type, source_id, locator, verified, verifier_version, created_by_kind, "
        "created_by_user_id) VALUES ($1, $2, 'workpaper_cell', $3, 1, 'document_text', "
        "'evidence_version', $4, $5::jsonb, true, 'v1', 'human', $6) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        uuid.uuid4(),
        theirs,
        f'{{"evidence_version_id": "{theirs}", "page": 1}}',
        firm.user_id,
    )
    title = (await citation_display(firm.person(), forged)).title
    assert title == "Document" and not title.startswith("Upload ")
