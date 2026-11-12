"""T-05-T22 (S38; TASK-7405; T-05 §4.2 M3; DEC-4404): partner TINs sealed, expand-only.

- `partners.tin_sealed` (an envelope under the firm's key, P-12, bound to the partner),
  `tin_last4` and `tin_kind` (ssn, ein or itin), all three or none. The value is never stored
  in clear, never logged and never in an audit row (DEC-52). Written only through
  `tax.partner_tins.seal_partner_tin`, by column grant.
- `partner_tin_reveals` (insert-only): one row per reveal, the reason code and the second factor's
  time, never the value; a person's row only (the session's actor, bound to the GUCs).

Retention record types `tax_workbook` and `preparer_memo` are code's (`evidence.retention`); their
years are content (P-14's policy model). The pipeline runs it after 8 pm CT inside the window
(P-29).

Revision ID: 0831
Revises: 0830
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0831"
down_revision = "0830"
branch_labels = None
depends_on = None

_REASONS = (
    "prepare_return",
    "review_return",
    "file_or_correct_filing",
    "respond_to_notice",
    "verify_identity",
)
_TIN = ("tin_sealed", "tin_last4", "tin_kind")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE partners
            ADD COLUMN tin_sealed bytea NULL,
            ADD COLUMN tin_last4 text NULL CHECK (tin_last4 ~ '^[0-9]{4}$'),
            ADD COLUMN tin_kind text NULL CHECK (tin_kind IN ('ssn', 'ein', 'itin')),
            ADD CONSTRAINT partners_tin_together CHECK (
                (tin_sealed IS NULL) = (tin_last4 IS NULL)
                AND (tin_sealed IS NULL) = (tin_kind IS NULL))
        """
    )
    op.execute(
        f"GRANT INSERT ({', '.join(_TIN)}), UPDATE ({', '.join(_TIN)}) ON partners TO abacus_app"
    )
    reasons = ", ".join(f"'{r}'" for r in _REASONS)
    op.execute(
        f"""
        CREATE TABLE partner_tin_reveals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            partner_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            reason_code text NOT NULL CHECK (reason_code IN ({reasons})),
            mfa_at timestamptz NOT NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            revealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (actor_id = user_id::text),
            FOREIGN KEY (tenant_id, partner_id) REFERENCES partners (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX partner_tin_reveals_user ON partner_tin_reveals (user_id, revealed_at)"
    )
    op.execute(
        """
        CREATE FUNCTION partner_tin_reveals_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: a TIN reveal is never changed or removed'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION partner_tin_reveals_immutable() FROM PUBLIC")
    tenant_table(op, "partner_tin_reveals")
    op.execute("REVOKE DELETE, TRUNCATE ON partner_tin_reveals FROM abacus_app")
    insert_columns(
        op,
        "partner_tin_reveals",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "partner_id",
            "user_id",
            "reason_code",
            "mfa_at",
        ),
    )
    insert_only(op, "partner_tin_reveals")
    op.execute(
        "CREATE TRIGGER partner_tin_reveals_immutable BEFORE UPDATE OR DELETE "
        "ON partner_tin_reveals FOR EACH ROW EXECUTE FUNCTION partner_tin_reveals_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE partner_tin_reveals")
    op.execute("DROP FUNCTION partner_tin_reveals_immutable()")
    op.execute(
        """
        ALTER TABLE partners
            DROP CONSTRAINT partners_tin_together,
            DROP COLUMN tin_kind,
            DROP COLUMN tin_last4,
            DROP COLUMN tin_sealed
        """
    )
