"""Durable run trace records (P-10-T44; SPEC-647 §3.9 AC-RR2 to AC-RR5; DEC-4302).

`agent_run_traces` keeps a v2 run's trace export as it was first rendered for each projection
(content or metadata): the canonical body, its SHA-256, the renderer version and the fingerprint
of the durable rows it was built from (`source_sha256`). It is insert-only: a run whose durable
rows move (an approved write lands, a person signs off) gets a new version, never an edit. P-09's
export answers the newest version whose fingerprint still matches, so a run adopted 90 days
earlier exports the same bytes after `run_events` is pruned and after names or the renderer move.

Kept as `agent_run_records` (Q-02's record class: the longer of seven years and the engagement's
retention, under legal holds); there is no delete path. Each version is audited
(`agent_run.trace_frozen`, `Ref(sha256, version)`), so the per-tenant hash chain covers it.

Revision ID: 0820
Revises: 0814
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0820"
down_revision = "0814"
branch_labels = None
depends_on = None

INSERTS = (
    "id", "tenant_id", "run_id", "engagement_id", "projection", "version", "renderer_version",
    "body", "body_sha256", "source_sha256",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_run_traces (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            projection text NOT NULL CHECK (projection IN ('content', 'metadata')),
            version integer NOT NULL CHECK (version >= 1),
            renderer_version text NOT NULL CHECK (length(renderer_version) BETWEEN 1 AND 40),
            body text NOT NULL,
            body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
            source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            record_type text NOT NULL DEFAULT 'agent_run_records'
                CHECK (record_type = 'agent_run_records'),
            frozen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, run_id, projection, version),
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX agent_run_traces_engagement ON agent_run_traces (tenant_id, engagement_id)"
    )
    op.execute(
        """
        CREATE FUNCTION agent_run_traces_immutable() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent_run_traces is insert-only' USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION agent_run_traces_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER agent_run_traces_immutable BEFORE UPDATE OR DELETE ON agent_run_traces "
        "FOR EACH ROW EXECUTE FUNCTION agent_run_traces_immutable()"
    )
    tenant_table(op, "agent_run_traces")
    insert_columns(op, "agent_run_traces", INSERTS)
    insert_only(op, "agent_run_traces")
    op.execute(
        "COMMENT ON TABLE agent_run_traces IS 'classification: confidential (trace bodies carry "
        "plan labels and names, never client figures beyond counts)'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE agent_run_traces")
    op.execute("DROP FUNCTION agent_run_traces_immutable()")
