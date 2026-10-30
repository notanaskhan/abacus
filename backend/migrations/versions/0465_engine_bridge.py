"""The engine bridge's records (T-01-T19; T-01 §4.2 `engine_bridge`; DEC-1363; expand-only).

Four tables, owned by `tax` (the plan named `integrations`, which may not read `review`: the
import's checkpoint and field values are review's, so the owner is the module that may call it):

- `engine_return_links`: a return's id in the engine and the engine version Accrued last took
  (`2025I:FeldJ`, V3). One per return and engine; the version moves on an approved import.
- `engine_sync_events` (insert-only): what crossed the bridge and when. A file that came back is
  stored write-once and encrypted (evidence's staging); this row keeps its key, version, size and
  SHA-256 so it is read back fingerprint-checked. No file content is ever in a column.
- `engine_import_diffs`: one per values import, its code-computed rows (field, Accrued, engine,
  cause) and the proposed checkpoint it waits on; `status` moves once, by a person.
- `engine_diagnostics` (insert-only but for `issue_id`): the engine's messages per import.

Values, diffs and diagnostics are TRI (ADR-031): restricted, never logged. The engine's message
text is client-system content (ADR-052). Forced RLS on all four.

Revision ID: 0465
Revises: 0464
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0465"
down_revision = "0464"
branch_labels = None
depends_on = None

_KINDS = (
    "'export_generated', 'marked_exported', 'import_uploaded', 'import_approved', "
    "'import_rejected', 'diagnostics', 'pdfs', 'acks'"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine_return_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            engine text NOT NULL CHECK (engine IN ('cch_axcess')),
            engine_return_id text NOT NULL
                CHECK (engine_return_id ~ '^[0-9]{4}[A-Z]:[A-Za-z0-9]{1,20}$'),
            version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT engine_return_links_one UNIQUE (tenant_id, return_id, engine),
            CONSTRAINT engine_return_links_engine_id UNIQUE (tenant_id, engine, engine_return_id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE engine_sync_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ({_KINDS})),
            engine_return_id text NULL,
            version integer NULL CHECK (version IS NULL OR version >= 1),
            file_name text NULL CHECK (length(file_name) BETWEEN 1 AND 255),
            file_key text NULL,
            file_version text NULL,
            file_size bigint NULL CHECK (file_size IS NULL OR file_size > 0),
            payload_sha256 text NULL CHECK (payload_sha256 ~ '^[0-9a-f]{{64}}$'),
            actor_user_id uuid NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind IN ('human', 'system')),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            summary jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(summary) = 'object'),
            write_operation_id uuid NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT engine_sync_events_file CHECK (
                (file_key IS NULL) = (file_version IS NULL)
                AND (file_key IS NULL) = (payload_sha256 IS NULL)
                AND (file_key IS NULL) = (file_size IS NULL)
            ),
            CONSTRAINT engine_sync_events_person CHECK (
                actor_kind <> 'human' OR actor_user_id IS NOT NULL
            ),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX engine_sync_events_return ON engine_sync_events (tenant_id, return_id, at)"
    )
    op.execute(
        """
        CREATE TABLE engine_import_diffs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            sync_event_id uuid NOT NULL,
            checkpoint_id uuid NULL,
            approved_checkpoint_id uuid NULL,
            engine_return_id text NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            rows jsonb NOT NULL CHECK (jsonb_typeof(rows) = 'array'),
            status text NOT NULL DEFAULT 'pending_approval'
                CHECK (status IN ('pending_approval', 'approved', 'rejected')),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT engine_import_diffs_one UNIQUE (tenant_id, sync_event_id),
            CONSTRAINT engine_import_diffs_decided CHECK (
                (status = 'pending_approval') = (decided_by IS NULL)
                AND (decided_by IS NULL) = (decided_at IS NULL)
            ),
            FOREIGN KEY (tenant_id, sync_event_id) REFERENCES engine_sync_events (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engine_diagnostics (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            sync_event_id uuid NOT NULL,
            code text NOT NULL CHECK (length(code) BETWEEN 1 AND 40),
            severity text NOT NULL CHECK (severity IN ('error', 'warning', 'informational')),
            field_key text NULL CHECK (length(field_key) BETWEEN 1 AND 80),
            message_text text NOT NULL CHECK (length(message_text) BETWEEN 1 AND 2000),
            issue_id uuid NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, sync_event_id) REFERENCES engine_sync_events (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    for table in (
        "engine_return_links",
        "engine_sync_events",
        "engine_import_diffs",
        "engine_diagnostics",
    ):
        tenant_table(op, table)
    insert_columns(
        op, "engine_return_links", ("tenant_id", "return_id", "engine", "engine_return_id")
    )
    op.execute("REVOKE UPDATE, DELETE ON engine_return_links FROM abacus_app")
    op.execute("GRANT UPDATE (version) ON engine_return_links TO abacus_app")
    insert_only(op, "engine_sync_events")
    op.execute(
        "CREATE TRIGGER engine_sync_events_immutable BEFORE UPDATE OR DELETE ON "
        "engine_sync_events FOR EACH ROW EXECUTE FUNCTION tax_return_events_immutable()"
    )
    op.execute("REVOKE TRUNCATE ON engine_sync_events FROM abacus_app")
    op.execute(
        "CREATE TRIGGER engine_sync_events_no_truncate BEFORE TRUNCATE ON engine_sync_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION tax_return_events_immutable()"
    )
    insert_columns(
        op,
        "engine_sync_events",
        (
            "tenant_id",
            "return_id",
            "kind",
            "engine_return_id",
            "version",
            "file_name",
            "file_key",
            "file_version",
            "file_size",
            "payload_sha256",
            "actor_user_id",
            "summary",
            "write_operation_id",
        ),
    )
    insert_columns(
        op,
        "engine_import_diffs",
        (
            "tenant_id",
            "return_id",
            "sync_event_id",
            "checkpoint_id",
            "engine_return_id",
            "version",
            "rows",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON engine_import_diffs FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, approved_checkpoint_id, decided_by, decided_at, row_version) "
        "ON engine_import_diffs TO abacus_app"
    )
    insert_columns(
        op,
        "engine_diagnostics",
        (
            "tenant_id",
            "return_id",
            "sync_event_id",
            "code",
            "severity",
            "field_key",
            "message_text",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON engine_diagnostics FROM abacus_app")
    op.execute("GRANT UPDATE (issue_id) ON engine_diagnostics TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE engine_diagnostics")
    op.execute("DROP TABLE engine_import_diffs")
    op.execute("DROP TABLE engine_sync_events")
    op.execute("DROP TABLE engine_return_links")
