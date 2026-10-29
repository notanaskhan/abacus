"""An engagement past acceptance, written directly for tests and the local stack (P-07-T59;
DEC-906). Product code never imports this.

SPEC-025's `engagement_acceptance` row was how a test or a local stack opened an engagement to
client data. With it gone, G1 reads CLI-07's decision and G2 CLI-08's conclusion, so
`open_engagement` writes those instead, as an engagement that went through CLI-07 and CLI-08
holds them:

- a questionnaire template version for the firm (`Seeded acceptance`, backdated to 2000 so a
  template a test imports is always the newest and start-acceptance picks it);
- an acceptance record `decided` (or `declined`) with its decision;
- a positive independence conclusion, unless `concluded` is false.

The guards that bind the app (a decider who is the record's partner-level EP with fresh MFA; a
conclusion that is the EP's own) are for the application's writes; seeding, like the suites'
`run_untriggered`, writes the rows in one transaction with triggers and foreign-key checks off,
so no test gains a team member it did not ask for. The sealed rationale is empty: nothing reads
it back from a seeded record.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

import asyncpg

TEMPLATE: Final = "Seeded acceptance"
_SECTIONS: Final = json.dumps([{"code": "scope", "title": "Scope"}])

Decision = Literal["accept", "accept_with_conditions", "decline"]


async def open_engagement(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    engagement_id: UUID,
    *,
    decided_by: UUID | None = None,
    decision: Decision = "accept",
    concluded: bool = True,
    decided_at: datetime | None = None,
) -> None:
    """Accept (or decline) the engagement and, unless `concluded` is false, conclude on
    independence; `decided_by` defaults to the engagement's creator, `decided_at` to now."""
    async with conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        by = decided_by or await conn.fetchval(
            "SELECT created_by FROM engagements WHERE tenant_id = $1 AND id = $2",
            tenant_id,
            engagement_id,
        )
        await conn.execute(
            "INSERT INTO acceptance_questionnaire_templates "
            "(tenant_id, name, family, created_by, created_at) "
            "VALUES ($1, $2, 'audit_assurance', $3, '2000-01-01') "
            "ON CONFLICT (tenant_id, name) DO NOTHING",
            tenant_id,
            TEMPLATE,
            by,
        )
        await conn.execute(
            "INSERT INTO acceptance_questionnaire_template_versions "
            "(tenant_id, template_id, version_no, sections, created_by, created_at) "
            "SELECT $1, t.id, 1, $2::jsonb, $3, '2000-01-01' "
            "FROM acceptance_questionnaire_templates t WHERE t.tenant_id = $1 AND t.name = $4 "
            "ON CONFLICT (tenant_id, template_id, version_no) DO NOTHING",
            tenant_id,
            _SECTIONS,
            by,
            TEMPLATE,
        )
        record = await conn.fetchval(
            "INSERT INTO acceptance_records (tenant_id, engagement_id, client_id, kind, "
            "template_version_id, prepared_by, status) "
            "SELECT $1, e.id, e.client_id, 'continuance', v.id, $3, $4 "
            "FROM engagements e, acceptance_questionnaire_template_versions v "
            "JOIN acceptance_questionnaire_templates t ON t.id = v.template_id "
            "WHERE e.tenant_id = $1 AND e.id = $2 AND t.tenant_id = $1 AND t.name = $5 "
            "AND v.version_no = 1 RETURNING id",
            tenant_id,
            engagement_id,
            by,
            "declined" if decision == "decline" else "decided",
            TEMPLATE,
        )
        await conn.execute(
            "INSERT INTO acceptance_decisions (tenant_id, record_id, option, rationale_sealed, "
            "decided_by, decided_at, mfa_verified_at, actor_kind) "
            "VALUES ($1, $2, $3, ''::bytea, $4, coalesce($5, clock_timestamp()), "
            "coalesce($5, clock_timestamp()), 'human')",
            tenant_id,
            record,
            decision,
            by,
            decided_at,
        )
        if concluded:
            await conn.execute(
                "INSERT INTO independence_conclusions (tenant_id, engagement_id, option, "
                "concluded_by, concluded_at, mfa_verified_at, actor_kind) "
                "VALUES ($1, $2, 'independent', $3, coalesce($4, clock_timestamp()), "
                "coalesce($4, clock_timestamp()), 'human')",
                tenant_id,
                engagement_id,
                by,
                decided_at,
            )
        await conn.execute("SET LOCAL session_replication_role = origin")


async def withdraw_conclusion(
    conn: asyncpg.Connection, tenant_id: UUID, engagement_id: UUID
) -> None:
    """Remove a seeded independence conclusion (G2 unmet again), as a test needs to show the
    gate closing; the app never deletes one."""
    async with conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        await conn.execute(
            "DELETE FROM independence_conclusions WHERE tenant_id = $1 AND engagement_id = $2",
            tenant_id,
            engagement_id,
        )
