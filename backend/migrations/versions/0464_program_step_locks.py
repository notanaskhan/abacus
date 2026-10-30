"""Mandatory step locks are a person's act (K-01-T14; K-01 §3.5 AC5.3; INV-1).

0224 kept `mandatory` and `lock_note` out of the app's column grants so that the lock would be
its own act. This grants the app UPDATE on those two columns and adds a trigger that refuses a
change to either unless the session's actor is a person (`app.actor_kind = 'human'`): the agent
and the system cannot lock or unlock a step even if the matrix were wrong. The frozen trigger
(0224) still refuses any change once the version leaves draft. The version events gain the
draft's step kinds (`step_added`, `step_edited`, `step_removed`, `mandatory_changed`) for KNW-02's
Activity tab. No data is touched.

Revision ID: 0464
Revises: 0463
"""

from __future__ import annotations

from alembic import op

revision = "0464"
down_revision = "0463"
branch_labels = None
depends_on = None

_BY_PERSON = """
    CREATE FUNCTION program_steps_lock_by_person() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF session_user = 'abacus_owner' THEN
            RETURN NEW;
        END IF;
        IF (NEW.mandatory IS DISTINCT FROM OLD.mandatory
            OR NEW.lock_note IS DISTINCT FROM OLD.lock_note)
           AND current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'only a person locks or unlocks a mandatory step'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


_KINDS = (
    "'legacy_backfilled', 'imported', 'published', 'draft_created', 'submitted', 'approved', "
    "'superseded', 'discarded', 'standards_mapped', 'exported'"
)
_STEP_KINDS = "'step_added', 'step_edited', 'step_removed', 'mandatory_changed'"


def _kinds(kinds: str) -> None:
    op.execute(
        "ALTER TABLE methodology_version_events "
        "DROP CONSTRAINT methodology_version_events_kind_check, "
        f"ADD CONSTRAINT methodology_version_events_kind_check CHECK (kind IN ({kinds}))"
    )


def upgrade() -> None:
    _kinds(f"{_KINDS}, {_STEP_KINDS}")
    op.execute("GRANT UPDATE (mandatory, lock_note) ON program_steps TO abacus_app")
    op.execute(_BY_PERSON)
    op.execute(
        "CREATE TRIGGER program_steps_lock_by_person BEFORE UPDATE OF mandatory, lock_note "
        "ON program_steps FOR EACH ROW EXECUTE FUNCTION program_steps_lock_by_person()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER program_steps_lock_by_person ON program_steps")
    op.execute("DROP FUNCTION program_steps_lock_by_person()")
    op.execute("REVOKE UPDATE (mandatory, lock_note) ON program_steps FROM abacus_app")
    _kinds(_KINDS)
