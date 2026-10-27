"""Status guards for review notes and decision cards (P-04-T21, T23 security review M4, L5;
DEC-506; TASK-1400, TASK-1402).

The app role may UPDATE `reviewable_notes.status` (0093) and `decision_cards.status` (0094), and
the sign-off rule R-SO-4 reads the note's status alone. So the database now holds the transitions
the services make, for the application (the owner's migrations and superuser seeding are not the
application, 0175's precedent):

- `reviewable_notes`: forward only (open -> responded, cleared, withdrawn or closed; responded ->
  cleared, withdrawn or closed; cleared -> open, a reopen); withdrawn and closed are final. Only a
  person changes a status, only the raiser withdraws, and a clear, withdrawal or close needs that
  event row, written in the same transaction by the same person.
- `reviewable_note_events`: a `withdrawn` event is a person's too, as `cleared` is (0093).
- `decision_cards`: awaiting_role -> decided only with the acting person's `decisions` row for
  the card; awaiting_role or decided -> superseded only once a card of the same engagement and
  kind supersedes it with a reassessment by the acting person (one successor per card, a unique
  index); nothing else, and only a person.
- `decisions.decided_by` and a decided or reassessed `decision_card_versions.actor_user_id` are the
  transaction's actor.

The trigger functions are SECURITY INVOKER (the default) with a pinned search path: they read
`decisions` and `decision_cards` under the caller's own row-level security.

Revision ID: 0213
Revises: 0212
"""

from __future__ import annotations

from alembic import op

revision = "0213"
down_revision = "0212"
branch_labels = None
depends_on = None

# 0154's and 0175's precedent: the owner's paths and superuser seeding are not the application.
_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)

_NOTES_GUARD = f"""
    CREATE FUNCTION reviewable_notes_status_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NEW.status IS NOT DISTINCT FROM OLD.status OR NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'a review note''s status is changed by a person'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT (
            (OLD.status = 'open' AND NEW.status IN ('responded', 'cleared', 'withdrawn', 'closed'))
            OR (OLD.status = 'responded' AND NEW.status IN ('cleared', 'withdrawn', 'closed'))
            OR (OLD.status = 'cleared' AND NEW.status = 'open')
        ) THEN
            RAISE EXCEPTION 'a review note cannot go from % to %', OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status = 'withdrawn'
           AND current_setting('app.actor_id', true) IS DISTINCT FROM OLD.raised_by::text THEN
            RAISE EXCEPTION 'only the raiser withdraws a review note'
                USING ERRCODE = 'check_violation';
        END IF;
        -- A clear, a withdrawal or a close is the event the same person wrote in this
        -- transaction (re-review L3): the status is never set on its own.
        IF NEW.status IN ('cleared', 'withdrawn', 'closed') AND NOT EXISTS (
            SELECT 1 FROM public.reviewable_note_events e
             WHERE e.tenant_id = NEW.tenant_id AND e.note_id = NEW.id AND e.kind = NEW.status
               AND e.actor_kind = 'human'
               AND e.by_user::text = current_setting('app.actor_id', true)
               AND e.xmin = pg_current_xact_id()::xid
        ) THEN
            RAISE EXCEPTION 'a review note''s % needs its event, written now by the same person',
                NEW.status USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""  # noqa: S608 -- fixed SQL, no input

_CARDS_GUARD = f"""
    CREATE FUNCTION decision_cards_status_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NEW.status IS NOT DISTINCT FROM OLD.status OR NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'a decision card''s status is changed by a person'
                USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.status = 'awaiting_role' AND NEW.status = 'decided' THEN
            IF NOT EXISTS (
                SELECT 1 FROM public.decisions d
                 WHERE d.tenant_id = NEW.tenant_id AND d.card_id = NEW.id
                   AND d.actor_kind = 'human'
                   AND d.actor_id = current_setting('app.actor_id', true)
            ) THEN
                RAISE EXCEPTION 'a card is decided only with its decision'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status IN ('awaiting_role', 'decided') AND NEW.status = 'superseded' THEN
            -- The successor is this card's own reassessment (re-review L2): the same engagement
            -- and kind, its first version a reassessment by the person acting now.
            IF NOT EXISTS (
                SELECT 1 FROM public.decision_cards c
                 WHERE c.tenant_id = NEW.tenant_id AND c.supersedes_id = NEW.id
                   AND c.engagement_id = NEW.engagement_id AND c.kind = NEW.kind
                   AND EXISTS (
                       SELECT 1 FROM public.decision_card_versions v
                        WHERE v.tenant_id = NEW.tenant_id AND v.card_id = c.id
                          AND v.event = 'reassessed'
                          AND v.actor_id = current_setting('app.actor_id', true)
                   )
            ) THEN
                RAISE EXCEPTION 'a card is superseded only by a card that supersedes it'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSE
            RAISE EXCEPTION 'a decision card cannot go from % to %', OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""  # noqa: S608 -- fixed SQL, no input


def upgrade() -> None:
    # One successor per card (re-review L2).
    op.execute(
        "CREATE UNIQUE INDEX decision_cards_one_successor ON decision_cards "
        "(tenant_id, supersedes_id) WHERE supersedes_id IS NOT NULL"
    )
    op.execute(_NOTES_GUARD)
    op.execute(
        "CREATE TRIGGER reviewable_notes_status_guard BEFORE UPDATE ON reviewable_notes "
        "FOR EACH ROW EXECUTE FUNCTION reviewable_notes_status_guard()"
    )
    op.execute(_CARDS_GUARD)
    op.execute(
        "CREATE TRIGGER decision_cards_status_guard BEFORE UPDATE ON decision_cards "
        "FOR EACH ROW EXECUTE FUNCTION decision_cards_status_guard()"
    )
    op.execute(
        "ALTER TABLE reviewable_note_events ADD CONSTRAINT "
        "reviewable_note_events_withdrawn_by_a_person "
        "CHECK (kind <> 'withdrawn' OR actor_kind = 'human') NOT VALID"
    )
    op.execute(
        "ALTER TABLE reviewable_note_events "
        "VALIDATE CONSTRAINT reviewable_note_events_withdrawn_by_a_person"
    )
    op.execute(
        "ALTER TABLE decisions ADD CONSTRAINT decisions_decider_is_the_actor "
        "CHECK (decided_by::text = actor_id) NOT VALID"
    )
    op.execute("ALTER TABLE decisions VALIDATE CONSTRAINT decisions_decider_is_the_actor")
    op.execute(
        "ALTER TABLE decision_card_versions ADD CONSTRAINT decision_card_versions_person_is_actor "
        "CHECK (event = 'proposed' OR actor_user_id::text = actor_id) NOT VALID"
    )
    op.execute(
        "ALTER TABLE decision_card_versions "
        "VALIDATE CONSTRAINT decision_card_versions_person_is_actor"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE decision_card_versions DROP CONSTRAINT decision_card_versions_person_is_actor"
    )
    op.execute("ALTER TABLE decisions DROP CONSTRAINT decisions_decider_is_the_actor")
    op.execute(
        "ALTER TABLE reviewable_note_events "
        "DROP CONSTRAINT reviewable_note_events_withdrawn_by_a_person"
    )
    op.execute("DROP TRIGGER decision_cards_status_guard ON decision_cards")
    op.execute("DROP FUNCTION decision_cards_status_guard()")
    op.execute("DROP TRIGGER reviewable_notes_status_guard ON reviewable_notes")
    op.execute("DROP FUNCTION reviewable_notes_status_guard()")
    op.execute("DROP INDEX decision_cards_one_successor")
