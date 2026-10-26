"""A-01-T18 (TASK-1334; A-01 §4.2 M2; SPEC-344 AC-6 to AC-8; DEC-435): engagement exports.

- `engagement_exports`: one binder export of an audit work item, requested by a person
  (`requested_by_kind = 'human'`: the database refuses an agent, the system or support, INV-1)
  with a fresh second factor (`mfa_at`) and held by a single-use approval grant (`grant_id`,
  P-35) until `not_before`, the end of the 10-second Undo window. The app inserts the request's
  columns; `status` starts `queued` (the default) and moves forward only (the guard):
  queued -> packaging | undone | failed; packaging -> ready | failed; ready -> expired. `undone`
  is the requester's own act, as a person, before `not_before` (`undo_window_closed`). A ready
  export carries its digests and its expiry (CHECK). The app may update the status and the stamps
  only; DELETE is revoked. Index `(tenant_id, work_item_id, requested_at DESC)` for the sheet's
  history.
- `engagement_export_downloads` (insert-only, ADR-004): each download with bytes and range
  (A-01-T22 writes it).
- `engagement_export_contents` (insert-only): the evidence versions a package holds, so a
  withdrawn file voids the ready bundle (A-01-T22).

Revision ID: 0191
Revises: 0190
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0191"
down_revision = "0190"
branch_labels = None
depends_on = None

_INSERT_ONLY = ("engagement_export_downloads", "engagement_export_contents")


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE engagement_exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            client_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('binder', 'final_binder')),
            scope jsonb NOT NULL CHECK (jsonb_typeof(scope) = 'object'),
            format_version text NOT NULL CHECK (format_version ~ '^[0-9]+\.[0-9]+$'),
            requested_by uuid NOT NULL,
            requested_by_kind text NOT NULL CHECK (requested_by_kind = 'human'),
            requested_at timestamptz NOT NULL DEFAULT abacus_now(),
            mfa_at timestamptz NOT NULL,
            grant_id uuid NOT NULL,
            not_before timestamptz NOT NULL,
            status text NOT NULL DEFAULT 'queued' CHECK (
                status IN ('queued', 'packaging', 'ready', 'failed', 'expired', 'undone')
            ),
            as_of_seq bigint NULL CHECK (as_of_seq >= 0),
            bundle_sha256 text NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
            manifest_sha256 text NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            bytes bigint NULL CHECK (bytes >= 0),
            file_count integer NULL CHECK (file_count >= 0),
            request_count integer NULL CHECK (request_count >= 0),
            segment_count integer NULL CHECK (segment_count >= 1),
            object_prefix text NULL CHECK (char_length(object_prefix) <= 200),
            ready_at timestamptz NULL,
            expires_at timestamptz NULL,
            failure_code text NULL CHECK (
                failure_code IN ('integrity_mismatch', 'export_section_missing', 'build_error')
            ),
            void_reason text NULL CHECK (void_reason IN ('withdrawn_content', 'expired')),
            undone_at timestamptz NULL,
            undone_by uuid NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, grant_id) REFERENCES approval_grants (tenant_id, id),
            CONSTRAINT engagement_exports_ready CHECK (
                status <> 'ready' OR (
                    bundle_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL
                    AND expires_at IS NOT NULL
                )
            ),
            CONSTRAINT engagement_exports_undone CHECK (
                (status = 'undone') = (undone_at IS NOT NULL)
                AND (undone_at IS NULL) = (undone_by IS NULL)
            ),
            CONSTRAINT engagement_exports_failed CHECK (
                (status = 'failed') = (failure_code IS NOT NULL)
            ),
            CONSTRAINT engagement_exports_window CHECK (not_before > requested_at)
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_exports_history ON engagement_exports "
        "(tenant_id, work_item_id, requested_at DESC, id DESC)"
    )
    tenant_table(op, "engagement_exports")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON engagement_exports FROM abacus_app")
    insert_columns(
        op,
        "engagement_exports",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "client_id",
            "kind",
            "scope",
            "format_version",
            "requested_by",
            "requested_by_kind",
            "mfa_at",
            "grant_id",
            "not_before",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, as_of_seq, bundle_sha256, manifest_sha256, bytes, file_count, "
        "request_count, segment_count, object_prefix, ready_at, expires_at, failure_code, "
        "void_reason, undone_at, undone_by) ON engagement_exports TO abacus_app"
    )
    # Forward only; Undo is the requester's, as a person, inside the window (business clock).
    op.execute(
        """
        CREATE FUNCTION engagement_exports_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.status = OLD.status THEN
                IF NEW.status NOT IN ('packaging', 'ready') THEN
                    RAISE EXCEPTION 'a % export takes no change', OLD.status
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF NOT (
                (OLD.status = 'queued' AND NEW.status IN ('packaging', 'undone', 'failed'))
                OR (OLD.status = 'packaging' AND NEW.status IN ('ready', 'failed'))
                OR (OLD.status = 'ready' AND NEW.status = 'expired')
            ) THEN
                RAISE EXCEPTION 'an export moves from % to % never', OLD.status, NEW.status
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status = 'undone' AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM OLD.requested_by::text
                OR NEW.undone_by IS DISTINCT FROM OLD.requested_by
            ) THEN
                RAISE EXCEPTION 'an export is undone by its requester only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.status = 'undone' AND abacus_now() >= OLD.not_before THEN
                RAISE EXCEPTION 'undo_window_closed' USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status = 'expired' AND NEW.void_reason IS NULL THEN
                RAISE EXCEPTION 'an expired export names why' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagement_exports_guard BEFORE UPDATE ON engagement_exports "
        "FOR EACH ROW EXECUTE FUNCTION engagement_exports_guard()"
    )
    op.execute(
        """
        CREATE TABLE engagement_export_downloads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            export_id uuid NOT NULL,
            user_id uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            bytes_sent bigint NOT NULL CHECK (bytes_sent >= 0),
            range_start bigint NULL CHECK (range_start >= 0),
            range_end bigint NULL CHECK (range_end >= range_start),
            mfa_at timestamptz NOT NULL,
            FOREIGN KEY (tenant_id, export_id) REFERENCES engagement_exports (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engagement_export_contents (
            tenant_id uuid NOT NULL,
            export_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            PRIMARY KEY (tenant_id, export_id, evidence_version_id),
            FOREIGN KEY (tenant_id, export_id) REFERENCES engagement_exports (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_export_contents_by_version ON engagement_export_contents "
        "(tenant_id, evidence_version_id)"
    )
    op.execute(
        """
        CREATE FUNCTION engagement_export_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in _INSERT_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION engagement_export_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION engagement_export_rows_immutable()"
        )
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "engagement_export_downloads",
        ("tenant_id", "export_id", "user_id", "bytes_sent", "range_start", "range_end", "mfa_at"),
    )
    insert_columns(
        op, "engagement_export_contents", ("tenant_id", "export_id", "evidence_version_id")
    )


def downgrade() -> None:
    for table in reversed(_INSERT_ONLY):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION engagement_export_rows_immutable()")
    op.execute("DROP TABLE engagement_exports")
    op.execute("DROP FUNCTION engagement_exports_guard()")
