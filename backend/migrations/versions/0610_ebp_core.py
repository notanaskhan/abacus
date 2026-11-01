"""A-05 M1 `ebp_core` (A-05-T06; A-05 §4.2; SPEC-640; DEC-1861): expand-only.

The EBP plan audit's first tables, each with `tenant_id`, `engagement_id` and `work_item_id` and
forced row-level security (walls are `visible()` in the service, as every engagement table's):

- `ebp_plans`: one per EBP audit work item, the plan-year facts (EBP-01). The plan number stays on
  `client_entities.plan_number`; the plan kind and §103(a)(3)(C) on `assurance_work_items`.
- `ebp_service_providers`: the plan's providers with their SOC and certification facts; a
  provider's EIN is sealed with its last four and a fingerprint, never plaintext.
- `ebp_provider_checks` (insert-only): code's checks (PN format, EIN and name mismatch, SOC gap),
  `facts` holding identifiers only.
- `ebp_provisions`: a workpaper version's plan provisions with their citations (EBP-02);
  verification is P-04's `sign_offs` (`kind = 'field_tick'`), not a column here.
- `ebp_provision_conflicts` (insert-only): an SPD mismatch or an amendment that governs.

Revision ID: 0610
Revises: 0580
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0610"
down_revision = "0580"
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
    "ebp_provision_conflicts",
    "ebp_provisions",
    "ebp_provider_checks",
    "ebp_service_providers",
    "ebp_plans",
)
_INSERT_ONLY = ("ebp_provider_checks", "ebp_provision_conflicts")
_PROVISION_SHAPE = "^[a-z][a-z0-9_]{0,63}$"
_INSERTS: dict[str, tuple[str, ...]] = {
    "ebp_plans": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "plan_entity_id",
        "sponsor_entity_id",
        "plan_year_start",
        "plan_year_end",
        "plan_type",
        "safe_harbor",
        "auto_enrollment",
        "match_formula",
        "qdia",
        "recordkeeper_plan_id",
        "participants_boy_with_balances",
        "participants_eoy",
        "prior_year_filer",
        "form_5558_filed_on",
        "report_target_on",
        "fidelity_bond_amount",
        "plan_document_on",
        "opinion_letter_on",
        "latest_amendment_ref",
        "version",
        "content_hash",
    ),
    "ebp_service_providers": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "org_name",
        "role",
        "contact_id",
        "grant_id",
        "ein_sealed",
        "ein_last4",
        "ein_fp",
        "soc_type",
        "soc_period_start",
        "soc_period_end",
        "soc_evaluation_id",
        "certifies",
        "certification_signed_on",
        "status",
    ),
    "ebp_provider_checks": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "check_kind",
        "provider_id",
        "result",
        "facts",
        "citation_ids",
        "issue_id",
    ),
    "ebp_provisions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "workpaper_version_id",
        "provision_key",
        "value",
        "reference",
        "citation_id",
        "amendment_effective_on",
        "amendment_citation_id",
        "origin",
        "suggestion_id",
    ),
    "ebp_provision_conflicts": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "provision_id",
        "kind",
        "governing_citation_id",
        "conflicting_citation_id",
        "issue_id",
    ),
}
_UPDATES: dict[str, tuple[str, ...]] = {
    "ebp_plans": (
        "plan_entity_id",
        "sponsor_entity_id",
        "safe_harbor",
        "auto_enrollment",
        "match_formula",
        "qdia",
        "recordkeeper_plan_id",
        "participants_boy_with_balances",
        "participants_eoy",
        "prior_year_filer",
        "form_5558_filed_on",
        "report_target_on",
        "fidelity_bond_amount",
        "plan_document_on",
        "opinion_letter_on",
        "latest_amendment_ref",
        "version",
        "content_hash",
    ),
    "ebp_service_providers": (
        "org_name",
        "contact_id",
        "grant_id",
        "ein_sealed",
        "ein_last4",
        "ein_fp",
        "soc_type",
        "soc_period_start",
        "soc_period_end",
        "soc_evaluation_id",
        "certifies",
        "certification_signed_on",
        "status",
    ),
    "ebp_provisions": (
        "value",
        "reference",
        "citation_id",
        "amendment_effective_on",
        "amendment_citation_id",
        "origin",
        "suggestion_id",
    ),
}


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ebp_plans (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            plan_entity_id uuid NULL,
            sponsor_entity_id uuid NULL,
            plan_year_start date NOT NULL,
            plan_year_end date NOT NULL CHECK (plan_year_end > plan_year_start),
            plan_type text NOT NULL CHECK (plan_type IN ('401k')),
            safe_harbor text NOT NULL
                CHECK (safe_harbor IN ('none', 'qaca', 'basic', 'nonelective')),
            auto_enrollment jsonb NULL CHECK (auto_enrollment IS NULL
                OR jsonb_typeof(auto_enrollment) = 'object'),
            match_formula jsonb NULL CHECK (match_formula IS NULL
                OR jsonb_typeof(match_formula) = 'object'),
            qdia text NULL CHECK (char_length(qdia) <= 200),
            recordkeeper_plan_id text NULL CHECK (char_length(recordkeeper_plan_id) <= 40),
            participants_boy_with_balances integer NULL
                CHECK (participants_boy_with_balances >= 0),
            participants_eoy integer NULL CHECK (participants_eoy >= 0),
            prior_year_filer text NULL CHECK (prior_year_filer IN ('large_plan', 'small_plan')),
            form_5558_filed_on date NULL,
            report_target_on date NULL,
            fidelity_bond_amount numeric(14, 2) NULL CHECK (fidelity_bond_amount >= 0),
            plan_document_on date NULL,
            opinion_letter_on date NULL,
            latest_amendment_ref text NULL CHECK (char_length(latest_amendment_ref) <= 200),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_service_providers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            org_name text NOT NULL CHECK (char_length(btrim(org_name)) BETWEEN 1 AND 200),
            role text NOT NULL CHECK (role IN ('recordkeeper', 'trustee_custodian', 'payroll',
                'tpa', 'sdba_broker', 'other')),
            contact_id uuid NULL,
            grant_id uuid NULL,
            ein_sealed bytea NULL,
            ein_last4 text NULL CHECK (ein_last4 ~ '^[0-9]{{4}}$'),
            ein_fp text NULL CHECK (ein_fp ~ '^[0-9a-f]{{64}}$'),
            soc_type text NULL CHECK (soc_type IN ('soc1_type1', 'soc1_type2', 'none')),
            soc_period_start date NULL,
            soc_period_end date NULL,
            soc_evaluation_id uuid NULL,
            certifies boolean NOT NULL DEFAULT false,
            certification_signed_on date NULL,
            status text NOT NULL DEFAULT 'waiting_on_inputs'
                CHECK (status IN ('received', 'waiting_on_inputs', 'correction_requested')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((ein_sealed IS NULL) = (ein_last4 IS NULL)
                AND (ein_last4 IS NULL) = (ein_fp IS NULL)),
            CHECK (soc_period_end IS NULL OR soc_period_start IS NULL
                OR soc_period_end >= soc_period_start),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_provider_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            check_kind text NOT NULL CHECK (check_kind IN ('pn_format', 'ein_mismatch',
                'name_mismatch', 'soc_gap')),
            provider_id uuid NULL,
            result text NOT NULL CHECK (result IN ('ok', 'flag')),
            facts jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(facts) = 'object'),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            issue_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, provider_id)
                REFERENCES ebp_service_providers (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_provisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            workpaper_version_id uuid NOT NULL,
            provision_key text NOT NULL CHECK (provision_key ~ '{_PROVISION_SHAPE}'),
            value jsonb NOT NULL,
            reference text NULL CHECK (char_length(reference) <= 300),
            citation_id uuid NULL,
            amendment_effective_on date NULL,
            amendment_citation_id uuid NULL,
            origin text NOT NULL CHECK (origin IN ('agent_suggested', 'human', 'import')),
            suggestion_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, workpaper_version_id, provision_key),
            CHECK ((amendment_effective_on IS NULL) = (amendment_citation_id IS NULL)),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_provision_conflicts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            provision_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('spd_mismatch', 'amendment_governs')),
            governing_citation_id uuid NOT NULL,
            conflicting_citation_id uuid NOT NULL,
            issue_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (governing_citation_id <> conflicting_citation_id),
            FOREIGN KEY (tenant_id, provision_id)
                REFERENCES ebp_provisions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    for table in ("ebp_service_providers", "ebp_provider_checks", "ebp_provisions"):
        op.execute(f"CREATE INDEX {table}_work_item ON {table} (tenant_id, work_item_id)")
    op.execute(
        "CREATE INDEX ebp_provision_conflicts_provision ON ebp_provision_conflicts "
        "(tenant_id, provision_id)"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        insert_only(op, table)
    # A plan's facts are edited through a new content hash and version; a provider's status and
    # SOC facts move as the evidence arrives; a provision's value is a person's edit.
    for table, columns in _INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in _UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
