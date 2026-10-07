"""AC-18, AC-20: the board reads over HTTP (TASK-012 interface contract, "board reads").

`GET request-items` (with `evidence_version_id`), `GET evidence-versions` and
`GET screening-results`. A retrieved trial balance comes from the real retrieval pipeline and the
results from the real screener with a fake model. Rows are seeded through the shared `Seeder`.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import httpx
import pytest

from abacus.ai_gateway import FakeModel, ModelRequest, ModelResponse, configure_provider
from abacus.api import create_app
from abacus.api.export_openapi import document
from abacus.modules.agents.api import (
    create_screening_run,
    install_fake_responses,
    load_agent_context,
    screen,
)
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World, retrieve, uploaded_version

Json = dict[str, object]
ROLES = ["engagement_partner", "manager", "senior", "staff", "reviewer"]
VERSION_KEYS = {
    "id",
    "evidence_item_id",
    "version_no",
    "method",
    "source",
    "pulled_at",
    "period_start",
    "period_end",
    "created_at",
}
RESULT_KEYS = {
    "id",
    "evidence_version_id",
    "action",
    "confidence",
    "rationale",
    "citations",
    "unverified",
    "created_at",
}
CITATION_KEYS = {"cell", "quote", "value", "verified", "reason"}
ITEM_KEYS = {
    "id",
    "engagement_id",
    "description",
    "audit_area",
    "status",
    "created_at",
    "evidence_version_id",
}
FORBIDDEN_WORDS = ("content", "storage", "key", "fingerprint", "sha256", "size_bytes", "tenant")
READS = ["request-items", "evidence-versions", "screening-results"]


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@dataclass(frozen=True)
class Api:
    http: httpx.AsyncClient
    idp: FakeIdentityProvider
    seed: Seeder

    async def token(self, who: Person) -> dict[str, str]:
        subject = await self.seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id)
        return {"Authorization": f"Bearer {self.idp.token(str(subject))}"}

    async def read(self, read: str, who: Person | None, engagement_id: object) -> httpx.Response:
        headers = {} if who is None else await self.token(who)
        return await self.http.get(f"/v1/engagements/{engagement_id}/{read}", headers=headers)

    async def list(self, read: str, who: Person, engagement_id: object) -> list[Json]:
        response = await self.read(read, who, engagement_id)
        assert response.status_code == 200, response.text
        return cast(list[Json], response.json())


@pytest.fixture
def api(http: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder) -> Api:
    return Api(http, idp, seed)


class Provider:
    """The stock fake screener, optionally with citations that cannot be verified."""

    def __init__(self) -> None:
        self.inner = FakeModel()
        install_fake_responses(self.inner)
        self.fabricate = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        response = await self.inner.complete(request)
        if not self.fabricate:
            return response
        output = cast(Json, json.loads(response.text))
        stock = cast(list[Json], output["citations"])
        output["rationale"] = "Second look: a figure does not match."
        output["confidence"] = 0.5
        output["citations"] = [
            *stock,
            {"cell": "Z99", "value": "1.00"},
            {"cell": stock[0]["cell"], "value": "1.00"},
        ]
        return ModelResponse(
            json.dumps(output), response.input_tokens, response.output_tokens, response.model
        )


@pytest.fixture
def provider() -> Iterator[Provider]:
    made = Provider()
    configure_provider(made)
    yield made
    configure_provider(None)


async def _screen(world: World, version_id: uuid.UUID) -> uuid.UUID:
    """One screening of the version (a fresh event each time); the run's id."""
    run_id = await create_screening_run(
        world.tenant_id, version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    await screen(await load_agent_context(world.tenant_id, run_id))
    return run_id


async def _result_row(seed: Seeder, run_id: uuid.UUID) -> Json:
    [row] = await seed.rows("SELECT * FROM screening_results WHERE agent_run_id = $1", run_id)
    return dict(row)


async def _fulfil(
    seed: Seeder,
    world: World,
    version_id: uuid.UUID,
    created_at: datetime,
    fulfilment_id: uuid.UUID | None = None,
) -> None:
    await seed.run(
        "INSERT INTO fulfilments (id, tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id, created_at) "
        "VALUES ($1, $2, $3, $4, $5, 'human', 'test-seed', $6)",
        fulfilment_id or uuid.uuid4(),
        world.tenant_id,
        world.engagement_id,
        world.item_id,
        version_id,
        created_at,
    )


async def _member(seed: Seeder, world: World, role: str) -> Person:
    who = await seed.person(world.tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        world.tenant_id,
        world.engagement_id,
        who.user_id,
        role,
    )
    return who


async def _other_world(seed: Seeder, world: World) -> World:
    """A second engagement in the same firm, with its own item."""
    entity_id = await seed.entity(world.tenant_id)
    engagement_id = await seed.engagement(world.tenant_id, entity_id, world.requester.user_id)
    await seed.member(engagement_id, world.requester, "staff")
    item_id = await seed.item(world.tenant_id, engagement_id, world.requester.user_id)
    connection_id = await seed.connection(world.tenant_id, entity_id)
    return World(
        world.tenant_id,
        engagement_id,
        entity_id,
        item_id,
        connection_id,
        world.requester,
        world.directory,
    )


# --- request items carry their evidence version ---------------------------------------


async def test_ac18_a_request_item_has_a_null_evidence_version_before_any_retrieval(
    api: Api, world: World
) -> None:
    [item] = await api.list("request-items", world.requester, world.engagement_id)
    assert set(item) == ITEM_KEYS
    assert item["id"] == str(world.item_id)
    assert item["evidence_version_id"] is None
    assert item["status"] == "open"


async def test_ac18_a_request_item_carries_the_retrievals_version_after_a_retrieval(
    api: Api, world: World
) -> None:
    result = await retrieve(world)
    [item] = await api.list("request-items", world.requester, world.engagement_id)
    assert item["evidence_version_id"] == str(result.evidence_version_id)
    assert item["id"] == str(world.item_id)
    assert item["engagement_id"] == str(world.engagement_id)
    assert item["description"] == "Trial balance"
    assert item["audit_area"] == "Financial reporting"
    assert item["status"] == "received"
    assert set(item) == ITEM_KEYS


async def test_ac18_a_request_item_carries_the_version_of_its_most_recent_fulfilment(
    api: Api, seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    later = await uploaded_version(seed, world)
    await _fulfil(seed, world, later, datetime.now(UTC))
    [item] = await api.list("request-items", world.requester, world.engagement_id)
    assert item["evidence_version_id"] == str(later)
    assert item["evidence_version_id"] != str(result.evidence_version_id)


async def test_ac18_the_most_recent_fulfilment_wins_whatever_the_insertion_order(
    api: Api, seed: Seeder, world: World
) -> None:
    first = await uploaded_version(seed, world)
    second = await uploaded_version(seed, world)
    await _fulfil(seed, world, second, datetime(2026, 1, 2, tzinfo=UTC))
    await _fulfil(seed, world, first, datetime(2026, 1, 1, tzinfo=UTC))
    [item] = await api.list("request-items", world.requester, world.engagement_id)
    assert item["evidence_version_id"] == str(second)


async def test_ac18_equal_fulfilment_times_are_broken_by_id(
    api: Api, seed: Seeder, world: World
) -> None:
    first = await uploaded_version(seed, world)
    second = await uploaded_version(seed, world)
    when = datetime(2026, 1, 1, tzinfo=UTC)
    low, high = sorted([uuid.uuid4(), uuid.uuid4()])
    await _fulfil(seed, world, first, when, high)
    await _fulfil(seed, world, second, when, low)
    [item] = await api.list("request-items", world.requester, world.engagement_id)
    # "by created_at, then id": the last in that order is the most recent
    assert item["evidence_version_id"] == str(first)


async def test_ac18_each_item_has_its_own_version(api: Api, seed: Seeder, world: World) -> None:
    result = await retrieve(world)
    second_item = await seed.item(world.tenant_id, world.engagement_id, world.requester.user_id)
    items = {
        str(i["id"]): i
        for i in await api.list("request-items", world.requester, world.engagement_id)
    }
    assert items[str(world.item_id)]["evidence_version_id"] == str(result.evidence_version_id)
    assert items[str(second_item)]["evidence_version_id"] is None


# --- evidence versions ------------------------------------------------------------------------


async def test_ac18_evidence_versions_is_an_empty_list_when_there_are_none(
    api: Api, world: World
) -> None:
    assert await api.list("evidence-versions", world.requester, world.engagement_id) == []


async def test_ac18_a_retrieved_version_is_listed_with_exactly_the_contract_fields(
    api: Api, seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    [version] = await api.list("evidence-versions", world.requester, world.engagement_id)
    assert set(version) == VERSION_KEYS
    assert version["id"] == str(result.evidence_version_id)
    assert version["method"] == "retrieved"
    assert version["version_no"] == 1
    [row] = await seed.rows(
        "SELECT * FROM evidence_versions WHERE id = $1", result.evidence_version_id
    )
    assert version["evidence_item_id"] == str(row["evidence_item_id"])
    assert version["source"] == row["source"]
    assert version["period_start"] == row["period_start"].isoformat()
    assert version["period_end"] == row["period_end"].isoformat()
    assert datetime.fromisoformat(cast(str, version["pulled_at"])) == row["pulled_at"]
    assert datetime.fromisoformat(cast(str, version["created_at"])) == row["created_at"]


async def test_ac18_an_uploaded_version_has_null_pull_time_and_period(
    api: Api, seed: Seeder, world: World
) -> None:
    version_id = await uploaded_version(seed, world)
    [version] = await api.list("evidence-versions", world.requester, world.engagement_id)
    assert version["id"] == str(version_id)
    assert version["method"] == "uploaded"
    assert version["pulled_at"] is None
    assert version["period_start"] is None
    assert version["period_end"] is None
    assert set(version) == VERSION_KEYS


async def test_ac18_evidence_versions_are_listed_oldest_first(
    api: Api, seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    second = await uploaded_version(seed, world)
    third = await uploaded_version(seed, world)
    versions = await api.list("evidence-versions", world.requester, world.engagement_id)
    assert [v["id"] for v in versions] == [
        str(result.evidence_version_id),
        str(second),
        str(third),
    ]
    stamps = [datetime.fromisoformat(cast(str, v["created_at"])) for v in versions]
    assert stamps == sorted(stamps)


async def test_ac18_evidence_versions_never_expose_content_keys_or_fingerprints(
    api: Api, seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    await uploaded_version(seed, world)
    response = await api.read("evidence-versions", world.requester, world.engagement_id)
    assert response.status_code == 200
    [row] = await seed.rows(
        "SELECT fingerprint, storage_key, storage_version_id FROM evidence_versions WHERE id = $1",
        result.evidence_version_id,
    )
    for hidden in (row["fingerprint"], row["storage_key"], row["storage_version_id"]):
        assert hidden not in response.text
    for version in cast(list[Json], response.json()):
        assert set(version) == VERSION_KEYS
        assert not [k for k in version if any(w in k for w in FORBIDDEN_WORDS)]


async def test_ac18_evidence_versions_are_only_this_engagements(
    api: Api, seed: Seeder, world: World
) -> None:
    mine = await uploaded_version(seed, world)
    other = await _other_world(seed, world)
    theirs = await uploaded_version(seed, other)
    here = await api.list("evidence-versions", world.requester, world.engagement_id)
    there = await api.list("evidence-versions", world.requester, other.engagement_id)
    assert [v["id"] for v in here] == [str(mine)]
    assert [v["id"] for v in there] == [str(theirs)]


# --- screening results --------------------------------------------------------------------------


async def test_ac18_screening_results_is_an_empty_list_when_there_are_none(
    api: Api, world: World
) -> None:
    assert await api.list("screening-results", world.requester, world.engagement_id) == []


async def test_ac18_a_version_with_no_screening_has_no_result(
    api: Api, seed: Seeder, world: World
) -> None:
    await retrieve(world)
    await uploaded_version(seed, world)
    assert await api.list("screening-results", world.requester, world.engagement_id) == []


async def test_ac18_a_screening_result_has_the_contract_fields_and_a_three_place_confidence(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    run_id = await _screen(world, result.evidence_version_id)
    row = await _result_row(seed, run_id)
    [found] = await api.list("screening-results", world.requester, world.engagement_id)
    assert set(found) == RESULT_KEYS
    assert found["id"] == str(row["id"])
    assert found["evidence_version_id"] == str(result.evidence_version_id)
    assert found["action"] == row["action"]
    assert found["action"] in {"ready_for_review", "needs_revision"}
    confidence = found["confidence"]
    assert isinstance(confidence, str)
    assert Decimal(confidence) == row["confidence"]
    assert len(confidence.split(".")[1]) == 3
    assert found["rationale"] == row["rationale"]
    assert found["unverified"] == json.loads(cast(str, row["unverified"]))
    assert datetime.fromisoformat(cast(str, found["created_at"])) == row["created_at"]


async def test_ac18_verified_citations_carry_their_cell_value_and_no_reason(
    api: Api, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    await _screen(world, result.evidence_version_id)
    [found] = await api.list("screening-results", world.requester, world.engagement_id)
    citations = cast(list[Json], found["citations"])
    assert citations
    for citation in citations:
        assert set(citation) == CITATION_KEYS
        assert citation["verified"] is True
        assert citation["reason"] is None
        assert isinstance(citation["cell"], str)
        assert isinstance(citation["value"], str)


async def test_ac18_unverified_citations_are_flagged_with_a_reason(
    api: Api, world: World, provider: Provider
) -> None:
    provider.fabricate = True
    result = await retrieve(world)
    await _screen(world, result.evidence_version_id)
    [found] = await api.list("screening-results", world.requester, world.engagement_id)
    citations = cast(list[Json], found["citations"])
    bad = [c for c in citations if c["verified"] is False]
    assert len(bad) >= 2
    assert {c["reason"] for c in bad} <= {"cell_not_found", "quote_mismatch", "value_mismatch"}
    assert all(c["reason"] is not None for c in bad)
    assert "Z99" in {c["cell"] for c in bad}
    assert [c for c in citations if c["verified"] is True]
    assert all(set(c) == CITATION_KEYS for c in citations)
    assert found["action"] == "needs_revision"
    assert found["unverified"]
    assert all(isinstance(u, str) for u in cast(list[object], found["unverified"]))


async def test_ac18_the_latest_screening_of_a_version_is_the_only_one_listed(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    first = await _result_row(seed, await _screen(world, result.evidence_version_id))
    provider.fabricate = True
    second = await _result_row(seed, await _screen(world, result.evidence_version_id))
    assert cast(datetime, second["created_at"]) > cast(datetime, first["created_at"])
    assert await seed.count("screening_results", world.tenant_id) == 2
    found = await api.list("screening-results", world.requester, world.engagement_id)
    assert [r["id"] for r in found] == [str(second["id"])]
    assert found[0]["rationale"] == "Second look: a figure does not match."
    assert found[0]["confidence"] == "0.500"


async def test_ac18_screening_results_are_only_this_engagements(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    mine = await _result_row(seed, await _screen(world, result.evidence_version_id))
    other = await _other_world(seed, world)
    assert await api.list("screening-results", world.requester, other.engagement_id) == []
    here = await api.list("screening-results", world.requester, world.engagement_id)
    assert [r["id"] for r in here] == [str(mine["id"])]


async def test_ac18_there_is_no_route_that_acts_on_a_screening_result(
    api: Api, world: World
) -> None:
    path = f"/v1/engagements/{world.engagement_id}/screening-results"
    headers = await api.token(world.requester)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = await api.http.request(method, path, headers=headers)
        assert response.status_code in {404, 405}, (method, response.status_code)


# --- permissions and tenancy ----------------------------------------------------------------


@pytest.mark.parametrize("read", READS)
@pytest.mark.parametrize("role", ROLES)
async def test_ac20_every_engagement_role_including_reviewer_may_read(
    api: Api, seed: Seeder, world: World, read: str, role: str
) -> None:
    who = await _member(seed, world, role)
    response = await api.read(read, who, world.engagement_id)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


@pytest.mark.parametrize("read", READS)
async def test_ac20_a_firm_member_with_no_relationship_to_the_engagement_gets_403(
    api: Api, seed: Seeder, world: World, read: str
) -> None:
    outsider = await seed.person(world.tenant_id)
    response = await api.read(read, outsider, world.engagement_id)
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


@pytest.mark.parametrize("read", READS)
async def test_ac20_a_member_of_another_engagement_only_gets_403(
    api: Api, seed: Seeder, world: World, read: str
) -> None:
    other = await _other_world(seed, world)
    only_there = await seed.person(world.tenant_id)
    await seed.member(other.engagement_id, only_there, "manager")
    assert (await api.read(read, only_there, other.engagement_id)).status_code == 200
    assert (await api.read(read, only_there, world.engagement_id)).status_code == 403


@pytest.mark.parametrize("read", READS)
async def test_ac20_another_firms_engagement_is_404_and_looks_like_an_unknown_one(
    api: Api, seed: Seeder, world: World, read: str
) -> None:
    other_firm = await seed.firm()
    stranger = await seed.person(other_firm)
    entity = await seed.entity(other_firm)
    engagement = await seed.engagement(other_firm, entity, stranger.user_id)
    await seed.member(engagement, stranger, "engagement_partner")
    foreign = await api.read(read, stranger, world.engagement_id)
    unknown = await api.read(read, stranger, uuid.uuid4())
    assert foreign.status_code == 404
    assert unknown.status_code == 404
    assert foreign.json() == unknown.json()
    assert (await api.read(read, world.requester, engagement)).status_code == 404


@pytest.mark.parametrize("read", READS)
async def test_ac20_an_unknown_engagement_is_404(api: Api, world: World, read: str) -> None:
    response = await api.read(read, world.requester, uuid.uuid4())
    assert response.status_code == 404


@pytest.mark.parametrize("read", READS)
async def test_ac20_an_unauthenticated_request_is_401(api: Api, world: World, read: str) -> None:
    assert (await api.read(read, None, world.engagement_id)).status_code == 401
    garbage = await api.http.get(
        f"/v1/engagements/{world.engagement_id}/{read}",
        headers={"Authorization": "Bearer not-a-token"},
    )
    assert garbage.status_code == 401


@pytest.mark.parametrize("read", READS)
async def test_ac20_a_person_whose_membership_was_revoked_gets_no_data(
    api: Api, seed: Seeder, world: World, read: str
) -> None:
    who = await _member(seed, world, "senior")
    await seed.revoke(who)
    assert (await api.read(read, who, world.engagement_id)).status_code in {401, 403, 404}


async def test_ac20_an_archived_engagement_remains_readable(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    await _screen(world, result.evidence_version_id)
    reviewer = await _member(seed, world, "reviewer")
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    for who in (world.requester, reviewer):
        [item] = await api.list("request-items", who, world.engagement_id)
        assert item["evidence_version_id"] == str(result.evidence_version_id)
        [version] = await api.list("evidence-versions", who, world.engagement_id)
        assert version["id"] == str(result.evidence_version_id)
        [screened] = await api.list("screening-results", who, world.engagement_id)
        assert screened["evidence_version_id"] == str(result.evidence_version_id)


async def test_ac20_reads_change_nothing_but_the_audited_screening_read(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    result = await retrieve(world)
    await _screen(world, result.evidence_version_id)
    before = await seed.actions(world.tenant_id)
    for read in ("request-items", "evidence-versions"):
        await api.list(read, world.requester, world.engagement_id)
        assert await seed.actions(world.tenant_id) == before
    await api.list("screening-results", world.requester, world.engagement_id)
    after = await seed.events(world.tenant_id)
    assert [e.action for e in after] == [*before, "screening_result.read"]
    assert after[-1].target_id == str(world.engagement_id)
    assert await seed.count("screening_results", world.tenant_id) == 1
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac20_a_screening_read_that_returns_nothing_writes_no_audit_event(
    api: Api, seed: Seeder, world: World, provider: Provider
) -> None:
    before = await seed.actions(world.tenant_id)
    assert await api.list("screening-results", world.requester, world.engagement_id) == []
    assert await seed.actions(world.tenant_id) == before


def test_ac20_the_openapi_document_has_the_board_read_operations() -> None:
    paths = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
    base = "/v1/engagements/{engagement_id}"
    versions = paths[f"{base}/evidence-versions"]
    results = paths[f"{base}/screening-results"]
    assert set(versions) == {"get"}
    assert set(results) == {"get"}
    assert versions["get"]["operationId"] == "list_evidence_versions"
    assert results["get"]["operationId"] == "list_screening_results"
