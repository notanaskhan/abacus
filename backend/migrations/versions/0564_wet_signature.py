"""E-file authorization policy and the handwritten fallback (N-02-T27; N-02 §3.7; DF-11;
DEC-1469). Expand-only.

- `envelope_signers.wet_recorded_by`: the person who recorded a hand-signed form. A trigger holds
  INV-1's database layer: a signer becomes `handwritten` only in a transaction whose actor is
  that person (`app.actor_kind = 'human'`, `app.actor_id`), and the recorder is never rewritten.
- 0292 tied `verification_failed` to exactly three failures; a firm may tighten the e-file
  family's `kba_max_attempts` below three (stricter-only), so the check becomes "at least one
  failure" (the poll moves the signer at the firm's limit).

Revision ID: 0564
Revises: 0563
"""

from __future__ import annotations

from alembic import op

revision = "0564"
down_revision = "0563"
branch_labels = None
depends_on = None


def _drop_three_failures_check() -> None:
    op.execute(
        """
        DO $$
        DECLARE c record;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'envelope_signers'::regclass AND contype = 'c'
                       AND pg_get_constraintdef(oid) LIKE '%kba_failures = 3%'
            LOOP
                EXECUTE format('ALTER TABLE envelope_signers DROP CONSTRAINT %I', c.conname);
            END LOOP;
        END $$
        """
    )


def upgrade() -> None:
    _drop_three_failures_check()
    op.execute(
        """
        ALTER TABLE envelope_signers
            ADD COLUMN wet_recorded_by uuid NULL,
            ADD CONSTRAINT envelope_signers_verification_failed
                CHECK (status <> 'verification_failed' OR kba_failures >= 1),
            ADD CONSTRAINT envelope_signers_wet_recorder
                CHECK ((signature_method = 'handwritten') = (wet_recorded_by IS NOT NULL)),
            ADD CONSTRAINT envelope_signers_wet_recorded_by_fk
                FOREIGN KEY (tenant_id, wet_recorded_by)
                REFERENCES memberships (tenant_id, user_id)
        """
    )
    op.execute(
        """
        CREATE FUNCTION envelope_signers_wet_person() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.wet_recorded_by IS NOT NULL
               AND NEW.wet_recorded_by IS DISTINCT FROM OLD.wet_recorded_by THEN
                RAISE EXCEPTION 'a hand-signed form''s recorder is never rewritten'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.wet_recorded_by IS NOT NULL AND OLD.wet_recorded_by IS NULL AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.wet_recorded_by::text
            ) THEN
                RAISE EXCEPTION 'a hand-signed form is recorded by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER envelope_signers_wet_person BEFORE UPDATE ON envelope_signers "
        "FOR EACH ROW EXECUTE FUNCTION envelope_signers_wet_person()"
    )
    op.execute("GRANT UPDATE (wet_recorded_by) ON envelope_signers TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TRIGGER envelope_signers_wet_person ON envelope_signers")
    op.execute("DROP FUNCTION envelope_signers_wet_person()")
    op.execute(
        """
        ALTER TABLE envelope_signers
            DROP CONSTRAINT envelope_signers_wet_recorded_by_fk,
            DROP CONSTRAINT envelope_signers_wet_recorder,
            DROP CONSTRAINT envelope_signers_verification_failed,
            DROP COLUMN wet_recorded_by,
            ADD CHECK (status <> 'verification_failed' OR kba_failures = 3)
        """
    )
