"""Guidance drafts (SPEC-035; TASK-072).

`guidance_drafts`: one per guidance drafter run on a request item: the drafted why and what good
looks like, optional effort and blocks-fieldwork suggestions with their reasons, and whether code's
checks passed (with the reason codes when not). Insert-only: the drafter proposes, a person
approves (ADR-005, ADR-111). Template items follow with TASK-073.

Revision ID: 0052
Revises: 0051
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE guidance_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
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
            CONSTRAINT guidance_drafts_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, engagement_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id)
        )
        """
    )
    tenant_table(op, "guidance_drafts")
    op.execute("REVOKE UPDATE, DELETE ON guidance_drafts FROM abacus_app")
    insert_columns(
        op,
        "guidance_drafts",
        (
            "tenant_id",
            "engagement_id",
            "request_item_id",
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


def downgrade() -> None:
    op.execute("DROP TABLE guidance_drafts")
