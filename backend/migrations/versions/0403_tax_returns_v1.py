"""Tax returns v1 (T-02-T07; T-02 §4.2 `tax_returns_v1`; SPEC-502 AC-8). Expand only.

- `tax_returns` (F-03-T22, 0089) gains the v1 columns, every one nullable or defaulted: fiscal
  year end, jurisdictions, filing status, the engine link, `status` (the registry's `return`
  codes, default `not_started`), review level, the sync state (written only by T-01 through
  `tax.api.record_sync_state`), the extended and on-hold flags, the pinned BH-TAX-02 and review-
  level versions, the C21 due dates with the rule versions used, prior-year and amended links, and
  a row version. The form CHECK gains `1040x`. The app may now update the v1 columns, never the
  identity columns, and never deletes a return.
- `tax_return_status_events` (forced RLS, insert-only, immutable): every move with its actor.
- `return_engine_summaries` (forced RLS, insert-only; TRI): the engine's figures from an approved
  import only (ADR-231).

Revision ID: 0403
Revises: 0402
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0403"
down_revision = "0402"
branch_labels = None
depends_on = None

_STATUSES = (
    "('not_started', 'gathering', 'preparing', 'prepared', 'in_review', 'action_required', "
    "'approved', 'awaiting_signature', 'filed', 'accepted', 'rejected', 'fixing')"
)
_SYNC = (
    "('not_yet_exported', 'ready_for_export', 'exporting', 'synced', 'out_of_sync', "
    "'import_pending_approval', 'failed')"
)
RETURN_UPDATE = (
    "fiscal_year_end",
    "jurisdictions",
    "filing_status",
    "engine",
    "engine_return_id",
    "status",
    "review_level",
    "sync_status",
    "last_synced_at",
    "extended",
    "on_hold",
    "approval_policy_version_id",
    "review_levels_version_id",
    "original_due_on",
    "extended_due_on",
    "due_rule_version_ids",
    "prior_year_return_id",
    "row_version",
)
_COLUMNS = (
    "fiscal_year_end date NULL",
    "jurisdictions text[] NOT NULL DEFAULT '{}'",
    "filing_status text NULL CHECK (filing_status IN ('single', 'mfj', 'mfs', 'hoh', 'qss'))",
    "engine text NULL CHECK (engine IN ('cch_axcess'))",
    "engine_return_id text NULL CHECK (char_length(engine_return_id) BETWEEN 1 AND 80)",
    f"status text NOT NULL DEFAULT 'not_started' CHECK (status IN {_STATUSES})",
    "review_level text NULL CHECK (review_level IN ('detail', 'manager', 'partner'))",
    f"sync_status text NULL CHECK (sync_status IN {_SYNC})",
    "last_synced_at timestamptz NULL",
    "extended boolean NOT NULL DEFAULT false",
    "on_hold boolean NOT NULL DEFAULT false",
    "approval_policy_version_id uuid NULL",
    "review_levels_version_id uuid NULL",
    "original_due_on date NULL",
    "extended_due_on date NULL",
    "due_rule_version_ids jsonb NOT NULL DEFAULT '[]'::jsonb "
    "CHECK (jsonb_typeof(due_rule_version_ids) = 'array')",
    "prior_year_return_id uuid NULL",
    "amends_return_id uuid NULL",
    "row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1)",
)


def upgrade() -> None:
    op.execute("ALTER TABLE tax_returns DROP CONSTRAINT tax_returns_form_check")
    op.execute(
        "ALTER TABLE tax_returns ADD CONSTRAINT tax_returns_form_check CHECK (form IN ('1040', "
        "'1041', '1065', '1120s', '1120', '990', '706', '709', '1040x'))"
    )
    for column in _COLUMNS:
        op.execute(f"ALTER TABLE tax_returns ADD COLUMN {column}")
    op.execute("CREATE INDEX tax_returns_board ON tax_returns (tenant_id, tax_year, status)")
    op.execute(f"GRANT UPDATE ({', '.join(RETURN_UPDATE)}) ON tax_returns TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE tax_return_status_events (
            id bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            work_item_id uuid NOT NULL REFERENCES tax_returns (work_item_id),
            from_status text NULL CHECK (from_status IN {_STATUSES}),
            to_status text NOT NULL CHECK (to_status IN {_STATUSES}),
            event text NOT NULL CHECK (event ~ '^[a-z][a-z_]{{1,59}}$'),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_id text NOT NULL CHECK (char_length(actor_id) BETWEEN 1 AND 200),
            on_behalf_of uuid NULL,
            reason text NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE return_engine_summaries (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            work_item_id uuid NOT NULL REFERENCES tax_returns (work_item_id),
            import_id uuid NULL,
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 80),
            kind text NOT NULL CHECK (kind IN ('pro_forma', 'working', 'final')),
            lines jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(lines) = 'array'),
            plan_items jsonb NOT NULL DEFAULT '[]'::jsonb,
            carryforwards jsonb NOT NULL DEFAULT '[]'::jsonb,
            prior_year jsonb NOT NULL DEFAULT '{}'::jsonb,
            approved_at timestamptz NOT NULL,
            PRIMARY KEY (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION tax_return_events_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'tax return events are insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in ("tax_return_status_events", "return_engine_summaries"):
        tenant_table(op, table)
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION tax_return_events_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION tax_return_events_immutable()"
        )
    insert_columns(
        op,
        "tax_return_status_events",
        (
            "tenant_id",
            "work_item_id",
            "from_status",
            "to_status",
            "event",
            "actor_kind",
            "actor_id",
            "on_behalf_of",
            "reason",
        ),
    )
    insert_columns(
        op,
        "return_engine_summaries",
        (
            "id",
            "tenant_id",
            "work_item_id",
            "import_id",
            "engine_version",
            "kind",
            "lines",
            "plan_items",
            "carryforwards",
            "prior_year",
            "approved_at",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE return_engine_summaries")
    op.execute("DROP TABLE tax_return_status_events")
    op.execute("DROP FUNCTION tax_return_events_immutable()")
    op.execute(f"REVOKE UPDATE ({', '.join(RETURN_UPDATE)}) ON tax_returns FROM abacus_app")
    op.execute("DROP INDEX tax_returns_board")
    for column in reversed(_COLUMNS):
        op.execute(f"ALTER TABLE tax_returns DROP COLUMN {column.split(' ', 1)[0]}")
    op.execute("ALTER TABLE tax_returns DROP CONSTRAINT tax_returns_form_check")
    op.execute(
        "ALTER TABLE tax_returns ADD CONSTRAINT tax_returns_form_check CHECK (form IN ('1040', "
        "'1041', '1065', '1120s', '1120', '990', '706', '709'))"
    )
