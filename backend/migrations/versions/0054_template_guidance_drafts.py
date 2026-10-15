"""Drafted guidance on methodology templates (SPEC-035 Q3; TASK-074).

- `agent_runs`: a guidance drafter run on a template version belongs to the firm, not an
  engagement (D1): `engagement_id` may be null only for that agent, with
  `methodology_version_id` naming the version it drafts for.
- `template_guidance_drafts` (insert-only): one per such run, for one template item (version and
  position), with code's check result.
- `template_guidance_decisions` (insert-only): a person approved (perhaps after editing, with the
  final text) or discarded a draft. Approved text reaches engagements only through a new template
  version (D2).
- `request_items.guidance_approved_by` becomes insertable (creation from such a version).
- `methodology_request_items.guidance_source` (null or `drafted`) and `guidance_approved_by`:
  provenance carried into engagements, so the client display rule applies (ADR-111).

Revision ID: 0054
Revises: 0053
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

_DRAFTER = "requests.guidance_drafter"


def upgrade() -> None:
    op.execute("ALTER TABLE agent_runs ALTER COLUMN engagement_id DROP NOT NULL")
    op.execute("ALTER TABLE agent_runs ADD COLUMN methodology_version_id uuid NULL")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_methodology_version "
        "FOREIGN KEY (tenant_id, methodology_version_id) "
        "REFERENCES methodology_versions (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_by_version "
        "UNIQUE (tenant_id, methodology_version_id, id)"
    )
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_firm_level CHECK ("
        "(engagement_id IS NOT NULL AND methodology_version_id IS NULL) OR "
        "(engagement_id IS NULL AND methodology_version_id IS NOT NULL "
        f"AND agent_id = '{_DRAFTER}'))"
    )
    op.execute("GRANT INSERT (methodology_version_id) ON agent_runs TO abacus_app")
    # Request items created from a version with drafted guidance (or rolled forward) keep who
    # approved it.
    op.execute("GRANT INSERT (guidance_approved_by) ON request_items TO abacus_app")
    op.execute(
        "ALTER TABLE methodology_request_items "
        "ADD COLUMN guidance_source text NULL CHECK (guidance_source IN ('drafted')), "
        "ADD COLUMN guidance_approved_by uuid NULL, "
        "ADD CONSTRAINT methodology_request_items_drafted_approver CHECK "
        "((guidance_source IS NULL) = (guidance_approved_by IS NULL))"
    )
    op.execute(
        "GRANT INSERT (guidance_source, guidance_approved_by) "
        "ON methodology_request_items TO abacus_app"
    )
    op.execute(
        """
        CREATE TABLE template_guidance_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            methodology_version_id uuid NOT NULL,
            position integer NOT NULL,
            agent_run_id uuid NOT NULL,
            prompt_ref text NOT NULL CHECK (prompt_ref ~ '^[a-z][a-z0-9_.]*@v[0-9]+$'),
            why text NOT NULL CHECK (length(why) BETWEEN 1 AND 300),
            good_looks_like text NOT NULL CHECK (length(good_looks_like) BETWEEN 1 AND 600),
            effort text NULL CHECK (effort IN ('small', 'medium', 'large')),
            effort_reason text NULL CHECK (length(effort_reason) <= 160),
            blocks_fieldwork boolean NULL,
            blocks_reason text NULL CHECK (length(blocks_reason) <= 160),
            passed_checks boolean NOT NULL,
            check_reasons text[] NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT template_guidance_drafts_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, methodology_version_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, methodology_version_id, id),
            FOREIGN KEY (tenant_id, methodology_version_id, position)
                REFERENCES methodology_request_items (tenant_id, version_id, position)
        )
        """
    )
    op.execute(
        "CREATE INDEX template_guidance_drafts_by_version "
        "ON template_guidance_drafts (tenant_id, methodology_version_id)"
    )
    tenant_table(op, "template_guidance_drafts")
    op.execute("REVOKE UPDATE, DELETE ON template_guidance_drafts FROM abacus_app")
    insert_columns(
        op,
        "template_guidance_drafts",
        (
            "tenant_id",
            "methodology_version_id",
            "position",
            "agent_run_id",
            "prompt_ref",
            "why",
            "good_looks_like",
            "effort",
            "effort_reason",
            "blocks_fieldwork",
            "blocks_reason",
            "passed_checks",
            "check_reasons",
        ),
    )
    op.execute(
        """
        CREATE TABLE template_guidance_decisions (
            tenant_id uuid NOT NULL,
            draft_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'discarded')),
            why text NULL CHECK (length(why) BETWEEN 1 AND 300),
            good_looks_like text NULL CHECK (length(good_looks_like) BETWEEN 1 AND 600),
            effort text NULL CHECK (effort IN ('small', 'medium', 'large')),
            blocks_fieldwork boolean NULL,
            edited boolean NOT NULL DEFAULT false,
            confirmed_read boolean NOT NULL DEFAULT false,
            decided_by uuid NOT NULL REFERENCES users (id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, draft_id),
            CONSTRAINT template_guidance_decisions_text CHECK (
                (decision = 'approved') = (why IS NOT NULL AND good_looks_like IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, draft_id) REFERENCES template_guidance_drafts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "template_guidance_decisions")
    op.execute("REVOKE UPDATE, DELETE ON template_guidance_decisions FROM abacus_app")
    insert_columns(
        op,
        "template_guidance_decisions",
        (
            "tenant_id",
            "draft_id",
            "decision",
            "why",
            "good_looks_like",
            "effort",
            "blocks_fieldwork",
            "edited",
            "confirmed_read",
            "decided_by",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE template_guidance_decisions")
    op.execute("DROP TABLE template_guidance_drafts")
    op.execute(
        "REVOKE INSERT (guidance_source, guidance_approved_by) "
        "ON methodology_request_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE methodology_request_items DROP CONSTRAINT "
        "methodology_request_items_drafted_approver, DROP COLUMN guidance_approved_by, "
        "DROP COLUMN guidance_source"
    )
    op.execute("REVOKE INSERT (guidance_approved_by) ON request_items FROM abacus_app")
    op.execute("REVOKE INSERT (methodology_version_id) ON agent_runs FROM abacus_app")
    op.execute("DELETE FROM agent_runs WHERE engagement_id IS NULL")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_firm_level")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_by_version")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_methodology_version")
    op.execute("ALTER TABLE agent_runs DROP COLUMN methodology_version_id")
    op.execute("ALTER TABLE agent_runs ALTER COLUMN engagement_id SET NOT NULL")
