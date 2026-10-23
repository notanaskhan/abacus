"""Audit hash-chain checkpoints and daily anchors (Q-02-T21; AC-26; P-43), owned by `kernel.uow`
(beside the events it seals; `audit_trail.api` re-exports the reads).

Every five minutes, each firm's new audit events up to a settle horizon are sealed into a
checkpoint:
- a SHA-256 leaf per event, over its canonical form (leaf version 1);
- a Merkle root over the range;
- a chain hash over the previous checkpoint's chain hash, the root, the seq range and the count.
A nightly verifier recomputes them from the rows, so a changed or removed event names its
checkpoint. A daily anchor records the chain hash written to the records bucket's COMPLIANCE
prefix.

Both tables are insert-only (the immutable trigger and no app UPDATE or DELETE) and under tenant
row-level security. Checkpoints are an operational ledger the chain itself proves, so they are
written without an audit event (as `kernel/slots.py` is).

Revision ID: 0106
Revises: 0105
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None

_TABLES = ("audit_checkpoints", "audit_anchors")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_checkpoints (
            tenant_id uuid NOT NULL,
            checkpoint_no bigint NOT NULL CHECK (checkpoint_no >= 1),
            seq_from bigint NOT NULL,
            seq_to bigint NOT NULL,
            event_count integer NOT NULL CHECK (event_count >= 1),
            leaf_version smallint NOT NULL CHECK (leaf_version >= 1),
            merkle_root bytea NOT NULL CHECK (octet_length(merkle_root) = 32),
            prev_chain_hash bytea NULL CHECK (octet_length(prev_chain_hash) = 32),
            chain_hash bytea NOT NULL CHECK (octet_length(chain_hash) = 32),
            closed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, checkpoint_no),
            UNIQUE (tenant_id, seq_to),
            CHECK (seq_to >= seq_from),
            CHECK ((checkpoint_no = 1) = (prev_chain_hash IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE audit_anchors (
            tenant_id uuid NOT NULL,
            anchor_date date NOT NULL,
            through_checkpoint_no bigint NOT NULL,
            chain_hash bytea NOT NULL CHECK (octet_length(chain_hash) = 32),
            object_key text NOT NULL CHECK (length(object_key) BETWEEN 1 AND 512),
            object_version_id text NULL CHECK (length(object_version_id) BETWEEN 1 AND 1024),
            retain_until timestamptz NOT NULL,
            PRIMARY KEY (tenant_id, anchor_date),
            FOREIGN KEY (tenant_id, through_checkpoint_no)
                REFERENCES audit_checkpoints (tenant_id, checkpoint_no)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION audit_chain_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_chain_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION audit_chain_immutable()"
        )
        tenant_table(op, table)
        insert_only(op, table)
    insert_columns(
        op,
        "audit_checkpoints",
        (
            "tenant_id",
            "checkpoint_no",
            "seq_from",
            "seq_to",
            "event_count",
            "leaf_version",
            "merkle_root",
            "prev_chain_hash",
            "chain_hash",
        ),
    )
    insert_columns(
        op,
        "audit_anchors",
        (
            "tenant_id",
            "anchor_date",
            "through_checkpoint_no",
            "chain_hash",
            "object_key",
            "object_version_id",
            "retain_until",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_anchors")
    op.execute("DROP TABLE audit_checkpoints")
    op.execute("DROP FUNCTION audit_chain_immutable()")
