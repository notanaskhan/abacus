"""A-01-T05: the assurance profile facts and record-mode phases (A-01 §4.2 M1; SPEC-330 AC-9 to
AC-14; DEC-262).

`assurance_work_items` gains:
- `ebp_plan_kind` (`dc`, `403b`, `db`; health and welfare plans stay off until the BAA chain
  exists) and `limited_scope_103a3c`: the EBP label facts ("EBP DC · §103(a)(3)(C)");
- `phase_source` (`recorded` by a named person while the phase's gate has no provider, or
  `derived` from the gate's `gate.met`), `phase_changed_at` and `version` (optimistic
  concurrency for PATCH profile).
The `phase` CHECK already holds the C2 `audit_engagement` codes (0068) and is kept: SPEC-314's
release and archive write `released` and `archived`, and the backfill wrote `archived`.

New `assurance_phase_events` (insert-only: UPDATE and DELETE revoked and refused by a trigger):
one row per phase move. A `recorded` row is a person's (CHECK); a `derived` row names its gate
and is the system's or the person whose act met the gate (SPEC-314's release and archive). The
optional reason is sealed under the tenant key, bound to the event's id (≤ 300 characters before
sealing, checked in the service). Indexed for the AUD-01 tiles and a work item's history.

The phase moves only through an event (security review, DEC-262): the app role loses UPDATE on
`phase`, and the SECURITY DEFINER insert trigger `assurance_phase_event_apply` checks the row and
moves the projection itself. It refuses an actor other than the session's own (`app.actor_kind`,
`app.actor_id`, as 0132 does for review decisions), a `from_phase` that is not the work item's
phase, a move that is not forward, and a recorded move of more than one step (In review to Ready
to release counts as one while Completion is not offered, DV-12).

Revision ID: 0134
Revises: 0133
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None

_PHASES = (
    "('planning', 'fieldwork', 'in_review', 'completion', 'ready_to_release', 'released', "
    "'archiving', 'archived')"
)

# The order of C2 `audit_engagement` codes; `archiving` is the index's clock, never moved to.
_APPLY = """
CREATE FUNCTION assurance_phase_event_apply() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_order text[] := ARRAY['planning', 'fieldwork', 'in_review', 'completion',
                            'ready_to_release', 'released', 'archiving', 'archived'];
    v_phase text;
    v_from integer;
    v_to integer;
BEGIN
    IF NEW.actor_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
       OR (NEW.actor_kind = 'human'
           AND NEW.actor_user_id::text IS DISTINCT FROM current_setting('app.actor_id', true))
    THEN
        RAISE EXCEPTION 'a phase move is made by the session''s own actor'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT w.phase INTO v_phase FROM public.assurance_work_items w
     WHERE w.tenant_id = NEW.tenant_id AND w.work_item_id = NEW.work_item_id
       AND w.engagement_id = NEW.engagement_id
       FOR UPDATE;
    IF NOT FOUND OR v_phase IS DISTINCT FROM NEW.from_phase THEN
        RAISE EXCEPTION 'phase_stale'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'assurance_phase_events_from_current';
    END IF;
    v_from := array_position(v_order, NEW.from_phase);
    v_to := array_position(v_order, NEW.to_phase);
    IF v_to <= v_from THEN
        RAISE EXCEPTION 'phase_backward'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'assurance_phase_events_forward';
    END IF;
    IF NEW.mode = 'recorded' AND NOT (
        v_to = v_from + 1
        OR (NEW.from_phase = 'in_review' AND NEW.to_phase = 'ready_to_release')
    ) THEN
        RAISE EXCEPTION 'phase_skip'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'assurance_phase_events_one_step';
    END IF;
    UPDATE public.assurance_work_items
       SET phase = NEW.to_phase, phase_source = NEW.mode,
           phase_changed_at = public.abacus_now(), version = version + 1
     WHERE tenant_id = NEW.tenant_id AND work_item_id = NEW.work_item_id;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE assurance_work_items
            ADD COLUMN ebp_plan_kind text NULL CHECK (ebp_plan_kind IN ('dc', '403b', 'db')),
            ADD COLUMN limited_scope_103a3c boolean NOT NULL DEFAULT false,
            ADD COLUMN phase_source text NOT NULL DEFAULT 'recorded'
                CHECK (phase_source IN ('recorded', 'derived')),
            ADD COLUMN phase_changed_at timestamptz NULL,
            ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1)
        """
    )
    op.execute(
        "GRANT UPDATE (ebp_plan_kind, limited_scope_103a3c, standards_set_id, version) "
        "ON assurance_work_items TO abacus_app"
    )
    # The phase moves only through an event row (assurance_phase_event_apply below).
    op.execute("REVOKE UPDATE (phase) ON assurance_work_items FROM abacus_app")
    op.execute(
        "CREATE INDEX assurance_work_items_by_phase "
        "ON assurance_work_items (tenant_id, phase, work_item_id)"
    )
    op.execute(
        f"""
        CREATE TABLE assurance_phase_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            from_phase text NOT NULL CHECK (from_phase IN {_PHASES}),
            to_phase text NOT NULL CHECK (to_phase IN {_PHASES}),
            mode text NOT NULL CHECK (mode IN ('recorded', 'derived')),
            reason_sealed bytea NULL,
            gate_ref text NULL CHECK (gate_ref ~ '^G[1-9]$'),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            mfa_at timestamptz NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (from_phase <> to_phase),
            CHECK (mode <> 'recorded' OR (actor_kind = 'human' AND gate_ref IS NULL)),
            CHECK (mode <> 'derived' OR gate_ref IS NOT NULL),
            CHECK ((actor_kind = 'human') = (actor_user_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX assurance_phase_events_by_item "
        "ON assurance_phase_events (tenant_id, work_item_id, recorded_at)"
    )
    op.execute(
        """
        CREATE FUNCTION assurance_phase_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'assurance_phase_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER assurance_phase_events_immutable "
        "BEFORE UPDATE OR DELETE ON assurance_phase_events "
        "FOR EACH ROW EXECUTE FUNCTION assurance_phase_events_immutable()"
    )
    op.execute(_APPLY)
    op.execute("REVOKE ALL ON FUNCTION assurance_phase_event_apply() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION assurance_phase_event_apply() TO abacus_app")
    op.execute(
        "CREATE TRIGGER assurance_phase_event_apply "
        "BEFORE INSERT ON assurance_phase_events "
        "FOR EACH ROW EXECUTE FUNCTION assurance_phase_event_apply()"
    )
    tenant_table(op, "assurance_phase_events")
    op.execute("REVOKE UPDATE, DELETE ON assurance_phase_events FROM abacus_app")
    insert_columns(
        op,
        "assurance_phase_events",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "from_phase",
            "to_phase",
            "mode",
            "reason_sealed",
            "gate_ref",
            "actor_kind",
            "actor_user_id",
            "mfa_at",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE assurance_phase_events")
    op.execute("DROP FUNCTION assurance_phase_event_apply()")
    op.execute("DROP FUNCTION assurance_phase_events_immutable()")
    op.execute("DROP INDEX assurance_work_items_by_phase")
    op.execute(
        "REVOKE UPDATE (ebp_plan_kind, limited_scope_103a3c, standards_set_id, version) "
        "ON assurance_work_items FROM abacus_app"
    )
    op.execute("GRANT UPDATE (phase) ON assurance_work_items TO abacus_app")
    op.execute(
        """
        ALTER TABLE assurance_work_items
            DROP COLUMN version,
            DROP COLUMN phase_changed_at,
            DROP COLUMN phase_source,
            DROP COLUMN limited_scope_103a3c,
            DROP COLUMN ebp_plan_kind
        """
    )
