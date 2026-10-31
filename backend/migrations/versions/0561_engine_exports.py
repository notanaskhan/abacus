"""Engine exports and write operations (T-01-T25; T-01 §4.2; `docs/contracts/tax-engine-bridge.md`
§2, §6; ADR-150; DEC-1462). Expand-only.

- `write_operations` (insert-only): one row per write a capability performed, here the W2 file
  bridge's export. It names the capability, the subject, the approval grant it consumed and the
  SHA-256 of what was written. A grant is consumed once (`UNIQUE (grant_id)`), and only a person
  acting (`app.actor_kind = 'human'`) can insert one: an agent or system context is refused by the
  database as well as the matrix and the service (INV-1).
- `engine_exports`: the workbook generated from an approved checkpoint, stored write-once and
  encrypted (evidence's staging; this row keeps the key, version, size and SHA-256 so a download
  is fingerprint-checked). Only `marked_exported_at`, `marked_exported_by` and `row_version` change
  after insert, once, by a person.

Both are tax's tables under forced row-level security. No file content is ever in a column.
`engine_export.generated` and `engine_export.marked_exported` join `abacus_human_only_actions()`
(the register's 62 entries; the downgrade restores 0290's 60).

Revision ID: 0561
Revises: 0560
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0561"
down_revision = "0560"
branch_labels = None
depends_on = None

OPERATION_INSERT = (
    "id",
    "tenant_id",
    "capability",
    "subject_type",
    "subject_id",
    "grant_id",
    "payload_sha256",
    "performed_by",
)
_BEFORE = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
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
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
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
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]

_HUMAN_ONLY = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
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
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
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
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


EXPORT_INSERT = (
    "id",
    "tenant_id",
    "return_id",
    "checkpoint_id",
    "content_hash",
    "engine_return_id",
    "version",
    "file_name",
    "file_key",
    "file_version",
    "file_size",
    "sha256",
    "write_operation_id",
    "generated_by",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE write_operations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            capability text NOT NULL CHECK (capability ~ '^[a-z][a-z0-9_]{1,63}$'),
            subject_type text NOT NULL CHECK (subject_type ~ '^[a-z][a-z_]{0,39}$'),
            subject_id uuid NOT NULL,
            grant_id uuid NOT NULL,
            payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
            performed_by uuid NOT NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (grant_id),
            FOREIGN KEY (tenant_id, grant_id) REFERENCES approval_grants (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engine_exports (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            checkpoint_id uuid NOT NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^(sha256:)?[0-9a-f]{64}$'),
            engine_return_id text NOT NULL
                CHECK (engine_return_id ~ '^[0-9]{4}[A-Z]:[A-Za-z0-9]{1,20}$'),
            version integer NOT NULL CHECK (version >= 1),
            file_name text NOT NULL CHECK (length(file_name) BETWEEN 1 AND 255),
            file_key text NOT NULL,
            file_version text NOT NULL,
            file_size bigint NOT NULL CHECK (file_size > 0),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            write_operation_id uuid NOT NULL,
            generated_by uuid NOT NULL,
            generated_at timestamptz NOT NULL DEFAULT abacus_now(),
            marked_exported_at timestamptz NULL,
            marked_exported_by uuid NULL,
            row_version integer NOT NULL DEFAULT 1,
            UNIQUE (tenant_id, id),
            -- One export per approved checkpoint: a second request answers the first (idempotent).
            UNIQUE (tenant_id, return_id, checkpoint_id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            FOREIGN KEY (tenant_id, write_operation_id)
                REFERENCES write_operations (tenant_id, id),
            CHECK ((marked_exported_at IS NULL) = (marked_exported_by IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION engine_exports_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RAISE EXCEPTION 'engine_exports keeps every export'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.marked_exported_at IS NOT NULL THEN
                RAISE EXCEPTION 'export % was already marked exported', OLD.id
                    USING ERRCODE = 'check_violation';
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
                RAISE EXCEPTION 'only a person marks an export exported'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER engine_exports_guard BEFORE UPDATE OR DELETE ON engine_exports "
        "FOR EACH ROW EXECUTE FUNCTION engine_exports_guard()"
    )
    for table in ("write_operations", "engine_exports"):
        tenant_table(op, table)
        op.execute(f"REVOKE TRUNCATE ON {table} FROM abacus_app")
    insert_only(op, "write_operations")
    insert_columns(op, "write_operations", OPERATION_INSERT)
    op.execute("REVOKE UPDATE, DELETE ON engine_exports FROM abacus_app")
    insert_columns(op, "engine_exports", EXPORT_INSERT)
    op.execute(
        "GRANT UPDATE (marked_exported_at, marked_exported_by, row_version) "
        "ON engine_exports TO abacus_app"
    )
    # INV-1 at the audit layer: generating and marking an export are a person's (62 entries).
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute("DROP TABLE engine_exports")
    op.execute("DROP FUNCTION engine_exports_guard()")
    op.execute("DROP TABLE write_operations")
