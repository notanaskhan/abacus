"""A-09-T05 (S45; TASK-8055; ADR-341, P-63; SPEC-658 AC-0.4, AC-1.1, AC-1.3; red): ledger
consolidation, expand-only.

- `consolidations` (ledger, tenant, forced RLS): one group consolidation of an engagement's
  assurance work item: name, year end, reporting currency (USD only, X-06), interim and prior
  period ends, an optional covering connection, `status` draft · finalized · discarded,
  `lock_state` open · locked, who finalized and locked (a person: `finalized_actor_kind` and
  `locked_actor_kind` are `human`), `row_version`.
- `consolidation_entities`: the structure. `level` 1 to 3 (a fourth tier is refused), level 1 has
  no parent and every other level has one, the parent sits one level up in the same
  consolidation, `ownership_pct` is exactly 100 (no NCI, X-06), the entity is one of the
  engagement's `engagement_entities`, and once the consolidation is finalized the structure is
  frozen (no insert, update or delete).
- `consolidation_trial_balances`: each entity's TB slot per label and period kind, `state`
  missing · attached · not_needed · needs_reauth; an attached slot names its immutable ledger
  snapshot, a not-needed one its reason; a replaced slot points at its successor, and only one
  slot per entity, label and period kind is current.
- `consolidation_events` (insert-only): finalized · locked · reopened, each a person's
  (`actor_kind = 'human'`), a reopen with its reason.

Revision ID: 0889
Revises: 0888
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0889"
down_revision = "0888"
branch_labels = None
depends_on = None

_LABELS = "'standard', 'interim', 'prior', 'budget', 'preliminary'"
_TABLES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "consolidations",
        (
            *("id", "tenant_id", "engagement_id", "work_item_id", "name", "year_end"),
            *("reporting_currency", "interim_period_end", "prior_period_end"),
            *("source_connection_id", "created_by"),
        ),
        (
            *("name", "year_end", "interim_period_end", "prior_period_end"),
            *("source_connection_id", "status", "lock_state", "finalized_by", "finalized_at"),
            *("finalized_actor_kind", "locked_by", "locked_at", "locked_actor_kind"),
            "row_version",
        ),
    ),
    (
        "consolidation_entities",
        (
            *("id", "tenant_id", "consolidation_id", "client_entity_id", "parent_id", "level"),
            *("ownership_pct", "city", "component_auditor_id", "position"),
        ),
        ("parent_id", "level", "city", "component_auditor_id", "position"),
    ),
    (
        "consolidation_trial_balances",
        (
            *("id", "tenant_id", "consolidation_entity_id", "label", "period_kind"),
            *("period_start", "period_end", "ledger_snapshot_id", "state", "source"),
            *("evidence_version_id", "not_needed_reason", "attached_by"),
        ),
        ("superseded_by",),
    ),
    (
        "consolidation_events",
        (*("tenant_id", "consolidation_id", "kind", "reason", "actor_kind", "actor_id"),),
        (),
    ),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE consolidations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            year_end date NOT NULL,
            reporting_currency text NOT NULL CHECK (reporting_currency = 'USD'),
            interim_period_end date NULL,
            prior_period_end date NULL,
            source_connection_id uuid NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'finalized', 'discarded')),
            lock_state text NOT NULL DEFAULT 'open' CHECK (lock_state IN ('open', 'locked')),
            finalized_by uuid NULL,
            finalized_at timestamptz NULL,
            finalized_actor_kind text NULL CHECK (finalized_actor_kind = 'human'),
            locked_by uuid NULL,
            locked_at timestamptz NULL,
            locked_actor_kind text NULL CHECK (locked_actor_kind = 'human'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            UNIQUE (tenant_id, id),
            CONSTRAINT consolidations_finalized CHECK (
                (status = 'finalized') = (finalized_by IS NOT NULL AND finalized_at IS NOT NULL
                    AND finalized_actor_kind = 'human')
            ),
            CONSTRAINT consolidations_locked CHECK (
                (lock_state = 'locked') = (locked_by IS NOT NULL AND locked_at IS NOT NULL
                    AND locked_actor_kind = 'human')
            ),
            CONSTRAINT consolidations_lock_after_finalize
                CHECK (lock_state = 'open' OR status = 'finalized'),
            CONSTRAINT consolidations_periods CHECK (
                (interim_period_end IS NULL OR interim_period_end <= year_end)
                AND (prior_period_end IS NULL OR prior_period_end < year_end)
            ),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE consolidation_entities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            consolidation_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            parent_id uuid NULL,
            level smallint NOT NULL CHECK (level BETWEEN 1 AND 3),
            ownership_pct numeric(9, 6) NOT NULL DEFAULT 100 CHECK (ownership_pct = 100),
            city text NULL CHECK (length(city) <= 120),
            component_auditor_id uuid NULL,
            position smallint NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, consolidation_id, client_entity_id),
            CONSTRAINT consolidation_entities_root CHECK ((level = 1) = (parent_id IS NULL)),
            CONSTRAINT consolidation_entities_not_self CHECK (parent_id IS DISTINCT FROM id),
            FOREIGN KEY (tenant_id, consolidation_id) REFERENCES consolidations (tenant_id, id),
            FOREIGN KEY (tenant_id, parent_id) REFERENCES consolidation_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE consolidation_trial_balances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            consolidation_entity_id uuid NOT NULL,
            label text NOT NULL CHECK (label IN ({_LABELS})),
            period_kind text NOT NULL CHECK (period_kind IN ('current', 'prior')),
            period_start date NOT NULL,
            period_end date NOT NULL,
            ledger_snapshot_id uuid NULL,
            state text NOT NULL
                CHECK (state IN ('missing', 'attached', 'not_needed', 'needs_reauth')),
            source text NULL CHECK (source IN ('upload', 'evidence', 'connection')),
            evidence_version_id uuid NULL,
            not_needed_reason text NULL CHECK (length(btrim(not_needed_reason)) BETWEEN 1 AND 500),
            superseded_by uuid NULL,
            attached_by uuid NULL,
            attached_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT consolidation_tbs_period CHECK (period_end >= period_start),
            CONSTRAINT consolidation_tbs_attached
                CHECK ((state = 'attached') = (ledger_snapshot_id IS NOT NULL)),
            CONSTRAINT consolidation_tbs_not_needed
                CHECK ((state = 'not_needed') = (not_needed_reason IS NOT NULL)),
            CONSTRAINT consolidation_tbs_not_self CHECK (superseded_by IS DISTINCT FROM id),
            FOREIGN KEY (tenant_id, consolidation_entity_id)
                REFERENCES consolidation_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, superseded_by)
                REFERENCES consolidation_trial_balances (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX consolidation_tbs_current ON consolidation_trial_balances "
        "(tenant_id, consolidation_entity_id, label, period_kind) WHERE superseded_by IS NULL"
    )
    op.execute(
        """
        CREATE TABLE consolidation_events (
            id bigserial PRIMARY KEY,
            tenant_id uuid NOT NULL,
            consolidation_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('finalized', 'locked', 'reopened')),
            reason text NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            actor_id uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT consolidation_events_reopen_reason
                CHECK (kind <> 'reopened' OR reason IS NOT NULL),
            FOREIGN KEY (tenant_id, consolidation_id) REFERENCES consolidations (tenant_id, id)
        )
        """
    )
    for index in (
        "consolidations (tenant_id, work_item_id)",
        "consolidation_entities (tenant_id, consolidation_id, position)",
        "consolidation_events (tenant_id, consolidation_id, at)",
    ):
        op.execute(f"CREATE INDEX {index.split(' (')[0]}_lookup ON {index}")

    # The structure: the entity belongs to the engagement, its parent sits one level up in the
    # same consolidation, and nothing changes once the consolidation is finalized.
    op.execute(
        """
        CREATE FUNCTION consolidation_entity_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_row consolidation_entities := COALESCE(NEW, OLD);
            v_status text;
            v_engagement uuid;
            v_parent_level smallint;
            v_parent_consolidation uuid;
        BEGIN
            SELECT c.status, c.engagement_id INTO v_status, v_engagement
              FROM consolidations c
             WHERE c.tenant_id = v_row.tenant_id AND c.id = v_row.consolidation_id;
            IF v_status IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'the structure is frozen once the consolidation is finalized'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM engagement_entities e
                 WHERE e.tenant_id = NEW.tenant_id AND e.engagement_id = v_engagement
                   AND e.client_entity_id = NEW.client_entity_id
            ) THEN
                RAISE EXCEPTION 'the entity is not one of the engagement''s entities'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.parent_id IS NOT NULL THEN
                SELECT p.level, p.consolidation_id INTO v_parent_level, v_parent_consolidation
                  FROM consolidation_entities p
                 WHERE p.tenant_id = NEW.tenant_id AND p.id = NEW.parent_id;
                IF v_parent_consolidation IS DISTINCT FROM NEW.consolidation_id
                   OR v_parent_level IS DISTINCT FROM NEW.level - 1 THEN
                    RAISE EXCEPTION 'the parent must sit one level up in the same consolidation'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER consolidation_entities_guard BEFORE INSERT OR UPDATE OR DELETE "
        "ON consolidation_entities FOR EACH ROW EXECUTE FUNCTION consolidation_entity_guard()"
    )
    # A finalized (or discarded) consolidation never goes back to draft, and a discarded one
    # never changes again.
    op.execute(
        """
        CREATE FUNCTION consolidation_status_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.status = 'discarded' THEN
                RAISE EXCEPTION 'a discarded consolidation does not change'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'finalized' AND NEW.status <> 'finalized' THEN
                RAISE EXCEPTION 'a finalized consolidation stays finalized'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'finalized' AND (
                NEW.year_end IS DISTINCT FROM OLD.year_end
                OR NEW.reporting_currency IS DISTINCT FROM OLD.reporting_currency
                OR NEW.finalized_by IS DISTINCT FROM OLD.finalized_by
                OR NEW.finalized_at IS DISTINCT FROM OLD.finalized_at
            ) THEN
                RAISE EXCEPTION 'a finalized consolidation''s facts are fixed'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER consolidations_status_forward BEFORE UPDATE ON consolidations "
        "FOR EACH ROW EXECUTE FUNCTION consolidation_status_forward()"
    )

    for table, inserts, updates in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, inserts)
        if updates:
            op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
        else:
            insert_only(op, table)
    # Draft structure rows may be removed while the consolidation is a draft (the guard refuses
    # it afterwards); nothing else is ever deleted.
    op.execute("GRANT DELETE ON consolidation_entities TO abacus_app")
    op.execute("GRANT USAGE ON SEQUENCE consolidation_events_id_seq TO abacus_app")


def downgrade() -> None:
    for table in (
        "consolidation_events",
        "consolidation_trial_balances",
        "consolidation_entities",
        "consolidations",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION consolidation_status_forward()")
    op.execute("DROP FUNCTION consolidation_entity_guard()")
