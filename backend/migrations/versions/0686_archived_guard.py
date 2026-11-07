"""A-07 M4: DB immutability after lock (A-07-T13; A-07 §4.2 M4; ADR P-43; DEC-71; AUD-25).

`archived_guard()` fires BEFORE INSERT, UPDATE or DELETE on every table with a `work_item_id` or
`engagement_id` column, for every principal. If the row's work item is locked, or its engagement
archived, it raises SQLSTATE `AB409`, message `archived`, unless `app.archived_write` holds a kind
this table's trigger names. Reasoned exemptions and kinds are in `kernel/db/archive_guard.py`.
`tenant_table()` attaches the guard to new tables from here on.

The lock's own final unit of work writes `archives` and the G9 rows before it sets
`work_items.archive_locked_at`, so the guard never blocks the lock. A locked `work_items` row is
itself frozen, and `work_items` reads only its own lock, not its engagement's status.

Revision ID: 0686
Revises: 0685
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.archive_guard import EXEMPT, trigger_arguments

revision = "0686"
down_revision = "0685"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION archived_guard() RETURNS trigger
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_row jsonb;
            v_work_item uuid;
            v_engagement uuid;
            v_locked boolean := false;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_row := to_jsonb(OLD);
            ELSE
                v_row := to_jsonb(NEW);
            END IF;
            IF TG_TABLE_NAME = 'work_items' THEN
                IF TG_OP <> 'INSERT' THEN
                    v_locked := OLD.archive_locked_at IS NOT NULL;
                END IF;
            ELSE
                v_work_item := NULLIF(v_row ->> 'work_item_id', '')::uuid;
                v_engagement := NULLIF(v_row ->> 'engagement_id', '')::uuid;
                IF v_work_item IS NOT NULL THEN
                    SELECT w.archive_locked_at IS NOT NULL INTO v_locked
                      FROM public.work_items w WHERE w.id = v_work_item;
                END IF;
                IF NOT COALESCE(v_locked, false) AND v_engagement IS NOT NULL THEN
                    SELECT e.status = 'archived' INTO v_locked
                      FROM public.engagements e WHERE e.id = v_engagement;
                END IF;
            END IF;
            IF COALESCE(v_locked, false)
               AND NOT (NULLIF(current_setting('app.archived_write', true), '') = ANY(TG_ARGV))
                   IS TRUE THEN
                RAISE EXCEPTION 'archived' USING ERRCODE = 'AB409';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION archived_guard() FROM PUBLIC")
    connection = op.get_bind()
    rows = connection.exec_driver_sql(
        """
        SELECT DISTINCT c.table_name
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
         WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
           AND c.column_name IN ('work_item_id', 'engagement_id')
         ORDER BY c.table_name
        """
    ).fetchall()
    for (table,) in rows:
        if table in EXEMPT:
            continue
        op.execute(
            f"CREATE TRIGGER archived_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION archived_guard({trigger_arguments(table)})"
        )


def downgrade() -> None:
    op.execute("DROP FUNCTION archived_guard() CASCADE")
