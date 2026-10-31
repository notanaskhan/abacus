"""The 8879 amount binding (T-01-T36; T-01 §3.12, §4.2; I-8879-DRIFT; DEC-85; DEC-1566).
Expand-only.

`efile_amount_bindings`: when the Form 8879 envelope is drafted, the figures it authorises (total
income, AGI, tax, withholding, refund and balance due per jurisdiction, from the approved
checkpoint) are bound to it with their SHA-256 and the Pub 1345 tolerances' reference-set version.
A later approved checkpoint or a corrected tolerance that moves a figure beyond the tolerance
supersedes the binding, and C7 marks the envelope superseded. The app may only set
`superseded_at` and `superseded_reason`, once: a guard trigger refuses clearing them (the system
may relock, never unlock), any other change, and every delete. Tax's table, forced RLS.

Classification (ADR-031): `figures` TRI; hashes and ids Internal.

Revision ID: 0524
Revises: 0523
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0524"
down_revision = "0523"
branch_labels = None
depends_on = None

INSERT = (
    "id",
    "tenant_id",
    "return_id",
    "envelope_id",
    "checkpoint_id",
    "figures",
    "figures_sha256",
    "tolerances_ref",
)
UPDATE = ("superseded_at", "superseded_reason")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE efile_amount_bindings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            checkpoint_id uuid NOT NULL,
            figures jsonb NOT NULL CHECK (jsonb_typeof(figures) = 'object'),
            figures_sha256 bytea NOT NULL CHECK (octet_length(figures_sha256) = 32),
            tolerances_ref uuid NOT NULL,
            bound_at timestamptz NOT NULL DEFAULT abacus_now(),
            superseded_at timestamptz NULL,
            superseded_reason text NULL CHECK (char_length(superseded_reason) BETWEEN 1 AND 500),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, envelope_id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            CHECK ((superseded_at IS NULL) = (superseded_reason IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX efile_amount_bindings_open ON efile_amount_bindings (tenant_id, return_id) "
        "WHERE superseded_at IS NULL"
    )
    op.execute(
        """
        CREATE FUNCTION efile_amount_bindings_guard() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'bindings are never deleted'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.superseded_at IS NOT NULL THEN
                RAISE EXCEPTION 'binding_superseded' USING ERRCODE = 'check_violation';
            END IF;
            IF (NEW.tenant_id, NEW.return_id, NEW.envelope_id, NEW.checkpoint_id, NEW.figures,
                NEW.figures_sha256, NEW.tolerances_ref, NEW.bound_at)
                IS DISTINCT FROM (OLD.tenant_id, OLD.return_id, OLD.envelope_id,
                OLD.checkpoint_id, OLD.figures, OLD.figures_sha256, OLD.tolerances_ref,
                OLD.bound_at) THEN
                RAISE EXCEPTION 'a binding is fixed' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER efile_amount_bindings_guard BEFORE UPDATE OR DELETE "
        "ON efile_amount_bindings FOR EACH ROW EXECUTE FUNCTION efile_amount_bindings_guard()"
    )
    tenant_table(op, "efile_amount_bindings")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON efile_amount_bindings FROM abacus_app")
    insert_columns(op, "efile_amount_bindings", INSERT)
    op.execute(f"GRANT UPDATE ({', '.join(UPDATE)}) ON efile_amount_bindings TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE efile_amount_bindings")
    op.execute("DROP FUNCTION efile_amount_bindings_guard()")
