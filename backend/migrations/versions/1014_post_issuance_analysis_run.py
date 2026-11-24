"""Q-05-T22 (S53; TASK-8909; Q-05 §6; SPEC-711 AC-16; red): a post-issuance case keeps its latest
analysis. Expand-only.

`post_issuance_events` gains `analysis_run_id` (the `agent_runs` row of the last
`assurance.post_issuance_analysis` run), `analysis_sealed` (the settled AgentBlocks as sealed JSON:
the run record holds identifiers and counts only), `analysis_recommendation` (the code-eligible
option the analysis tagged, or none) and `analysis_citation_ids` (its verified citations). The
four move together. The analysis is written past `archived_guard()` under the existing
`post_issuance` kind (ADR P-43), like the decision.

Revision ID: 1014
Revises: 1013
"""

from __future__ import annotations

from alembic import op

revision = "1014"
down_revision = "1013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE post_issuance_events ADD COLUMN analysis_run_id uuid NULL, "
        "ADD COLUMN analysis_sealed bytea NULL CHECK (octet_length(analysis_sealed) <= 65536), "
        "ADD COLUMN analysis_recommendation text NULL CHECK (analysis_recommendation IN "
        "('no_action', 'revise_and_reissue', 'notify_users')), "
        "ADD COLUMN analysis_citation_ids uuid[] NULL, "
        "ADD CONSTRAINT post_issuance_events_analysis_run_fkey FOREIGN KEY (analysis_run_id) "
        "REFERENCES agent_runs (id), "
        "ADD CONSTRAINT post_issuance_events_analysis_whole CHECK ("
        "(analysis_run_id IS NULL) = (analysis_sealed IS NULL) "
        "AND (analysis_run_id IS NULL) = (analysis_citation_ids IS NULL) "
        "AND (analysis_recommendation IS NULL OR analysis_run_id IS NOT NULL))"
    )
    op.execute(
        "GRANT UPDATE (analysis_run_id, analysis_sealed, analysis_recommendation, "
        "analysis_citation_ids) ON post_issuance_events TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE post_issuance_events DROP COLUMN analysis_citation_ids, "
        "DROP COLUMN analysis_recommendation, DROP COLUMN analysis_sealed, "
        "DROP COLUMN analysis_run_id"
    )
