"""Envelope drafts are edited in place (N-02-T20; N-02 §3.4; SIG-02; DEC-1178).

SIG-02 reorders documents and signers and removes a signer from a draft:
- the `(envelope_id, "order")` uniques on `envelope_documents` and `envelope_signers` become
  deferrable, checked at commit, so a reorder swaps positions in one unit of work;
- Undo inside the window clears the send: `envelopes_human_actor` now lets the person who
  pressed Send clear `sent_by` and `sent_at` while the envelope is still a draft (the grant is
  voided in the same unit of work), and nobody else;
- the app may delete a signer of a draft only: `envelope_draft_signer_delete` refuses a delete
  once the envelope has left `draft` or a person has pressed Send (`sent_at` set). A signer of a
  sent envelope, and its evidence, is never removed.

Revision ID: 0405
Revises: 0404
"""

from __future__ import annotations

from alembic import op

revision = "0405"
down_revision = "0404"
branch_labels = None
depends_on = None


_HUMAN_ACTOR = """
        CREATE OR REPLACE FUNCTION envelopes_human_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            person text := current_setting('app.actor_id', true);
            human boolean := current_setting('app.actor_kind', true) = 'human';
            undo boolean := TG_OP = 'UPDATE' AND OLD.sent_by IS NOT NULL AND NEW.sent_by IS NULL
                AND NEW.sent_at IS NULL AND OLD.status = 'draft' AND NEW.status = 'draft'
                AND human AND OLD.sent_by::text = person;
        BEGIN
            IF NEW.sent_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.sent_by IS DISTINCT FROM OLD.sent_by)
               AND (NOT human OR NEW.sent_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is sent by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.voided_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.voided_by IS DISTINCT FROM OLD.voided_by)
               AND (NOT human OR NEW.voided_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is voided by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.imported_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.imported_by IS DISTINCT FROM OLD.imported_by)
               AND (NOT human OR NEW.imported_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is imported by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'UPDATE' AND (
                   NEW.number IS DISTINCT FROM OLD.number
                OR NEW.client_id IS DISTINCT FROM OLD.client_id
                OR NEW.provider IS DISTINCT FROM OLD.provider
                OR (OLD.imported_by IS NOT NULL
                    AND NEW.imported_by IS DISTINCT FROM OLD.imported_by)
                OR (OLD.sent_by IS NOT NULL AND NEW.sent_by IS DISTINCT FROM OLD.sent_by
                    AND NOT undo)
                OR (OLD.voided_by IS NOT NULL AND NEW.voided_by IS DISTINCT FROM OLD.voided_by)
                OR OLD.status IN ('completed', 'declined', 'expired', 'voided')
                   AND NEW.status IS DISTINCT FROM OLD.status) THEN
                RAISE EXCEPTION 'an envelope''s number, client, provider, actors and final status '
                    'do not change' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
"""


def upgrade() -> None:
    for table in ("envelope_documents", "envelope_signers"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_envelope_id_order_key")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_envelope_id_order_key "
            'UNIQUE (envelope_id, "order") DEFERRABLE INITIALLY DEFERRED'
        )
    op.execute(
        """
        CREATE FUNCTION envelope_draft_signer_delete() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM envelopes e
                WHERE e.tenant_id = OLD.tenant_id AND e.id = OLD.envelope_id
                  AND e.status = 'draft' AND e.sent_at IS NULL
            ) THEN
                RAISE EXCEPTION 'a signer is removed from a draft only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN OLD;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER envelope_signers_draft_delete BEFORE DELETE ON envelope_signers "
        "FOR EACH ROW EXECUTE FUNCTION envelope_draft_signer_delete()"
    )
    op.execute("GRANT DELETE ON envelope_signers TO abacus_app")
    # Undo: the sender may clear their own send while the envelope is still a draft (DEC-1178).
    op.execute(_HUMAN_ACTOR)


def downgrade() -> None:
    # 0292's rule again: once set, `sent_by` never changes.
    op.execute(_HUMAN_ACTOR.replace("\n                    AND NOT undo", ""))
    op.execute("REVOKE DELETE ON envelope_signers FROM abacus_app")
    op.execute("DROP TRIGGER envelope_signers_draft_delete ON envelope_signers")
    op.execute("DROP FUNCTION envelope_draft_signer_delete()")
    for table in ("envelope_documents", "envelope_signers"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_envelope_id_order_key")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_envelope_id_order_key "
            'UNIQUE (envelope_id, "order")'
        )
