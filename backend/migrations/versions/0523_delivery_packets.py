"""The delivery packet (T-01-T35; T-01 §3.11, §4.2; TAX-12 a, b; DEC-38; DEC-1565). Expand-only.

`delivery_packets`: one row per assembled version of a return's packet, the engine PDFs filed by
the bridge plus the filing-instructions letter C11 renders (`letter_document_id`, a generated
document). `items` is the list of `{kind, evidence_version_id, included}`; a packet is `draft`
until the signer or a manager approves it, and a re-assembly supersedes the draft before it. The
app may move a row's status forward, toggle its items and name its letter, and nothing else: a
guard trigger refuses any other change, a status moving backward, a change to an approved or
superseded packet, and every delete. Tax's table, forced RLS.

Classification (ADR-031): `items` TRI (the return's documents); people's ids Confidential.

Revision ID: 0523
Revises: 0522
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0523"
down_revision = "0522"
branch_labels = None
depends_on = None

INSERT = ("id", "tenant_id", "return_id", "version", "items", "letter_document_id", "prepared_by")
UPDATE = ("items", "letter_document_id", "status", "approved_by", "approved_at", "row_version")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE delivery_packets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            items jsonb NOT NULL CHECK (jsonb_typeof(items) = 'array'),
            letter_document_id uuid NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'approved', 'superseded')),
            prepared_by uuid NOT NULL,
            approved_by uuid NULL,
            approved_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, return_id, version),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            CHECK ((status = 'approved') = (approved_by IS NOT NULL AND approved_at IS NOT NULL)
                OR status = 'superseded')
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX delivery_packets_one_open ON delivery_packets (tenant_id, return_id) "
        "WHERE status <> 'superseded'"
    )
    op.execute(
        """
        CREATE FUNCTION delivery_packets_guard() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'delivery packets are never deleted'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.status <> 'draft' AND NEW.status IS DISTINCT FROM 'superseded' THEN
                RAISE EXCEPTION 'packet_not_draft' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'superseded' THEN
                RAISE EXCEPTION 'packet_not_draft' USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.return_id IS DISTINCT FROM OLD.return_id
                OR NEW.version IS DISTINCT FROM OLD.version
                OR NEW.prepared_by IS DISTINCT FROM OLD.prepared_by
                OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION 'packet identity is fixed' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'approved' AND (NEW.items IS DISTINCT FROM OLD.items
                OR NEW.letter_document_id IS DISTINCT FROM OLD.letter_document_id
                OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
                OR NEW.approved_at IS DISTINCT FROM OLD.approved_at) THEN
                RAISE EXCEPTION 'packet_not_draft' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER delivery_packets_guard BEFORE UPDATE OR DELETE ON delivery_packets "
        "FOR EACH ROW EXECUTE FUNCTION delivery_packets_guard()"
    )
    tenant_table(op, "delivery_packets")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON delivery_packets FROM abacus_app")
    insert_columns(op, "delivery_packets", INSERT)
    op.execute(f"GRANT UPDATE ({', '.join(UPDATE)}) ON delivery_packets TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE delivery_packets")
    op.execute("DROP FUNCTION delivery_packets_guard()")
