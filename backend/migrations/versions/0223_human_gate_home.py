"""The C13 gate half for Home (I-01-T04; I-01 §4.2; DF-25, DEC-30, DEC-43, DEC-403; TASK-1425).

- `human_gates` (P-04's rebuildable projection) gains what Home sorts, bands and filters on:
  - `subkind`: the owner's registered gate name (`acceptance_decision_due`, ...), backfilled from
    the subject type the projector has always written as that name (P-07-T47);
  - `office_id`: the work item's office, else the engagement's (a filter, never a boundary:
    DEC-30);
  - `blocked`, `blocked_reason_code` (a code, never text) and `sort_hint`;
  - `kind` admits `evidence_review` (DEC-403: SPEC-004 review assignments and uploads awaiting
    review, banded under Approvals & sends);
  - an index for role-routed gates, and `(tenant_id, id)` unique so the new tables can refer to a
    gate of their own firm only.
  The projector may also update the four new derived columns; `subkind` is set once.
- `human_gate_snoozes` (insert-only): a person's snooze of a gate, for them alone; the latest row
  per (gate, person) wins and an unsnooze is a row with `until` at the time it was written.
- `human_gate_reassignments` (insert-only): who moved a gate from whom to whom.
  Both are a person's acts at the database: `actor_kind = 'human'` is a CHECK, and a BEFORE
  INSERT trigger binds `actor_kind` and `actor_id` to the transaction's actor (`app.actor_*`, set
  by `tenant_connection` from the request, never by the caller; 0015's pattern), and a snooze's
  `user_id` to that same person. A snooze is of an open gate that waits on that person and lasts
  at most 30 days; a reassignment names its open gate's own subject. Neither has a writable
  `created_at`.
- `decision_cards.reserved_user_id`: the app role may now UPDATE that one column (the reassign
  hook, I-01-T07). `decision_cards_reassign_guard` holds it to a person reassigning an open card
  (`awaiting_role`): never to themselves; the mover is the reserved person, the engagement's
  partner or a manager on it; the new person holds the reserved role on the engagement and is not
  walled off from its client; and the transaction wrote the matching `human_gate_reassignments`
  row from the reserved person. The status grant and 0213's status guard are unchanged
  (security review M1, DEC-575).

The trigger functions are SECURITY INVOKER with a pinned search path: they read under the
caller's own row-level security.

Revision ID: 0223
Revises: 0220
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0223"
down_revision = "0220"
branch_labels = None
depends_on = None

_KINDS_0093 = (
    "'decision', 'sign_off_request', 'proposal', 'send', 'final_approval', 'export', 'release'"
)
_KINDS = f"{_KINDS_0093}, 'evidence_review'"
_CODE = "'^[a-z][a-z_]{0,39}$'"

# 0154's and 0175's precedent: the owner's paths and superuser seeding are not the application.
_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)

_ACTOR_GUARD = """
    CREATE FUNCTION human_gate_acts_by_a_person() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NEW.actor_kind IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'only a person snoozes or reassigns a gate'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.actor_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
           OR NEW.actor_id IS DISTINCT FROM current_setting('app.actor_id', true) THEN
            RAISE EXCEPTION 'a gate is snoozed or reassigned by the session''s own person'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- Nested: plpgsql resolves NEW.user_id only on the table that has it.
        IF TG_TABLE_NAME = 'human_gate_snoozes' THEN
            IF NEW.user_id::text IS DISTINCT FROM NEW.actor_id THEN
                RAISE EXCEPTION 'a person snoozes a gate for themselves only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- Only an open gate that waits on this person (theirs, or assigned to nobody).
            IF NOT EXISTS (
                SELECT 1 FROM public.human_gates g
                 WHERE g.tenant_id = NEW.tenant_id AND g.id = NEW.gate_id AND g.state = 'open'
                   AND (g.assignee_user_id IS NULL OR g.assignee_user_id = NEW.user_id)
            ) THEN
                RAISE EXCEPTION 'a person snoozes only an open gate that waits on them'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSE
            -- A reassignment names its open gate's own subject, so it cannot stand in for a
            -- card the gate is not about.
            IF NOT EXISTS (
                SELECT 1 FROM public.human_gates g
                 WHERE g.tenant_id = NEW.tenant_id AND g.id = NEW.gate_id AND g.state = 'open'
                   AND g.subject_ref = NEW.subject_ref
            ) THEN
                RAISE EXCEPTION 'a reassignment names its open gate''s own subject'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        RETURN NEW;
    END $$
"""

_IMMUTABLE = """
    CREATE FUNCTION human_gate_acts_immutable() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        RAISE EXCEPTION 'snoozes and reassignments are insert-only (ADR-004)'
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""

_REASSIGN_GUARD = f"""
    CREATE FUNCTION decision_cards_reassign_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_actor text := current_setting('app.actor_id', true);
        v_client uuid;
    BEGIN
        IF NEW.reserved_user_id IS NOT DISTINCT FROM OLD.reserved_user_id OR NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
            RAISE EXCEPTION 'a decision card is reassigned by a person'
                USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.status IS DISTINCT FROM 'awaiting_role'
           OR NEW.status IS DISTINCT FROM OLD.status THEN
            RAISE EXCEPTION 'only a card awaiting its role is reassigned, and nothing else changes'
                USING ERRCODE = 'check_violation';
        END IF;
        -- Never to oneself: a person moves a card to someone else.
        IF NEW.reserved_user_id IS NULL OR NEW.reserved_user_id::text = v_actor THEN
            RAISE EXCEPTION 'a card is reassigned to another person'
                USING ERRCODE = 'check_violation';
        END IF;
        -- Who may move it: the reserved person, or the engagement's partner or a manager on it.
        IF OLD.reserved_user_id::text IS DISTINCT FROM v_actor AND NOT EXISTS (
            SELECT 1 FROM public.engagement_members m
             WHERE m.tenant_id = NEW.tenant_id AND m.engagement_id = NEW.engagement_id
               AND m.user_id::text = v_actor AND m.role IN ('engagement_partner', 'manager')
        ) THEN
            RAISE EXCEPTION 'only the reserved person, the partner or a manager moves a card'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- The new person holds the reserved role on the engagement and is not walled off.
        IF NOT EXISTS (
            SELECT 1 FROM public.engagement_members m
             WHERE m.tenant_id = NEW.tenant_id AND m.engagement_id = NEW.engagement_id
               AND m.user_id = NEW.reserved_user_id AND m.role = NEW.reserved_role
        ) THEN
            RAISE EXCEPTION 'a card goes only to a holder of its reserved role'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT e.client_id INTO v_client FROM public.engagements e
         WHERE e.tenant_id = NEW.tenant_id AND e.id = NEW.engagement_id;
        IF EXISTS (
            SELECT 1 FROM public.ethical_walls w
             WHERE w.tenant_id = NEW.tenant_id AND w.user_id = NEW.reserved_user_id
               AND w.client_id = v_client AND w.status = 'active'
        ) THEN
            RAISE EXCEPTION 'a card never goes to a person walled off from its client'
                USING ERRCODE = 'check_violation';
        END IF;
        -- And its reassignment row, written now by this person, from the reserved person.
        IF NOT EXISTS (
            SELECT 1 FROM public.human_gate_reassignments r
             WHERE r.tenant_id = NEW.tenant_id
               AND r.subject_ref = jsonb_build_object('type', 'decision_card', 'id', NEW.id::text)
               AND r.from_user_id IS NOT DISTINCT FROM OLD.reserved_user_id
               AND r.to_user_id = NEW.reserved_user_id
               AND r.actor_id = v_actor
               AND r.created_at = now()
        ) THEN
            RAISE EXCEPTION 'a card is reassigned only with its reassignment, written now'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""  # noqa: S608 -- fixed SQL, no input


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE human_gates
            ADD COLUMN subkind text NULL CHECK (subkind ~ {_CODE}),
            ADD COLUMN office_id uuid NULL,
            ADD COLUMN blocked boolean NOT NULL DEFAULT false,
            ADD COLUMN blocked_reason_code text NULL CHECK (blocked_reason_code ~ {_CODE}),
            ADD COLUMN sort_hint integer NULL,
            ADD CONSTRAINT human_gates_blocked_reason
                CHECK (blocked_reason_code IS NULL OR blocked)
        """
    )
    # The backfill reads every firm's rows: forced row-level security binds the owner too, so it
    # is lifted for this statement only and forced again (0180's precedent).
    op.execute("ALTER TABLE human_gates NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE human_gates SET subkind = subject_ref ->> 'type' WHERE subkind IS NULL")
    op.execute("ALTER TABLE human_gates FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE human_gates ALTER COLUMN subkind SET NOT NULL")
    op.execute("ALTER TABLE human_gates DROP CONSTRAINT human_gates_kind_check")
    op.execute(
        f"ALTER TABLE human_gates ADD CONSTRAINT human_gates_kind_check CHECK (kind IN ({_KINDS}))"
    )
    op.execute(
        "CREATE INDEX human_gates_by_role ON human_gates (tenant_id, role, engagement_id, state)"
    )
    op.execute(
        "ALTER TABLE human_gates ADD CONSTRAINT human_gates_tenant_id UNIQUE (tenant_id, id)"
    )
    insert_columns(
        op,
        "human_gates",
        (
            "tenant_id",
            "kind",
            "subject_ref",
            "engagement_id",
            "work_item_id",
            "client_id",
            "assignee_user_id",
            "role",
            "due_on",
            "state",
            "source_event_id",
            "subkind",
            "office_id",
            "blocked",
            "blocked_reason_code",
            "sort_hint",
        ),
    )
    op.execute(
        "GRANT UPDATE (office_id, blocked, blocked_reason_code, sort_hint) "
        "ON human_gates TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE human_gate_snoozes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            gate_id uuid NOT NULL,
            user_id uuid NOT NULL,
            until timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            -- ADR-005: only a person snoozes, and only for themselves (the trigger).
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 200),
            -- A snooze is at most 30 days long (I-01 OQ-4 bounds it by the due date too, in
            -- the route); an unsnooze is a row whose `until` is now.
            CONSTRAINT human_gate_snoozes_bounded
                CHECK (until <= created_at + interval '30 days'),
            FOREIGN KEY (tenant_id, gate_id) REFERENCES human_gates (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX human_gate_snoozes_latest "
        "ON human_gate_snoozes (tenant_id, gate_id, user_id, created_at DESC, id DESC)"
    )
    op.execute(
        """
        CREATE TABLE human_gate_reassignments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            gate_id uuid NOT NULL,
            subject_ref jsonb NOT NULL CHECK (jsonb_typeof(subject_ref) = 'object'),
            from_user_id uuid NULL,
            to_user_id uuid NOT NULL,
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z_]{0,39}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            -- ADR-005: only a person reassigns (the trigger binds it to the session's).
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 200),
            CONSTRAINT human_gate_reassignments_moves
                CHECK (from_user_id IS DISTINCT FROM to_user_id),
            FOREIGN KEY (tenant_id, gate_id) REFERENCES human_gates (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX human_gate_reassignments_gate "
        "ON human_gate_reassignments (tenant_id, gate_id, created_at)"
    )
    op.execute(_ACTOR_GUARD)
    op.execute(_IMMUTABLE)
    for table, columns in (
        ("human_gate_snoozes", ("tenant_id", "gate_id", "user_id", "until")),
        (
            "human_gate_reassignments",
            ("tenant_id", "gate_id", "subject_ref", "from_user_id", "to_user_id", "reason_code"),
        ),
    ):
        tenant_table(op, table)
        insert_only(op, table)
        insert_columns(op, table, (*columns, "actor_kind", "actor_id"))
        op.execute(
            f"CREATE TRIGGER {table}_by_a_person BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION human_gate_acts_by_a_person()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION human_gate_acts_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION human_gate_acts_immutable()"
        )

    op.execute("GRANT UPDATE (reserved_user_id) ON decision_cards TO abacus_app")
    op.execute(_REASSIGN_GUARD)
    op.execute(
        "CREATE TRIGGER decision_cards_reassign_guard BEFORE UPDATE OF reserved_user_id "
        "ON decision_cards FOR EACH ROW EXECUTE FUNCTION decision_cards_reassign_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER decision_cards_reassign_guard ON decision_cards")
    op.execute("DROP FUNCTION decision_cards_reassign_guard()")
    op.execute("REVOKE UPDATE (reserved_user_id) ON decision_cards FROM abacus_app")
    op.execute("DROP TABLE human_gate_reassignments")
    op.execute("DROP TABLE human_gate_snoozes")
    op.execute("DROP FUNCTION human_gate_acts_immutable()")
    op.execute("DROP FUNCTION human_gate_acts_by_a_person()")
    op.execute(
        "REVOKE UPDATE (office_id, blocked, blocked_reason_code, sort_hint) "
        "ON human_gates FROM abacus_app"
    )
    op.execute("ALTER TABLE human_gates DROP CONSTRAINT human_gates_tenant_id")
    op.execute("DROP INDEX human_gates_by_role")
    op.execute("ALTER TABLE human_gates NO FORCE ROW LEVEL SECURITY")
    op.execute("DELETE FROM human_gates WHERE kind = 'evidence_review'")
    op.execute("ALTER TABLE human_gates FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE human_gates DROP CONSTRAINT human_gates_kind_check")
    op.execute(
        f"ALTER TABLE human_gates ADD CONSTRAINT human_gates_kind_check "
        f"CHECK (kind IN ({_KINDS_0093}))"
    )
    op.execute(
        "ALTER TABLE human_gates DROP CONSTRAINT human_gates_blocked_reason, "
        "DROP COLUMN sort_hint, DROP COLUMN blocked_reason_code, DROP COLUMN blocked, "
        "DROP COLUMN office_id, DROP COLUMN subkind"
    )
    # 0093's insert grant (the columns just dropped took theirs with them).
    insert_columns(
        op,
        "human_gates",
        (
            "tenant_id",
            "kind",
            "subject_ref",
            "engagement_id",
            "work_item_id",
            "client_id",
            "assignee_user_id",
            "role",
            "due_on",
            "state",
            "source_event_id",
        ),
    )
