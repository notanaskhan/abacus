"""A-01-T23 (TASK-1443; A-01 §4.2 M3; SPEC-330; DEC-590, DEC-591): record-mode release and archive.

- `assurance_external_releases`: the engagement partner records that the report was released
  outside Accrued (interim G8): the date, the report kind, the person (`actor_kind = 'human'`)
  and their fresh second factor (`mfa_at`). One per work item.
- `assurance_external_archives`: the audit file now lives in the firm's own tool (interim G9),
  recorded against a ready final binder export: its id and manifest SHA-256, and the firm tool's
  reference sealed under the tenant key (bound to the work item). One per work item. This is not
  A-07's sealed archive (P-43): nothing here sets `archive_locked_at`.

Both are insert-only (UPDATE, DELETE and TRUNCATE revoked and refused by a trigger), with forced
row-level security and column-level INSERT. An insert trigger binds `recorded_by` to the session's
own human actor (INV-1). The archive's insert trigger re-reads the export FOR SHARE, so a
withdrawal voiding it or the expiry sweep waits for this unit: the same tenant and work item,
`kind = 'final_binder'`, `status = 'ready'`, not voided, not past `expires_at` on either clock,
and the manifest the service read.

`abacus_human_only_actions()` gains `assurance.release_recorded` and
`assurance.archive_recorded` (0212's list plus these two; the downgrade restores 0212's).

Revision ID: 0226
Revises: 0224
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0226"
down_revision = "0224"
branch_labels = None
depends_on = None

_TABLES = ("assurance_external_releases", "assurance_external_archives")

_HUMAN_ONLY_0212 = [
    "acceptance.decided",
    "acceptance.review_completed",
    "assurance.phase_recorded",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "materiality.decided",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "team.approved",
]
_HUMAN_ONLY = sorted(
    [*_HUMAN_ONLY_0212, "assurance.archive_recorded", "assurance.release_recorded"]
)


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE assurance_external_releases (
            work_item_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            report_released_on date NOT NULL,
            report_kind text NOT NULL CHECK (report_kind IN ('opinion', 'no_report')),
            recorded_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            mfa_at timestamptz NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, work_item_id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE assurance_external_archives (
            work_item_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            export_id uuid NOT NULL,
            manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            firm_tool_ref_sealed bytea NOT NULL CHECK (octet_length(firm_tool_ref_sealed) <= 2048),
            recorded_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            mfa_at timestamptz NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, work_item_id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, export_id) REFERENCES engagement_exports (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION assurance_external_records_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    # INV-1: the person recording is the session's own human actor.
    op.execute(
        """
        CREATE FUNCTION assurance_external_records_actor() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.recorded_by::text
            THEN
                RAISE EXCEPTION 'a record is made by the person acting'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    # The export is re-read under a share lock: a void or an expiry waits for this unit.
    op.execute(
        """
        CREATE FUNCTION assurance_external_archive_export() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v public.engagement_exports%ROWTYPE;
        BEGIN
            SELECT * INTO v FROM public.engagement_exports e
             WHERE e.tenant_id = NEW.tenant_id AND e.id = NEW.export_id
               FOR SHARE;
            IF NOT FOUND
                OR v.work_item_id IS DISTINCT FROM NEW.work_item_id
                OR v.engagement_id IS DISTINCT FROM NEW.engagement_id
                OR v.kind <> 'final_binder'
                OR v.status <> 'ready'
                OR v.void_reason IS NOT NULL
                OR v.expires_at IS NULL
                OR GREATEST(public.abacus_now(), clock_timestamp()) >= v.expires_at
                OR v.manifest_sha256 IS DISTINCT FROM NEW.manifest_sha256
            THEN
                RAISE EXCEPTION 'final_export_required'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'assurance_external_archives_ready_export';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION assurance_external_records_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION assurance_external_records_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_actor BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION assurance_external_records_actor()"
        )
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    op.execute(
        "CREATE TRIGGER assurance_external_archives_export BEFORE INSERT "
        "ON assurance_external_archives "
        "FOR EACH ROW EXECUTE FUNCTION assurance_external_archive_export()"
    )
    op.execute(
        "CREATE INDEX assurance_external_releases_by_engagement "
        "ON assurance_external_releases (tenant_id, engagement_id)"
    )
    op.execute(
        "CREATE INDEX assurance_external_archives_by_engagement "
        "ON assurance_external_archives (tenant_id, engagement_id)"
    )
    insert_columns(
        op,
        "assurance_external_releases",
        (
            "work_item_id",
            "tenant_id",
            "engagement_id",
            "report_released_on",
            "report_kind",
            "recorded_by",
            "actor_kind",
            "mfa_at",
        ),
    )
    insert_columns(
        op,
        "assurance_external_archives",
        (
            "work_item_id",
            "tenant_id",
            "engagement_id",
            "export_id",
            "manifest_sha256",
            "firm_tool_ref_sealed",
            "recorded_by",
            "actor_kind",
            "mfa_at",
        ),
    )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0212)
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION assurance_external_archive_export()")
    op.execute("DROP FUNCTION assurance_external_records_actor()")
    op.execute("DROP FUNCTION assurance_external_records_immutable()")
