"""SSARS workspace (A-08-T22; A-08 §3 F8, §6 M7; SPEC-657 AC-8.1 to AC-8.6; AUD-26 a to e;
DEC-5401).

- `workpapers.kind` gains `ssars_read_fs`: compilation's "Read the FS for obvious material
  misstatements" procedure, signed at L1 like any working paper.
- `ssars_inquiry_programs`: the inquiry program a person built from the firm's methodology
  program for a review work item: one T-02 `ssars_inquiry` questionnaire per recipient, the
  same questions in each; published once (a person, never the agent).
- The engagement type `preparation` already exists (0069, F-03), so no type swap.

Revision ID: 0941
Revises: 0940
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0941"
down_revision = "0940"
branch_labels = None
depends_on = None

_PLANNING = (
    "general_audit_planning",
    "risk_assessment",
    "internal_control",
    "service_organizations",
)
_EBP = (
    "ebp_plan",
    "ebp_provisions",
    "ebp_eligibility",
    "ebp_contributions",
    "ebp_distributions_loans",
    "ebp_investments",
    "ebp_form5500",
    "ebp_participant_accounts",
    "ebp_admin_expenses",
)
_TAX = ("tax_workbook",)
_SSARS = ("ssars_read_fs",)
INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "methodology_program_id", "questionnaire_ids",
    "questions", "created_by",
)  # fmt: skip
UPDATES = ("published_at", "published_by")


def _kinds(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{k}'" for k in kinds)
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_kind_check")
    op.execute(
        f"ALTER TABLE workpapers ADD CONSTRAINT workpapers_kind_check CHECK (kind IN ({listed}))"
    )


def upgrade() -> None:
    _kinds(_PLANNING + _EBP + _TAX + _SSARS)
    op.execute(
        """
        CREATE TABLE ssars_inquiry_programs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            methodology_program_id uuid NOT NULL,
            questionnaire_ids uuid[] NOT NULL
                CHECK (cardinality(questionnaire_ids) BETWEEN 1 AND 20),
            questions integer NOT NULL CHECK (questions BETWEEN 1 AND 500),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            published_at timestamptz NULL,
            published_by uuid NULL,
            UNIQUE (tenant_id, id),
            CHECK ((published_at IS NULL) = (published_by IS NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, published_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ssars_inquiry_programs_work_item ON ssars_inquiry_programs "
        "(tenant_id, work_item_id, created_at DESC)"
    )
    tenant_table(op, "ssars_inquiry_programs")
    insert_columns(op, "ssars_inquiry_programs", INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON ssars_inquiry_programs FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON ssars_inquiry_programs TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE ssars_inquiry_programs")
    op.execute("DELETE FROM workpapers WHERE kind = 'ssars_read_fs'")
    _kinds(_PLANNING + _EBP + _TAX)
