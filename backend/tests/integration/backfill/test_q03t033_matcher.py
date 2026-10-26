# ac-test-author: ayushkbhatia
"""Q-03-T033: back-fill of TASK-064 (SPEC-033 AC-1, AC-2, AC-6: content rules with fixed-label
reasons and the followed source in the assignment audit), TASK-065 (AC-3, AC-4: the matcher's
candidate references, citation checks, the data boundary) and TASK-066 (AC-3, AC-5, AC-6: the
matcher in the product, "Suggest with AI", firm-only reads and picks for clients).

The row's promise: a match proposal never files a document without a named person's decision,
and the code rules keep their reasons.

Boundary: `create_app()` over HTTP as the firm's people and a client admin (fake-identity
tokens), the compose S3 image, the `upload_processing` stages run on the stored inbox file
(extraction, word layer and PII scan, so the matcher's material exists whether or not masking
waits for the scan), and the matcher's two Temporal activities run in an `ActivityEnvironment`
with a stub provider on a real route (`bedrock`): the fake model only, never a real one or
`make evals` (ADR-076). Expectations: SPEC-033 §4 and §5, the agent spec
`evidence.matcher` (the 0.5 confidence floor), the matrix rows `inbox_match.read` and
`inbox_match.request`, `error-codes.yaml` (`ai_match_unavailable`), DEC-267 and DEC-43.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Final, cast

import httpx
import pytest
from temporalio.testing import ActivityEnvironment
from types_boto3_s3 import S3Client

import abacus.ai_gateway as gateway
from abacus.ai_gateway import ModelRequest, ModelResponse
from abacus.ai_gateway.boundary import clear_cache
from abacus.ai_gateway.providers import Tier
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.config import Route, settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.agents import inbox_match, match_start
from abacus.modules.agents.activities import create_match_run_activity, match_activity
from abacus.modules.agents.api import MatchInput, MatchRunInput
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_INBOX, UploadInput
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import Forbidden, Resource, agent_context_for_run, authorise
from abacus_tools.synthetic.documents import bank_statement_pdf, loan_agreement_pdf

from .support import Net, Person, Role, Seeder, Site

BUCKET: Final = "backfill-q03t033-matcher"
MASTER: Final = b"backfill-q03t033-matcher-master-key-01234"
PDF: Final = "application/pdf"
REASON_CODES: Final = {"kind", "date", "account", "holder", "file_name"}
LOAN_QUOTE: Final = "This Term Loan Agreement is dated March 1, 2026"
RATIONALE: Final = "A signed term loan agreement between the company and its lender."
NONE_FIT: Final = "None of the open requests asks for a term loan agreement."


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
    forget_flags()
    yield
    forget_flags()
    storage.reset_storage()
    reset_key_service()


# --- A stub provider on the real route (the fake model only; ADR-076) ---------------------------


Answer = Callable[[ModelRequest], dict[str, object]]


@dataclass
class Stub:
    """Answers the matcher with `answer(request)`; records every call it receives."""

    calls: list[ModelRequest] = field(default_factory=list[ModelRequest])
    answer: Answer | dict[str, object] | None = None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        made = self.answer(request) if callable(self.answer) else self.answer
        return ModelResponse(json.dumps(made), 400, 120, request.model)


def _only_bedrock(route: Route) -> bool:
    return route == "bedrock"


def _catalog_model(tier: Tier, route: Route) -> str | None:
    """The real route serves the catalog's fake-route models here (the stub answers)."""
    return settings().model_catalog[tier].ids.get("fake")


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stub]:
    """A real route (`bedrock`) is enabled for the matcher, with the stub on it."""
    provider = Stub()
    configure_route("bedrock", provider)
    monkeypatch.setattr(gateway, "route_enabled", _only_bedrock)
    monkeypatch.setattr(gateway, "model_id", _catalog_model)
    monkeypatch.setattr(inbox_match, "model_available", lambda: True)
    clear_cache()
    yield provider
    configure_route("bedrock", None)
    clear_cache()


def ref_of(request: ModelRequest, marker: str) -> str:
    """The candidate reference (R1..R60) the context gives the request whose text holds
    `marker` (SPEC-033 §4.3: candidates in a fixed task layer; TASK-065 D1)."""
    for line in request.user.splitlines():
        if line.startswith('{"candidates"'):
            candidates = cast(list[dict[str, object]], json.loads(line)["candidates"])
            [found] = [c for c in candidates if marker in str(c["request"])]
            return str(found["ref"])
    raise AssertionError(request.user)


def proposes_debt(firm: Firm, confidence: float = 0.9) -> Answer:
    """The matcher's answer: the debt request, quoting the agreement's dated sentence."""

    def answer(request: ModelRequest) -> dict[str, object]:
        ref = ref_of(request, f"Debt agreements {firm.marker}")
        return {"none_fit": False, "proposals": [proposal(ref, LOAN_QUOTE, confidence)]}

    return answer


def proposal(ref: str, quote: str, confidence: float = 0.9) -> dict[str, object]:
    return {
        "request": ref,
        "confidence": confidence,
        "rationale": RATIONALE,
        "citations": [{"page": 1, "quote": quote}],
    }


# --- The firm --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    staff: Person
    reviewer: Person
    client: Person
    site: Site
    statement_4471: uuid.UUID
    statement_2290: uuid.UUID
    debt: uuid.UUID
    marker: str

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def synthetic(self) -> None:
        await self.seed.run(
            "UPDATE firms SET synthetic = true WHERE tenant_id = $1", self.tenant_id
        )

    async def drop(self, who: Person, name: str, content: bytes) -> uuid.UUID:
        """A file dropped into the engagement inbox, then extracted, laid out and scanned."""
        response = await self.net.http.post(
            f"{self.base}/inbox",
            params={"filename": name},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        file_id = uuid.UUID(response.json()["id"])
        given = UploadInput(str(self.tenant_id), UPLOAD_INBOX, str(file_id))
        assert await extract_upload(given) == "extracted"
        await words_upload(given)
        await pii_scan_upload(given)
        return file_id

    async def inbox(self, who: Person) -> httpx.Response:
        return await self.net.call("GET", f"{self.base}/inbox", who)

    async def suggestions(self, who: Person, file_id: uuid.UUID) -> list[dict[str, object]]:
        response = await self.inbox(who)
        assert response.status_code == 200, response.text
        [entry] = [f for f in response.json() if f["id"] == str(file_id)]
        return cast(list[dict[str, object]], entry["suggestions"])

    async def match(self, file_id: uuid.UUID) -> tuple[str | None, str]:
        """The matcher's two activities, as its workflow runs them, for the partner."""
        env = ActivityEnvironment()
        run_id = await env.run(
            create_match_run_activity,
            MatchInput(
                str(self.tenant_id), str(file_id), str(uuid.uuid4()), str(self.partner.user_id)
            ),
        )
        assert run_id is not None
        try:
            outcome = await env.run(
                match_activity, MatchRunInput(str(self.tenant_id), str(run_id), str(file_id))
            )
        except Exception as exc:  # a terminal error ends the run as failed and is raised
            return run_id, f"raised:{type(exc).__name__}"
        return run_id, outcome.status

    async def matches(self, who: Person) -> httpx.Response:
        return await self.net.call("GET", f"{self.base}/inbox-matches", who)

    async def file_match(self, who: Person, file_id: uuid.UUID) -> dict[str, object]:
        response = await self.matches(who)
        assert response.status_code == 200, response.text
        [found] = [m for m in response.json() if m["inbox_file_id"] == str(file_id)]
        return cast(dict[str, object], found)

    async def count(self, sql: str, *args: object) -> int:
        return int(cast(int, await self.seed.value(sql, *args)))


async def _request(net: Net, firm_base: str, who: Person, description: str) -> uuid.UUID:
    """A request created through the firm's route, so its document kind is set by rule."""
    response = await net.call(
        "POST",
        f"{firm_base}/request-items",
        who,
        body={"description": description, "audit_area": "Cash"},
    )
    assert response.status_code == 201, response.text
    made = uuid.UUID(response.json()["id"])
    await net.seed.run("UPDATE request_items SET client_visible = true WHERE id = $1", made)
    return made


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'uploads.processing', 'true', 'test-seed', 'Q-03-T033')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Harbor")
    people: dict[str, Person] = {}
    roles: tuple[Role, ...] = ("engagement_partner", "manager", "staff", "reviewer")
    for role in roles:
        people[role] = await seed.person(tenant_id)
        await seed.member(site, people[role], role)
    client = await seed.client_contact(site)
    base = f"/v1/engagements/{site.engagement_id}"
    manager = people["manager"]
    statement_4471 = await _request(
        net, base, manager, f"December bank statement, account ending 4471 {site.marker}"
    )
    statement_2290 = await _request(
        net, base, manager, f"December bank statement, account ending 2290 {site.marker}"
    )
    debt = await _request(net, base, manager, f"Debt agreements {site.marker}")
    return Firm(
        net,
        tenant_id,
        admin,
        people["engagement_partner"],
        manager,
        people["staff"],
        people["reviewer"],
        client,
        site,
        statement_4471,
        statement_2290,
        debt,
        site.marker,
    )


def _statement(firm: Firm, last4: str) -> bytes:
    """A December statement of the engagement's year end, in the client entity's name."""
    from datetime import date

    return bank_statement_pdf(
        holder=f"Entity {firm.marker}",
        last4=last4,
        start=date(2025, 12, 1),
        end=date(2025, 12, 31),
    )


# --- AC-1, AC-2: content rules, with fixed-label reasons, for every firm -----------------------


async def test_ac1_an_extracted_statement_is_suggested_by_its_contents_with_fixed_reasons(
    firm: Firm,
) -> None:
    file_id = await firm.drop(firm.manager, "scan0042.pdf", _statement(firm, "4471"))
    suggestions = await firm.suggestions(firm.manager, file_id)
    assert 1 <= len(suggestions) <= 3
    top = suggestions[0]
    assert top["request_item_id"] == str(firm.statement_4471)
    assert top["source"] == "content"  # a meaningless name, so the contents decided
    reasons = cast(list[dict[str, object]], top["reasons"])
    codes = {str(r["code"]) for r in reasons}
    assert codes <= REASON_CODES
    assert {"kind", "date", "account"} <= codes
    [account] = [r for r in reasons if r["code"] == "account"]
    assert "4471" in str(account["value"])


async def test_ac1_the_content_rules_run_for_a_firm_that_is_not_synthetic(firm: Firm) -> None:
    assert (
        await firm.seed.value("SELECT synthetic FROM firms WHERE tenant_id = $1", firm.tenant_id)
        is False
    )
    file_id = await firm.drop(firm.manager, "scan0043.pdf", _statement(firm, "2290"))
    [top, *_] = await firm.suggestions(firm.manager, file_id)
    assert top["source"] == "content" and top["reasons"]


@pytest.mark.parametrize(("last4", "first", "other"), [("4471", 0, 1), ("2290", 1, 0)])
async def test_ac2_the_needed_account_digits_decide_between_two_statement_requests(
    firm: Firm, last4: str, first: int, other: int
) -> None:
    requests = (firm.statement_4471, firm.statement_2290)
    file_id = await firm.drop(firm.manager, "statement.pdf", _statement(firm, last4))
    ranked = [s["request_item_id"] for s in await firm.suggestions(firm.manager, file_id)]
    assert ranked[0] == str(requests[first])
    if str(requests[other]) in ranked:
        assert ranked.index(str(requests[other])) > 0


async def test_ac1_a_file_without_content_facts_keeps_its_file_name_suggestion(
    firm: Firm,
) -> None:
    """A loan agreement has no statement or aging fields: code has only the name to go on."""
    file_id = await firm.drop(firm.manager, "debt agreements.pdf", loan_agreement_pdf())
    suggestions = await firm.suggestions(firm.manager, file_id)
    assert suggestions and suggestions[0]["request_item_id"] == str(firm.debt)
    assert suggestions[0]["source"] == "file_name"
    assert {str(r["code"]) for r in cast(list[dict[str, object]], suggestions[0]["reasons"])} <= {
        "file_name"
    }


# --- AC-3: the matcher proposes from the candidate list, with verified citations only -----------


async def test_ac3_only_verified_in_list_proposals_above_the_floor_are_shown(
    firm: Firm, stub: Stub
) -> None:
    await firm.synthetic()
    file_id = await firm.drop(firm.manager, "scan0044.pdf", loan_agreement_pdf())

    def answer(request: ModelRequest) -> dict[str, object]:
        debt = ref_of(request, f"Debt agreements {firm.marker}")
        other = ref_of(request, f"account ending 2290 {firm.marker}")
        return {
            "none_fit": False,
            "proposals": [
                proposal(debt, LOAN_QUOTE),
                proposal(other, "Statement of account ending 2290 for December"),  # not in it
                proposal("R60", LOAN_QUOTE),  # outside the candidate list
            ],
        }

    stub.answer = answer
    run_id, status = await firm.match(file_id)
    assert status == "completed", status
    assert len(stub.calls) == 1
    found = await firm.file_match(firm.partner, file_id)
    assert found["status"] == "completed" and found["none_fit"] is False
    proposals = cast(list[dict[str, object]], found["proposals"])
    assert [p["request_item_id"] for p in proposals] == [str(firm.debt)]
    [shown] = proposals
    assert shown["rationale"] == RATIONALE
    quotes = cast(list[dict[str, object]], shown["quotes"])
    assert quotes and all(LOAN_QUOTE in json.dumps(q) for q in quotes)
    # Insert-only results keep the hidden proposal for evaluation (SPEC-033 §4.6).
    kept = await firm.seed.rows(
        "SELECT p.request_item_id, p.shown FROM inbox_match_proposals p "
        "JOIN inbox_match_runs r ON r.id = p.match_id WHERE r.agent_run_id = $1 ORDER BY p.rank",
        uuid.UUID(str(run_id)),
    )
    assert {(r["request_item_id"], r["shown"]) for r in kept} >= {
        (firm.debt, True),
        (firm.statement_2290, False),
    }
    assert all(r["request_item_id"] in (firm.debt, firm.statement_2290) for r in kept)


async def test_ac3_a_verified_proposal_under_half_confidence_is_not_shown(
    firm: Firm, stub: Stub
) -> None:
    await firm.synthetic()
    file_id = await firm.drop(firm.manager, "scan0045.pdf", loan_agreement_pdf())
    stub.answer = proposes_debt(firm, 0.3)
    _, status = await firm.match(file_id)
    assert status == "completed", status
    assert (await firm.file_match(firm.partner, file_id))["proposals"] == []


async def test_ac3_none_fit_is_shown_with_its_rationale_and_no_proposal(
    firm: Firm, stub: Stub
) -> None:
    await firm.synthetic()
    file_id = await firm.drop(firm.manager, "scan0046.pdf", loan_agreement_pdf())
    stub.answer = {"none_fit": True, "rationale": NONE_FIT, "proposals": []}
    _, status = await firm.match(file_id)
    assert status == "completed", status
    found = await firm.file_match(firm.partner, file_id)
    assert found["none_fit"] is True
    assert found["none_fit_rationale"] == NONE_FIT
    assert found["proposals"] == []


async def test_ac1_the_code_rules_keep_their_reasons_beside_a_matcher_pick(
    firm: Firm, stub: Stub
) -> None:
    """The pick comes first with no reasons; the content suggestions keep theirs; one list of
    at most three, each request once (TASK-066 D1 over TASK-064)."""
    await firm.synthetic()
    file_id = await firm.drop(firm.manager, "scan0053.pdf", _statement(firm, "4471"))

    def answer(request: ModelRequest) -> dict[str, object]:
        ref = ref_of(request, f"Debt agreements {firm.marker}")
        return {"none_fit": False, "proposals": [proposal(ref, "First Example Bank")]}

    stub.answer = answer
    _, status = await firm.match(file_id)
    assert status == "completed", status
    suggestions = await firm.suggestions(firm.manager, file_id)
    assert len(suggestions) <= 3
    ids = [s["request_item_id"] for s in suggestions]
    assert len(ids) == len(set(ids))
    assert (suggestions[0]["source"], ids[0]) == ("matcher", str(firm.debt))
    [content] = [s for s in suggestions if s["request_item_id"] == str(firm.statement_4471)]
    assert content["source"] == "content"
    codes = {str(r["code"]) for r in cast(list[dict[str, object]], content["reasons"])}
    assert {"kind", "date", "account"} <= codes <= REASON_CODES


# --- AC-4: never for a firm that is not synthetic ---------------------------------------------


async def test_ac4_a_real_firm_is_refused_at_the_boundary_and_keeps_its_content_suggestions(
    firm: Firm, stub: Stub
) -> None:
    file_id = await firm.drop(firm.manager, "scan0047.pdf", _statement(firm, "4471"))
    stub.answer = {"none_fit": True, "rationale": NONE_FIT, "proposals": []}
    _, status = await firm.match(file_id)
    assert status != "completed"
    assert stub.calls == []  # nothing left for a model
    found = await firm.file_match(firm.partner, file_id)
    assert found["status"] == "failed"
    assert found["reason"] == "data_boundary"
    assert found["proposals"] == []
    [top, *_] = await firm.suggestions(firm.manager, file_id)
    assert top["source"] == "content" and top["request_item_id"] == str(firm.statement_4471)


# --- AC-5: clients see picks by the firm's own descriptions, never the matcher's words ----------


async def test_ac5_a_client_gets_the_pick_without_rationale_or_quotes_and_no_firm_read(
    firm: Firm, stub: Stub
) -> None:
    await firm.synthetic()
    file_id = await firm.drop(firm.client, "scan0048.pdf", loan_agreement_pdf())
    stub.answer = proposes_debt(firm)
    _, status = await firm.match(file_id)
    assert status == "completed", status
    listing = await firm.inbox(firm.client)
    assert listing.status_code == 200, listing.text
    assert RATIONALE not in listing.text and LOAN_QUOTE not in listing.text
    [entry] = [f for f in listing.json() if f["id"] == str(file_id)]
    picks = [s for s in entry["suggestions"] if s["source"] == "matcher"]
    assert [s["request_item_id"] for s in picks] == [str(firm.debt)]
    assert all(s["reasons"] == [] for s in picks)  # code reasons only, and a pick has none
    refused = await firm.matches(firm.client)
    assert refused.status_code == 403
    assert RATIONALE not in refused.text


# --- AC-6: a person assigns; the audit records the source and rank -----------------------------


async def test_ac6_a_proposal_files_nothing_until_a_named_person_assigns_it(
    firm: Firm, stub: Stub
) -> None:
    await firm.synthetic()
    file_id = await firm.drop(firm.manager, "scan0049.pdf", loan_agreement_pdf())
    stub.answer = proposes_debt(firm)
    versions = "SELECT count(*) FROM evidence_versions WHERE engagement_id = $1"
    fulfilled = "SELECT count(*) FROM fulfilments WHERE request_item_id = $1"
    before = await firm.count(versions, firm.site.engagement_id)
    _, status = await firm.match(file_id)
    assert status == "completed", status
    assert await firm.count(versions, firm.site.engagement_id) == before
    assert await firm.count(fulfilled, firm.debt) == 0
    assert str(file_id) in {f["id"] for f in (await firm.inbox(firm.manager)).json()}
    [pick, *_] = await firm.suggestions(firm.manager, file_id)
    assert pick["source"] == "matcher" and pick["request_item_id"] == str(firm.debt)

    assigned = await firm.net.call(
        "POST",
        f"{firm.base}/inbox/{file_id}/assign",
        firm.manager,
        body={
            "request_item_id": str(firm.debt),
            "followed_suggestion": True,
            "suggestion_source": "matcher",
            "suggestion_rank": 1,
        },
    )
    assert assigned.status_code == 201, assigned.text
    assert await firm.count(fulfilled, firm.debt) == 1
    rows = await firm.seed.rows(
        "SELECT actor_kind, actor_id, after_ref::text AS after FROM audit_events "
        "WHERE tenant_id = $1 AND after_ref::text LIKE '%suggestion_source%' ORDER BY seq",
        firm.tenant_id,
    )
    [audit] = rows
    assert audit["actor_kind"] == "human"
    assert str(firm.manager.user_id) in str(audit["actor_id"])
    after = json.loads(audit["after"])
    assert after["suggestion_source"] == 3  # TASK-064 D5 / TASK-066: matcher, as an integer
    assert after["suggestion_rank"] == 1


@pytest.mark.parametrize(("source", "code"), [("content", 2), ("file_name", 1)])
async def test_ac6_the_audit_records_a_followed_content_or_file_name_suggestion(
    firm: Firm, source: str, code: int
) -> None:
    file_id = await firm.drop(firm.manager, "scan0050.pdf", _statement(firm, "4471"))
    assigned = await firm.net.call(
        "POST",
        f"{firm.base}/inbox/{file_id}/assign",
        firm.manager,
        body={
            "request_item_id": str(firm.statement_4471),
            "followed_suggestion": True,
            "suggestion_source": source,
            "suggestion_rank": 2,
        },
    )
    assert assigned.status_code == 201, assigned.text
    [row] = await firm.seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 "
        "AND after_ref::text LIKE '%suggestion_source%'",
        firm.tenant_id,
    )
    after = json.loads(row["after"])
    assert (after["suggestion_source"], after["suggestion_rank"]) == (code, 2)


async def test_ac6_the_matchers_agent_context_may_not_assign_a_file(firm: Firm) -> None:
    """INV-1 (ADR-005): the matcher's task scope reads and records proposals; filing a file is
    a person's `evidence.upload`, which no agent context holds."""
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.matcher",
        engagement_id=firm.site.engagement_id,
        task_scope=frozenset({"evidence.read", "inbox_match.run"}),
        initiator_user_id=firm.partner.user_id,
    )
    with pytest.raises(Forbidden):
        await authorise(
            agent,
            "evidence.upload",
            Resource.engagement(firm.tenant_id, firm.site.engagement_id, archived=False),
        )


# --- "Suggest with AI" and the firm's reads: who may -------------------------------------------


@pytest.fixture
def dispatched(monkeypatch: pytest.MonkeyPatch) -> list[MatchInput]:
    """A real matcher route is enabled; starting the workflow is recorded instead."""
    started: list[MatchInput] = []

    async def dispatch(given: MatchInput, *, again: bool = False) -> None:
        started.append(given)

    monkeypatch.setattr(match_start, "model_available", lambda: True)
    monkeypatch.setattr(match_start, "dispatch_match", dispatch)
    return started


async def test_ac3_suggest_with_ai_is_for_partner_manager_senior_and_staff(
    firm: Firm, dispatched: list[MatchInput]
) -> None:
    await firm.synthetic()
    senior = await firm.seed.person(firm.tenant_id)
    await firm.seed.member(firm.site, senior, "senior")
    file_id = await firm.drop(firm.manager, "scan0051.pdf", loan_agreement_pdf())
    path = f"{firm.base}/inbox/{file_id}/match"
    for who in (firm.partner, firm.manager, senior, firm.staff):
        response = await firm.net.call("POST", path, who)
        assert response.status_code == 202, response.text
        assert response.json() == {"inbox_file_id": str(file_id)}
    assert {d.requested_by for d in dispatched} >= {str(firm.manager.user_id)}
    for refused in (firm.reviewer, firm.client, firm.admin):
        response = await firm.net.call("POST", path, refused)
        assert response.status_code == 403, (refused, response.text)
    assert len(dispatched) == 4


async def test_ac3_suggest_with_ai_without_a_real_route_is_ai_match_unavailable(
    firm: Firm,
) -> None:
    file_id = await firm.drop(firm.manager, "scan0052.pdf", loan_agreement_pdf())
    response = await firm.net.call("POST", f"{firm.base}/inbox/{file_id}/match", firm.manager)
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "ai_match_unavailable"


async def test_ac5_the_firm_reads_are_for_firm_roles_and_g2_blocks_view_gates_a_pending_member(
    firm: Firm,
) -> None:
    """Spec drift: the matrix marks `inbox_match.read` `independence: required`; ADR-164 item 2
    lets a pending member read content, and item 3's `g2_blocks_view` restores the gate on an
    attest client's engagement."""
    for allowed in (firm.partner, firm.manager, firm.staff, firm.reviewer):
        assert (await firm.matches(allowed)).status_code == 200
    assert (await firm.matches(firm.client)).status_code == 403
    pending = await firm.seed.person(firm.tenant_id)
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        firm.tenant_id,
        firm.site.engagement_id,
        pending.user_id,
    )  # no independence confirmation
    assert (await firm.matches(pending)).status_code == 200  # ADR-164 item 2
    await firm.seed.attest(firm.tenant_id, firm.site.engagement_id)
    await firm.seed.blocks_view(firm.tenant_id, firm.admin.user_id)
    assert (await firm.matches(pending)).status_code == 403
    assert (await firm.matches(firm.staff)).status_code == 200  # confirmed staff still read


async def test_ac5_a_walled_member_and_another_firm_get_404(firm: Firm, net: Net) -> None:
    await net.wall(firm.admin, firm.staff, firm.site)
    assert (await firm.matches(firm.staff)).status_code == 404
    other_tenant = await net.seed.firm()
    stranger = await net.seed.person(other_tenant)
    response = await net.call("GET", f"{firm.base}/inbox-matches", stranger)
    assert response.status_code == 404
