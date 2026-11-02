"""S25 end pass (DEC-2077): repair 0642's hash CHECKs. Expand only.

0642 built five CHECKs from a plain string holding `{{64}}` (meant for an f-string), so the
regex Postgres stored is `^[0-9a-f]{{64}}$`, which no SHA-256 hex digest matches: every import,
participant fingerprint, attribute test and population query was refused. 0642 is on main and
stays as it is; this replaces the five constraints with `^[0-9a-f]{64}$`, under their own names.

Revision ID: 0654
Revises: 0653
"""

from __future__ import annotations

from alembic import op

revision = "0654"
down_revision = "0653"
branch_labels = None
depends_on = None

COLUMNS = (
    ("ebp_source_imports", "sha256"),
    ("ebp_participants", "ssn_fp"),
    ("ebp_participants", "dob_fp"),
    ("attribute_tests", "content_hash"),
    ("ebp_population_queries", "inputs_hash"),
)
_SHA = "~ '^[0-9a-f]{64}$'"
_BROKEN = "~ '^[0-9a-f]{{64}}$'"


def _replace(pattern: str) -> None:
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_{column}_check")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_check CHECK ({column} {pattern})"
        )


def upgrade() -> None:
    _replace(_SHA)


def downgrade() -> None:
    _replace(_BROKEN)
