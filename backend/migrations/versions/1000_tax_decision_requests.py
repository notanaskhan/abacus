"""T-06-T35 (S52; TASK-8833; SPEC-702 F3; amber): a §754 decision sent to the client's owner
(`tax_decision_requests`, one per card: a second send is refused) and the client's answer
(`tax_decision_answers`, one per request, attributed to the contact, the grant and the decider
basis). Insert-only, forced RLS. The decision card itself stays C3's. Expand-only.

Revision ID: 1000
Revises: 0999
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1000"
down_revision = "0999"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_decision_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            card_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind = 'section_754'),
            subject_partner_id uuid NULL,
            contact_id uuid NOT NULL,
            contact_user_id uuid NOT NULL,
            issue_id uuid NULL,
            sent_by uuid NOT NULL CHECK (sent_by::text = current_setting('app.actor_id', true)),
            sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, card_id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tax_decision_answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            request_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('accept', 'decline')),
            contact_id uuid NOT NULL,
            user_id uuid NOT NULL CHECK (user_id::text = current_setting('app.actor_id', true)),
            grant_id uuid NOT NULL,
            designation_basis text NOT NULL
                CHECK (designation_basis IN ('owner', 'approver_of_record', 'ske_designee')),
            answered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, request_id),
            FOREIGN KEY (tenant_id, request_id) REFERENCES tax_decision_requests (tenant_id, id)
        )
        """
    )
    for table, columns in (
        ("tax_decision_requests",
         ("tenant_id", "engagement_id", "work_item_id", "card_id", "kind", "subject_partner_id",
          "contact_id", "contact_user_id", "issue_id", "sent_by")),
        ("tax_decision_answers",
         ("tenant_id", "request_id", "decision", "contact_id", "user_id", "grant_id",
          "designation_basis")),
    ):  # fmt: skip
        tenant_table(op, table)
        insert_columns(op, table, columns)
        insert_only(op, table)


def downgrade() -> None:
    op.execute("DROP TABLE tax_decision_answers")
    op.execute("DROP TABLE tax_decision_requests")
