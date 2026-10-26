"""P-03-T19 against Postgres and the S3 gateway (SPEC-322 F5, AC5.1 to AC5.5; C4 §3.5, §6, §7):
"A correct password yields masked pages linked to the untouched original version, a wrong one
returns attempts_left, and the password appears in no log, table, storage object or workflow
history."

The Halvard consolidated 1099 (`password_pdf`, a real RC4 file) goes through the upload pipeline
first, so its manifest reads `password_protected`. The unlock runs through the service inside a
recorded request, as the route serves it. Unlock is never a workflow, so no Temporal history can
hold the password; the outbox (what the relay hands on) is checked instead.
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs
from types_boto3_s3 import S3Client

from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.unlock import (
    UNLOCK_LIMIT,
    NotPasswordProtected,
    UnlockRateLimited,
    UnlockResult,
    unlock_version,
)
from abacus.modules.evidence.viewer import viewer_manifest, viewer_page, viewer_text
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import Forbidden, agent_context_for_run
from abacus.modules.identity.authz import recording_checks
from abacus_tools.synthetic.documents import password_pdf, w2_pdf

from .support import BUCKET, Firm, Seeder, as_version, make_firm

SENTINEL = "Sentinel-Halvard-7781"
TABLES = (
    "audit_events",
    "outbox",
    "access_events",
    "evidence_derivations",
    "evidence_pages",
    "pii_scan_runs",
    "pii_regions",
    "upload_previews",
    "upload_preview_pages",
    "evidence_versions",
)


async def _flags(firm: Firm) -> None:
    for flag in ("evidence.viewer_unlock", "evidence.viewer_v1"):
        await firm.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-03-T19') ON CONFLICT DO NOTHING",
            firm.tenant_id,
            flag,
        )


async def _processed(firm: Firm, content: bytes) -> uuid.UUID:
    """A version through the upload pipeline (extract, words, scan, masked rendition)."""
    version = await firm.version(content)
    given = as_version(firm, version)
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)
    return version


async def _locked(firm: Firm) -> uuid.UUID:
    await _flags(firm)
    return await _processed(firm, password_pdf(SENTINEL))


async def _unlock(ctx: object, version: uuid.UUID, password: str) -> UnlockResult:
    with recording_checks():
        return await unlock_version(ctx, version, SecretStr(password))  # type: ignore[arg-type]  # refused principals on purpose


async def _count(seed: Seeder, firm: Firm, sql: str) -> int:
    return int(str(await seed.value(sql, firm.tenant_id)))


async def test_ac5_1_a_protected_version_offers_unlock(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _locked(firm)
    manifest = await viewer_manifest(firm.person(), version)
    assert manifest.status == "password_protected"
    assert manifest.derivation_id is None
    assert "evidence.unlock" in manifest.allowed_actions


async def test_ac5_2_the_right_password_derives_masked_pages_and_leaves_the_version(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _locked(firm)
    before = await seed.rows(
        "SELECT fingerprint, size_bytes, storage_key, storage_version_id FROM evidence_versions "
        "WHERE id = $1",
        version,
    )
    result = await _unlock(firm.person(), version, SENTINEL)
    assert result.status == "ready" and result.derivation_id is not None
    after = await seed.rows(
        "SELECT fingerprint, size_bytes, storage_key, storage_version_id FROM evidence_versions "
        "WHERE id = $1",
        version,
    )
    assert [dict(r) for r in before] == [dict(r) for r in after]  # ADR-004: untouched
    [derivation] = await seed.rows(
        "SELECT id, evidence_version_id, kind, created_by_user_id FROM evidence_derivations "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert (derivation["evidence_version_id"], derivation["kind"]) == (version, "password_unlock")
    assert derivation["created_by_user_id"] == firm.user_id
    # The same scan as any upload: the recipient's TIN and the payer's EIN are regions.
    kinds = await seed.rows(
        "SELECT kind, last4 FROM pii_regions WHERE derivation_id = $1 ORDER BY kind",
        result.derivation_id,
    )
    assert [(r["kind"], r["last4"]) for r in kinds] == [("ein", "4321"), ("ssn", "3456")]
    manifest = await viewer_manifest(firm.person(), version)
    assert (manifest.status, manifest.derivation_id) == ("ready", result.derivation_id)
    assert {m.display for m in manifest.pii_masks} >= {"•••-••-3456"}
    assert "evidence.unlock" not in manifest.allowed_actions
    page = await viewer_page(firm.person(), version, 1)
    assert page.startswith(b"\x89PNG")
    text = await viewer_text(firm.person(), version)
    assert "3456" in text.items[0].text and "900-12-3456" not in text.items[0].text
    audits = await _count(
        seed,
        firm,
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_version.unlocked'",
    )
    events = await _count(
        seed,
        firm,
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'evidence_version.unlocked'",
    )
    assert (audits, events) == (1, 1)
    # Unlocked already: not offered again, and refused.
    with pytest.raises(NotPasswordProtected):
        await _unlock(firm.person(), version, SENTINEL)


async def test_ac5_3_a_wrong_password_returns_attempts_left_then_429(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _locked(firm)
    for attempt in range(1, UNLOCK_LIMIT + 1):
        result = await _unlock(firm.person(), version, f"wrong-{attempt}")
        assert (result.status, result.attempts_left) == ("wrong_password", UNLOCK_LIMIT - attempt)
    with pytest.raises(UnlockRateLimited) as limited:
        await _unlock(firm.person(), version, SENTINEL)  # even the right one, now
    assert 0 < int(limited.value.facts["retry_after"]) <= 900
    failed = await seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'evidence_version.unlock_failed' ORDER BY seq",
        firm.tenant_id,
    )
    assert len(failed) == UNLOCK_LIMIT
    assert all("wrong-" not in r["after"] for r in failed)  # by count only
    assert (
        await _count(seed, firm, "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1")
        == 0
    )


async def test_ac5_4_the_password_is_in_no_log_table_or_storage_object(
    seed: Seeder, evidence_storage: S3Client
) -> None:
    firm = await make_firm(seed)
    version = await _locked(firm)
    with capture_logs() as logs:
        await _unlock(firm.person(), version, "not-the-password")
        await _unlock(firm.person(), version, SENTINEL)
    assert all(SENTINEL not in str(entry) for entry in logs)
    for table in TABLES:
        dumped = await seed.value(
            f"SELECT coalesce(string_agg(t::text, ''), '') FROM {table} t "  # noqa: S608 -- fixed names
            "WHERE tenant_id = $1",
            firm.tenant_id,
        )
        assert SENTINEL not in str(dumped), table
        assert SENTINEL.encode().hex() not in str(dumped), table
    listing = evidence_storage.list_objects_v2(Bucket=BUCKET)
    for entry in listing.get("Contents", []):
        body = evidence_storage.get_object(Bucket=BUCKET, Key=entry.get("Key", ""))["Body"]
        assert SENTINEL.encode() not in body.read()


async def test_ac5_5_agents_clients_support_and_offline_callers_are_refused(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _locked(firm)
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.upload_reviewer",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read", "evidence.unlock"}),
        initiator_user_id=firm.user_id,
    )
    client = dataclasses.replace(firm.person(), client=True)
    support = dataclasses.replace(
        firm.person(), tenant=dataclasses.replace(firm.person().tenant, actor_kind="support")
    )
    for refused in (agent, client, support):
        with pytest.raises(Forbidden):
            await _unlock(refused, version, SENTINEL)
    with pytest.raises(Forbidden):  # outside a request being served
        await unlock_version(firm.person(), version, SecretStr(SENTINEL))
    assert (
        await _count(seed, firm, "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1")
        == 0
    )
    assert (
        await _count(
            seed,
            firm,
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action LIKE 'evidence_version.unlock%'",
        )
        == 0
    )


async def test_a_version_that_is_not_locked_answers_409(seed: Seeder) -> None:
    firm = await make_firm(seed)
    await _flags(firm)
    version = await _processed(firm, w2_pdf())
    with pytest.raises(NotPasswordProtected):
        await _unlock(firm.person(), version, "anything")
    assert "evidence.unlock" not in (await viewer_manifest(firm.person(), version)).allowed_actions
