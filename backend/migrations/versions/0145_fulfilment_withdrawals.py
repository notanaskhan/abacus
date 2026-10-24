"""A withdrawn upload's fulfilments are voided (P-06-T19; ADR-162 §4; DEC-298).

`fulfilment_withdrawals` (tenant, forced RLS, insert-only): one row per fulfilment of a version
the client withdrew, written in the withdrawal's unit of work. `fulfilments` stays insert-only
(ADR-004); every requests read of fulfilments leaves out a version listed here, so the request
item no longer counts it, and an item whose only fulfilment it was goes back to `requested`.
Only a person (the client who withdrew) writes a row: the guard binds the session's actor.

Revision ID: 0145
Revises: 0144
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE fulfilment_withdrawals (
            tenant_id uuid NOT NULL,
            fulfilment_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            withdrawn_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, fulfilment_id),
            FOREIGN KEY (tenant_id, fulfilment_id) REFERENCES fulfilments (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX fulfilment_withdrawals_by_version "
        "ON fulfilment_withdrawals (tenant_id, evidence_version_id)"
    )
    tenant_table(op, "fulfilment_withdrawals")
    insert_only(op, "fulfilment_withdrawals")
    op.execute("REVOKE TRUNCATE ON fulfilment_withdrawals FROM abacus_app")
    insert_columns(
        op,
        "fulfilment_withdrawals",
        (
            "tenant_id",
            "fulfilment_id",
            "engagement_id",
            "request_item_id",
            "evidence_version_id",
            "withdrawn_by_user_id",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION fulfilment_withdrawals_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.withdrawn_by_user_id::text
                  IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a fulfilment is voided by the withdrawing person (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM fulfilments f
                 WHERE f.tenant_id = NEW.tenant_id AND f.id = NEW.fulfilment_id
                   AND f.request_item_id = NEW.request_item_id
                   AND f.evidence_version_id = NEW.evidence_version_id
            ) THEN
                RAISE EXCEPTION 'the voided fulfilment must be the version''s own'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER fulfilment_withdrawals_guard BEFORE INSERT ON fulfilment_withdrawals "
        "FOR EACH ROW EXECUTE FUNCTION fulfilment_withdrawals_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE fulfilment_withdrawals")
    op.execute("DROP FUNCTION fulfilment_withdrawals_guard()")
