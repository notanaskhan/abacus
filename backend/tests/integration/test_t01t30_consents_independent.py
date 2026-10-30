# ac-test-author: ayushkbhatia
"""T-01-T30 (ADR-078; TASK-2418): the database half of §7216 consents (0402; C19 §1, §2, §5),
written from the C19 contract and SPEC-501, not from the code: one purpose per row, a standing
decline refuses a new request for the same taxpayer, purpose and years until it is superseded,
the event log is immutable, the record and export actions ask a fresh second factor, and the
agent holds no consent action. The planted combined document is in
`tests/unit/tax/test_t01t30_consent_plant.py`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import cast

import asyncpg
import pytest
import yaml

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

ROOT = Path(__file__).resolve().parents[3]


async def _taxpayer(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant, "Feld household")
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    return tenant, person.user_id, client, entity


async def _consent(
    seed: Seeder,
    tenant: uuid.UUID,
    by: uuid.UUID,
    client: uuid.UUID,
    entity: uuid.UUID,
    *,
    purpose: str = "use",
    status: str = "requested",
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
            "provider_terms_version, template_version_id, text_sha256, source, status, "
            "declined_at, created_by) VALUES ($1, $2, $3, $4, ARRAY[2025], 'v1', $5, $6, "
            "'record', $7, CASE WHEN $7 = 'declined' THEN now() END, $8) RETURNING id",
            tenant,
            client,
            entity,
            purpose,
            uuid.uuid4(),
            b"\x01" * 32,
            status,
            by,
        ),
    )


async def test_one_purpose_per_row(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, by, client, entity = await _taxpayer(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await _consent(seed, tenant, by, client, entity, purpose="use,ai_disclosure")


async def test_a_standing_decline_blocks_re_solicitation(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, by, client, entity = await _taxpayer(seed)
    declined = await _consent(seed, tenant, by, client, entity, status="declined")
    with pytest.raises(asyncpg.UniqueViolationError):
        await _consent(seed, tenant, by, client, entity)
    # Another purpose is its own document and may be asked.
    await _consent(seed, tenant, by, client, entity, purpose="ai_disclosure")
    # Once the decline is superseded, the purpose may be asked again.
    await seed.run("UPDATE consents SET status = 'superseded' WHERE id = $1", declined)
    await _consent(seed, tenant, by, client, entity)


async def test_the_event_log_is_immutable(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, by, client, entity = await _taxpayer(seed)
    consent = await _consent(seed, tenant, by, client, entity)
    event = await seed.value(
        "INSERT INTO consent_events (tenant_id, consent_id, kind, actor_kind, actor_id) "
        "VALUES ($1, $2, 'requested', 'human', $3) RETURNING id",
        tenant,
        consent,
        str(by),
    )
    with pytest.raises(asyncpg.PostgresError):
        await seed.run("UPDATE consent_events SET kind = 'signed' WHERE id = $1", event)
    with pytest.raises(asyncpg.PostgresError):
        await seed.run("DELETE FROM consent_events WHERE id = $1", event)


def test_record_and_export_ask_a_fresh_second_factor_and_the_agent_holds_none() -> None:
    fresh = cast(
        dict[str, list[dict[str, str]]],
        yaml.safe_load((ROOT / "docs/architecture/fresh-mfa-actions.yaml").read_text()),
    )
    listed = {a["action"] for a in fresh["actions"]}
    assert {"consent.record", "consent.export"} <= listed
    matrix = cast(
        dict[str, dict[str, dict[str, object]]],
        yaml.safe_load(
            (ROOT / "docs/architecture/permission-matrix/organisations.yaml").read_text()
        ),
    )
    consent = {k: v for k, v in matrix["actions"].items() if k.startswith("consent.")}
    assert consent
    for name, row in consent.items():
        assert row.get("agent", "deny") == "deny", name
