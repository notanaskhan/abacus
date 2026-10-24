# ac-test-author: ayushkbhatia
"""P-06-T19 security review (DEC-299): what the withdrawal and its purge must also guarantee.

1. Nothing derived from a withdrawn upload reaches the firm: screening results, upload-review
   flags and their counts, the engagement graph, a run's trace, citations into it, its regions
   and its word layer.
2. The purge never destroys a held key: the database function itself requires the window to have
   passed and no active hold on the version, under the lock a hold placement takes; and a version
   a legal hold covers is not withdrawn at all (409 `legal_hold_active`, audited, nothing written).
3. Erasing leaves no content behind: extraction fields, checks, previews, PII values and last-4s,
   citation values, screening and review rationales and approved statement data go with the key;
   the audit trail keeps only that an erase happened.
8. The withdrawal is authorised on the item the client's own upload was made to, and voids only
   the links the client may withdraw from.
9. Two concurrent withdrawals: one answers, the other answers 404 as if the version never existed.

Boundary: `create_app()` over HTTP, the migrated Postgres (superuser seeding where no route makes
the row), the compose S3 image, the processing activities, the purge's body on a synthetic firm's
business clock (`kernel.clock.frozen` reaches `abacus_now()` only for a synthetic firm).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from sqlalchemy import text
from types_boto3_s3 import S3Client

from abacus.kernel import holds as kernel_holds
from abacus.kernel.clock import frozen
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_VERSION,
    UploadInput,
    check_upload_content,
    holds_covering,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.repository import pages_of
from abacus.modules.evidence.withdrawals import PURGE_ACTOR, erase_withdrawn
from abacus.modules.evidence.words import WORDS_VERSION, words_upload
from abacus_tools.synthetic.documents import bank_statement_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "p06t19-security-review"
MASTER: Final = b"p06t19-security-review-master-key-0123456"
PDF: Final = "application/pdf"
DAY: Final = 24 * 3600


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


@pytest.fixture
def no_python_hold() -> Iterator[None]:
    """A hold check that sees nothing: the database function must still refuse a held key."""

    async def nothing(_tenant: TenantContext, _ids: object) -> frozenset[uuid.UUID]:
        return frozenset()

    kernel_holds.reset_hold_check()
    kernel_holds.register_hold_check(nothing)
    yield
    kernel_holds.reset_hold_check()
    kernel_holds.register_hold_check(holds_covering)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    manager: Person
    admin: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def upload(self, who: Person, content: bytes) -> uuid.UUID:
        response = await self.net.http.post(
            f"{self.base}/request-items/{self.site.item_id}/uploads",
            params={"filename": "statement.pdf"},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["evidence_version_id"])

    async def withdraw(self, version: uuid.UUID) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/evidence-versions/{version}/withdraw",
            headers={**self.net.headers(self.admin), "Idempotency-Key": str(uuid.uuid4())},
        )

    async def processed(self, version: uuid.UUID) -> None:
        given = UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version))
        await extract_upload(given)
        await check_upload_content(given)
        await preview_upload(given)
        await words_upload(given)

    async def erase_after(self, version: uuid.UUID) -> datetime:
        return cast(
            datetime,
            await self.seed.value(
                "SELECT erase_after FROM evidence_withdrawals WHERE evidence_version_id = $1",
                version,
            ),
        )

    async def count(self, sql: str, *args: object) -> int:
        return int(cast(int, await self.seed.value(sql, *args)))

    async def agent_run(self, agent_id: str, version: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
                "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
                "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'], 'completed', now()) "
                "RETURNING id",
                self.tenant_id,
                agent_id,
                self.site.engagement_id,
                version,
                self.manager.user_id,
            ),
        )

    async def derived(self, version: uuid.UUID) -> dict[str, uuid.UUID]:
        """What the agents, the trust kit and statement review derive from a version, seeded."""
        screen = await self.agent_run("evidence.screener", version)
        result = await self.seed.value(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
            "($1, $2, $3, $4, 'needs_revision', 0.5, 'Holder Claire Feld, ending 1181', "
            '\'[{"cell": "B2", "quote": "Claire Feld", "value": "Claire Feld", '
            '"verified": true, "reason": null}]\', \'[]\') RETURNING id',
            self.tenant_id,
            self.site.engagement_id,
            version,
            screen,
        )
        review_run = await self.agent_run("evidence.upload_reviewer", version)
        review = await self.seed.value(
            "INSERT INTO upload_reviews (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, prompt_ref, no_concerns) VALUES ($1, $2, $3, $4, "
            "'evidence.upload_reviewer@v1', false) RETURNING id",
            self.tenant_id,
            self.site.engagement_id,
            version,
            review_run,
        )
        await self.seed.run(
            "INSERT INTO upload_review_flags (tenant_id, review_id, position, category, "
            "confidence, rationale, citations, shown) VALUES ($1, $2, 1, 'altered', 0.9, "
            '\'Balance 4,210.55 differs\', \'[{"quote": "4,210.55", "verified": true}]\', true)',
            self.tenant_id,
            review,
        )
        citation = await self.seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, locator, match_id, quote_sha256, value_text, verified, "
            "verifier_version, created_by_kind, created_by_run_id) VALUES ($1, $2, "
            "'upload_review', $3, 1, 'document_text', 'evidence_version', $4, "
            "'{\"page\": 1}', $5, $6, 'Claire Feld', true, 'v1', 'agent', $7) RETURNING id",
            self.tenant_id,
            self.site.engagement_id,
            review,
            version,
            f"ev:{version.hex[:12]}#p1",
            bytes(32),
            review_run,
        )
        region = await self.seed.value(
            "INSERT INTO pii_regions (tenant_id, evidence_version_id, page_no, bbox, kind, "
            "value_sealed, last4, label_anchored, detector_version) VALUES ($1, $2, 1, "
            "ARRAY[1, 2, 3, 4]::numeric[], 'bank_account', '\\x0102'::bytea, '1181', true, 'v1') "
            "RETURNING id",
            self.tenant_id,
            version,
        )
        dataset = await self.seed.value(
            "INSERT INTO statement_datasets (tenant_id, engagement_id, request_item_id, "
            "evidence_version_id, format, account_kind, issuer, last4, opening, closing, "
            "opening_source, closing_source, included_total, line_count, excluded_count, "
            "approved_by, actor_kind) VALUES ($1, $2, $3, $4, 'pdf_text', 'bank', "
            "'Lakeshore Bank', '1181', 100, 150, 'printed', 'printed', 50, 1, 0, $5, 'human') "
            "RETURNING id",
            self.tenant_id,
            self.site.engagement_id,
            self.site.item_id,
            version,
            self.manager.user_id,
        )
        return {
            "screen_run": screen,
            "result": cast(uuid.UUID, result),
            "review_run": review_run,
            "review": cast(uuid.UUID, review),
            "citation": cast(uuid.UUID, citation),
            "region": cast(uuid.UUID, region),
            "dataset": cast(uuid.UUID, dataset),
        }


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    # A synthetic firm: the business clock (`frozen`) reaches `abacus_now()` (F-04.3).
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    for flag in (
        "uploads.processing",
        "evidence.withdrawal",
        "evidence.viewer_v1",
        "evidence.citations_v2",
        "compliance.legal_holds",
    ):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'DEC-299')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Feld")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    admin = await seed.client_contact(site, "client_admin")
    return Firm(net, tenant_id, owner, manager, admin, site)


# --- 1. nothing derived reaches the firm ---------------------------------------------------------


async def test_dec299_derived_agent_output_of_a_withdrawn_upload_is_hidden(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="1181"))
    ids = await firm.derived(version)

    async def surfaces() -> list[str]:
        out: list[str] = []
        for path in (
            f"{firm.base}/screening-results",
            f"{firm.base}/review-flags",
            f"{firm.base}/graph",
            f"/v1/agent-runs/{ids['screen_run']}/trace",
            f"/v1/citations?source_version_id={version}",
        ):
            response = await firm.net.call("GET", path, firm.manager)
            assert response.status_code == 200, (path, response.text)
            out.append(response.text)
        return out

    before = await surfaces()
    assert str(version) in before[0] and "Claire Feld" in before[0]  # the controls
    assert str(version) in before[1]
    assert str(ids["citation"]) in before[4]
    assert (await firm.withdraw(version)).status_code == 200
    after = await surfaces()
    assert all(str(version) not in body for body in after[:2])
    assert "Claire Feld" not in after[0] and "Claire Feld" not in after[3]
    assert str(version) not in after[2]
    assert str(ids["citation"]) not in after[4]
    one = await firm.net.call("GET", f"/v1/citations/{ids['citation']}", firm.manager)
    assert one.status_code == 404, one.text


async def test_dec299_a_withdrawn_versions_word_layer_is_never_read(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="2282"))
    await firm.processed(version)
    reader = TenantContext(firm.tenant_id, "system", "evidence.upload_processing")
    async with tenant_session(reader) as session:
        assert await pages_of(
            session, evidence_version_id=version, extractor_version=WORDS_VERSION
        )
    assert (await firm.withdraw(version)).status_code == 200
    async with tenant_session(reader) as session:
        found = await pages_of(
            session, evidence_version_id=version, extractor_version=WORDS_VERSION
        )
    assert list(found) == []


# --- 2. never a held key ------------------------------------------------------------------------


async def test_dec299_a_held_version_is_not_withdrawn(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="3383"))
    placed = await firm.net.call(
        "POST",
        "/v1/legal-holds",
        firm.owner,
        body={
            "scope": {"kind": "engagement", "engagement_id": str(firm.site.engagement_id)},
            "reason_code": "litigation",
        },
    )
    assert placed.status_code in (200, 201, 202), placed.text
    refused = await firm.withdraw(version)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "legal_hold_active"
    assert (
        await firm.count(
            "SELECT count(*) FROM evidence_withdrawals WHERE evidence_version_id = $1", version
        )
        == 0
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM fulfilment_withdrawals WHERE evidence_version_id = $1", version
        )
        == 0
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
            "AND action = 'evidence_version.withdrawal_refused'",
            firm.tenant_id,
            str(version),
        )
        == 1
    )


async def test_dec299_the_database_refuses_to_destroy_a_key_before_its_window(
    firm: Firm,
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="4484"))
    assert (await firm.withdraw(version)).status_code == 200
    purge = TenantContext(firm.tenant_id, "system", PURGE_ACTOR)
    async with tenant_session(purge) as session:
        status = (
            await session.execute(text("SELECT evidence_key_destroy(:v)"), {"v": version})
        ).scalar_one()
    assert status == "not_due"
    assert (
        await firm.count(
            "SELECT count(*) FROM evidence_object_keys WHERE evidence_version_id = $1 "
            "AND wrapped_key IS NOT NULL",
            version,
        )
        == 1
    )


async def test_dec299_a_hold_placed_after_the_withdrawal_blocks_the_erase_in_the_database(
    firm: Firm, no_python_hold: None
) -> None:
    """The Python hold check sees nothing here; the database function still refuses."""
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="5585"))
    assert (await firm.withdraw(version)).status_code == 200
    placed = await firm.net.call(
        "POST",
        "/v1/legal-holds",
        firm.owner,
        body={
            "scope": {"kind": "engagement", "engagement_id": str(firm.site.engagement_id)},
            "reason_code": "litigation",
        },
    )
    assert placed.status_code in (200, 201, 202), placed.text
    with frozen(await firm.erase_after(version) + timedelta(days=1)):
        assert await erase_withdrawn(firm.tenant_id, version) == DAY
    assert (
        await firm.count(
            "SELECT count(*) FROM evidence_object_keys WHERE evidence_version_id = $1 "
            "AND wrapped_key IS NOT NULL",
            version,
        )
        == 1
    )
    assert (
        await firm.seed.value(
            "SELECT block_reason FROM evidence_withdrawals WHERE evidence_version_id = $1", version
        )
        == "legal_hold"
    )


# --- 3. no content survives the erase ------------------------------------------------------------


async def test_dec299_erasing_leaves_no_content_behind(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="6686"))
    await firm.processed(version)
    ids = await firm.derived(version)
    assert (
        await firm.count(
            "SELECT count(*) FROM upload_extractions WHERE evidence_version_id = $1", version
        )
        >= 1
    )
    assert (await firm.withdraw(version)).status_code == 200
    with frozen(await firm.erase_after(version) + timedelta(minutes=1)):
        assert await erase_withdrawn(firm.tenant_id, version) == 0
    for table, sql in (
        ("extractions", "SELECT count(*) FROM upload_extractions WHERE evidence_version_id = $1"),
        ("checks", "SELECT count(*) FROM upload_checks WHERE evidence_version_id = $1"),
        ("previews", "SELECT count(*) FROM upload_previews WHERE evidence_version_id = $1"),
        ("statements", "SELECT count(*) FROM statement_datasets WHERE evidence_version_id = $1"),
    ):
        assert await firm.count(sql, version) == 0, table
    assert (
        await firm.count(
            "SELECT count(*) FROM statement_transactions WHERE dataset_id = $1", ids["dataset"]
        )
        == 0
    )
    result = (
        await firm.seed.rows(
            "SELECT rationale, citations::text AS c FROM screening_results WHERE id = $1",
            ids["result"],
        )
    )[0]
    assert "Claire" not in f"{result['rationale']}{result['c']}"
    flag = (
        await firm.seed.rows(
            "SELECT rationale, citations::text AS c FROM upload_review_flags WHERE review_id = $1",
            ids["review"],
        )
    )[0]
    assert "4,210.55" not in f"{flag['rationale']}{flag['c']}"
    citation = (
        await firm.seed.rows(
            "SELECT value_text, quote_sha256 FROM citations WHERE id = $1", ids["citation"]
        )
    )[0]
    assert (citation["value_text"], citation["quote_sha256"]) == (None, None)
    region = (
        await firm.seed.rows(
            "SELECT last4, value_sealed FROM pii_regions WHERE id = $1", ids["region"]
        )
    )[0]
    assert region["last4"] is None and bytes(region["value_sealed"]) == b""
    # The audit trail keeps that an erase happened, and nothing of the file.
    rows = await firm.seed.rows(
        "SELECT action, after_ref::text AS a FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_withdrawal.erased'",
        firm.tenant_id,
    )
    assert len(rows) == 1
    assert "Claire" not in json.dumps([str(r["a"]) for r in rows])


# --- 8. the client's own upload's item, and only its own links ---------------------------------


async def test_dec299_the_withdrawal_voids_only_links_the_client_may_withdraw_from(
    firm: Firm,
) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="7787"))
    hidden = await firm.seed.item(firm.site, "Internal cash tie-out")
    await firm.seed.run("UPDATE request_items SET client_visible = false WHERE id = $1", hidden)
    await firm.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'rule', 'matcher')",
        firm.tenant_id,
        firm.site.engagement_id,
        hidden,
        version,
    )
    response = await firm.withdraw(version)
    assert response.status_code == 200, response.text
    assert response.json()["request_item_id"] == str(firm.site.item_id)
    voided = await firm.seed.rows(
        "SELECT request_item_id FROM fulfilment_withdrawals WHERE evidence_version_id = $1",
        version,
    )
    assert [r["request_item_id"] for r in voided] == [firm.site.item_id]


# --- 9. concurrent withdrawals -------------------------------------------------------------------


async def test_dec299_two_concurrent_withdrawals_answer_once_and_404(firm: Firm) -> None:
    version = await firm.upload(firm.admin, bank_statement_pdf(last4="8888"))
    first, second = await asyncio.gather(firm.withdraw(version), firm.withdraw(version))
    assert sorted([first.status_code, second.status_code]) == [200, 404], (
        first.text,
        second.text,
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM evidence_withdrawals WHERE evidence_version_id = $1", version
        )
        == 1
    )
