"""A signer's portal decline can be withdrawn (N-02-T23; SPEC-381 AC-12; DEC-1283).

`envelopes_human_actor` (0292, as 0405 left it with the Undo rule) made `declined` final like
completed, expired and voided, so a decline made in the portal could never be withdrawn although
AC-12 allows it while the envelope is open (until the firm voids or resends). The trigger now
lets a person (`app.actor_kind = human`) move a declined envelope back to sent, viewed or
partially signed, and nothing else: the system, an agent or support still cannot, and completed,
expired and voided stay final. Which declines may be withdrawn (the signer's own, made in the
portal) is the service's rule.

Revision ID: 0433
Revises: 0432
"""

from __future__ import annotations

from alembic import op

revision = "0433"
down_revision = "0432"
branch_labels = None
depends_on = None

_WITHDRAWABLE = """
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
                OR OLD.status IN ('completed', 'expired', 'voided')
                   AND NEW.status IS DISTINCT FROM OLD.status
                OR OLD.status = 'declined' AND NEW.status IS DISTINCT FROM OLD.status
                   AND NOT (human AND NEW.status IN ('sent', 'viewed', 'partially_signed'))) THEN
                RAISE EXCEPTION 'an envelope''s number, client, provider, actors and final status '
                    'do not change' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
"""

# 0405's function, restored on downgrade.
_ORIGINAL = """
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
    op.execute(_WITHDRAWABLE)


def downgrade() -> None:
    op.execute(_ORIGINAL)
