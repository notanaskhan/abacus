"""The matcher's intake mode (N-01-T22; N-01 §5; evidence.matcher v3). Expand-only.

`agent_runs` gains `inbox_attachment_id`: the run's intake attachment. An engagement-less run was
the guidance drafter's on a template version only (0054); the matcher's intake run is the second
kind, always naming its attachment.

`inbox_match_runs` gains the intake attachment and its client: a run is on an inbox file (the
engagement mode, v2, unchanged) or on an intake attachment of a matched client, never both and
never neither. `inbox_match_proposals` gains the attachment and the destination it proposes (a
request, the permanent file, a work-item folder or a registered kind, as INB-02's picker names
them); a request proposal keeps `request_item_id`. Both stay insert-only: the matcher proposes, a
person files (ADR-005, I-AGENT-NEVER).

Revision ID: 0431
Revises: 0406
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

_DRAFTER = "requests.guidance_drafter"
_MATCHER = "evidence.matcher"

revision = "0431"
down_revision = "0406"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_runs ADD COLUMN inbox_attachment_id uuid NULL")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_inbox_attachment "
        "FOREIGN KEY (tenant_id, inbox_attachment_id) REFERENCES inbox_attachments (tenant_id, id)"
    )
    op.execute(
        "CREATE INDEX agent_runs_by_inbox_attachment ON agent_runs "
        "(tenant_id, inbox_attachment_id) WHERE inbox_attachment_id IS NOT NULL"
    )
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_firm_level")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_firm_level CHECK ("
        "(engagement_id IS NOT NULL AND methodology_version_id IS NULL "
        "AND inbox_attachment_id IS NULL) OR "
        "(engagement_id IS NULL AND methodology_version_id IS NOT NULL "
        f"AND inbox_attachment_id IS NULL AND agent_id = '{_DRAFTER}') OR "
        "(engagement_id IS NULL AND methodology_version_id IS NULL "
        f"AND inbox_attachment_id IS NOT NULL AND agent_id = '{_MATCHER}'))"
    )
    op.execute("GRANT INSERT (inbox_attachment_id) ON agent_runs TO abacus_app")
    op.execute(
        """
        ALTER TABLE inbox_match_runs
            ALTER COLUMN engagement_id DROP NOT NULL,
            ALTER COLUMN inbox_file_id DROP NOT NULL,
            ADD COLUMN inbox_attachment_id uuid NULL,
            ADD COLUMN client_id uuid NULL,
            ADD CONSTRAINT inbox_match_runs_one_source
                CHECK (num_nonnulls(inbox_file_id, inbox_attachment_id) = 1),
            ADD CONSTRAINT inbox_match_runs_file_engagement
                CHECK (inbox_file_id IS NULL OR engagement_id IS NOT NULL),
            ADD CONSTRAINT inbox_match_runs_attachment_client
                CHECK (inbox_attachment_id IS NULL OR client_id IS NOT NULL),
            ADD FOREIGN KEY (tenant_id, inbox_attachment_id)
                REFERENCES inbox_attachments (tenant_id, id),
            ADD FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            ADD CONSTRAINT inbox_match_runs_agent_run
                FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs (tenant_id, id)
        """
    )
    op.execute(
        "CREATE INDEX inbox_match_runs_by_attachment ON inbox_match_runs "
        "(tenant_id, inbox_attachment_id, created_at) WHERE inbox_attachment_id IS NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE inbox_match_proposals
            ALTER COLUMN request_item_id DROP NOT NULL,
            ADD COLUMN inbox_attachment_id uuid NULL,
            ADD COLUMN destination_kind text NULL
                CHECK (destination_kind ~ '^[a-z][a-z0-9_]*$'),
            ADD COLUMN destination_id uuid NULL,
            ADD CONSTRAINT inbox_match_proposals_names_a_target CHECK (
                request_item_id IS NOT NULL
                OR (destination_kind IS NOT NULL AND destination_id IS NOT NULL)
            ),
            ADD CONSTRAINT inbox_match_proposals_destination_pair
                CHECK ((destination_kind IS NULL) = (destination_id IS NULL)),
            ADD FOREIGN KEY (tenant_id, inbox_attachment_id)
                REFERENCES inbox_attachments (tenant_id, id)
        """
    )
    insert_columns(
        op,
        "inbox_match_runs",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "inbox_file_id",
            "inbox_attachment_id",
            "client_id",
            "agent_run_id",
            "prompt_ref",
            "none_fit",
            "truncated",
        ),
    )
    insert_columns(
        op,
        "inbox_match_proposals",
        (
            "tenant_id",
            "match_id",
            "rank",
            "request_item_id",
            "inbox_attachment_id",
            "destination_kind",
            "destination_id",
            "confidence",
            "rationale",
            "citations",
            "shown",
        ),
    )


def downgrade() -> None:
    # Only before any intake row exists: restoring the NOT NULLs fails otherwise, by design.
    insert_columns(
        op,
        "inbox_match_proposals",
        (
            "tenant_id",
            "match_id",
            "rank",
            "request_item_id",
            "confidence",
            "rationale",
            "citations",
            "shown",
        ),
    )
    insert_columns(
        op,
        "inbox_match_runs",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "inbox_file_id",
            "agent_run_id",
            "prompt_ref",
            "none_fit",
            "truncated",
        ),
    )
    op.execute(
        """
        ALTER TABLE inbox_match_proposals
            DROP CONSTRAINT inbox_match_proposals_destination_pair,
            DROP CONSTRAINT inbox_match_proposals_names_a_target,
            DROP COLUMN destination_id,
            DROP COLUMN destination_kind,
            DROP COLUMN inbox_attachment_id,
            ALTER COLUMN request_item_id SET NOT NULL
        """
    )
    op.execute("DROP INDEX inbox_match_runs_by_attachment")
    op.execute(
        """
        ALTER TABLE inbox_match_runs
            DROP CONSTRAINT inbox_match_runs_agent_run,
            DROP CONSTRAINT inbox_match_runs_attachment_client,
            DROP CONSTRAINT inbox_match_runs_file_engagement,
            DROP CONSTRAINT inbox_match_runs_one_source,
            DROP COLUMN client_id,
            DROP COLUMN inbox_attachment_id,
            ALTER COLUMN inbox_file_id SET NOT NULL,
            ALTER COLUMN engagement_id SET NOT NULL
        """
    )
    op.execute("REVOKE INSERT (inbox_attachment_id) ON agent_runs FROM abacus_app")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_firm_level")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_firm_level CHECK ("
        "(engagement_id IS NOT NULL AND methodology_version_id IS NULL) OR "
        "(engagement_id IS NULL AND methodology_version_id IS NOT NULL "
        f"AND agent_id = '{_DRAFTER}'))"
    )
    op.execute("DROP INDEX agent_runs_by_inbox_attachment")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_inbox_attachment")
    op.execute("ALTER TABLE agent_runs DROP COLUMN inbox_attachment_id")
