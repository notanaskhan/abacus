"""I-02 M1: the Today brief's stored briefings (I-02-T06; I-02 §4.2; SPEC-654; DEC-4611).

`daily_briefings` (agents) holds two kinds of row, one per (scope, viewer, engagement, day, seq):

- scope `engagement`: one `briefing.today` run's verified `EngagementBriefing` (`blocks`,
  AgentBlocks `p` parts with facts by reference into the run's fact registry, ADR-230) for one
  viewer and one engagement on one firm-time-zone day. Rebuilds add rows (`seq`).
- scope `user`: the viewer's day snapshot, code only: integers and identifier refs in `counts`,
  `lead_facts` and `card_refs`; no text.

Expand-only. RLS is forced; a terminal row (`ready`, `unverified`, `failed`, `unavailable`) is
immutable by trigger; DELETE is revoked from the app role (the retention job runs as the retention
definer; record type `daily_briefing`, 90 days by content, Q3). No column holds a TIN, an SSN or
quoted document text: `blocks` is the verified block list, `citation_ids` point at citation rows.

Revision ID: 0851
Revises: 0850
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0851"
down_revision = "0850"
branch_labels = None
depends_on = None

INSERTS = (
    "id", "tenant_id", "scope", "viewer_user_id", "engagement_id", "work_item_ids", "brief_date",
    "seq", "status", "unavailable_reason", "facts_hash", "blocks", "citation_ids", "agent_run_id",
    "prompt_ref", "capability_version", "counts", "lead_facts", "card_refs", "built_at",
)  # fmt: skip
UPDATES = (
    "status", "unavailable_reason", "blocks", "citation_ids", "agent_run_id", "counts",
    "lead_facts", "card_refs", "built_at",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE daily_briefings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            scope text NOT NULL CHECK (scope IN ('engagement', 'user')),
            viewer_user_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_ids uuid[] NOT NULL DEFAULT '{}',
            brief_date date NOT NULL,
            seq smallint NOT NULL DEFAULT 1 CHECK (seq >= 1),
            status text NOT NULL DEFAULT 'building'
                CHECK (status IN ('building', 'ready', 'unverified', 'failed', 'unavailable')),
            unavailable_reason text NULL CHECK (
                unavailable_reason IS NULL
                OR unavailable_reason ~ ('^(boundary_refused:[a-z_]{1,20}|consent_7216'
                                         '|metadata_only|budget_soft_limit|flag_off)$')
            ),
            facts_hash bytea NULL CHECK (facts_hash IS NULL OR length(facts_hash) = 32),
            blocks jsonb NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            agent_run_id uuid NULL,
            prompt_ref text NULL
                CHECK (prompt_ref IS NULL OR prompt_ref ~ '^[a-z_.]{1,60}@v[0-9]{1,4}$'),
            capability_version integer NULL
                CHECK (capability_version IS NULL OR capability_version >= 1),
            counts jsonb NULL,
            lead_facts jsonb NULL,
            card_refs jsonb NULL,
            built_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, viewer_user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs (tenant_id, id),
            CONSTRAINT daily_briefings_scope_engagement CHECK (
                (scope = 'engagement' AND engagement_id IS NOT NULL
                    AND counts IS NULL AND lead_facts IS NULL AND card_refs IS NULL)
                OR (scope = 'user' AND engagement_id IS NULL AND blocks IS NULL
                    AND cardinality(citation_ids) = 0)
            ),
            CONSTRAINT daily_briefings_unavailable_reason CHECK (
                (status = 'unavailable') = (unavailable_reason IS NOT NULL)
            ),
            CONSTRAINT daily_briefings_blocks_only_ready CHECK (
                blocks IS NULL OR status = 'ready'
            ),
            CONSTRAINT daily_briefings_counts_are_integers CHECK (
                counts IS NULL OR jsonb_typeof(counts) = 'object'
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX daily_briefings_key ON daily_briefings (tenant_id, scope, "
        "viewer_user_id, coalesce(engagement_id, '00000000-0000-0000-0000-000000000000'::uuid), "
        "brief_date, seq)"
    )
    op.execute(
        "CREATE INDEX daily_briefings_viewer_day ON daily_briefings "
        "(tenant_id, viewer_user_id, brief_date DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION daily_briefings_terminal() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status <> 'building' THEN
                RAISE EXCEPTION 'a daily briefing is immutable once %', OLD.status
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.scope <> OLD.scope OR NEW.viewer_user_id <> OLD.viewer_user_id
               OR NEW.engagement_id IS DISTINCT FROM OLD.engagement_id
               OR NEW.brief_date <> OLD.brief_date OR NEW.seq <> OLD.seq THEN
                RAISE EXCEPTION 'a daily briefing keeps its key'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION daily_briefings_terminal() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER daily_briefings_terminal BEFORE UPDATE ON daily_briefings "
        "FOR EACH ROW EXECUTE FUNCTION daily_briefings_terminal()"
    )
    tenant_table(op, "daily_briefings")
    insert_columns(op, "daily_briefings", INSERTS)
    op.execute("REVOKE DELETE ON daily_briefings FROM abacus_app")
    op.execute("REVOKE UPDATE ON daily_briefings FROM abacus_app")  # column grants only
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON daily_briefings TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE daily_briefings")
    op.execute("DROP FUNCTION daily_briefings_terminal()")
