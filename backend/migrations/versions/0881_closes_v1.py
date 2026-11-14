"""C-01-T09 (S44; TASK-8009; C-01 §4.2 T09; SPEC-655 AC-9 to AC-22, AC-28): `closes_v1`,
expand-only over F-03's `closes` subtype (0089).

- `closes` gains its lifecycle: the six canonical states (DF-23; no "Closed"), the On hold side
  flag with its required reason, the pinned plan version (set once: a trigger refuses a change
  after `plan_pinned_at`, QC-2), BD1 and due dates, the run counter, `locked_at` and
  `row_version`. The app may now update exactly those columns; existing rows read `not_started`
  (the default), so no row is rewritten.
- `close_plans` (one per client entity), `close_plan_versions` (one draft per plan by a partial
  unique index; publishing is a named human's, `published_actor_kind = 'human'`; a trigger freezes
  published and discarded versions and refuses to publish while a drafted row nobody adopted
  remains, `unadopted_rows`), `close_plan_rows` and `close_request_templates` (frozen with their
  version), `close_templates` (DB content imported through `POST /v1/close-templates:import`;
  insert-only) and the `close_procedures` projection (one row per step attempt; a retry is a new
  row; its status only moves forward).
- Forced RLS on every table through `tenant_table()`. Classification (ADR-031): plan rows name
  client accounts (`confidential`); no TRI.

The retention record type `cas_workpaper` (7 years from period end) is a published floor-set row
(Q-02-T23's staff floor routes), content rather than schema, so it is not written here.

Revision ID: 0881
Revises: 0880
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0881"
down_revision = "0880"
branch_labels = None
depends_on = None

_PERIOD = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
_STATUSES = "('not_started', 'in_progress', 'in_review', 'approved', 'delivered', 'locked')"
_PROCEDURES = (
    "('reconciliation', 'aging', 'clear_and_age', 'third_party_sales', 'rollforward', "
    "'amortization', 'depreciation', 'aging_cutoff', 'accrual', 'tie_to_return', "
    "'tie_to_filings', 'recategorize', 'flux')"
)
_SOURCES = "('bank_feed', 'client_upload', 'quickbooks_online', 'files', 'accrued_register')"
_CLOSE_UPDATES = (
    "client_entity_id", "status", "on_hold", "on_hold_reason", "close_plan_version_id",
    "plan_pinned_at", "requests_publish_on", "due_on", "run_no", "locked_at", "row_version",
)  # fmt: skip


def _lock_down(table: str, inserts: tuple[str, ...], updates: tuple[str, ...] = ()) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, table, inserts)
    if updates:
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    else:
        insert_only(op, table)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE close_plans (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            template_key text NULL CHECK (template_key ~ '^[a-z][a-z0-9_-]{0,63}$'),
            close_due_business_day integer NOT NULL DEFAULT 7
                CHECK (close_due_business_day BETWEEN 1 AND 20),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE close_plan_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            plan_id uuid NOT NULL,
            version integer NOT NULL CHECK (version > 0),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'discarded')),
            effective_from text NULL CHECK (effective_from {_PERIOD}),
            change_note text NULL CHECK (length(change_note) <= 500),
            drafted_by uuid NOT NULL,
            drafted_by_run_id uuid NULL,
            publish_requested_by uuid NULL,
            publish_requested_at timestamptz NULL,
            published_by uuid NULL,
            published_actor_kind text NULL CHECK (published_actor_kind = 'human'),
            published_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (plan_id, version),
            CHECK (status <> 'published' OR (effective_from IS NOT NULL
                AND published_by IS NOT NULL AND published_actor_kind = 'human'
                AND published_at IS NOT NULL)),
            CHECK ((publish_requested_by IS NULL) = (publish_requested_at IS NULL)),
            FOREIGN KEY (tenant_id, plan_id) REFERENCES close_plans (tenant_id, id),
            FOREIGN KEY (tenant_id, drafted_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, drafted_by_run_id) REFERENCES agent_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, publish_requested_by)
                REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, published_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX close_plan_versions_one_draft ON close_plan_versions (plan_id) "
        "WHERE status = 'draft'"
    )
    op.execute(
        f"""
        CREATE TABLE close_plan_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            account_external_id text NULL CHECK (length(account_external_id) <= 64),
            account_name text NOT NULL CHECK (length(account_name) BETWEEN 1 AND 200),
            account_class text NOT NULL CHECK (length(account_class) BETWEEN 1 AND 64),
            procedure text NOT NULL CHECK (procedure IN {_PROCEDURES}),
            method text NOT NULL CHECK (length(method) BETWEEN 1 AND 500),
            evidence_required text NULL CHECK (length(evidence_required) <= 500),
            source text NOT NULL CHECK (source IN {_SOURCES}),
            review_level text NOT NULL
                CHECK (review_level IN ('senior_signoff', 'manager_approval')),
            frequency text NOT NULL DEFAULT 'monthly'
                CHECK (frequency IN ('monthly', 'quarterly', 'annual')),
            threshold_ref jsonb NULL,
            drafted_suggestion_id uuid NULL,
            adopted_by uuid NULL,
            adopted_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (version_id, position),
            CHECK ((adopted_by IS NULL) = (adopted_at IS NULL)),
            FOREIGN KEY (tenant_id, version_id) REFERENCES close_plan_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, adopted_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE close_request_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            category_path text[] NOT NULL DEFAULT '{}',
            due_business_day integer NOT NULL CHECK (due_business_day BETWEEN 1 AND 20),
            client_visible boolean NOT NULL DEFAULT true,
            source_row_ids uuid[] NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, version_id) REFERENCES close_plan_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE close_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z][a-z0-9_-]{0,63}$'),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            version integer NOT NULL CHECK (version > 0),
            rows jsonb NOT NULL CHECK (jsonb_typeof(rows) = 'array'),
            request_templates jsonb NOT NULL CHECK (jsonb_typeof(request_templates) = 'array'),
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, key, version),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE close_procedures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            run_id uuid NOT NULL,
            run_step_id uuid NOT NULL,
            plan_row_id uuid NULL,
            group_key text NOT NULL CHECK (group_key ~ '^[a-z][a-z0-9_]{0,63}$'),
            account_external_id text NULL CHECK (length(account_external_id) <= 64),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'needs_attention', 'done', 'failed')),
            meta text NULL CHECK (length(meta) <= 200),
            open_count integer NOT NULL DEFAULT 0 CHECK (open_count >= 0),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z0-9_]{0,63}$'),
            started_at timestamptz NULL,
            finished_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (run_step_id),
            CHECK (status <> 'failed' OR failure_code IS NOT NULL),
            FOREIGN KEY (close_id) REFERENCES closes (work_item_id),
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, run_step_id) REFERENCES agent_run_steps (tenant_id, id),
            FOREIGN KEY (tenant_id, plan_row_id) REFERENCES close_plan_rows (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX close_procedures_by_close ON close_procedures (close_id, run_id)")

    # The close record's lifecycle, on F-03's subtype (expand-only: defaults, nullable columns).
    op.execute(
        f"""
        ALTER TABLE closes
            ADD COLUMN client_entity_id uuid NULL,
            ADD COLUMN status text NOT NULL DEFAULT 'not_started'
                CONSTRAINT closes_status_check CHECK (status IN {_STATUSES}),
            ADD COLUMN on_hold boolean NOT NULL DEFAULT false,
            ADD COLUMN on_hold_reason text NULL
                CONSTRAINT closes_on_hold_reason_length CHECK (length(on_hold_reason) <= 500),
            ADD COLUMN close_plan_version_id uuid NULL,
            ADD COLUMN plan_pinned_at timestamptz NULL,
            ADD COLUMN requests_publish_on date NULL,
            ADD COLUMN due_on date NULL,
            ADD COLUMN run_no integer NOT NULL DEFAULT 0
                CONSTRAINT closes_run_no_check CHECK (run_no >= 0),
            ADD COLUMN locked_at timestamptz NULL,
            ADD COLUMN row_version integer NOT NULL DEFAULT 1
                CONSTRAINT closes_row_version_check CHECK (row_version > 0),
            ADD CONSTRAINT closes_on_hold_reason
                CHECK (on_hold = (on_hold_reason IS NOT NULL)),
            ADD CONSTRAINT closes_locked_at CHECK (status <> 'locked' OR locked_at IS NOT NULL),
            ADD CONSTRAINT closes_pin CHECK (
                (close_plan_version_id IS NULL) = (plan_pinned_at IS NULL)),
            ADD CONSTRAINT closes_client_entity_fk FOREIGN KEY (tenant_id, client_entity_id)
                REFERENCES client_entities (tenant_id, id),
            ADD CONSTRAINT closes_plan_version_fk FOREIGN KEY (tenant_id, close_plan_version_id)
                REFERENCES close_plan_versions (tenant_id, id)
        """
    )
    op.execute("REVOKE UPDATE ON closes FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_CLOSE_UPDATES)}) ON closes TO abacus_app")
    op.execute(
        "GRANT INSERT (client_entity_id, requests_publish_on, due_on) ON closes TO abacus_app"
    )

    _lock_down(
        "close_plans",
        ("tenant_id", "client_entity_id", "template_key", "close_due_business_day", "created_by"),
        ("template_key", "close_due_business_day"),
    )
    _lock_down(
        "close_plan_versions",
        ("tenant_id", "plan_id", "version", "effective_from", "change_note", "drafted_by",
         "drafted_by_run_id"),
        ("status", "effective_from", "change_note", "publish_requested_by",
         "publish_requested_at", "published_by", "published_actor_kind", "published_at",
         "row_version"),
    )  # fmt: skip
    _lock_down(
        "close_plan_rows",
        ("tenant_id", "version_id", "position", "account_external_id", "account_name",
         "account_class", "procedure", "method", "evidence_required", "source", "review_level",
         "frequency", "threshold_ref", "drafted_suggestion_id"),
        ("position", "account_external_id", "account_name", "account_class", "procedure",
         "method", "evidence_required", "source", "review_level", "frequency", "threshold_ref",
         "adopted_by", "adopted_at"),
    )  # fmt: skip
    _lock_down(
        "close_request_templates",
        ("tenant_id", "version_id", "title", "category_path", "due_business_day",
         "client_visible", "source_row_ids"),
        ("title", "category_path", "due_business_day", "client_visible", "source_row_ids"),
    )  # fmt: skip
    _lock_down(
        "close_templates",
        ("tenant_id", "key", "name", "version", "rows", "request_templates", "imported_by"),
    )
    _lock_down(
        "close_procedures",
        ("tenant_id", "close_id", "run_id", "run_step_id", "plan_row_id", "group_key",
         "account_external_id", "status", "meta", "open_count", "started_at"),
        ("status", "meta", "open_count", "failure_code", "started_at", "finished_at"),
    )  # fmt: skip

    # QC-2: a close's plan version is set once, at BD1 publication, and never changes.
    op.execute(
        """
        CREATE FUNCTION closes_plan_pinned() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.plan_pinned_at IS NOT NULL AND (
                NEW.close_plan_version_id IS DISTINCT FROM OLD.close_plan_version_id
                OR NEW.plan_pinned_at IS DISTINCT FROM OLD.plan_pinned_at) THEN
                RAISE EXCEPTION 'plan_version_pinned' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER closes_plan_pinned BEFORE UPDATE ON closes "
        "FOR EACH ROW EXECUTE FUNCTION closes_plan_pinned()"
    )
    # A published or discarded version never changes; publishing refuses unadopted drafted rows.
    op.execute(
        """
        CREATE FUNCTION close_plan_version_frozen() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'close plan versions are never deleted'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status <> 'draft' THEN
                RAISE EXCEPTION 'plan_version_frozen' USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status = 'published' AND EXISTS (
                SELECT 1 FROM public.close_plan_rows r
                 WHERE r.version_id = NEW.id AND r.drafted_suggestion_id IS NOT NULL
                   AND r.adopted_at IS NULL) THEN
                RAISE EXCEPTION 'unadopted_rows' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER close_plan_version_frozen BEFORE UPDATE OR DELETE ON close_plan_versions "
        "FOR EACH ROW EXECUTE FUNCTION close_plan_version_frozen()"
    )
    # Rows and request templates change only while their version is a draft.
    op.execute(
        """
        CREATE FUNCTION close_plan_child_frozen() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_version uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.version_id
                ELSE NEW.version_id END;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.version_id IS DISTINCT FROM OLD.version_id THEN
                RAISE EXCEPTION 'plan_version_frozen' USING ERRCODE = 'check_violation';
            END IF;
            IF (SELECT v.status FROM public.close_plan_versions v WHERE v.id = v_version)
                    IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'plan_version_frozen' USING ERRCODE = 'check_violation';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    for table in ("close_plan_rows", "close_request_templates"):
        op.execute(
            f"CREATE TRIGGER {table}_frozen BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION close_plan_child_frozen()"
        )
    # A procedure's status only moves forward; a retry is a new row (P-47).
    op.execute(
        """
        CREATE FUNCTION close_procedure_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_old integer := CASE OLD.status WHEN 'queued' THEN 0 WHEN 'running' THEN 1
                WHEN 'needs_attention' THEN 2 ELSE 3 END;
            v_new integer := CASE NEW.status WHEN 'queued' THEN 0 WHEN 'running' THEN 1
                WHEN 'needs_attention' THEN 2 ELSE 3 END;
        BEGIN
            IF OLD.status IN ('done', 'failed') AND NEW.status IS DISTINCT FROM OLD.status THEN
                RAISE EXCEPTION 'close procedure % is final', OLD.id
                    USING ERRCODE = 'check_violation';
            END IF;
            IF v_new < v_old THEN
                RAISE EXCEPTION 'close procedure status moves forward only'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER close_procedure_forward BEFORE UPDATE ON close_procedures "
        "FOR EACH ROW EXECUTE FUNCTION close_procedure_forward()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER closes_plan_pinned ON closes")
    op.execute("DROP FUNCTION closes_plan_pinned()")
    op.execute("REVOKE UPDATE ON closes FROM abacus_app")
    op.execute("REVOKE INSERT ON closes FROM abacus_app")
    op.execute(
        "GRANT INSERT (tenant_id, work_item_id, engagement_id, period) ON closes TO abacus_app"
    )
    op.execute(
        """
        ALTER TABLE closes
            DROP CONSTRAINT closes_plan_version_fk,
            DROP CONSTRAINT closes_client_entity_fk,
            DROP CONSTRAINT closes_pin,
            DROP CONSTRAINT closes_locked_at,
            DROP CONSTRAINT closes_on_hold_reason,
            DROP COLUMN row_version,
            DROP COLUMN locked_at,
            DROP COLUMN run_no,
            DROP COLUMN due_on,
            DROP COLUMN requests_publish_on,
            DROP COLUMN plan_pinned_at,
            DROP COLUMN close_plan_version_id,
            DROP COLUMN on_hold_reason,
            DROP COLUMN on_hold,
            DROP COLUMN status,
            DROP COLUMN client_entity_id
        """
    )
    for table in (
        "close_procedures",
        "close_templates",
        "close_request_templates",
        "close_plan_rows",
        "close_plan_versions",
        "close_plans",
    ):
        op.execute(f"DROP TABLE {table}")
    for function in (
        "close_procedure_forward()",
        "close_plan_child_frozen()",
        "close_plan_version_frozen()",
    ):
        op.execute(f"DROP FUNCTION {function}")
