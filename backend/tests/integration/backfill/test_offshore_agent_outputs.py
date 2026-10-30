# ac-test-author: ayushkbhatia
"""TASK-1207 re-check (DEC-52, DEC-319; SPEC-322 AC-25, P-03-T15): stored content that quotes a
client's documents never reaches an offshore member unmasked.

Masking an agent's input at run time doesn't cover what earlier, unmasked runs stored: verbatim
quotes, values and rationales, started by onshore people. Until masked projections of those
outputs exist, an offshore reader is refused them (403 at the condition layer, after each route's
own authorise), or, on a route that mixes metadata with quoted content, gets the metadata with
the quoted fields left out. Here the client's W-2 (box a: SSN 000-00-6081) is uploaded and
processed, and every stored output that quotes it is seeded with the raw SSN, as an earlier
onshore run would have written it.

The sweep walks every served GET route outside the portal, with this engagement's, client's,
version's, inbox file's, run's, screening result's and citation's ids filled in: wherever Mia
(onshore, the same roles) reads the raw SSN, Remy (offshore) gets 403 or a body without it; and
Mia reads it on each surface the review named, so the sweep can't pass by finding nothing. The
POST routes that return content are checked one by one. Boundary: `create_app()` over HTTP, the
migrated Postgres (superuser seeding where no route makes the row), the compose S3 image and the
processing activities.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, cast

import pytest
from types_boto3_s3 import S3Client

from abacus.api import create_app
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    UploadInput,
    check_upload_content,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.words import words_upload
from abacus_tools.codegen.security_tests import served
from abacus_tools.synthetic.documents import w2_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "task1207-agent-outputs"
MASTER: Final = b"task1207-agent-outputs-master-key-0123456"
PDF: Final = "application/pdf"
SSN: Final = "000-00-6081"
QUOTED: Final = f"Employee SSN {SSN}"
FORBIDDEN: Final = {"detail": "forbidden"}
_PARAM: Final = re.compile(r"\{(\w+)\}")
# The surfaces the re-check named, by the GET path the sweep calls: Mia reads the SSN on each.
NAMED: Final = (
    "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/review",  # 1
    "/v1/engagements/{engagement_id}/inbox-matches",  # 2
    "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads/{version_id}/statement",  # 4
    "/v1/engagements/{engagement_id}/review-queue",  # 6
    "/v1/engagements/{engagement_id}/screening-results",  # 6
    "/v1/agent-runs/{run_id}/trace",  # 7
    "/v1/citations/{citation_id}",  # 9
)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    mia: Person
    remy: Person
    site: Site
    ids: dict[str, uuid.UUID]

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    def fill(self, path: str) -> str:
        known = {
            "engagement_id": self.site.engagement_id,
            "client_id": self.site.client_id,
            "item_id": self.site.item_id,
            **self.ids,
        }

        def one(match: re.Match[str]) -> str:
            name = match.group(1)
            if name == "page_no":
                return "1"
            if name == "which":
                return "acceptance"
            return str(known.get(name, uuid.uuid4()))

        return _PARAM.sub(one, path)


async def _value(seed: Seeder, sql: str, *args: object) -> uuid.UUID:
    return cast(uuid.UUID, await seed.value(sql, *args))


_RUN: Final = (
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "evidence_version_id, inbox_file_id, initiator_user_id, task_scope, status, finished_at) "
    "VALUES ($1, $2, 1, $3, $4, $5, $6, ARRAY['evidence.read'], 'completed', now()) RETURNING id"
)


async def _run(
    seed: Seeder,
    firm: uuid.UUID,
    site: Site,
    agent_id: str,
    who: Person,
    *,
    evidence_version_id: uuid.UUID | None = None,
    inbox_file_id: uuid.UUID | None = None,
) -> uuid.UUID:
    return await _value(
        seed,
        _RUN,
        firm,
        agent_id,
        site.engagement_id,
        evidence_version_id,
        inbox_file_id,
        who.user_id,
    )


async def _derived(
    seed: Seeder, firm: uuid.UUID, site: Site, mia: Person, version: uuid.UUID, inbox: uuid.UUID
) -> dict[str, uuid.UUID]:
    """What earlier onshore runs and reviews stored about the W-2, each quoting the raw SSN."""
    quote = (
        f'[{{"cell": "B2", "quote": "{QUOTED}", "value": "{SSN}", "verified": true, '
        '"reason": null}]'
    )
    screen = await _run(seed, firm, site, "evidence.screener", mia, evidence_version_id=version)
    result = await _value(
        seed,
        "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
        "($1, $2, $3, $4, 'needs_revision', 0.5, $5, $6::jsonb, '[]') RETURNING id",
        firm,
        site.engagement_id,
        version,
        screen,
        QUOTED,
        quote,
    )
    review_run = await _run(
        seed, firm, site, "evidence.upload_reviewer", mia, evidence_version_id=version
    )
    review = await _value(
        seed,
        "INSERT INTO upload_reviews (tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, prompt_ref, no_concerns) VALUES ($1, $2, $3, $4, "
        "'evidence.upload_reviewer@v1', false) RETURNING id",
        firm,
        site.engagement_id,
        version,
        review_run,
    )
    await seed.run(
        "INSERT INTO upload_review_flags (tenant_id, review_id, position, category, "
        "confidence, rationale, citations, shown) VALUES ($1, $2, 1, 'altered', 0.9, $3, "
        "$4::jsonb, true)",
        firm,
        review,
        QUOTED,
        f'[{{"page": 1, "quote": "{QUOTED}", "verified": true}}]',
    )
    match_run = await _run(seed, firm, site, "evidence.matcher", mia, inbox_file_id=inbox)
    match = await _value(
        seed,
        "INSERT INTO inbox_match_runs (tenant_id, engagement_id, inbox_file_id, agent_run_id, "
        "prompt_ref, none_fit) VALUES ($1, $2, $3, $4, 'evidence.inbox_match@v2', false) "
        "RETURNING id",
        firm,
        site.engagement_id,
        inbox,
        match_run,
    )
    await seed.run(
        "INSERT INTO inbox_match_proposals (tenant_id, match_id, rank, request_item_id, "
        "confidence, rationale, citations, shown) VALUES ($1, $2, 1, $3, 0.8, $4, $5::jsonb, "
        "true)",
        firm,
        match,
        site.item_id,
        QUOTED,
        f'[{{"page": 1, "quote": "{QUOTED}", "verified": true}}]',
    )
    citation = await _value(
        seed,
        "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
        "kind, source_type, source_id, locator, match_id, quote_sha256, value_text, verified, "
        "verifier_version, created_by_kind, created_by_run_id) VALUES ($1, $2, "
        "'upload_review', $3, 1, 'document_text', 'evidence_version', $4, "
        "'{\"page\": 1}', $5, $6, $7, true, 'v1', 'agent', $8) RETURNING id",
        firm,
        site.engagement_id,
        review,
        version,
        f"ev:{version.hex[:12]}#p1",
        bytes(32),
        SSN,
        review_run,
    )
    await seed.run(
        "INSERT INTO statement_datasets (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, format, account_kind, issuer, last4, opening, closing, "
        "opening_source, closing_source, included_total, line_count, excluded_count, "
        "approved_by, actor_kind) VALUES ($1, $2, $3, $4, 'pdf_text', 'bank', $5, '6081', "
        "100, 150, 'printed', 'printed', 50, 1, 0, $6, 'human')",
        firm,
        site.engagement_id,
        site.item_id,
        version,
        QUOTED,
        mia.user_id,
    )
    return {
        "version_id": version,
        "file_id": inbox,
        "run_id": screen,
        "screening_result_id": result,
        "review_run": review_run,
        "citation_id": citation,
    }


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in (
        "uploads.processing",
        "evidence.viewer_v1",
        "evidence.citations_v2",
        "evidence.pii_reveal",
    ):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1207')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Ashford")
    mia = await seed.person(tenant_id)
    remy = await seed.person(tenant_id)
    for who in (mia, remy):
        await seed.member(site, who, "manager")
    admin = await seed.client_contact(site, "client_admin")
    uploaded = await net.http.post(
        f"/v1/engagements/{site.engagement_id}/request-items/{site.item_id}/uploads",
        params={"filename": "w2.pdf"},
        content=w2_pdf(),
        headers={**net.headers(admin), "Content-Type": PDF},
    )
    assert uploaded.status_code == 201, uploaded.text
    version = uuid.UUID(uploaded.json()["evidence_version_id"])
    dropped = await net.http.post(
        f"/v1/engagements/{site.engagement_id}/inbox",
        params={"filename": "w2.pdf"},
        content=w2_pdf(),
        headers={**net.headers(mia), "Content-Type": PDF},
    )
    assert dropped.status_code == 201, dropped.text
    inbox = uuid.UUID(dropped.json()["id"])
    for given in (
        UploadInput(str(tenant_id), UPLOAD_VERSION, str(version)),
        UploadInput(str(tenant_id), UPLOAD_INBOX, str(inbox)),
    ):
        await extract_upload(given)
        await check_upload_content(given)
        await preview_upload(given)
        await words_upload(given)
    ids = await _derived(seed, tenant_id, site, mia, version, inbox)
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        tenant_id,
        remy.user_id,
    )
    return Firm(net, tenant_id, owner, mia, remy, site, ids)


def _swept() -> list[str]:
    """Every served GET route a firm member may call (the portal's are a client's)."""
    guarded, _ = served(create_app())
    return sorted({p for m, p, _ in guarded if m == "GET" and not p.startswith("/v1/portal")})


async def test_recheck_the_sweep_finds_no_raw_ssn_for_an_offshore_reader(firm: Firm) -> None:
    routes = _swept()
    assert len(routes) > 150
    extra = (
        f"/v1/citations?source_version_id={firm.ids['version_id']}",
        f"/v1/evidence-versions/{firm.ids['version_id']}/regions",
    )
    raw_for_mia: set[str] = set()
    leaks: list[str] = []
    for route in [*routes, *extra]:
        path = firm.fill(route)
        mia = await firm.net.call("GET", path, firm.mia)
        if mia.status_code >= 300 or SSN not in mia.text:
            continue
        raw_for_mia.add(route)
        remy = await firm.net.call("GET", path, firm.remy)
        if remy.status_code == 403:
            assert remy.json() == FORBIDDEN, route
            continue
        if SSN in remy.text:
            leaks.append(f"{route}: {remy.status_code}")
    assert leaks == [], "\n".join(leaks)
    assert set(NAMED) <= raw_for_mia  # not vacuous: each named surface held the raw SSN


async def test_recheck_the_named_stored_outputs_are_refused_at_the_condition(firm: Firm) -> None:
    """Items 1 to 4, 6 and 7: refused outright (the queue keeps its metadata, below)."""
    for route in NAMED:
        if route.endswith(("/review-queue", "/citations/{citation_id}")):
            continue
        response = await firm.net.call("GET", firm.fill(route), firm.remy)
        assert (response.status_code, response.json()) == (403, FORBIDDEN), route
    assessments = f"{firm.base}/procedures/{uuid.uuid4()}/assessments"  # 3
    assert (await firm.net.call("GET", assessments, firm.remy)).status_code == 403
    assert (await firm.net.call("GET", assessments, firm.mia)).status_code != 403


async def test_recheck_the_review_queue_keeps_its_metadata_without_the_quotes(firm: Firm) -> None:
    """Item 6, mixed route: the entry and its proposal's action stay (a reviewer can still take
    and decide it); its rationale, citations and unverified claims are left out."""
    mine = await firm.net.call("GET", f"{firm.base}/review-queue", firm.mia)
    theirs = await firm.net.call("GET", f"{firm.base}/review-queue", firm.remy)
    assert theirs.status_code == 200, theirs.text
    [m] = [e for e in mine.json() if e["proposal"] is not None]
    [r] = [e for e in theirs.json() if e["evidence_version"]["id"] == m["evidence_version"]["id"]]
    assert m["proposal"]["rationale"] == QUOTED  # the control
    assert r["proposal"]["screening_result_id"] == m["proposal"]["screening_result_id"]
    assert r["proposal"]["action"] == m["proposal"]["action"]
    assert (r["proposal"]["rationale"], r["proposal"]["citations"]) == ("", [])
    assert r["proposal"]["unverified"] == []


async def test_recheck_a_citation_leaves_out_its_raw_value_for_an_offshore_reader(
    firm: Firm,
) -> None:
    """Item 9: the printed value is raw; the masked quote and the rest stay."""
    path = f"/v1/citations/{firm.ids['citation_id']}"
    mine = await firm.net.call("GET", path, firm.mia)
    theirs = await firm.net.call("GET", path, firm.remy)
    assert mine.status_code == theirs.status_code == 200, (mine.text, theirs.text)
    assert mine.json()["value_text"] == SSN  # the control
    assert theirs.json()["value_text"] is None
    assert theirs.json()["id"] == mine.json()["id"]


async def test_recheck_the_content_posts_refuse_an_offshore_member(firm: Firm) -> None:
    """Item 4's preview and approval, and item 7's trace export."""
    statement = f"{firm.base}/request-items/{firm.site.item_id}/uploads/{firm.ids['version_id']}"
    for path, body in (
        (f"{statement}/statement/preview", {}),
        (f"{statement}/statement/approve", {}),
        (f"/v1/agent-runs/{firm.ids['run_id']}/trace-exports", {"format": "json"}),
    ):
        remy = await firm.net.call("POST", path, firm.remy, body=body)
        assert (remy.status_code, remy.json()) == (403, FORBIDDEN), path
        mia = await firm.net.call("POST", path, firm.mia, body=body)
        assert mia.status_code != 403, (path, mia.text)


async def test_recheck_a_wall_still_comes_first(firm: Firm) -> None:
    await firm.net.wall(firm.owner, firm.remy, firm.site)
    for route in NAMED:
        response = await firm.net.call("GET", firm.fill(route), firm.remy)
        assert response.status_code == 404, (route, response.text)


async def test_recheck_the_retired_setup_file_serves_no_one(firm: Firm) -> None:
    """Item 5: the stored acceptance documentation was raw client content (as the signed letter)
    and an offshore member was refused its bytes. P-07-T59 (DEC-906) retired the attachment with
    `engagement_acceptance`: the route stores and serves nothing, onshore or offshore."""
    partner = await firm.seed.person(firm.tenant_id)
    await firm.seed.member(firm.site, partner, "engagement_partner")
    stored = await firm.net.http.post(
        f"{firm.base}/acceptance/file",
        params={"filename": "acceptance.pdf"},
        content=w2_pdf(),
        headers={**firm.net.headers(partner), "Content-Type": PDF},
    )
    assert stored.status_code in (404, 405), stored.text
    # `GET …/{which}/file` serves the signed letter only; `acceptance` is not a `which` (422).
    path = f"{firm.base}/acceptance/file"
    for who in (firm.mia, firm.remy):
        response = await firm.net.call("GET", path, who)
        assert response.status_code in (404, 405, 422), response.text
