"""TIN reveals: every logged reveal of a sealed taxpayer ID, by a person (P-07-T10; DEC-52).

- New `tin_reveals`: who revealed which client entity's TIN, why (a registry reason code,
  DEC-141), on which engagement their role allowed it, and when. Never the value. Insert-only
  (trigger plus revoked UPDATE and DELETE), and `actor_kind` must be `human`: an agent or a system
  run can't write one even if the matrix let it through (INV-1, I-AGENT-NEVER).
- The one `tin.revealed` audit event of the same unit of work points at this row.

Revision ID: 0123
Revises: 0115
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0123"
down_revision = "0115"
branch_labels = None
depends_on = None

_REASONS = (
    "'prepare_return', 'review_return', 'file_or_correct_filing', 'respond_to_notice', "
    "'verify_identity'"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE tin_reveals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            user_id uuid NOT NULL,
            reason_code text NOT NULL CHECK (reason_code IN ({_REASONS})),
            mfa_at timestamptz NOT NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            revealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX tin_reveals_by_entity ON tin_reveals "
        "(tenant_id, client_entity_id, revealed_at)"
    )
    op.execute("CREATE INDEX tin_reveals_by_user ON tin_reveals (tenant_id, user_id, revealed_at)")
    op.execute(
        """
        CREATE FUNCTION tin_reveals_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tin_reveals is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER tin_reveals_immutable BEFORE UPDATE OR DELETE ON tin_reveals "
        "FOR EACH ROW EXECUTE FUNCTION tin_reveals_immutable()"
    )
    tenant_table(op, "tin_reveals")
    op.execute("REVOKE UPDATE, DELETE ON tin_reveals FROM abacus_app")
    insert_columns(
        op,
        "tin_reveals",
        ("tenant_id", "client_entity_id", "engagement_id", "user_id", "reason_code", "mfa_at"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE tin_reveals")
    op.execute("DROP FUNCTION tin_reveals_immutable()")
