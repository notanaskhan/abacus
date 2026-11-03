"""A-05 M4: EBP contributions (A-05-T26; A-05 §4.2 M4; EBP-04, EBP-07, AUD-27; DEC-2207;
expand-only).

Three tables on the EBP audit's work item, tenant-scoped with forced RLS:
- `ebp_payrolls`: one row per payroll from the imported register, with code's business-day and
  calendar lags against the deposit and its `timely`/`late` result (A-05-T24's engine), each
  value cited.
- `ebp_late_remittances`: **one row per late payroll** (UNIQUE work item and payroll): the
  principal, the dates, the lost earnings and the excise exposure as code computed them, and the
  correction and Form 5330 states. The correction columns move only through events: the app
  role's UPDATE grant covers the computed columns, and the projector's own grant the rest.
- `ebp_late_remittance_events` (insert-only): `found`, `correction_recorded` and `reverted`;
  **a correction is a person's record** (CHECK `actor_kind = 'human'`), never the agent's.

Revision ID: 0658
Revises: 0657
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0658"
down_revision = "0657"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_MONEY = "numeric(18,2)"
_ENGINE = """
            engine_name text NULL,
            engine_version text NULL,
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),"""
_TABLES = ("ebp_payrolls", "ebp_late_remittances", "ebp_late_remittance_events")

_IMMUTABLE = """
    CREATE FUNCTION ebp_late_remittance_events_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        RAISE EXCEPTION 'late-remittance events are insert-only'
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ebp_payrolls (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            import_id uuid NULL,
            pay_date date NOT NULL,
            deferrals_pretax {_MONEY} NOT NULL DEFAULT 0 CHECK (deferrals_pretax >= 0),
            deferrals_roth {_MONEY} NOT NULL DEFAULT 0 CHECK (deferrals_roth >= 0),
            match {_MONEY} NOT NULL DEFAULT 0 CHECK (match >= 0),
            deposit_date date NULL,
            business_day_lag integer NULL CHECK (business_day_lag >= 0),
            calendar_lag integer NULL CHECK (calendar_lag >= 0),
            result text NULL CHECK (result IN ('timely', 'late')),{_ENGINE}
            citation_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(citation_ids) <= 50),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, pay_date),
            CHECK (deposit_date IS NULL OR deposit_date >= pay_date),
            CHECK (result IS NULL OR (business_day_lag IS NOT NULL AND inputs_hash IS NOT NULL)),
            FOREIGN KEY (tenant_id, import_id)
                REFERENCES ebp_source_imports (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_late_remittances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            payroll_id uuid NOT NULL,
            principal {_MONEY} NOT NULL CHECK (principal > 0),
            due_on date NOT NULL,
            deposited_on date NULL,
            business_days_late integer NOT NULL CHECK (business_days_late > 0),
            interest_days integer NULL CHECK (interest_days >= 0),
            rate numeric(7,4) NULL CHECK (rate >= 0),
            rate_ref text NULL CHECK (char_length(rate_ref) <= 120),
            lost_earnings {_MONEY} NULL CHECK (lost_earnings >= 0),
            correction_status text NOT NULL DEFAULT 'found'
                CHECK (correction_status IN ('found', 'pending_vfcp_scc', 'corrected')),
            lost_earnings_deposited_on date NULL,
            scc_notice_on date NULL,
            form_5330_status text NOT NULL DEFAULT 'exposure'
                CHECK (form_5330_status IN ('exposure', 'not_required_pte_2002_51', 'filed')),
            excise_exposure {_MONEY} NULL CHECK (excise_exposure >= 0),
            schedule_h_4a jsonb NULL CHECK (schedule_h_4a IS NULL
                OR jsonb_typeof(schedule_h_4a) = 'object'),
            finding_id uuid NULL,{_ENGINE}
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT ebp_late_remittances_one_per_payroll
                UNIQUE (tenant_id, work_item_id, payroll_id),
            CHECK (lost_earnings IS NULL OR inputs_hash IS NOT NULL),
            CHECK (correction_status <> 'corrected' OR lost_earnings_deposited_on IS NOT NULL),
            FOREIGN KEY (tenant_id, payroll_id) REFERENCES ebp_payrolls (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_late_remittance_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            late_remittance_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('found', 'correction_recorded', 'reverted')),
            payload jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
            evidence_version_ids uuid[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(evidence_version_ids) <= 20),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
            actor_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT ebp_late_remittance_events_human_correction
                CHECK (event <> 'correction_recorded'
                    OR (actor_kind = 'human' AND actor_user_id IS NOT NULL)),
            CHECK (event <> 'reverted' OR actor_kind = 'human'),
            FOREIGN KEY (tenant_id, late_remittance_id)
                REFERENCES ebp_late_remittances (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE INDEX ebp_late_remittance_events_row ON ebp_late_remittance_events "
        "(tenant_id, late_remittance_id, created_at)"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "ebp_payrolls",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "import_id",
            "pay_date",
            "deferrals_pretax",
            "deferrals_roth",
            "match",
            "deposit_date",
            "business_day_lag",
            "calendar_lag",
            "result",
            "engine_name",
            "engine_version",
            "inputs_hash",
            "citation_ids",
        ),
    )
    op.execute("REVOKE UPDATE ON ebp_payrolls FROM abacus_app")
    insert_columns(
        op,
        "ebp_late_remittances",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "payroll_id",
            "principal",
            "due_on",
            "deposited_on",
            "business_days_late",
            "interest_days",
            "rate",
            "rate_ref",
            "lost_earnings",
            "excise_exposure",
            "schedule_h_4a",
            "engine_name",
            "engine_version",
            "inputs_hash",
        ),
    )
    op.execute("REVOKE UPDATE ON ebp_late_remittances FROM abacus_app")
    # Code recomputes these; the correction columns move only through the event projector.
    op.execute(
        "GRANT UPDATE (interest_days, rate, rate_ref, lost_earnings, excise_exposure, "
        "schedule_h_4a, engine_name, engine_version, inputs_hash, finding_id, "
        "correction_status, lost_earnings_deposited_on, scc_notice_on, form_5330_status, "
        "version, updated_at) ON ebp_late_remittances TO abacus_app"
    )
    insert_only(op, "ebp_late_remittance_events")
    insert_columns(
        op,
        "ebp_late_remittance_events",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "late_remittance_id",
            "event",
            "payload",
            "evidence_version_ids",
            "actor_kind",
            "actor_user_id",
        ),
    )
    op.execute(_IMMUTABLE)
    op.execute("REVOKE ALL ON FUNCTION ebp_late_remittance_events_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER ebp_late_remittance_events_immutable BEFORE UPDATE OR DELETE "
        "ON ebp_late_remittance_events FOR EACH ROW "
        "EXECUTE FUNCTION ebp_late_remittance_events_immutable()"
    )
    op.execute(
        "CREATE TRIGGER ebp_late_remittance_events_no_truncate BEFORE TRUNCATE "
        "ON ebp_late_remittance_events FOR EACH STATEMENT "
        "EXECUTE FUNCTION ebp_late_remittance_events_immutable()"
    )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION ebp_late_remittance_events_immutable()")
