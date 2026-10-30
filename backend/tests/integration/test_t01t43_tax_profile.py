"""T-01-T43 (TASK-2601; SPEC-501 AC-30 to AC-34; T-01 §3.6; DEC-1651) against Postgres: CLI-05's
tax profile backend.

The row's acceptance: "The Whitley TY2024 comparison returns 2 differences totalling 3,120.00
computed by code, and the profile never returns a full CAF number or SSN." The transcript is the
T-01-T45 golden, parsed by `compute.transcripts` and stored as the upload stores it; the return as
filed is an approved engine-import checkpoint carrying `ir.<form>.<n>` fields (DEC-1651).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.errors import DomainConflict
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations import tax_profile as org_profile
from abacus.modules.organisations.api import TaxElectionIn, TranscriptComparisonIn
from abacus.modules.tax import api as tax_api  # registers the tax-profile backend
from abacus.modules.tax import tax_profile
from abacus.modules.tax.compute.transcripts import TranscriptKind, parse_transcript

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

GOLDEN = Path(__file__).parents[1] / "golden" / "tax" / "transcripts"
assert tax_api  # imported for its registration
FILED_2024 = (
    ("w_2", 1, "Cobalt Ridge Engineering, LLC", "96400.00"),
    ("w_2", 2, "Larkspur Pediatrics P.C.", "71850.00"),
    ("1098", 1, "Summit Home Lending", "14322.18"),
    ("1099_int", 1, "Aspen Grove Savings", "412.56"),
)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass(frozen=True)
class Whitley:
    tenant: uuid.UUID
    kevin: Person
    client: uuid.UUID
    entity: uuid.UUID
    engagement: uuid.UUID
    return_2024: uuid.UUID
    authorization: uuid.UUID
    transcript: uuid.UUID

    @property
    def ctx(self) -> AuthContext:
        return self.kevin.context()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _transcript(seed: Seeder, w: dict[str, object], name: str, kind: str) -> uuid.UUID:
    """A transcript as the upload stores it: its staged file, evidence version and parsed lines."""
    text = (GOLDEN / name).read_text(encoding="utf-8")
    parsed = parse_transcript(text, cast(TranscriptKind, kind))
    assert parsed.parsed
    tenant, entity, kevin = w["tenant"], w["entity"], cast(Person, w["kevin"])
    file_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO tax_profile_files (tenant_id, client_entity_id, uploaded_by, file_name, "
            "media_type, size_bytes, sha256, storage_key, storage_version_id) VALUES ($1, $2, $3, "
            "$4, 'text/plain', $5, $6, 'probe', 'v1') RETURNING id",
            tenant,
            entity,
            kevin.user_id,
            name,
            len(text),
            _sha(text),
        ),
    )
    item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, client_id, scope, folder_kind, title, "
        "created_by_kind, created_by_id) VALUES ($1, $2, 'client', 'source_documents', $3, "
        "'human', $4) RETURNING id",
        tenant,
        w["client"],
        name,
        str(kevin.user_id),
    )
    version = await seed.value(
        "INSERT INTO evidence_versions (tenant_id, evidence_item_id, version_no, fingerprint, "
        "storage_key, storage_version_id, size_bytes, media_type, source, method, pulled_at, "
        "channel, display_name) VALUES ($1, $2, 1, $3, $6, 'v1', $4, 'text/plain', "
        "'irs_transcript', 'retrieved', now(), 'retrieval', $5) RETURNING id",
        tenant,
        item,
        _sha(text),
        len(text),
        name,
        f"tenants/{tenant}/sha256/{_sha(text)}",
    )
    transcript = uuid.uuid4()
    await seed.run(
        "INSERT INTO transcripts (id, tenant_id, client_entity_id, kind, tax_year, pulled_at, "
        "pulled_by, authorization_id, evidence_version_id, file_id, parse_status, "
        "account_balance) VALUES ($1, $2, $3, $4, $5, now(), $6, $7, $8, $9, 'parsed', $10)",
        transcript,
        tenant,
        entity,
        kind,
        parsed.tax_year,
        kevin.user_id,
        w["authorization"],
        version,
        file_id,
        parsed.account_balance,
    )
    for row in tax_profile.line_rows(cast(uuid.UUID, tenant), transcript, parsed):
        await seed.run(
            "INSERT INTO transcript_lines (tenant_id, transcript_id, line_no, form, payer_name, "
            "amount, tc_code, tc_date) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            *row.values(),
        )
    return transcript


async def _approved_import(
    seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID, item: uuid.UUID, kevin: Person
) -> uuid.UUID:
    checkpoint = uuid.uuid4()
    actor = ("human", str(kevin.user_id))
    await seed.as_actor(
        tenant,
        actor,
        "INSERT INTO checkpoints (id, tenant_id, engagement_id, target_type, target_id, seq, "
        "author_kind, author_ref, cause, status, content_hash) VALUES ($1, $2, $3, 'tax_return', "
        "$4, 1, 'import', 'Imported from CCH Axcess 2024I:WhitleyM:V1', 'engine_import', "
        "'approved', $5)",
        checkpoint,
        tenant,
        engagement,
        item,
        _sha("whitley-2024"),
    )
    for slug, n, payer, amount in FILED_2024:
        for part, value in (
            ("payer", {"t": "text", "v": payer}),
            ("amount", {"t": "decimal", "v": amount}),
        ):
            await seed.as_actor(
                tenant,
                actor,
                "INSERT INTO checkpoint_diffs (tenant_id, checkpoint_id, field_key, old, new, "
                "cause) VALUES ($1, $2, $3, NULL, $4::jsonb, 'import')",
                tenant,
                checkpoint,
                f"ir.{slug}.{n}.{part}",
                json.dumps(value),
            )
    return checkpoint


@pytest.fixture
async def whitley(seed: Seeder) -> Whitley:
    tenant = await seed.firm()
    kevin = await seed.person(tenant)
    entity = await seed.entity(tenant, "Marcus Whitley")
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    await seed.run(
        "UPDATE client_entities SET entity_type = 'individual', tin_kind = 'ssn', "
        "tin_last4 = '4410', tin_status = 'on_file', tin_sealed = '\\x00'::bytea, "
        "tin_fingerprint = sha256('probe'::bytea) WHERE id = $1",
        entity,
    )
    engagement = await seed.engagement(tenant, entity, kevin.user_id)
    await seed.member(engagement, kevin, "staff")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2024 Form 1040', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            kevin.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1040', 2024)",
        tenant,
        item,
        engagement,
        entity,
    )
    authorization = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO tax_authorizations (tenant_id, client_entity_id, form, designees, "
            "tax_matters, tax_years, received_on, status, created_by) VALUES ($1, $2, '8821', "
            "$3::jsonb, '{Income}', '{2022,2023,2024,2025,2026}', '2026-02-03', 'on_file', $4) "
            "RETURNING id",
            tenant,
            entity,
            json.dumps(
                [{"user_id": str(kevin.user_id), "caf_sealed": "c2VhbGVk", "caf_last4": "4471"}]
            ),
            kevin.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'clients.tax_profile', 'true', 't01', 'TASK-2601')",
        tenant,
    )
    w = {
        "tenant": tenant,
        "entity": entity,
        "client": client,
        "kevin": kevin,
        "authorization": authorization,
    }
    transcript = await _transcript(seed, w, "whitley_wage_income_2024.txt", "wage_income")
    await _approved_import(seed, tenant, engagement, item, kevin)
    return Whitley(tenant, kevin, client, entity, engagement, item, authorization, transcript)


async def test_ac30_whitley_2024_two_differences_total_3120_by_code(whitley: Whitley) -> None:
    out = await tax_profile.compare(
        whitley.ctx, whitley.transcript, TranscriptComparisonIn(return_id=whitley.return_2024)
    )
    assert out.result == "differences"
    assert out.difference_total == Decimal("3120.00")
    differing = [
        (x.payer_name, x.transcript_amount, x.return_amount, x.status)
        for x in out.lines
        if x.status != "agrees"
    ]
    assert differing == [
        ("FRONT RANGE BANK", Decimal("1870.00"), None, "not_on_return"),
        ("LAKEVIEW CREDIT UNION", Decimal("1250.00"), None, "not_on_return"),
    ]
    assert [(a.form, a.count) for a in out.agreeing] == [("W-2", 2), ("1098", 1), ("1099-INT", 1)]
    assert out.checkpoint_id is not None
    latest = await tax_profile.comparison(whitley.ctx, whitley.transcript)
    assert latest.id == out.id and latest.difference_total == Decimal("3120.00")
    (row,) = await tax_profile.transcripts(whitley.ctx, whitley.entity)
    assert (row.result, row.difference_count, row.authorization_form) == ("differences", 2, "8821")


async def test_ac31_no_return_as_filed_or_another_year_is_refused(
    seed: Seeder, whitley: Whitley
) -> None:
    await seed.run(
        "UPDATE tax_returns SET tax_year = 2025 WHERE work_item_id = $1", whitley.return_2024
    )
    with pytest.raises(DomainConflict) as refused:
        await tax_profile.compare(
            whitley.ctx, whitley.transcript, TranscriptComparisonIn(return_id=whitley.return_2024)
        )
    assert refused.value.code == "return_mismatch"


async def test_ac32_the_profile_never_serves_a_full_caf_or_ssn(whitley: Whitley) -> None:
    profile = await org_profile.profile(whitley.ctx, whitley.entity)
    body = profile.model_dump_json()
    assert "4471" in body and "4410" in body  # last four only
    assert not re.search(r"\b\d{9,}\b", body)  # no full SSN, CAF or other 9+ digit identifier
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", body)
    (authorization,) = profile.authorizations
    assert [d.caf_last4 for d in authorization.designees] == ["4471"]
    assert "caf_sealed" not in body
    assert profile.taxpayer_tin is not None and profile.taxpayer_tin.last4 == "4410"


async def test_ac33_elections_upsert_with_seen_version(whitley: Whitley) -> None:
    first = await tax_profile.put_election(
        whitley.ctx,
        whitley.entity,
        "ptet",
        TaxElectionIn(
            jurisdiction="IL", tax_year=2025, amount=Decimal("28044"), status_code="elected"
        ),
    )
    assert first.row_version == 1
    with pytest.raises(DomainConflict) as stale:
        await tax_profile.put_election(
            whitley.ctx,
            whitley.entity,
            "ptet",
            TaxElectionIn(jurisdiction="IL", tax_year=2025, status_code="elected"),
        )
    assert stale.value.code == "stale_version"
    second = await tax_profile.put_election(
        whitley.ctx,
        whitley.entity,
        "ptet",
        TaxElectionIn(
            jurisdiction="IL",
            tax_year=2025,
            amount=Decimal("28044"),
            status_code="elected",
            seen_version=1,
        ),
    )
    assert second.row_version == 2
    assert [e.amount for e in await tax_profile.elections(whitley.ctx, whitley.entity)] == [
        Decimal("28044.00")
    ]


async def test_ac34_transcript_rows_are_insert_only(seed: Seeder, whitley: Whitley) -> None:
    for sql in (
        "UPDATE transcripts SET tax_year = 2023 WHERE id = $1",
        "DELETE FROM transcript_lines WHERE transcript_id = $1",
    ):
        with pytest.raises(Exception, match="insert-only"):
            await seed.run(sql, whitley.transcript)
