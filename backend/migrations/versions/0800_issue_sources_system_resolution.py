"""Issue sources, category paths and the system resolution of a dependency issue (T-04-T23;
TASK-6724; T-04 §3.4 AC-4.2; ISSUE-001; ADR P-07).

A return's issues come from code (a mismatch, a self-check, an engine diagnostic) or from a
dependency the people cannot settle by hand: the Draft K-1 issue resolves only when the final K-1
is released (TAX-06b), as **system**, never by a person.

- `issues.source_kind` (`mismatch`, `self_check`, `engine_diagnostic`, `k1_dependency`, `manual`;
  null for an issue raised before this migration), `issues.category_path` (the queue's grouping,
  `income/k1` and so on: codes joined by `/`, at most four), and `issues.system_resolved_only`
  (default false). Insert-only for the app, like the rest of the issue's identity.
- `issue_events.event` gains `system_resolved`, and a CHECK that only a `system` actor writes it;
  0094's `issue_events_resolution_by_a_person` (resolved, verified, not applicable: a person only)
  is unchanged.
- `issue_events_system_only` (trigger): a `resolved` or `marked_not_applicable` event on an issue
  marked `system_resolved_only` is refused, so the database holds TAX-06b's rule even past the
  service's 409 `system_resolved_only`; and a `system_resolved` event only lands on such an issue.

Expand-only; the downgrade drops the trigger, its function, the constraint and the columns.

Revision ID: 0800
Revises: 0790
"""

from __future__ import annotations

from alembic import op

revision = "0800"
down_revision = "0790"
branch_labels = None
depends_on = None

_EVENTS = (
    "'created', 'assigned', 'status_changed', 'fix_instructions_set', 'sent_to_client', "
    "'explained', 'resolved', 'verified', 'reopened', 'marked_not_applicable', "
    "'system_resolved'"
)
_EVENTS_BEFORE = (
    "'created', 'assigned', 'status_changed', 'fix_instructions_set', 'sent_to_client', "
    "'explained', 'resolved', 'verified', 'reopened', 'marked_not_applicable'"
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE issues
            ADD COLUMN source_kind text NULL CHECK (source_kind IN
                ('mismatch', 'self_check', 'engine_diagnostic', 'k1_dependency', 'manual')),
            ADD COLUMN category_path text NULL
                CHECK (category_path ~ '^[a-z][a-z0-9_]{0,39}(/[a-z][a-z0-9_]{0,39}){0,3}$'),
            ADD COLUMN system_resolved_only boolean NOT NULL DEFAULT false,
            ADD CONSTRAINT issues_system_resolved_dependency
                CHECK (NOT system_resolved_only OR source_kind = 'k1_dependency')
        """
    )
    op.execute(
        "GRANT INSERT (source_kind, category_path, system_resolved_only) ON issues TO abacus_app"
    )
    op.execute("ALTER TABLE issue_events DROP CONSTRAINT issue_events_event_check")
    op.execute(
        f"ALTER TABLE issue_events ADD CONSTRAINT issue_events_event_check "
        f"CHECK (event IN ({_EVENTS}))"
    )
    op.execute(
        "ALTER TABLE issue_events ADD CONSTRAINT issue_events_system_resolved_by_system "
        "CHECK (event <> 'system_resolved' OR actor_kind = 'system')"
    )
    op.execute(
        """
        CREATE FUNCTION issue_events_system_only() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        DECLARE
            only_system boolean;
        BEGIN
            SELECT system_resolved_only INTO only_system FROM issues
                WHERE tenant_id = NEW.tenant_id AND id = NEW.issue_id;
            IF only_system AND NEW.event IN ('resolved', 'marked_not_applicable') THEN
                RAISE EXCEPTION 'issue % resolves only by the system', NEW.issue_id
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.event = 'system_resolved' AND NOT coalesce(only_system, false) THEN
                RAISE EXCEPTION 'issue % is not a system-resolved dependency', NEW.issue_id
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION issue_events_system_only() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER issue_events_system_only BEFORE INSERT ON issue_events "
        "FOR EACH ROW EXECUTE FUNCTION issue_events_system_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER issue_events_system_only ON issue_events")
    op.execute("DROP FUNCTION issue_events_system_only()")
    op.execute(
        "ALTER TABLE issue_events DROP CONSTRAINT issue_events_system_resolved_by_system, "
        "DROP CONSTRAINT issue_events_event_check"
    )
    op.execute(
        f"ALTER TABLE issue_events ADD CONSTRAINT issue_events_event_check "
        f"CHECK (event IN ({_EVENTS_BEFORE}))"
    )
    op.execute(
        "REVOKE INSERT (source_kind, category_path, system_resolved_only) ON issues "
        "FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE issues DROP CONSTRAINT issues_system_resolved_dependency, "
        "DROP COLUMN system_resolved_only, DROP COLUMN category_path, DROP COLUMN source_kind"
    )
