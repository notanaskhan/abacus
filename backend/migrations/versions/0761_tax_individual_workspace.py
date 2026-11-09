"""T-04-T10 (S33; TASK-6523; SPEC-649; T-04 §4.2; DEC-3123): the individual return workspace,
expand-only.

Nine new tables owned by `tax`; no change to T-02's `tax_returns`, `k1_packages` or binders. Every
table carries the return's work item and engagement (`tax_return_id` is the return's work item,
0089), so `tenant_table()` attaches forced RLS, `tenant_isolation` and the `archived_guard`. Value
columns hold tax return information (TRI, Restricted) as typed JSON (`{t, v}`), never a TIN. The
pipeline runs it after 8 pm CT inside the window (P-29).

- `return_worksheets`, `return_worksheet_sections`, `return_fields`: the worksheet tree; a field's
  derivation is `input`, `formula` (a code formula id, never an expression in data, ADR-052),
  `engine` (needs its engine field key) or `copy`; `current_value` caches P-04's field versions.
- `document_approvals`: insert-only, human-only (the row is the transaction's own person), a
  reversal names the approval it reverses, once.
- `k1_activities` (DEC-88: `source_package_id` joins T-02's package), `k1_treatments` (status a
  projection of its events) and insert-only `k1_treatment_events`.
- `residency_determinations` and insert-only `residency_facts`.

Revision ID: 0761
Revises: 0760
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0761"
down_revision = "0760"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            tax_return_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, tax_return_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tax_return_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT"""
_TSJ = "CHECK ({col} IN ('T', 'S', 'J'))"
_SHA = "~ '^[0-9a-f]{64}$'"
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_TYPED = "CHECK ({col} IS NULL OR (jsonb_typeof({col}) = 'object' AND {col} ? 't'))"
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_HUMAN = (
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
IMMUTABLE = ("document_approvals", "k1_treatment_events", "residency_facts")
TABLES = (
    "return_worksheets",
    "return_worksheet_sections",
    "return_fields",
    "document_approvals",
    "k1_activities",
    "k1_treatments",
    "k1_treatment_events",
    "residency_determinations",
    "residency_facts",
)
_S = ("tenant_id", "engagement_id", "tax_return_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "return_worksheets": (
        *_S, "id", "key", "form_code", "title", "group_path", "jurisdiction", "default_tsj",
        "origin", "new_vs_prior_year", "k1_activity_id", "sort_order", "footer_note", "active",
        "created_in_checkpoint_id", "content_hash",
    ),
    "return_worksheet_sections": (
        *_S, "id", "worksheet_id", "key", "name", "sort_order", "content_hash",
    ),
    "return_fields": (
        *_S, "id", "worksheet_id", "section_id", "field_key", "line_ref", "label", "tsj",
        "value_type", "derivation", "formula_ref", "engine_field_key", "estimate_flag",
        "new_this_year_note", "current_value", "current_fvv_seq", "sort_order",
    ),
    "document_approvals": (
        *_S, "evidence_version_id", "level", "kind", "reverses_id", "actor_user_id",
        "function_at_time", "reason_sealed", "seen_version",
    ),
    "k1_activities": (
        *_S, "id", "issuer_name", "issuer_client_entity_id", "issuer_form", "recipient_tsj",
        "ownership_pct", "source_package_id", "k1_state", "released_at",
        "source_evidence_version_ids", "k1_worksheet_id", "content_hash",
    ),
    "k1_treatments": (
        *_S, "id", "k1_activity_id", "kind", "resolved", "prior_year", "changed_vs_prior",
        "status", "proposal_id", "engine_name", "engine_version", "inputs_hash",
    ),
    "k1_treatment_events": (
        *_S, "treatment_id", "event", "actor_kind", "actor_id", "proposal_id", "reason_sealed",
    ),
    "residency_determinations": (
        *_S, "id", "scope", "jurisdictions", "options", "proposed_option",
        "recommended_by_run_id", "status", "conflict", "proposal_id",
    ),
    "residency_facts": (
        *_S, "determination_id", "fact_key", "value", "citation_ids", "source_kind",
        "added_by_kind",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "return_worksheets": (
        "title", "group_path", "footer_note", "active", "sort_order", "content_hash",
        "version_no", "updated_at",
    ),
    "return_worksheet_sections": (
        "name", "sort_order", "content_hash", "version_no", "updated_at",
    ),
    "return_fields": (
        "label", "estimate_flag", "new_this_year_note", "current_value", "current_fvv_seq",
        "sort_order", "updated_at",
    ),
    "k1_activities": (
        "k1_state", "released_at", "source_evidence_version_ids", "k1_worksheet_id",
        "content_hash", "version_no", "updated_at",
    ),
    "k1_treatments": (
        "resolved", "prior_year", "changed_vs_prior", "status", "override_value",
        "override_reason_sealed", "decided_by", "decided_at", "proposal_id", "checkpoint_id",
        "follow_up_note", "engine_name", "engine_version", "inputs_hash", "version_no",
        "updated_at",
    ),
    "residency_determinations": (
        "jurisdictions", "options", "proposed_option", "recommended_by_run_id", "status",
        "conflict", "confirmed_by", "confirmed_at", "proposal_id", "checkpoint_id", "issue_id",
        "version_no", "updated_at",
    ),
}  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE return_worksheets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9:_-]{{0,79}}$'),
            form_code text NOT NULL CHECK (char_length(form_code) BETWEEN 1 AND 40),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            group_path text NULL CHECK (char_length(group_path) <= 200),
            jurisdiction text NOT NULL CHECK (jurisdiction ~ '^(US|[A-Z]{{2}}|NYC)$'),
            default_tsj text NOT NULL {_TSJ.format(col="default_tsj")},
            origin text NOT NULL
                CHECK (origin IN ('agent', 'human', 'engine_import', 'roll_forward')),
            new_vs_prior_year boolean NOT NULL DEFAULT false,
            k1_activity_id uuid NULL,
            sort_order integer NOT NULL DEFAULT 0,
            footer_note text NULL CHECK (char_length(footer_note) <= 500),
            active boolean NOT NULL DEFAULT true,
            created_in_checkpoint_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tax_return_id, key),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE return_worksheet_sections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            worksheet_id uuid NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_-]{{0,59}}$'),
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
            sort_order integer NOT NULL DEFAULT 0,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (worksheet_id, key),
            FOREIGN KEY (tenant_id, worksheet_id)
                REFERENCES return_worksheets (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE return_fields (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            worksheet_id uuid NOT NULL,
            section_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[a-z0-9][a-z0-9_.:-]{{0,99}}$'),
            line_ref text NULL CHECK (char_length(line_ref) <= 40),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            tsj text NOT NULL {_TSJ.format(col="tsj")},
            value_type text NOT NULL
                CHECK (value_type IN ('amount', 'text', 'enum', 'months', 'bool', 'date')),
            derivation text NOT NULL CHECK (derivation IN ('input', 'formula', 'engine', 'copy')),
            formula_ref text NULL CHECK (formula_ref ~ '^[a-z][a-z0-9_.]{{0,79}}$'),
            engine_field_key text NULL CHECK (char_length(engine_field_key) <= 120),
            estimate_flag boolean NOT NULL DEFAULT false,
            new_this_year_note text NULL CHECK (char_length(new_this_year_note) <= 300),
            current_value jsonb NULL {_TYPED.format(col="current_value")},
            current_fvv_seq bigint NULL CHECK (current_fvv_seq >= 1),
            sort_order integer NOT NULL DEFAULT 0,
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (worksheet_id, field_key),
            CONSTRAINT return_fields_engine CHECK (
                derivation <> 'engine' OR engine_field_key IS NOT NULL
            ),
            CONSTRAINT return_fields_formula
                CHECK ((derivation = 'formula') = (formula_ref IS NOT NULL)),
            FOREIGN KEY (tenant_id, worksheet_id) REFERENCES return_worksheets (tenant_id, id),
            FOREIGN KEY (tenant_id, section_id)
                REFERENCES return_worksheet_sections (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE document_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NOT NULL,
            level text NOT NULL CHECK (level IN ('preparer', 'detail', 'manager')),
            kind text NOT NULL CHECK (kind IN ('approve', 'reverse')),
            reverses_id uuid NULL,
            actor_user_id uuid NOT NULL REFERENCES users (id),
            function_at_time text NULL CHECK (char_length(function_at_time) <= 40),
            reason_sealed bytea NULL,
            seen_version integer NOT NULL CHECK (seen_version >= 1),
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_ACTOR},
            UNIQUE (tenant_id, id),
            UNIQUE (reverses_id),
            CONSTRAINT document_approvals_reverse
                CHECK ((kind = 'reverse') = (reverses_id IS NOT NULL)),
            CONSTRAINT document_approvals_reason CHECK (kind = 'reverse' OR reason_sealed IS NULL),
            CONSTRAINT document_approvals_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, reverses_id)
                REFERENCES document_approvals (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE INDEX document_approvals_live ON document_approvals "
        "(tenant_id, evidence_version_id, level)"
    )
    op.execute(
        f"""
        CREATE TABLE k1_activities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            issuer_name text NOT NULL CHECK (char_length(issuer_name) BETWEEN 1 AND 200),
            issuer_client_entity_id uuid NULL,
            issuer_form text NOT NULL CHECK (issuer_form IN ('1065', '1120s', '1041')),
            recipient_tsj text NOT NULL {_TSJ.format(col="recipient_tsj")},
            ownership_pct numeric(9, 6) NULL CHECK (ownership_pct BETWEEN 0 AND 100),
            source_package_id uuid NULL REFERENCES k1_packages (id),
            k1_state text NOT NULL DEFAULT 'draft_pre_release'
                CHECK (k1_state IN ('draft_pre_release', 'released', 'superseded')),
            released_at timestamptz NULL,
            source_evidence_version_ids uuid[] NOT NULL DEFAULT '{{}}',
            k1_worksheet_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, k1_worksheet_id)
                REFERENCES return_worksheets (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX k1_activities_one_per_package ON k1_activities "
        "(tax_return_id, source_package_id) WHERE source_package_id IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE return_worksheets ADD CONSTRAINT return_worksheets_k1_activity "
        "FOREIGN KEY (tenant_id, k1_activity_id) REFERENCES k1_activities (tenant_id, id)"
    )
    op.execute(
        f"""
        CREATE TABLE k1_treatments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            k1_activity_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('passive_nonpassive', 'ptp', 'qbi_199a', 'niit',
                'basis_at_risk', 'state_sourcing', 'ptet_credits', 'tax_exempt_interest')),
            resolved jsonb NULL CHECK (resolved IS NULL OR jsonb_typeof(resolved) = 'object'),
            prior_year jsonb NULL
                CHECK (prior_year IS NULL OR jsonb_typeof(prior_year) = 'object'),
            changed_vs_prior boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'approved', 'overridden')),
            override_value jsonb NULL {_TYPED.format(col="override_value")},
            override_reason_sealed bytea NULL,
            decided_by uuid NULL REFERENCES users (id),
            decided_at timestamptz NULL,
            proposal_id uuid NULL,
            checkpoint_id uuid NULL,
            follow_up_note text NULL CHECK (char_length(follow_up_note) <= 500),
            engine_name text NULL CHECK (char_length(engine_name) <= 60),
            engine_version text NULL CHECK (char_length(engine_version) <= 20),
            inputs_hash text NULL CHECK (inputs_hash {_SHA}),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (k1_activity_id, kind),
            CONSTRAINT k1_treatments_decided CHECK (
                (status = 'proposed') = (decided_by IS NULL AND decided_at IS NULL)
            ),
            CONSTRAINT k1_treatments_override CHECK (
                (status = 'overridden') = (override_value IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, k1_activity_id)
                REFERENCES k1_activities (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE k1_treatment_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            treatment_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('proposed', 'approved', 'overridden',
                'went_stale', 'reproposed')),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
            actor_id text NOT NULL CHECK (char_length(actor_id) BETWEEN 1 AND 120),
            proposal_id uuid NULL,
            reason_sealed bytea NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- A person approves or overrides; the agent only proposes (ADR-005).
            CONSTRAINT k1_treatment_events_decided_by_a_person CHECK (
                event NOT IN ('approved', 'overridden') OR actor_kind = 'human'
            ),
            FOREIGN KEY (tenant_id, treatment_id)
                REFERENCES k1_treatments (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE residency_determinations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            scope text NOT NULL {_TSJ.format(col="scope")},
            jurisdictions text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(jurisdictions) <= 10),
            options jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(options) = 'object'),
            proposed_option text NULL CHECK (proposed_option IN ('full_year_nys_nyc',
                'full_year_nys_part_year_nyc', 'part_year_nys')),
            recommended_by_run_id uuid NULL,
            status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'confirmed')),
            conflict boolean NOT NULL DEFAULT false,
            confirmed_by uuid NULL REFERENCES users (id),
            confirmed_at timestamptz NULL,
            proposal_id uuid NULL,
            checkpoint_id uuid NULL,
            issue_id uuid NULL,
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tax_return_id, scope),
            -- Confirmation only through an approved proposal, by a person.
            CONSTRAINT residency_confirmed CHECK (
                (status = 'confirmed') = (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
                AND (status <> 'confirmed' OR proposal_id IS NOT NULL)
            ),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE residency_facts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            determination_id uuid NOT NULL,
            fact_key text NOT NULL CHECK (fact_key IN ('domicile', 'second_residence', 'days',
                'work_location', 'voter_registration', 'drivers_licenses', 'trigger',
                'main_home_answer')),
            value jsonb NOT NULL CHECK (jsonb_typeof(value) = 'object' AND value ? 't'),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(citation_ids) <= 20),
            source_kind text NOT NULL
                CHECK (source_kind IN ('organizer_answer', 'document', 'engine', 'human')),
            added_by_kind text NOT NULL CHECK (added_by_kind IN ('human', 'agent', 'system')),
            {_CREATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, determination_id)
                REFERENCES residency_determinations (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION tax_workspace_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: approvals, treatment events and residency facts never '
                'change; add a reversing or newer row' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION tax_workspace_rows_immutable() FROM PUBLIC")
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table in IMMUTABLE:
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION tax_workspace_rows_immutable()"
        )
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE return_worksheets DROP CONSTRAINT return_worksheets_k1_activity")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION tax_workspace_rows_immutable()")
