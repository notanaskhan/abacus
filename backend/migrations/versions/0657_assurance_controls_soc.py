"""A-04 internal control and SOC 1 (A-04-T25; A-04 §4.2, §3.6, §3.7; DEC-2206; expand-only).

Six tables on the audit work item, tenant-scoped with forced RLS:
- `control_activities`: one process per name on the work item, with design, implementation and
  reliance (AUD-09 e); `walkthroughs` (insert-only) records each walkthrough with its evidence.
- `control_exceptions`: the Exceptions sheet's rows (row 2 onward, header row 1) with a
  **proposed** severity only, the disposition, the COSO component, an optional misstatement
  candidate amount and where the row was routed. There is no concluded column: a concluded
  severity is A-06's `deficiencies` record (AC6.3, INV-1).
- `soc_report_evaluations`, `soc_exceptions`, `cuecs`: the SOC 1 evaluation AUD-10 reads; their
  service arrives with A-04-T31.

Status CHECKs are the status vocabulary's codes, frozen here.

Revision ID: 0657
Revises: 0656
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0657"
down_revision = "0656"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_TABLES = (
    "control_activities",
    "walkthroughs",
    "control_exceptions",
    "soc_report_evaluations",
    "soc_exceptions",
    "cuecs",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "control_activities": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "process_name",
        "design",
        "implementation",
        "reliance",
        "service_organization_id",
    ),
    "walkthroughs": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "control_activity_id",
        "performed_on",
        "performed_by_user_id",
        "evidence_version_ids",
    ),
    "control_exceptions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "workpaper_id",
        "sheet_row",
        "matter",
        "description",
        "proposed_severity",
        "proposed_by_kind",
        "proposed_by_user_id",
        "disposition",
        "coso_component",
        "misstatement_candidate_amount",
        "suggestion_id",
        "citation_ids",
        "recorded_by_kind",
    ),
    "soc_report_evaluations": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "service_organization_id",
        "evidence_version_id",
        "service_auditor_name",
        "opinion",
        "report_type",
        "period_start",
        "period_end",
        "report_date",
        "objectives_total",
        "objectives_relevant",
    ),
    "soc_exceptions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "evaluation_id",
        "co_ref",
        "description",
        "impact",
        "impact_rationale",
    ),
    "cuecs": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "evaluation_id",
        "n",
        "text",
        "control_activity_id",
        "evidence_refs",
        "status",
        "page_citation_id",
    ),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "control_activities": (
        "design",
        "implementation",
        "reliance",
        "service_organization_id",
        "row_version",
        "updated_at",
    ),
    "control_exceptions": (
        "matter",
        "description",
        "proposed_severity",
        "proposed_by_kind",
        "proposed_by_user_id",
        "disposition",
        "coso_component",
        "misstatement_candidate_amount",
        "routed_kind",
        "routed_ref",
        "suggestion_id",
        "citation_ids",
        "row_version",
        "updated_at",
    ),
    "soc_report_evaluations": (
        "service_auditor_name",
        "opinion",
        "report_type",
        "period_start",
        "period_end",
        "report_date",
        "objectives_total",
        "objectives_relevant",
        "bridge_letter_request_item_id",
        "bridge_letter_evidence_version_id",
        "gap_days",
        "engine_version",
        "inputs_hash",
        "reliance_state",
        "reliance_card_id",
        "row_version",
        "updated_at",
    ),
    "soc_exceptions": ("impact", "impact_rationale", "routed_ref", "updated_at"),
    "cuecs": (
        "control_activity_id",
        "evidence_refs",
        "status",
        "page_citation_id",
        "updated_at",
    ),
}

_IMMUTABLE = """
    CREATE FUNCTION walkthroughs_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        RAISE EXCEPTION 'walkthroughs are insert-only' USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE control_activities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            process_name text NOT NULL CHECK (char_length(btrim(process_name)) BETWEEN 1 AND 200),
            design text NOT NULL DEFAULT 'not_assessed'
                CHECK (design IN ('effective', 'deficient', 'not_assessed')),
            implementation text NOT NULL DEFAULT 'not_assessed'
                CHECK (implementation IN ('implemented', 'not_implemented', 'not_assessed')),
            reliance text NOT NULL DEFAULT 'none'
                CHECK (reliance IN ('none', 'via_soc1', 'tested')),
            service_organization_id uuid NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, process_name),
            CHECK (reliance <> 'via_soc1' OR service_organization_id IS NOT NULL),
            FOREIGN KEY (tenant_id, service_organization_id)
                REFERENCES service_organizations (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE walkthroughs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            control_activity_id uuid NOT NULL,
            performed_on date NOT NULL,
            performed_by_user_id uuid NOT NULL,
            evidence_version_ids uuid[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(evidence_version_ids) <= 50),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, control_activity_id)
                REFERENCES control_activities (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE INDEX walkthroughs_activity ON walkthroughs "
        "(tenant_id, control_activity_id, performed_on DESC)"
    )
    op.execute(
        f"""
        CREATE TABLE control_exceptions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            workpaper_id uuid NOT NULL,
            sheet_row integer NOT NULL CHECK (sheet_row BETWEEN 2 AND 10000),
            matter text NOT NULL CHECK (char_length(btrim(matter)) BETWEEN 1 AND 200),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 4000),
            proposed_severity text NULL CHECK (proposed_severity IN
                ('deficiency', 'significant_deficiency', 'material_weakness')),
            proposed_by_kind text NULL CHECK (proposed_by_kind IN ('human', 'agent')),
            proposed_by_user_id uuid NULL,
            disposition text NOT NULL DEFAULT 'exception_for_resolution'
                CHECK (disposition IN ('exception_for_resolution', 'proposed')),
            coso_component text NOT NULL CHECK (coso_component IN ('control_environment',
                'risk_assessment', 'control_activities', 'information_communication',
                'monitoring')),
            misstatement_candidate_amount numeric(18,2) NULL,
            routed_kind text NULL CHECK (routed_kind IN ('finding', 'misstatement')),
            routed_ref uuid NULL,
            suggestion_id uuid NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(citation_ids) <= 50),
            recorded_by_kind text NOT NULL DEFAULT 'human'
                CHECK (recorded_by_kind IN ('human', 'agent')),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, workpaper_id, sheet_row),
            CHECK ((routed_kind IS NULL) = (routed_ref IS NULL)),
            CHECK (proposed_severity IS NULL OR proposed_by_kind IS NOT NULL),
            CHECK (proposed_by_kind IS DISTINCT FROM 'human' OR proposed_by_user_id IS NOT NULL),
            CHECK (routed_kind IS DISTINCT FROM 'misstatement'
                OR misstatement_candidate_amount IS NOT NULL),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE soc_report_evaluations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            service_organization_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            service_auditor_name text NULL CHECK (char_length(service_auditor_name) <= 200),
            opinion text NULL CHECK (opinion IN ('unmodified', 'qualified', 'adverse',
                'disclaimer')),
            report_type text NULL CHECK (report_type IN ('type_1', 'type_2')),
            period_start date NULL,
            period_end date NULL,
            report_date date NULL,
            objectives_total integer NULL CHECK (objectives_total >= 0),
            objectives_relevant integer NULL CHECK (objectives_relevant >= 0),
            bridge_letter_request_item_id uuid NULL,
            bridge_letter_evidence_version_id uuid NULL,
            gap_days integer NULL CHECK (gap_days >= 0),
            engine_version text NULL,
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            reliance_state text NOT NULL DEFAULT 'pending'
                CHECK (reliance_state IN ('pending', 'relied', 'not_relied')),
            reliance_card_id uuid NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end),
            CHECK (objectives_relevant IS NULL OR objectives_total IS NULL
                OR objectives_relevant <= objectives_total),
            CHECK (gap_days IS NULL OR (engine_version IS NOT NULL AND inputs_hash IS NOT NULL)),
            FOREIGN KEY (tenant_id, service_organization_id)
                REFERENCES service_organizations (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE soc_exceptions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evaluation_id uuid NOT NULL,
            co_ref text NOT NULL CHECK (char_length(btrim(co_ref)) BETWEEN 1 AND 40),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 4000),
            impact text NULL CHECK (impact IN ('low', 'high')),
            impact_rationale text NULL CHECK (char_length(impact_rationale) <= 2000),
            routed_ref uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, evaluation_id, co_ref),
            FOREIGN KEY (tenant_id, evaluation_id)
                REFERENCES soc_report_evaluations (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE cuecs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evaluation_id uuid NOT NULL,
            n integer NOT NULL CHECK (n BETWEEN 1 AND 500),
            text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 4000),
            control_activity_id uuid NULL,
            evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(evidence_refs) = 'array'),
            status text NOT NULL DEFAULT 'evidence_missing'
                CHECK (status IN ('evidence_missing', 'evidenced')),
            page_citation_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, evaluation_id, n),
            FOREIGN KEY (tenant_id, evaluation_id)
                REFERENCES soc_report_evaluations (tenant_id, id),
            FOREIGN KEY (tenant_id, control_activity_id)
                REFERENCES control_activities (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    insert_only(op, "walkthroughs")
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute(_IMMUTABLE)
    op.execute("REVOKE ALL ON FUNCTION walkthroughs_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER walkthroughs_immutable BEFORE UPDATE OR DELETE ON walkthroughs "
        "FOR EACH ROW EXECUTE FUNCTION walkthroughs_immutable()"
    )
    op.execute(
        "CREATE TRIGGER walkthroughs_no_truncate BEFORE TRUNCATE ON walkthroughs "
        "FOR EACH STATEMENT EXECUTE FUNCTION walkthroughs_immutable()"
    )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION walkthroughs_immutable()")
