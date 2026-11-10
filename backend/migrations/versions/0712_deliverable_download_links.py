"""R-02-T07: single-use, 60-second deliverable download links (R-02 §3.15 AC-39; ADR-104).

ADR-104 keeps presigned object URLs out of every answer (objects are ciphertext), so a C10
download URL is the API's own file route carrying a link id, as DEC-509 did for firm exports. A
`deliverable_download_links` row is issued to one person for one deliverable version and its
evidence version, expires 60 seconds after issue (server-set), and is used once: `used_at` is set
once, never after expiry, and the row is never deleted. The person on the row is the session's
actor (the CHECK binds `user_id` to `app.actor_id`), so a link cannot be issued for someone else.

Revision ID: 0712
Revises: 0711
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0712"
down_revision = "0711"
branch_labels = None
depends_on = None

INSERTS = (
    "id", "tenant_id", "deliverable_version_id", "evidence_version_id", "contact_id", "user_id",
    "request_id",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE deliverable_download_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            deliverable_version_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            user_id uuid NOT NULL,
            request_id uuid NULL,
            -- one statement_timestamp() for both: two clock_timestamp() reads differ by a
            -- microsecond and the second would break the sixty-second CHECK below
            issued_at timestamptz NOT NULL DEFAULT statement_timestamp(),
            expires_at timestamptz NOT NULL DEFAULT statement_timestamp() + interval '60 seconds',
            used_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, deliverable_version_id)
                REFERENCES deliverable_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            CONSTRAINT deliverable_download_links_sixty_seconds
                CHECK (expires_at <= issued_at + interval '60 seconds'),
            CONSTRAINT deliverable_download_links_issued_to_the_actor
                CHECK (user_id::text = current_setting('app.actor_id', true)),
            CONSTRAINT deliverable_download_links_used_in_time
                CHECK (used_at IS NULL OR used_at <= expires_at)
        )
        """
    )
    tenant_table(op, "deliverable_download_links")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON deliverable_download_links FROM abacus_app")
    insert_columns(op, "deliverable_download_links", INSERTS)
    op.execute("GRANT UPDATE (used_at) ON deliverable_download_links TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION deliverable_download_links_once() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RAISE EXCEPTION 'deliverable_download_links is never deleted'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.used_at IS NOT NULL THEN
                RAISE EXCEPTION 'a download link is used once'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF (to_jsonb(NEW) - 'used_at') IS DISTINCT FROM (to_jsonb(OLD) - 'used_at') THEN
                RAISE EXCEPTION 'a download link changes only when used'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION deliverable_download_links_once() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER deliverable_download_links_once BEFORE UPDATE OR DELETE "
        "ON deliverable_download_links FOR EACH ROW "
        "EXECUTE FUNCTION deliverable_download_links_once()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE deliverable_download_links")
    op.execute("DROP FUNCTION deliverable_download_links_once()")
