"""Duplicate uploads a person resolves (T-02-T17; T-02 §4.2 `evidence_duplicates`; DEC-58 g;
DEC-1371; expand-only). Red (evidence).

Under `evidence.duplicate_review`, a client-channel upload with the same bytes as a version already
on the request is accepted and flagged (`upload_checks` `duplicate_hash`, a free check code since
0044) instead of refused. A person then keeps the newer or discards the duplicate; each decision is
one insert-only `duplicate_resolutions` row naming the version decided on and the one kept. A
discard voids and hides the version through P-31's path and never deletes it; an accepted version
is never discarded or superseded (the service, and the fulfilment's own accept guard).

Revision ID: 0468
Revises: 0467
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0468"
down_revision = "0467"
branch_labels = None
depends_on = None

_IMMUTABLE = """
    CREATE FUNCTION duplicate_resolutions_immutable() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        RAISE EXCEPTION 'duplicate resolutions are insert-only'
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE duplicate_resolutions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            version_id uuid NOT NULL,
            kept_version_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('keep_newer', 'discard_duplicate')),
            decided_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT duplicate_resolutions_once UNIQUE (tenant_id, version_id),
            CONSTRAINT duplicate_resolutions_two CHECK (version_id <> kept_version_id),
            FOREIGN KEY (tenant_id, version_id) REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, kept_version_id) REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "duplicate_resolutions")
    insert_only(op, "duplicate_resolutions")
    insert_columns(
        op,
        "duplicate_resolutions",
        ("tenant_id", "engagement_id", "version_id", "kept_version_id", "decision", "decided_by"),
    )
    op.execute(_IMMUTABLE)
    op.execute(
        "CREATE TRIGGER duplicate_resolutions_immutable BEFORE UPDATE OR DELETE ON "
        "duplicate_resolutions FOR EACH ROW EXECUTE FUNCTION duplicate_resolutions_immutable()"
    )
    op.execute("REVOKE TRUNCATE ON duplicate_resolutions FROM abacus_app")
    op.execute(
        "CREATE TRIGGER duplicate_resolutions_no_truncate BEFORE TRUNCATE "
        "ON duplicate_resolutions FOR EACH STATEMENT "
        "EXECUTE FUNCTION duplicate_resolutions_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE duplicate_resolutions")
    op.execute("DROP FUNCTION duplicate_resolutions_immutable()")
