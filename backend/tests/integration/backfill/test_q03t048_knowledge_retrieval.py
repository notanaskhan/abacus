# ac-test-author: ayushkbhatia
"""SPEC-009 AC-1, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9 (TASK-024; Q-03-T048, TASK-1439): firm
knowledge is added, embedded and searched, and retrieval never returns another firm's chunk.

Boundary: `create_app()` over HTTP on the migrated Postgres (pgvector) as the firm's people. The
embedding workflow's one activity, `knowledge.embed_batch`, is run as the batch-class workflow
runs it (until it reports done), with the synthetic embedder the test environment configures.
Rows are read back through the superuser only to check what the routes cannot show (chunks,
usage records, the index design).

Q-03-T048's line "walled engagements' chunks are excluded" is read against SPEC-009 §9:
knowledge is firm-wide, names no client and carries no engagement, so walls do not apply and no
walled engagement's text can be in it (DEC-580). The suite proves both halves: the tables hold no
engagement or client reference, and a member walled from a client searches exactly what an
unwalled colleague does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, cast

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.modules.agents.activities import embed_batch_activity
from abacus.modules.agents.workflow_types import KnowledgeInput

from .support import Net, Person, Seeder, Site

DOCS: Final = "/v1/knowledge/documents"
SEARCH: Final = "/v1/knowledge/search"
NOT_FOUND: Final = {"detail": "not found"}


def _manual(marker: str) -> str:
    """A small firm methodology note: two headed sections, a distinctive word in each."""
    return (
        f"# Cash\n\nConfirm every bank balance at year end. Reconcile {marker} accounts to the "
        "general ledger and inspect the cut-off.\n\n"
        f"## Leases\n\nRead each lease agreement and recompute the {marker} liability from its "
        "payment schedule.\n"
    )


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    staff: Person
    walled: Person
    client: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def add(self, text: str, *, title: str = "Audit manual") -> httpx.Response:
        return await self.net.call(
            "POST",
            DOCS,
            self.admin,
            body={
                "title": title,
                "source_kind": "firm_own",
                "media_type": "text/markdown",
                "text": text,
            },
        )

    async def ready(self, text: str, *, title: str = "Audit manual") -> uuid.UUID:
        """Add `text` and run the embedding workflow's batches until it reports done."""
        added = await self.add(text, title=title)
        assert added.status_code == 201, added.text
        document = uuid.UUID(added.json()["id"])
        for _ in range(50):
            given = KnowledgeInput(str(self.tenant_id), str(document))
            outcome = await embed_batch_activity(given)
            if outcome.done:
                break
        read = await self.net.call("GET", f"{DOCS}/{document}", self.admin)
        assert read.json()["status"] == "ready", read.text
        return document

    async def search(self, query: str, who: Person | None = None, k: int = 20) -> httpx.Response:
        return await self.net.call(
            "POST", SEARCH, who or self.staff, body={"query": query, "k": k}
        )


async def _firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Knowledge")
    staff = await seed.person(tenant_id)
    walled = await seed.person(tenant_id)
    await seed.member(site, staff, "staff")
    await seed.member(site, walled, "staff")
    client = await seed.client_contact(site)
    await net.wall(admin, walled, site)
    return Firm(net, tenant_id, admin, staff, walled, client, site)


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    return await _firm(net, seed)


@pytest.fixture
async def other(net: Net, seed: Seeder) -> Firm:
    return await _firm(net, seed)


def _ids(response: httpx.Response) -> set[str]:
    assert response.status_code == 200, response.text
    return {str(hit["document_id"]) for hit in response.json()}


# --- Story 1: a firm adds its methodology -----------------------------------------------------


async def test_ac1_an_added_document_is_pending_chunked_audited_then_ready(firm: Firm) -> None:
    added = await firm.add(_manual("halyard"))
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["status"] == "pending"
    assert body["chunk_count"] >= 2  # the two headed sections
    document = uuid.UUID(body["id"])
    fingerprint = await firm.seed.value(
        "SELECT fingerprint FROM knowledge_documents WHERE id = $1", document
    )
    assert len(str(fingerprint)) == 64
    unembedded = await firm.seed.value(
        "SELECT count(*) FROM knowledge_chunks WHERE document_id = $1 AND embedding IS NULL",
        document,
    )
    assert int(str(unembedded)) == body["chunk_count"]
    assert "knowledge_document.added" in await firm.seed.actions(firm.tenant_id)
    for _ in range(50):
        if (await embed_batch_activity(KnowledgeInput(str(firm.tenant_id), str(document)))).done:
            break
    read = await firm.net.call("GET", f"{DOCS}/{document}", firm.admin)
    assert read.json()["status"] == "ready", read.text


async def test_ac1_only_a_firm_admin_or_practice_leader_adds_knowledge(firm: Firm) -> None:
    response = await firm.net.call(
        "POST",
        DOCS,
        firm.staff,
        body={
            "title": "Manual",
            "source_kind": "firm_own",
            "media_type": "text/markdown",
            "text": "# Cash\n\nConfirm.",
        },
    )
    assert response.status_code == 403, response.text


@pytest.mark.parametrize(
    ("change", "status"),
    [({"source_kind": "licensed"}, 422), ({"media_type": "application/pdf"}, 422)],
)
async def test_ac3_an_unknown_source_kind_or_media_type_stores_nothing(
    firm: Firm, change: dict[str, str], status: int
) -> None:
    body = {
        "title": "Manual",
        "source_kind": "firm_own",
        "media_type": "text/markdown",
        "text": _manual("tamarack"),
        **change,
    }
    response = await firm.net.call("POST", DOCS, firm.admin, body=body)
    assert response.status_code == status, response.text
    assert await _documents(firm) == 0


async def test_ac3_a_document_over_one_megabyte_answers_knowledge_too_large(firm: Firm) -> None:
    response = await firm.add("word " * 220_000)  # 1.1 MB of text
    assert (response.status_code, response.json()["detail"]) == (422, "knowledge_too_large")
    assert await _documents(firm) == 0


async def test_ac3_the_same_text_twice_answers_knowledge_duplicate(firm: Firm) -> None:
    assert (await firm.add(_manual("bollard"))).status_code == 201
    again = await firm.add(_manual("bollard"), title="Same manual")
    assert (again.status_code, again.json()["detail"]) == (409, "knowledge_duplicate")
    assert await _documents(firm) == 1


async def _documents(firm: Firm) -> int:
    count = await firm.seed.value(
        "SELECT count(*) FROM knowledge_documents WHERE tenant_id = $1", firm.tenant_id
    )
    return int(str(count))


async def test_ac4_a_withdrawn_document_leaves_search_at_once_and_is_audited(firm: Firm) -> None:
    document = await firm.ready(_manual("quillon"))
    assert str(document) in _ids(await firm.search("quillon liability lease"))
    withdrawn = await firm.net.call("POST", f"{DOCS}/{document}/withdraw", firm.admin)
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "withdrawn"
    assert str(document) not in _ids(await firm.search("quillon liability lease"))
    assert "knowledge_document.withdrawn" in await firm.seed.actions(firm.tenant_id)


# --- Story 2: embedding is a model call like any other ----------------------------------------


async def test_ac5_ingestion_and_query_embeddings_are_metered_to_the_firm(firm: Firm) -> None:
    await firm.ready(_manual("gantry"))
    before = await _embed_usage(firm)
    assert before >= 1  # the ingestion batches
    assert (await firm.search("gantry")).status_code == 200
    assert await _embed_usage(firm) == before + 1  # the query


async def _embed_usage(firm: Firm) -> int:
    count = await firm.seed.value(
        "SELECT count(*) FROM usage_records WHERE tenant_id = $1 AND prompt_id = 'embed'",
        firm.tenant_id,
    )
    return int(str(count))


async def test_ac7_a_model_change_leaves_old_chunks_out_and_reports_stale(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await firm.ready(_manual("capstan"))
    assert str(document) in _ids(await firm.search("capstan"))
    monkeypatch.setenv("ABACUS_EMBEDDING_MODEL", "fake-embed-next")
    settings.cache_clear()
    try:
        assert _ids(await firm.search("capstan")) == set()
        read = await firm.net.call("GET", f"{DOCS}/{document}", firm.admin)
        assert read.json()["status"] == "stale", read.text
    finally:
        monkeypatch.delenv("ABACUS_EMBEDDING_MODEL")
        settings.cache_clear()


# --- Story 3: recall without leaks ------------------------------------------------------------


async def test_ac8_search_returns_ranked_chunks_with_their_provenance(firm: Firm) -> None:
    document = await firm.ready(_manual("windlass"))
    response = await firm.search("windlass lease liability payment schedule", k=1)
    assert response.status_code == 200, response.text
    [hit] = response.json()
    assert hit["document_id"] == str(document)
    assert hit["title"] == "Audit manual"
    assert "Leases" in hit["heading_path"]
    assert "lease agreement" in hit["text"]
    assert isinstance(hit["position"], int) and -1.0 <= hit["score"] <= 1.0
    both = (await firm.search("windlass lease liability payment schedule", k=20)).json()
    scores = [h["score"] for h in both]
    assert scores == sorted(scores, reverse=True)


async def test_ac8_a_pending_document_is_never_returned(firm: Firm) -> None:
    added = await firm.add(_manual("sheave"))
    assert added.status_code == 201
    assert _ids(await firm.search("sheave")) == set()


@pytest.mark.parametrize("k", [0, 21])
async def test_ac8_k_is_at_most_twenty(firm: Firm, k: int) -> None:
    response = await firm.search("cash", k=k)
    assert response.status_code == 422, response.text


async def test_ac8_a_client_user_never_searches_knowledge(firm: Firm) -> None:
    await firm.ready(_manual("davit"))
    response = await firm.search("davit", firm.client)
    assert response.status_code in {403, 404}, response.text
    assert "davit" not in response.text.lower()


async def test_ac9_another_firm_with_the_same_text_never_sees_this_firms_chunks(
    firm: Firm, other: Firm
) -> None:
    marker = f"cleat{uuid.uuid4().hex[:6]}"
    mine = await firm.ready(_manual(marker))
    theirs = await other.ready(_manual(marker))
    assert _ids(await firm.search(marker)) == {str(mine)}
    assert _ids(await other.search(marker)) == {str(theirs)}
    for who in (other.admin, other.staff):
        read = await other.net.call("GET", f"{DOCS}/{mine}", who)
        assert (read.status_code, read.json()) == (404, NOT_FOUND)
        listed = await other.net.call("GET", DOCS, who)
        assert str(mine) not in listed.text
    withdraw = await other.net.call("POST", f"{DOCS}/{mine}/withdraw", other.admin)
    assert withdraw.status_code == 404, withdraw.text
    status = await firm.seed.value("SELECT status FROM knowledge_documents WHERE id = $1", mine)
    assert status == "ready"


async def test_ac9_a_person_in_two_firms_searches_only_the_firm_they_act_for(
    firm: Firm, other: Firm
) -> None:
    marker = f"bitt{uuid.uuid4().hex[:6]}"
    mine = await firm.ready(_manual(marker))
    theirs = await other.ready(_manual(marker))
    both = await firm.seed.person(firm.tenant_id, "firm_admin", also=other.tenant_id)
    as_firm = await firm.net.call(
        "POST", SEARCH, both, body={"query": marker, "k": 20}, tenant=firm.tenant_id
    )
    as_other = await firm.net.call(
        "POST", SEARCH, both, body={"query": marker, "k": 20}, tenant=other.tenant_id
    )
    assert _ids(as_firm) == {str(mine)}
    assert _ids(as_other) == {str(theirs)}


async def test_ac9_no_shared_approximate_index_spans_firms(firm: Firm) -> None:
    """Q1: exact search inside the tenant; no HNSW or IVFFlat index over every firm's vectors."""
    rows = await firm.seed.rows(
        "SELECT indexdef FROM pg_indexes WHERE tablename IN "
        "('knowledge_chunks', 'knowledge_documents')"
    )
    defs = " ".join(str(r["indexdef"]).lower() for r in rows)
    assert "hnsw" not in defs and "ivfflat" not in defs
    forced = await firm.seed.rows(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relname IN ('knowledge_chunks', 'knowledge_documents')"
    )
    assert {r["relname"]: (r["relrowsecurity"], r["relforcerowsecurity"]) for r in forced} == {
        "knowledge_chunks": (True, True),
        "knowledge_documents": (True, True),
    }


# --- Q-03-T048 walls (DEC-580: knowledge is firm-wide, SPEC-009 §9) ---------------------------


async def test_ac9_knowledge_holds_no_engagement_or_client_so_no_walled_text(firm: Firm) -> None:
    columns = await firm.seed.rows(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name IN ('knowledge_chunks', 'knowledge_documents')"
    )
    names = {str(c["column_name"]) for c in columns}
    assert not {n for n in names if "engagement" in n or "client" in n or "entity" in n}


async def test_ac9_a_walled_member_searches_exactly_what_an_unwalled_colleague_does(
    firm: Firm,
) -> None:
    marker = f"fairlead{uuid.uuid4().hex[:6]}"
    await firm.ready(_manual(marker))
    seen = await firm.search(marker, firm.staff)
    walled = await firm.search(marker, firm.walled)
    assert walled.status_code == 200, walled.text
    assert cast(list[object], walled.json()) == cast(list[object], seen.json())
    assert seen.json()  # not vacuous: the firm's manual is found
