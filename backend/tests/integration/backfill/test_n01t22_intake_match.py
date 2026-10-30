"""N-01-T22 (TASK-2230; DEC-1278): `evidence.matcher` v3 intake mode.

Acceptance (the task row): "The direct-route suite passes at the protected thresholds and no code
path lets the agent file, ignore, hold or supersede." The direct-route run is `make evals` in the
eval environment (a real model); here the fake model only (ADR-076): a stub provider on a real
route, the matcher's two intake activities in an `ActivityEnvironment`, and the outcomes through
SQL.

Boundary: an intake attachment received by email from a matched client, run through the upload
steps (extraction, word layer, PII scan) and the classify step as AttachmentTriage runs them.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast

import pytest
from temporalio.testing import ActivityEnvironment

import abacus.ai_gateway as gateway
from abacus.ai_gateway import ModelRequest, ModelResponse
from abacus.ai_gateway.boundary import clear_cache
from abacus.ai_gateway.providers import Tier
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.config import Route, settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.agents import inbox_match, intake_match, intake_start
from abacus.modules.agents.activities import (
    create_intake_run_activity,
    match_intake_activity,
)
from abacus.modules.agents.workflow_types import IntakeMatchInput, IntakeMatchRunInput
from abacus.modules.communications.api import (
    Inbound,
    TriageInput,
    add_attachment,
    record_inbound_message,
)
from abacus.modules.communications.deliveries import address_hash
from abacus.modules.communications.triage_classify import attachment_classified
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import INTAKE, UploadInput, pii_scan_upload, words_upload
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n01t22-evidence"
MASTER: Final = b"n01t22-intake-matcher-master-key-0123456"
QUOTE: Final = "Form 1095-C Employer-Provided Health Insurance Offer and Coverage"
F1095C: Final = positioned_pdf(
    [[(50, 740, QUOTE), (50, 720, "Employee: Claire Feld"), (50, 700, "Tax year 2025")]]
)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    yield
    storage.reset_storage()
    reset_key_service()
    forget_flags()


# --- A stub provider on the real route (the fake model only; ADR-076) ---------------------------

Answer = Callable[[ModelRequest], dict[str, object]]


@dataclass
class Stub:
    calls: list[ModelRequest] = field(default_factory=list[ModelRequest])
    answer: Answer | None = None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        assert self.answer is not None
        return ModelResponse(json.dumps(self.answer(request)), 400, 120, request.model)


def _only_bedrock(route: Route) -> bool:
    return route == "bedrock"


def _catalog_model(tier: Tier, route: Route) -> str | None:
    return settings().model_catalog[tier].ids.get("fake")


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stub]:
    provider = Stub()
    configure_route("bedrock", provider)
    monkeypatch.setattr(gateway, "route_enabled", _only_bedrock)
    monkeypatch.setattr(gateway, "model_id", _catalog_model)
    monkeypatch.setattr(inbox_match, "model_available", lambda: True)
    monkeypatch.setattr(intake_match, "model_available", lambda: True)
    monkeypatch.setattr(intake_start, "model_available", lambda: True)
    clear_cache()
    yield provider
    configure_route("bedrock", None)
    clear_cache()


def destinations(request: ModelRequest) -> list[dict[str, object]]:
    for line in request.user.splitlines():
        if line.startswith('{"destinations"'):
            return cast(list[dict[str, object]], json.loads(line)["destinations"])
    raise AssertionError(request.user)


def ref_of(request: ModelRequest, marker: str) -> str:
    [found] = [d for d in destinations(request) if marker in str(d["label"])]
    return str(found["ref"])


def answer(
    marker: str, *, quote: str = QUOTE, confidence: float = 0.92, extra_ref: str | None = None
) -> Answer:
    def made(request: ModelRequest) -> dict[str, object]:
        proposals: list[dict[str, object]] = [
            {
                "destination": ref_of(request, marker),
                "confidence": confidence,
                "rationale": "The form is the 1095-C this request asks for.",
                "citations": [{"page": 1, "quote": quote}],
            }
        ]
        if extra_ref is not None:
            proposals.append(
                {
                    "destination": extra_ref,
                    "confidence": 0.9,
                    "rationale": "Another place.",
                    "citations": [{"page": 1, "quote": QUOTE}],
                }
            )
        return {
            "none_fit": False,
            "classification": {
                "form_family": "1095-C",
                "tax_year": 2025,
                "issuer": "Harbor Health",
                "kind": "tax_form",
                "confidence": 0.95,
            },
            "proposals": proposals,
        }

    return made


# --- The firm ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    partner: Person
    site: Site
    request_marker: str

    async def receive(self, file_name: str = "1095-C.pdf", content: bytes = F1095C) -> uuid.UUID:
        """One matched email with one file, through the upload and classify steps."""
        system = TenantContext(self.tenant_id, "system", "test.n01t22")
        address = f"sender+{uuid.uuid4().hex[:6]}@example.com"
        await self.net.seed.run(
            "INSERT INTO inbox_sender_rules (tenant_id, address_hmac, address_sealed, client_id, "
            "created_by) VALUES ($1, $2, '\\x00', $3, $4)",
            self.tenant_id,
            address_hash(address).hex(),
            self.site.client_id,
            self.partner.user_id,
        )
        made = await record_inbound_message(
            system,
            Inbound(
                channel="email",
                sender_display="Sender",
                subject="2025 tax documents",
                received_at=datetime.now(UTC),
                body="Attached.",
                sender_address=address,
            ),
        )
        got = await add_attachment(system, made.message_id, file_name=file_name, content=content)
        given = UploadInput(str(self.tenant_id), INTAKE, str(got.attachment_id))
        await extract_upload(given)
        await words_upload(given)
        await pii_scan_upload(given)
        await attachment_classified(TriageInput(str(self.tenant_id), str(got.attachment_id)))
        return got.attachment_id

    async def match(self, attachment_id: uuid.UUID) -> tuple[str | None, str]:
        env = ActivityEnvironment()
        run_id = await env.run(
            create_intake_run_activity,
            IntakeMatchInput(
                str(self.tenant_id),
                str(attachment_id),
                str(self.site.client_id),
                str(uuid.uuid4()),
            ),
        )
        if run_id is None:
            return None, "skipped"
        try:
            outcome = await env.run(
                match_intake_activity,
                IntakeMatchRunInput(str(self.tenant_id), str(run_id), str(attachment_id)),
            )
        except Exception as exc:  # a terminal error ends the run as failed and is raised
            return run_id, f"raised:{type(exc).__name__}"
        return run_id, outcome.status


async def _flag(net: Net, tenant: uuid.UUID, flag: str, on: bool = True) -> None:
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, $3, 'test-seed', 'N-01-T22')",
        tenant,
        flag,
        "true" if on else "false",
    )


async def _firm(net: Net, *, matching: bool = True) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await _flag(net, tenant, "inbox.firm_intake")
    await _flag(net, tenant, "matching.firm_intake", matching)
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    # The relationship partner triages the firm's intake (`inbox.triage`, as INB-02's picker asks).
    partner = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, partner.user_id, "Feld")
    await seed.member(site, partner, "engagement_partner")
    await seed.run(
        "UPDATE clients SET relationship_partner_id = $2 WHERE id = $1",
        site.client_id,
        partner.user_id,
    )
    marker = f"Form 1095-C {uuid.uuid4().hex[:6]}"
    await seed.item(site, description=marker)
    forget_flags()
    return Firm(net, tenant, partner, site, marker)


async def _proposals(net: Net, attachment: uuid.UUID) -> list[dict[str, object]]:
    return [
        dict(r)
        for r in await net.seed.rows(
            "SELECT p.rank, p.request_item_id, p.destination_kind, p.destination_id, p.shown, "
            "p.inbox_attachment_id, r.client_id, r.engagement_id, r.inbox_file_id, r.prompt_ref "
            "FROM inbox_match_proposals p JOIN inbox_match_runs r ON r.id = p.match_id "
            "WHERE r.inbox_attachment_id = $1 ORDER BY p.rank",
            attachment,
        )
    ]


async def test_flag_off_starts_no_run(net: Net, stub: Stub) -> None:
    firm = await _firm(net, matching=False)
    attachment = await firm.receive()
    run_id, status = await firm.match(attachment)
    assert (run_id, status) == (None, "skipped")
    assert stub.calls == []


async def test_a_matched_attachment_gets_a_shown_request_proposal_and_a_classification(
    net: Net, stub: Stub
) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker)
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status == "completed"
    [row] = await _proposals(net, attachment)
    assert row["destination_kind"] == "request" and row["shown"] is True
    assert row["request_item_id"] == row["destination_id"]
    assert row["client_id"] == firm.site.client_id and row["engagement_id"] is None
    assert row["inbox_file_id"] is None and row["prompt_ref"] == "evidence.inbox_match@v3"
    agent_rows = await net.seed.rows(
        "SELECT form_family, tax_year, kind, agent_run_id FROM document_classifications "
        "WHERE subject_id = $1 AND proposed_by_kind = 'agent'",
        attachment,
    )
    assert [(r["form_family"], r["tax_year"], r["kind"]) for r in agent_rows] == [
        ("1095-C", 2025, "tax_form")
    ]
    # The masked text and the file name go in untrusted blocks; the permanent file is offered.
    [request] = stub.calls
    assert '<untrusted name="document">' in request.user
    assert '<untrusted name="file_name">' in request.user
    assert any(d["kind"] == "permanent file" for d in destinations(request))


async def test_only_the_matched_clients_destinations_reach_the_model(net: Net, stub: Stub) -> None:
    firm = await _firm(net)
    other = await net.seed.site(firm.tenant_id, firm.partner.user_id, "Whitley")
    await net.seed.member(other, firm.partner, "engagement_partner")
    other_marker = f"Form 1095-C other {uuid.uuid4().hex[:6]}"
    await net.seed.item(other, description=other_marker)
    stub.answer = answer(firm.request_marker)
    attachment = await firm.receive()
    await firm.match(attachment)
    [request] = stub.calls
    labels = [str(d["label"]) for d in destinations(request)]
    assert any(firm.request_marker in label for label in labels)
    assert not any(other_marker in label for label in labels)  # INV-3
    assert other.marker not in request.user


async def test_unknown_references_are_discarded_and_unverified_quotes_stay_hidden(
    net: Net, stub: Stub
) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker, quote="Not on the page at all", extra_ref="D60")
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status == "completed"
    [row] = await _proposals(net, attachment)  # D60 was never given: discarded
    assert row["shown"] is False  # the quote isn't on the page


async def test_tax_return_information_is_refused_without_consent(net: Net, stub: Stub) -> None:
    firm = await _firm(net)
    await net.seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'tax_return', "
        "'TY2025 Form 1040', '2025-01-01', '2025-12-31', $5)",
        firm.tenant_id,
        firm.site.engagement_id,
        firm.site.client_id,
        firm.site.entity_id,
        firm.partner.user_id,
    )
    stub.answer = answer(firm.request_marker)
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status.startswith("raised:")  # consent_7216: refused, never retried
    assert stub.calls == []  # no model saw the return's client
    assert await _proposals(net, attachment) == []


async def test_the_matcher_never_files_ignores_holds_or_supersedes(net: Net, stub: Stub) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker)
    attachment = await firm.receive()
    await firm.match(attachment)
    (row,) = await net.seed.rows(
        "SELECT status, filed_evidence_version_id, filed_destination_kind FROM inbox_attachments "
        "WHERE id = $1",
        attachment,
    )
    assert row["status"] == "waiting"
    assert row["filed_evidence_version_id"] is None and row["filed_destination_kind"] is None
    decisions = await net.seed.value(
        "SELECT count(*) FROM triage_decisions WHERE attachment_id = $1", attachment
    )
    assert decisions == 0


async def test_no_relationship_partner_starts_no_run(net: Net, stub: Stub) -> None:
    firm = await _firm(net)
    await net.seed.run(
        "UPDATE clients SET relationship_partner_id = NULL WHERE id = $1", firm.site.client_id
    )
    attachment = await firm.receive()
    assert await firm.match(attachment) == (None, "skipped")
    assert stub.calls == []


async def test_classifying_a_matched_attachment_announces_it(net: Net) -> None:
    firm = await _firm(net)
    attachment = await firm.receive()
    found = await net.seed.rows(
        "SELECT payload FROM outbox WHERE event_type = 'inbox_attachment.matchable' "
        "AND tenant_id = $1",
        firm.tenant_id,
    )
    payloads = [json.loads(r["payload"]) for r in found]
    assert {"attachment_id": str(attachment), "client_id": str(firm.site.client_id)} in [
        {k: p[k] for k in ("attachment_id", "client_id")} for p in payloads
    ]
