"""A run artifact names its stored object (P-10-T38; TASK-6802; DEC-3402; SPEC-647 AC-P1).

`files.build_workbook` stores the workbook's bytes under Object Lock before its row is written;
`files.save_approved` reads them back to file the approved copy. The object store needs the key
(already here), its version id and the content's SHA-256 to return verified bytes, so both are
stored with the artifact. Null for a row written before this migration.

Expand-only; the downgrade drops both columns.

Revision ID: 0811
Revises: 0810
"""

from __future__ import annotations

from alembic import op

revision = "0811"
down_revision = "0810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE run_artifacts
            ADD COLUMN storage_version_id text NULL
                CHECK (length(storage_version_id) BETWEEN 1 AND 1024),
            ADD COLUMN sha256 text NULL CHECK (sha256 ~ '^[0-9a-f]{64}$')
        """
    )
    op.execute("GRANT INSERT (storage_version_id, sha256) ON run_artifacts TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE run_artifacts DROP COLUMN storage_version_id, DROP COLUMN sha256")
