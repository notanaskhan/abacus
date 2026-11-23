"""K-03-T12 (S53; TASK-8902; SPEC-720 §4; ADR-213; K-03 §4.2; amber): template links, rollouts,
updates and scoping evaluations (engagements, methodology, requests). Expand-only.

- `engagement_template_links` (one per engagement; state current · update_available · updated ·
  held, a hold carries its reason) and insert-only `template_link_events`.
- `template_rollouts` and `template_rollout_actions` (Hold and On rollover need a reason: CHECK).
- `template_updates` and `template_update_changes` (idempotent on `(update_id, change_key)`).
- Insert-only `scoping_evaluations`; `request_items.shown_by_rule_id` (requests).
- Backfill: every engagement with a pinned methodology version gets one link in state `current`
  on the wrapper 1010 made for that version, and one `pinned` event. The legacy column
  `engagements.methodology_version_id` is untouched (the service keeps it equal to the link's
  methodology component).

The backfill runs before `tenant_table` attaches `archived_guard`, so an archived engagement's
link is written once here and never again.

Revision ID: 1011
Revises: 1010
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1011"
down_revision = "1010"
branch_labels = None
depends_on = None

_PERSON = "FOREIGN KEY (tenant_id, {col}) REFERENCES memberships (tenant_id, user_id)"


def _person(col: str) -> str:
    return _PERSON.format(col=col)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE engagement_template_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            template_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            state text NOT NULL DEFAULT 'current'
                CHECK (state IN ('current', 'update_available', 'updated', 'held')),
            held_reason text NULL CHECK (length(btrim(held_reason)) BETWEEN 1 AND 500),
            held_by uuid NULL,
            held_at timestamptz NULL,
            pinned_at timestamptz NOT NULL DEFAULT abacus_now(),
            updated_from_version_id uuid NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, template_id) REFERENCES engagement_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, updated_from_version_id)
                REFERENCES template_versions (tenant_id, id),
            {_person("held_by")},
            CONSTRAINT engagement_template_links_held CHECK (
                (state = 'held') = (held_reason IS NOT NULL AND held_by IS NOT NULL
                                    AND held_at IS NOT NULL)),
            CONSTRAINT engagement_template_links_updated CHECK (
                state <> 'updated' OR updated_from_version_id IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_template_links_by_version ON engagement_template_links "
        "(tenant_id, template_version_id, state)"
    )
    op.execute(
        f"""
        CREATE TABLE template_link_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            seq bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            link_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('pinned', 'update_available', 'updated', 'held',
                                                'hold_released')),
            template_version_id uuid NOT NULL,
            reason text NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
            actor_user_id uuid NULL,
            actor_kind text NOT NULL DEFAULT coalesce(
                nullif(current_setting('app.actor_kind', true), ''), 'system')
                CHECK (actor_kind IN ('human', 'agent', 'system')),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            FOREIGN KEY (tenant_id, link_id) REFERENCES engagement_template_links (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES template_versions (tenant_id, id),
            {_person("actor_user_id")},
            CHECK (kind NOT IN ('held', 'hold_released') OR (reason IS NOT NULL
                                                             AND actor_user_id IS NOT NULL)),
            CONSTRAINT template_link_events_own_actor CHECK (
                actor_user_id IS NULL
                OR actor_user_id::text = current_setting('app.actor_id', true))
        )
        """
    )
    op.execute(
        "CREATE INDEX template_link_events_by_link ON template_link_events "
        "(tenant_id, link_id, seq)"
    )
    _backfill()

    op.execute(
        f"""
        CREATE TABLE template_rollouts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            from_version_id uuid NOT NULL,
            to_version_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'in_progress', 'complete')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            started_by uuid NULL,
            started_at timestamptz NULL,
            completed_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, from_version_id, to_version_id),
            FOREIGN KEY (tenant_id, template_id) REFERENCES engagement_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, from_version_id) REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, to_version_id) REFERENCES template_versions (tenant_id, id),
            {_person("created_by")},
            {_person("started_by")},
            CHECK (from_version_id <> to_version_id),
            CHECK (status = 'not_started' OR (started_by IS NOT NULL AND started_at IS NOT NULL)),
            CHECK (status <> 'complete' OR completed_at IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE template_rollout_actions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            rollout_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            suggested_action text NULL
                CHECK (suggested_action IN ('update_now', 'on_rollover', 'hold')),
            action text NULL CHECK (action IN ('update_now', 'on_rollover', 'hold')),
            reason text NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
            set_by uuid NULL,
            set_at timestamptz NULL,
            manager_notified_user_id uuid NULL,
            notified_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, rollout_id, engagement_id),
            FOREIGN KEY (tenant_id, rollout_id) REFERENCES template_rollouts (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            {_person("set_by")},
            {_person("manager_notified_user_id")},
            CONSTRAINT template_rollout_actions_reason CHECK (
                action IS NULL OR action = 'update_now' OR reason IS NOT NULL),
            CHECK (action IS NULL OR (set_by IS NOT NULL AND set_at IS NOT NULL)),
            CHECK (notified_at IS NULL OR manager_notified_user_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE template_updates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            from_version_id uuid NOT NULL,
            to_version_id uuid NOT NULL,
            workflow_id text NOT NULL CHECK (length(workflow_id) BETWEEN 1 AND 300),
            status text NOT NULL DEFAULT 'applying'
                CHECK (status IN ('applying', 'applied', 'failed')),
            change_list jsonb NOT NULL CHECK (jsonb_typeof(change_list) = 'array'),
            change_count integer NOT NULL CHECK (change_count >= 0),
            applied_count integer NOT NULL DEFAULT 0 CHECK (applied_count >= 0),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z0-9_]{0, 59}$'),
            started_by uuid NOT NULL,
            started_at timestamptz NOT NULL DEFAULT abacus_now(),
            applied_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, workflow_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, from_version_id) REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, to_version_id) REFERENCES template_versions (tenant_id, id),
            {_person("started_by")},
            CHECK (from_version_id <> to_version_id),
            CHECK (applied_count <= change_count),
            CHECK (status <> 'applied' OR applied_at IS NOT NULL),
            CHECK (status <> 'failed' OR failure_code IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX template_updates_one_applying ON template_updates "
        "(tenant_id, engagement_id) WHERE status = 'applying'"
    )
    op.execute(
        """
        CREATE TABLE template_update_changes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            update_id uuid NOT NULL,
            change_key text NOT NULL CHECK (length(change_key) BETWEEN 1 AND 200),
            kind text NOT NULL CHECK (kind IN ('added', 'changed', 'removed')),
            component text NOT NULL CHECK (component IN (
                'program', 'sheets', 'forms', 'request_list', 'triggers', 'report_templates',
                'skills', 'scoping_rules')),
            item_ref text NOT NULL CHECK (length(item_ref) BETWEEN 1 AND 200),
            effect_here text NULL CHECK (length(effect_here) <= 500),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN (
                'pending', 'applied', 'kept_signed_off', 'kept_team_value', 'recorded')),
            applied_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, update_id, change_key),
            FOREIGN KEY (tenant_id, update_id) REFERENCES template_updates (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            CHECK (status = 'pending' OR applied_at IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE scoping_evaluations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            rule_id uuid NOT NULL,
            result text NOT NULL CHECK (result IN ('shows', 'hides', 'no_change', 'no_answer')),
            inputs_hash char(64) NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            evaluated_at timestamptz NOT NULL DEFAULT abacus_now(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, rule_id) REFERENCES scoping_rules (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX scoping_evaluations_latest ON scoping_evaluations "
        "(tenant_id, engagement_id, rule_id, evaluated_at DESC)"
    )
    op.execute(
        "ALTER TABLE request_items ADD COLUMN shown_by_rule_id uuid NULL, "
        "ADD CONSTRAINT request_items_shown_by_rule_fkey "
        "FOREIGN KEY (tenant_id, shown_by_rule_id) REFERENCES scoping_rules (tenant_id, id)"
    )
    op.execute("GRANT INSERT (shown_by_rule_id), UPDATE (shown_by_rule_id) ON request_items "
               "TO abacus_app")  # fmt: skip

    # Grants (after the backfill, which ran as the owner).
    tenant_table(op, "engagement_template_links")
    insert_columns(
        op, "engagement_template_links",
        ("id", "tenant_id", "engagement_id", "template_id", "template_version_id", "state"),
    )  # fmt: skip
    op.execute("REVOKE UPDATE, DELETE ON engagement_template_links FROM abacus_app")
    op.execute(
        "GRANT UPDATE (template_id, template_version_id, state, held_reason, held_by, held_at, "
        "pinned_at, updated_from_version_id, row_version) ON engagement_template_links "
        "TO abacus_app"
    )
    for table, columns in (
        ("template_link_events",
         ("tenant_id", "engagement_id", "link_id", "kind", "template_version_id", "reason",
          "actor_user_id", "actor_kind")),
        ("scoping_evaluations",
         ("tenant_id", "engagement_id", "template_version_id", "rule_id", "result",
          "inputs_hash")),
    ):  # fmt: skip
        tenant_table(op, table)
        insert_columns(op, table, columns)
        insert_only(op, table)
    for table, inserts, updates in (
        ("template_rollouts",
         ("id", "tenant_id", "template_id", "from_version_id", "to_version_id", "created_by"),
         ("status", "started_by", "started_at", "completed_at")),
        ("template_rollout_actions",
         ("id", "tenant_id", "rollout_id", "engagement_id", "suggested_action"),
         ("suggested_action", "action", "reason", "set_by", "set_at",
          "manager_notified_user_id", "notified_at", "row_version")),
        ("template_updates",
         ("id", "tenant_id", "engagement_id", "from_version_id", "to_version_id", "workflow_id",
          "change_list", "change_count", "started_by"),
         ("status", "applied_count", "failure_code", "applied_at")),
        ("template_update_changes",
         ("tenant_id", "engagement_id", "update_id", "change_key", "kind", "component",
          "item_ref", "effect_here"),
         ("status", "applied_at")),
    ):  # fmt: skip
        tenant_table(op, table)
        insert_columns(op, table, inserts)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")


def _backfill() -> None:
    """One `current` link and one `pinned` event per engagement with a pinned methodology
    version, on that version's 1010 wrapper. Owner-run with RLS unforced on the sources."""
    sources = ("engagements", "template_versions")
    for table in sources:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        INSERT INTO engagement_template_links (tenant_id, engagement_id, template_id,
                                               template_version_id, state, pinned_at)
        SELECT e.tenant_id, e.id, w.template_id, w.id, 'current', e.created_at
          FROM engagements e
          JOIN LATERAL (
                SELECT tv.id, tv.template_id FROM template_versions tv
                 WHERE tv.tenant_id = e.tenant_id
                   AND tv.methodology_version_id = e.methodology_version_id
                 ORDER BY tv.seq LIMIT 1) w ON true
         WHERE e.methodology_version_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO template_link_events (tenant_id, engagement_id, link_id, kind,
                                          template_version_id, actor_kind, at)
        SELECT l.tenant_id, l.engagement_id, l.id, 'pinned', l.template_version_id, 'system',
               l.pinned_at
          FROM engagement_template_links l
        """
    )
    for table in sources:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE request_items DROP COLUMN shown_by_rule_id")
    for table in ("scoping_evaluations", "template_update_changes", "template_updates",
                  "template_rollout_actions", "template_rollouts", "template_link_events",
                  "engagement_template_links"):  # fmt: skip
        op.execute(f"DROP TABLE {table}")
