"""A-06 `assurance_completion` (A-06-T04; A-06 §4.2; SPEC-642; DEC-1963): expand-only, amber.

A-06's completion records on the audit work item, beside SPEC-043's fieldwork `findings` and
`misstatements` (0064, untouched; DEC-1960). Each table is work-item scoped with forced RLS:

- `audit_findings`: one per P-04 issue (DEC-83: the issue holds lifecycle, assignee and events),
  with the audit facts; `why_surfaced` sealed; unique ref (F-01) on the work item.
- `deficiencies`: one per finding; Concluded or Communicated needs the concluded severity and a
  person's decision on the deficiency's own card (a guard reads `decisions`, human-only by 0094).
- `audit_misstatements`: factual, judgmental or projected, with their AU-C 450 states.
- `sum_snapshots` (insert-only): the SUM frozen for the partner's card and A-07's letter.
- `consultations`: minimal (DEC-83); concluded only by the person consulted (a guard on the
  session's actor).

Status CHECKs are the status vocabulary's codes as of this migration.

Revision ID: 0644
Revises: 0643
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0644"
down_revision = "0643"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
DEFICIENCY = ("exception_for_resolution", "proposed", "concluded", "communicated")
SEVERITY = ("deficiency", "significant_deficiency", "material_weakness")
MISSTATEMENT = (
    "candidate",
    "confirmed",
    "below_ct",
    "proposed_to_client",
    "booked",
    "passed_on_sum",
)
ROUTE = ("under_evaluation", "converted_to_misstatement", "converted_to_deficiency")
_TABLES = (
    "consultations",
    "sum_snapshots",
    "audit_misstatements",
    "deficiencies",
    "audit_findings",
)
_INSERT_ONLY = ("sum_snapshots",)
INSERTS: dict[str, tuple[str, ...]] = {
    "audit_findings": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "issue_id",
        "ref",
        "kind",
        "route",
        "compliance_standard",
        "coso_component",
        "title",
        "why_surfaced_sealed",
        "why_surfaced_suggestion_id",
        "created_by_kind",
        "agent_run_id",
        "materiality_version_id",
        "evaluation",
        "consultation_id",
    ),
    "deficiencies": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "finding_id",
        "status",
        "severity_proposed",
        "severity_proposed_by_kind",
        "severity_suggestion_id",
    ),
    "audit_misstatements": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "finding_id",
        "ref",
        "origin_ref",
        "type",
        "nature",
        "status",
        "amount",
        "column_set",
        "fs_effect",
        "carried_from_py",
        "py_ref",
        "projection",
        "materiality_version_id",
        "proposed_entry_id",
    ),
    "sum_snapshots": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "version_no",
        "materiality_version_id",
        "column_set",
        "engine_version",
        "inputs_hash",
        "totals",
        "qualitative_factors",
        "purpose",
        "decision_card_id",
        "created_by",
    ),
    "consultations": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "ref",
        "question_sealed",
        "raised_by",
        "consulted_with_user_id",
        "links",
    ),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "audit_findings": ("route", "kind", "coso_component", "title", "evaluation", "version"),
    "deficiencies": (
        "status",
        "severity_proposed",
        "severity_proposed_by_kind",
        "severity_suggestion_id",
        "severity_concluded",
        "decision_card_id",
        "decision_id",
        "communicated_ref",
        "communicated_at",
        "version",
    ),
    "audit_misstatements": (
        "ref",
        "status",
        "amount",
        "fs_effect",
        "projection",
        "proposed_entry_id",
        "passed_by",
        "passed_reason_sealed",
        "version",
    ),
    "consultations": ("status", "conclusion_sealed", "concluded_at"),
}


def _in(codes: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{c}'" for c in codes) + ")"


_DEFICIENCY_GUARD = """
CREATE FUNCTION deficiencies_concluded_by_a_person() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NEW.status NOT IN ('concluded', 'communicated') THEN
        RETURN NEW;
    END IF;
    IF NEW.severity_concluded IS NULL OR NEW.decision_id IS NULL THEN
        RAISE EXCEPTION 'a concluded deficiency names its severity and the decision'
            USING ERRCODE = 'check_violation';
    END IF;
    -- AU-C 265, DEC-83: the engagement partner's own decision on this deficiency's card.
    IF NOT EXISTS (
        SELECT 1 FROM public.decisions d
         WHERE d.id = NEW.decision_id
           AND d.tenant_id = NEW.tenant_id
           AND d.card_id = NEW.decision_card_id
           AND d.actor_kind = 'human'
    ) THEN
        RAISE EXCEPTION 'a concluded deficiency names the person''s decision on its own card'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
_CONSULTATION_GUARD = """
CREATE FUNCTION consultations_concluded_by_the_consulted() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NEW.status = 'concluded' AND OLD.status IS DISTINCT FROM 'concluded' AND (
        current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
        OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.consulted_with_user_id::text
    ) THEN
        RAISE EXCEPTION 'a consultation is concluded by the person consulted'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE consultations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            ref text NOT NULL CHECK (ref ~ '^C-[0-9]{2,4}$'),
            question_sealed bytea NOT NULL CHECK (octet_length(question_sealed) <= 65536),
            raised_by uuid NOT NULL,
            consulted_with_user_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'concluded')),
            conclusion_sealed bytea NULL CHECK (octet_length(conclusion_sealed) <= 65536),
            concluded_at timestamptz NULL,
            links jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(links) = 'array'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((status = 'concluded')
                = (conclusion_sealed IS NOT NULL AND concluded_at IS NOT NULL)),
            CHECK (work_item_id IS NULL OR engagement_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE audit_findings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            issue_id uuid NOT NULL,
            ref text NOT NULL CHECK (ref ~ '^F-[0-9]{{2,4}}$'),
            kind text NOT NULL
                CHECK (kind IN ('control_deficiency', 'misstatement', 'compliance', 'other')),
            route text NOT NULL DEFAULT 'under_evaluation' CHECK (route IN {_in(ROUTE)}),
            compliance_standard text NULL CHECK (char_length(compliance_standard) <= 60),
            coso_component text NULL CHECK (coso_component IN ('control_environment',
                'risk_assessment', 'control_activities', 'information_communication',
                'monitoring')),
            title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
            why_surfaced_sealed bytea NULL CHECK (octet_length(why_surfaced_sealed) <= 65536),
            why_surfaced_suggestion_id uuid NULL,
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('human', 'agent')),
            agent_run_id uuid NULL,
            materiality_version_id uuid NULL,
            evaluation jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(evaluation) = 'object'),
            consultation_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- DEC-83: one finding per issue; the issue holds lifecycle, assignee and events.
            UNIQUE (tenant_id, issue_id),
            UNIQUE (tenant_id, work_item_id, ref),
            CHECK (created_by_kind = 'human' OR agent_run_id IS NOT NULL),
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id),
            FOREIGN KEY (tenant_id, consultation_id) REFERENCES consultations (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE deficiencies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            finding_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'proposed' CHECK (status IN {_in(DEFICIENCY)}),
            severity_proposed text NULL CHECK (severity_proposed IN {_in(SEVERITY)}),
            severity_proposed_by_kind text NULL
                CHECK (severity_proposed_by_kind IN ('human', 'agent')),
            severity_suggestion_id uuid NULL,
            severity_concluded text NULL CHECK (severity_concluded IN {_in(SEVERITY)}),
            decision_card_id uuid NULL,
            decision_id uuid NULL,
            communicated_ref text NULL CHECK (char_length(communicated_ref) <= 200),
            communicated_at timestamptz NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, finding_id),
            CHECK ((status = 'communicated') = (communicated_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES audit_findings (tenant_id, id),
            FOREIGN KEY (tenant_id, decision_card_id) REFERENCES decision_cards (tenant_id, id),
            FOREIGN KEY (decision_id) REFERENCES decisions (id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE audit_misstatements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            finding_id uuid NULL,
            ref text NOT NULL CHECK (ref ~ '^(AJE|RJE|PAJE|BCT|PY|M)-[1-9][0-9]{{0,3}}$'),
            origin_ref text NULL CHECK (char_length(origin_ref) <= 20),
            type text NOT NULL CHECK (type IN ('factual', 'judgmental', 'projected')),
            nature text NOT NULL DEFAULT 'misstatement'
                CHECK (nature IN ('misstatement', 'reclassification')),
            status text NOT NULL DEFAULT 'candidate' CHECK (status IN {_in(MISSTATEMENT)}),
            amount numeric(20, 2) NOT NULL CHECK (amount <> 0),
            column_set text NOT NULL CHECK (column_set IN ('ebp_net_assets', 'commercial')),
            fs_effect jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(fs_effect) = 'object'),
            carried_from_py boolean NOT NULL DEFAULT false,
            py_ref text NULL CHECK (char_length(py_ref) <= 20),
            projection jsonb NULL
                CHECK (projection IS NULL OR jsonb_typeof(projection) = 'object'),
            materiality_version_id uuid NULL,
            proposed_entry_id uuid NULL,
            passed_by uuid NULL,
            passed_reason_sealed bytea NULL CHECK (octet_length(passed_reason_sealed) <= 65536),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, ref),
            -- DF-28: passing on SUM is the EP's act, with a reason.
            CHECK (status <> 'passed_on_sum'
                OR (passed_by IS NOT NULL AND passed_reason_sealed IS NOT NULL)),
            CHECK (type <> 'projected' OR projection IS NOT NULL),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES audit_findings (tenant_id, id),
            FOREIGN KEY (tenant_id, proposed_entry_id) REFERENCES proposed_entries (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sum_snapshots (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            version_no integer NOT NULL CHECK (version_no >= 1),
            materiality_version_id uuid NOT NULL,
            column_set text NOT NULL CHECK (column_set IN ('ebp_net_assets', 'commercial')),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            totals jsonb NOT NULL CHECK (jsonb_typeof(totals) = 'object'),
            qualitative_factors jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(qualitative_factors) = 'array'),
            purpose text NOT NULL CHECK (purpose IN ('conclusion', 'rep_letter_attachment')),
            decision_card_id uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, version_no),
            FOREIGN KEY (tenant_id, materiality_version_id)
                REFERENCES materiality_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(_DEFICIENCY_GUARD)
    op.execute(
        "CREATE TRIGGER deficiencies_concluded_by_a_person BEFORE INSERT OR UPDATE "
        "ON deficiencies FOR EACH ROW EXECUTE FUNCTION deficiencies_concluded_by_a_person()"
    )
    op.execute(_CONSULTATION_GUARD)
    op.execute(
        "CREATE TRIGGER consultations_concluded_by_the_consulted BEFORE UPDATE "
        "ON consultations FOR EACH ROW EXECUTE FUNCTION consultations_concluded_by_the_consulted()"
    )
    for function in (
        "deficiencies_concluded_by_a_person()",
        "consultations_concluded_by_the_consulted()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    for table in ("audit_findings", "deficiencies", "audit_misstatements", "sum_snapshots"):
        op.execute(f"CREATE INDEX {table}_work_item ON {table} (tenant_id, work_item_id)")
    op.execute("CREATE INDEX consultations_engagement ON consultations (tenant_id, engagement_id)")
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        insert_only(op, table)
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION consultations_concluded_by_the_consulted()")
    op.execute("DROP FUNCTION deficiencies_concluded_by_a_person()")
