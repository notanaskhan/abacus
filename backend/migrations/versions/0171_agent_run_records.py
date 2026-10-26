"""Agent run records (Q-02-T41; TASK-1287; ADR-169 §3, P-47, conflict C-12; SPEC-341 AC-44).

`agent_run_records` holds the decision-relevant facts of one ended specialist run, written once
by the run's own workflow (`agents.persist_run_record`) after the terminal state, and never
updated or deleted by the app. Identifiers, versions and fingerprints only: no prompt text, no
model text, no client content (a citation keeps its locator and the SHA-256 of the quoted words).
Raw traces keep ADR-032's ~30 days; a record outlives them for the engagement's retention.

- `run_id` is the primary key (one record per run) and references `agent_runs`; a run with an
  engagement references the run's own engagement (template runs are firm-level, no engagement).
- A citation's quoted words and sheet name are kept only as HMAC-SHA-256 fingerprints under the
  firm's own key (`quote_fingerprint`, `sheet_fingerprint`; DEC-396), never plain hashes.
- `record_sha256` is the SHA-256 of the canonical JSON of every other field (ADR-169 §3), as
  lowercase hex, the form `kernel.uow.Ref` carries into the `agent_run_record.persisted` audit
  event. It is not the run view's read-time `run_record_sha256` (TASK-5000; DEC-396).
- Insert-only for the app role, TRUNCATE revoked; forced row-level security.
- A guard requires the `system` actor, and a run that has ended whose capability, engagement,
  initiator, spec version, stage (its shadow flag), start and finish, failure code and terminal
  state (ADR-169 §2's legacy map) the record repeats (security review, DEC-396).

Numbered 0171 on a branch based on 0160; re-pointed at the S9 batch merge to follow 0168.
The downgrade refuses while any record exists.

Revision ID: 0171
Revises: 0168
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0171"
down_revision = "0168"
branch_labels = None
depends_on = None

_SHA = "~ '^[0-9a-f]{64}$'"
_COLUMNS = (
    "run_id",
    "tenant_id",
    "engagement_id",
    "work_item_id",
    "capability",
    "spec_version",
    "stage",
    "prompt_ref",
    "prompt_sha256",
    "model",
    "route",
    "region",
    "terms_version",
    "boundary_basis",
    "input_hashes",
    "records_read",
    "citations",
    "outcome",
    "initiator_user_id",
    "started_at",
    "completed_at",
    "record_sha256",
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE agent_run_records (
            run_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            capability text NOT NULL CHECK (capability ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'),
            spec_version integer NOT NULL CHECK (spec_version >= 1),
            stage text NOT NULL CHECK (stage IN ('shadow', 'live')),
            prompt_ref text NULL CHECK (length(prompt_ref) BETWEEN 1 AND 120),
            prompt_sha256 text NULL CHECK (prompt_sha256 {_SHA}),
            model text NULL CHECK (length(model) BETWEEN 1 AND 100),
            route text NULL CHECK (route IN ('fake', 'direct', 'bedrock')),
            region text NULL CHECK (length(region) BETWEEN 1 AND 40),
            terms_version text NULL CHECK (terms_version {_SHA}),
            boundary_basis text NULL CHECK (boundary_basis IN ('synthetic', 'client_data')),
            input_hashes jsonb NOT NULL CHECK (jsonb_typeof(input_hashes) = 'object'),
            records_read jsonb NOT NULL CHECK (jsonb_typeof(records_read) = 'array'),
            citations jsonb NOT NULL CHECK (jsonb_typeof(citations) = 'array'),
            outcome jsonb NOT NULL CHECK (
                jsonb_typeof(outcome) = 'object'
                AND outcome ->> 'state' IN ('succeeded', 'needs_input', 'failed', 'cancelled')
            ),
            initiator_user_id uuid NOT NULL,
            started_at timestamptz NOT NULL,
            completed_at timestamptz NOT NULL,
            record_sha256 text NOT NULL CHECK (record_sha256 {_SHA}),
            persisted_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (run_id),
            CONSTRAINT agent_run_records_completed CHECK (completed_at >= started_at),
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX agent_run_records_engagement "
        "ON agent_run_records (tenant_id, engagement_id, completed_at)"
    )
    tenant_table(op, "agent_run_records")
    insert_only(op, "agent_run_records")
    op.execute("REVOKE TRUNCATE ON agent_run_records FROM abacus_app")
    insert_columns(op, "agent_run_records", _COLUMNS)
    op.execute(
        """
        CREATE FUNCTION agent_run_records_guard() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_run record;
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'a run record is persisted by the run''s workflow (ADR-169)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT r.status, r.agent_id, r.engagement_id, r.initiator_user_id, r.spec_version,
                   r.shadow, r.started_at, r.finished_at, r.failure_code
              INTO v_run FROM agent_runs r
             WHERE r.tenant_id = NEW.tenant_id AND r.id = NEW.run_id;
            IF NOT FOUND OR v_run.status = 'running' THEN
                RAISE EXCEPTION 'a run record is written once the run has ended'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'agent_run_records_run_ended';
            END IF;
            IF NEW.capability IS DISTINCT FROM v_run.agent_id
               OR NEW.engagement_id IS DISTINCT FROM v_run.engagement_id
               OR NEW.initiator_user_id IS DISTINCT FROM v_run.initiator_user_id
               OR NEW.spec_version IS DISTINCT FROM v_run.spec_version
               OR NEW.stage IS DISTINCT FROM (CASE WHEN v_run.shadow THEN 'shadow' ELSE 'live' END)
               OR NEW.started_at IS DISTINCT FROM v_run.started_at
               OR NEW.completed_at IS DISTINCT FROM v_run.finished_at
               OR NEW.outcome ->> 'failure_code' IS DISTINCT FROM v_run.failure_code
               OR NEW.outcome ->> 'state' IS DISTINCT FROM (CASE v_run.status
                    WHEN 'completed' THEN 'succeeded'
                    WHEN 'escalated' THEN 'needs_input'
                    ELSE CASE WHEN v_run.failure_code = 'cancelled' THEN 'cancelled'
                              ELSE 'failed' END
                  END) THEN
                RAISE EXCEPTION 'a run record repeats its run'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'agent_run_records_of_run';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER agent_run_records_guard BEFORE INSERT ON agent_run_records "
        "FOR EACH ROW EXECUTE FUNCTION agent_run_records_guard()"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM agent_run_records) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: agent run records exist'; "
        "END IF; END $$"
    )
    op.execute("ALTER TABLE agent_run_records NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP TABLE agent_run_records")
    op.execute("DROP FUNCTION agent_run_records_guard()")
