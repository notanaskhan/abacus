"""A-08 fieldwork tests on the shared attribute grid (A-08-T14; A-08 §3 F2; AUD-12; DEC-5306).
Expand only.

- `attribute_tests.variant` gains `aud12_je` (JE Testing on A-05's grid, beside `aud12_tod` and
  `aud12_toc`): the CHECK is replaced by a wider one, so no existing row changes meaning.
- `control_deviations` (insert-only): one row per deviation or exception a person logs on a
  tested item, with the amount difference and whether it sits below clearly trivial (code
  decides), and the finding it reached (AUD-15). The deviation log and its UDL read these.

Revision ID: 0930
Revises: 0921
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0930"
down_revision = "0921"
branch_labels = None
depends_on = None

_OLD = "'ebp_eligibility', 'ebp_contribution_recalc', 'ebp_distribution', 'aud12_tod', 'aud12_toc'"
_NEW = f"{_OLD}, 'aud12_je'"
INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "test_id", "sample_item_id", "attribute_key",
    "kind", "description", "difference", "below_ct", "finding_id", "recorded_by", "actor_kind",
)  # fmt: skip


def upgrade() -> None:
    op.execute("ALTER TABLE attribute_tests DROP CONSTRAINT attribute_tests_variant_check")
    op.execute(
        f"ALTER TABLE attribute_tests ADD CONSTRAINT attribute_tests_variant_check "
        f"CHECK (variant IN ({_NEW}))"
    )
    op.execute(
        """
        CREATE TABLE control_deviations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            test_id uuid NOT NULL,
            sample_item_id uuid NOT NULL,
            attribute_key text NOT NULL CHECK (attribute_key ~ '^[a-z][a-z0-9_]{0,63}$'),
            kind text NOT NULL CHECK (kind IN ('deviation', 'exception', 'difference')),
            description text NOT NULL CHECK (length(btrim(description)) BETWEEN 1 AND 1000),
            difference numeric(18, 2) NULL,
            below_ct boolean NOT NULL DEFAULT false,
            finding_id uuid NULL,
            recorded_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- A difference below clearly trivial is logged, never an exception (A-08 F2).
            CHECK (NOT (below_ct AND kind = 'exception')),
            FOREIGN KEY (tenant_id, test_id) REFERENCES attribute_tests (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, recorded_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX control_deviations_test ON control_deviations (tenant_id, test_id, at)"
    )
    tenant_table(op, "control_deviations")
    insert_columns(op, "control_deviations", INSERTS)
    insert_only(op, "control_deviations")


def downgrade() -> None:
    op.execute("DROP TABLE control_deviations")
    op.execute("DELETE FROM attribute_tests WHERE variant = 'aud12_je'")
    op.execute("ALTER TABLE attribute_tests DROP CONSTRAINT attribute_tests_variant_check")
    op.execute(
        f"ALTER TABLE attribute_tests ADD CONSTRAINT attribute_tests_variant_check "
        f"CHECK (variant IN ({_OLD}))"
    )
