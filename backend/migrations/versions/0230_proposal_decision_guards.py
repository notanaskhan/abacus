"""Guards for proposal and suggestion decisions (P-04-T24; TASK-1460; DEC-601).

The app role may UPDATE `proposals (state, routed_to_user_id, version)` and
`suggestions (status, version)` (0095), and SHL-10, Home and the field history read those columns
alone. So the database holds the transitions the service makes, for the application (the owner's
migrations and superuser seeding are not the application, 0213's precedent):

- `proposals`: only a person changes a row. `pending` -> `approved`, `approved_with_edits` or
  `rejected` only with that person's decision row of the same kind, written in this transaction;
  a new `routed_to_user_id` only with their `routed` row naming that person; nothing else moves
  the state (`superseded` arrives with its producer).
- `suggestions`: only a person changes a row. `pending` -> `adopted`, `edited` or `dismissed` only
  with that person's decision row of the same kind, written in this transaction.
- `proposal_decisions.decided_by` and `suggestion_decisions.decided_by` are the transaction's
  actor (CHECK), and the app may insert their `id`, so a sealed note binds to its own row.

The trigger functions are SECURITY INVOKER (the default) with a pinned search path. A decision row
"written in this transaction" is one whose `xmin` is the current transaction id: the service
writes the row and the state in one unit of work with no savepoint, and must keep it so.

Revision ID: 0230
Revises: 0235
"""

from __future__ import annotations

from alembic import op

revision = "0230"
down_revision = "0235"
branch_labels = None
depends_on = None

_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)

_PROPOSALS_GUARD = f"""
    CREATE FUNCTION proposals_state_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'a proposal is changed by a person' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.state IS DISTINCT FROM OLD.state THEN
            IF NOT (OLD.state = 'pending'
                    AND NEW.state IN ('approved', 'approved_with_edits', 'rejected')) THEN
                RAISE EXCEPTION 'a proposal cannot go from % to %', OLD.state, NEW.state
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.proposal_decisions d
                 WHERE d.tenant_id = NEW.tenant_id AND d.proposal_id = NEW.id
                   AND d.decision = NEW.state AND d.actor_kind = 'human'
                   AND d.actor_id = current_setting('app.actor_id', true)
                   AND d.xmin = pg_current_xact_id()::xid
            ) THEN
                RAISE EXCEPTION 'a proposal is % only with its decision, written now', NEW.state
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        IF NEW.routed_to_user_id IS DISTINCT FROM OLD.routed_to_user_id AND NOT EXISTS (
            SELECT 1 FROM public.proposal_decisions d
             WHERE d.tenant_id = NEW.tenant_id AND d.proposal_id = NEW.id
               AND d.decision = 'routed' AND d.routed_to_user_id = NEW.routed_to_user_id
               AND d.actor_kind = 'human'
               AND d.actor_id = current_setting('app.actor_id', true)
               AND d.xmin = pg_current_xact_id()::xid
        ) THEN
            RAISE EXCEPTION 'a proposal is routed only with its routing, written now'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""  # noqa: S608 -- fixed SQL, no input

_SUGGESTIONS_GUARD = f"""
    CREATE FUNCTION suggestions_status_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'a suggestion is changed by a person'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            IF NOT (OLD.status = 'pending' AND NEW.status IN ('adopted', 'edited', 'dismissed'))
            THEN
                RAISE EXCEPTION 'a suggestion cannot go from % to %', OLD.status, NEW.status
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.suggestion_decisions d
                 WHERE d.tenant_id = NEW.tenant_id AND d.suggestion_id = NEW.id
                   AND d.decision = NEW.status AND d.actor_kind = 'human'
                   AND d.actor_id = current_setting('app.actor_id', true)
                   AND d.xmin = pg_current_xact_id()::xid
            ) THEN
                RAISE EXCEPTION 'a suggestion is % only with its decision, written now',
                    NEW.status USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        RETURN NEW;
    END $$
"""  # noqa: S608 -- fixed SQL, no input


def upgrade() -> None:
    op.execute(_PROPOSALS_GUARD)
    op.execute(
        "CREATE TRIGGER proposals_state_guard BEFORE UPDATE ON proposals "
        "FOR EACH ROW EXECUTE FUNCTION proposals_state_guard()"
    )
    op.execute(_SUGGESTIONS_GUARD)
    op.execute(
        "CREATE TRIGGER suggestions_status_guard BEFORE UPDATE ON suggestions "
        "FOR EACH ROW EXECUTE FUNCTION suggestions_status_guard()"
    )
    for table in ("proposal_decisions", "suggestion_decisions"):
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_decider_is_the_actor "
            "CHECK (decided_by::text = actor_id) NOT VALID"
        )
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {table}_decider_is_the_actor")
        op.execute(f"GRANT INSERT (id) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in ("suggestion_decisions", "proposal_decisions"):
        op.execute(f"REVOKE INSERT (id) ON {table} FROM abacus_app")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_decider_is_the_actor")
    op.execute("DROP TRIGGER suggestions_status_guard ON suggestions")
    op.execute("DROP FUNCTION suggestions_status_guard()")
    op.execute("DROP TRIGGER proposals_state_guard ON proposals")
    op.execute("DROP FUNCTION proposals_state_guard()")
