"""A mapping set's prior-year source (A-03 §4.2 `mapping_sets`; TASK-2718; DEC-1769). Expand-only.

The plan's `mapping_sets` names where the prior year's line for each account comes from:
`prior_engagement` (the engagement this one rolled forward from, read on demand, A-03-T08),
`predecessor_file` (a mapping file the predecessor auditor gave, uploaded as evidence and parsed
by code once, when the run starts) or `none` (number ranges only, QA-7). The columns are set at
insert and never change (no UPDATE grant): a new prior source is a new mapping set.

- `prior_source` defaults to `prior_engagement`, so every existing set keeps its behaviour.
- `predecessor_evidence_version_id` names the file, present exactly when the source is a file.
- `predecessor_keys` holds the parsed file as normalised account code to FS-line key (only keys
  of the set's grouping version; figures never cross over), so a read never re-parses a client
  file.

Revision ID: 0582
Revises: 0612
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0582"
down_revision = "0612"
branch_labels = None
depends_on = None

_INSERT = (
    "tenant_id",
    "engagement_id",
    "trial_balance_id",
    "grouping_set_version_id",
    "created_by",
    "prior_source",
    "predecessor_evidence_version_id",
    "predecessor_keys",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE mapping_sets
            ADD COLUMN prior_source text NOT NULL DEFAULT 'prior_engagement'
                CHECK (prior_source IN ('prior_engagement', 'predecessor_file', 'none')),
            ADD COLUMN predecessor_evidence_version_id uuid NULL,
            ADD COLUMN predecessor_keys jsonb NULL
                CHECK (predecessor_keys IS NULL OR jsonb_typeof(predecessor_keys) = 'object'),
            ADD CONSTRAINT mapping_sets_predecessor_file CHECK (
                (prior_source = 'predecessor_file')
                = (predecessor_evidence_version_id IS NOT NULL AND predecessor_keys IS NOT NULL)
            ),
            ADD CONSTRAINT mapping_sets_predecessor_version
                FOREIGN KEY (tenant_id, predecessor_evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        """
    )
    insert_columns(op, "mapping_sets", _INSERT)


def downgrade() -> None:
    insert_columns(op, "mapping_sets", _INSERT[:5])
    op.execute(
        """
        ALTER TABLE mapping_sets
            DROP CONSTRAINT mapping_sets_predecessor_version,
            DROP CONSTRAINT mapping_sets_predecessor_file,
            DROP COLUMN predecessor_keys,
            DROP COLUMN predecessor_evidence_version_id,
            DROP COLUMN prior_source
        """
    )
