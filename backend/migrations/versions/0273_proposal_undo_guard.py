"""A proposal Undo returns it to pending (P-04-T29; DEC-24, ADR-161 clause 6; DEC-713).

`proposals_state_guard()` (0230) lets a person move a proposal only from `pending` to a decision
with that decision written now. It now also lets the person who decided move it back to `pending`
with an `undone` decision, written now, naming their decision of the state being left; the
10-second window and every other rule are the service's and evidence's (0117). The function is
replaced in place; the downgrade restores 0230's.

Revision ID: 0273
Revises: 0272 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

revision = "0273"
down_revision = "0272"
branch_labels = None
depends_on = None

_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)

_GUARD_V1 = f"""
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

_GUARD_V2 = f"""
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
        IF NEW.state IS DISTINCT FROM OLD.state AND NEW.state = 'pending' THEN
            -- P-04-T29 (DEC-24, ADR-161 clause 6): an Undo takes a decided proposal back to
            -- pending, only with its `undone` decision, written now by the same person, naming
            -- that person's decision of the state being left.
            IF NOT (OLD.state IN ('approved', 'approved_with_edits', 'rejected') AND EXISTS (
                SELECT 1 FROM public.proposal_decisions u
                  JOIN public.proposal_decisions d
                    ON d.tenant_id = u.tenant_id AND d.id = u.undoes_decision_id
                 WHERE u.tenant_id = NEW.tenant_id AND u.proposal_id = NEW.id
                   AND u.decision = 'undone' AND d.decision = OLD.state
                   AND u.actor_kind = 'human' AND d.actor_id = u.actor_id
                   AND u.actor_id = current_setting('app.actor_id', true)
                   AND u.xmin = pg_current_xact_id()::xid)) THEN
                RAISE EXCEPTION 'a proposal returns to pending only with its undo, written now'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
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


def upgrade() -> None:
    op.execute(_GUARD_V2.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))


def downgrade() -> None:
    op.execute(_GUARD_V1.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
