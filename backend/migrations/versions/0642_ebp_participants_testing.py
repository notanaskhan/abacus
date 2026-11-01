"""A-05 M2 `ebp_participants_testing` (A-05-T15; A-05 §4.2 M2; SPEC-640; DEC-1959): expand-only.

The census and the shared attribute grid of an EBP audit. Every table is work-item scoped with
forced row-level security:

- `ebp_source_imports`: a client file read into a population (census, payroll register, loan
  report…), its column map, row count, totals and SHA-256; recorded by a person.
- `ebp_participants`: one row per participant of an import. **No plaintext SSN or date-of-birth
  column exists**: each is sealed (`kernel.crypto`), with its last four digits (SSN only) and an
  HMAC fingerprint for equality, so a test compares fingerprints and never reads either.
- `attribute_tests` (workpapers): the attribute grid of one sampled test (EBP-03 eligibility,
  EBP-04 contribution recalculation, EBP-05 distributions; A-08 reuses it), versioned by hash.
- `test_attribute_results` (insert-only): each attribute's result per sampled item, newest `seq`
  current. The agent may write `agent_tested` or `needs_human`; only a person writes `pass`,
  `exception` or `no_effect` (a CHECK on the transaction's actor).
- `ebp_population_queries` (insert-only): a code rule run over the population (the rule, its
  inputs' hash, the engine version and the keys it returned).

Revision ID: 0642
Revises: 0641
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0642"
down_revision = "0641"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
# The row is the transaction's own actor's (0094's rule).
_TRANSACTION_ACTOR = (
    "CHECK (actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_TABLES = (
    "ebp_population_queries",
    "test_attribute_results",
    "attribute_tests",
    "ebp_participants",
    "ebp_source_imports",
)
_INSERT_ONLY = ("test_attribute_results", "ebp_population_queries")
_SHA = "~ '^[0-9a-f]{{64}}$'"
INSERTS: dict[str, tuple[str, ...]] = {
    "ebp_source_imports": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "evidence_version_id",
        "kind",
        "column_map",
        "row_count",
        "totals",
        "sha256",
        "status",
        "refusal_code",
        "imported_by",
    ),
    "ebp_participants": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "import_id",
        "participant_key",
        "name",
        "ssn_sealed",
        "ssn_fp",
        "ssn_last4",
        "dob_sealed",
        "dob_fp",
        "hire_on",
        "termination_on",
        "status",
        "compensation",
        "deferral_election_pct",
        "years_of_service",
        "vested_pct",
    ),
    "attribute_tests": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "workpaper_id",
        "variant",
        "sample_set_id",
        "sample_set_version",
        "attributes",
        "version_no",
        "content_hash",
    ),
    "test_attribute_results": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "test_id",
        "sample_item_id",
        "attribute_key",
        "seq",
        "value",
        "citation_ids",
        "result",
        "note_sealed",
        "trace",
        "suggestion_id",
    ),
    "ebp_population_queries": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "import_id",
        "rule_key",
        "inputs_hash",
        "engine_version",
        "result_keys",
        "count",
    ),
}
# An import moves from mapped to imported or refused; an attribute grid is re-versioned.
UPDATES: dict[str, tuple[str, ...]] = {
    "ebp_source_imports": ("status", "refusal_code", "row_count", "totals"),
    "attribute_tests": ("attributes", "version_no", "content_hash"),
}


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ebp_source_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('census', 'payroll_register', 'loan_report',
                'account_balances', 'sdba_detail', 'trust_receipts', 'hr_roster',
                'vendor_master', 'customer_master')),
            column_map jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(column_map) = 'object'),
            row_count integer NULL CHECK (row_count >= 0),
            totals jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(totals) = 'object'),
            sha256 text NOT NULL CHECK (sha256 {_SHA}),
            status text NOT NULL DEFAULT 'mapped'
                CHECK (status IN ('mapped', 'imported', 'refused')),
            refusal_code text NULL CHECK (char_length(refusal_code) <= 60),
            imported_by uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((status = 'refused') = (refusal_code IS NOT NULL)),
            -- A person imports a client file (A-05 §4.2 M2: actor CHECK human).
            CONSTRAINT ebp_source_imports_by_a_person CHECK (actor_kind = 'human'),
            CONSTRAINT ebp_source_imports_transaction_actor {_TRANSACTION_ACTOR},{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_participants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            import_id uuid NOT NULL,
            participant_key text NOT NULL CHECK (participant_key ~ '^[A-Za-z0-9-]{{1,40}}$'),
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),
            -- No plaintext SSN or date of birth: sealed, last four (SSN) and an HMAC fingerprint.
            ssn_sealed bytea NULL CHECK (octet_length(ssn_sealed) <= 4096),
            ssn_fp text NULL CHECK (ssn_fp {_SHA}),
            ssn_last4 text NULL CHECK (ssn_last4 ~ '^[0-9]{{4}}$'),
            dob_sealed bytea NULL CHECK (octet_length(dob_sealed) <= 4096),
            dob_fp text NULL CHECK (dob_fp {_SHA}),
            hire_on date NULL,
            termination_on date NULL,
            status text NOT NULL CHECK (status IN ('active', 'terminated')),
            compensation numeric(20, 2) NULL CHECK (compensation >= 0),
            deferral_election_pct numeric(7, 4) NULL
                CHECK (deferral_election_pct >= 0 AND deferral_election_pct <= 100),
            years_of_service numeric(6, 2) NULL CHECK (years_of_service >= 0),
            vested_pct numeric(7, 4) NULL CHECK (vested_pct >= 0 AND vested_pct <= 100),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, import_id, participant_key),
            CHECK ((ssn_sealed IS NULL) = (ssn_fp IS NULL)
                AND (ssn_fp IS NULL) = (ssn_last4 IS NULL)),
            CHECK ((dob_sealed IS NULL) = (dob_fp IS NULL)),
            CHECK (termination_on IS NULL OR hire_on IS NULL OR termination_on >= hire_on),
            FOREIGN KEY (tenant_id, import_id) REFERENCES ebp_source_imports (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE attribute_tests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            workpaper_id uuid NOT NULL,
            variant text NOT NULL CHECK (variant IN ('ebp_eligibility',
                'ebp_contribution_recalc', 'ebp_distribution', 'aud12_tod', 'aud12_toc')),
            sample_set_id uuid NULL,
            sample_set_version integer NULL CHECK (sample_set_version >= 1),
            attributes jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(attributes) = 'array'),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((sample_set_id IS NULL) = (sample_set_version IS NULL)),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE test_attribute_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            test_id uuid NOT NULL,
            sample_item_id uuid NOT NULL,
            attribute_key text NOT NULL CHECK (attribute_key ~ '^[a-z][a-z0-9_]{{0,63}}$'),
            seq integer NOT NULL CHECK (seq >= 1),
            value jsonb NULL CHECK (value IS NULL OR jsonb_typeof(value) = 'object'),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            result text NOT NULL CHECK (result IN ('not_started', 'agent_tested', 'needs_human',
                'pass', 'exception', 'no_effect')),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            trace jsonb NULL CHECK (trace IS NULL OR jsonb_typeof(trace) = 'object'),
            suggestion_id uuid NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, test_id, sample_item_id, attribute_key, seq),
            -- INV-1 (A-05 §4.2 M2): only a person concludes an attribute.
            CONSTRAINT test_attribute_results_human_concludes
                CHECK (result NOT IN ('pass', 'exception', 'no_effect') OR actor_kind = 'human'),
            CONSTRAINT test_attribute_results_transaction_actor {_TRANSACTION_ACTOR},
            FOREIGN KEY (tenant_id, test_id) REFERENCES attribute_tests (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_population_queries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            import_id uuid NOT NULL,
            rule_key text NOT NULL CHECK (rule_key ~ '^[a-z][a-z0-9_]{{0,63}}$'),
            inputs_hash text NOT NULL CHECK (inputs_hash {_SHA}),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            result_keys text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(result_keys) <= 100000),
            count integer NOT NULL CHECK (count >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (count = cardinality(result_keys)),
            FOREIGN KEY (tenant_id, import_id) REFERENCES ebp_source_imports (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    for table, column in (
        ("ebp_source_imports", "work_item_id"),
        ("ebp_participants", "import_id"),
        ("attribute_tests", "workpaper_id"),
        ("test_attribute_results", "test_id"),
        ("ebp_population_queries", "import_id"),
    ):
        op.execute(f"CREATE INDEX {table}_{column} ON {table} (tenant_id, {column})")
    op.execute(
        "CREATE INDEX ebp_participants_ssn_fp ON ebp_participants (tenant_id, ssn_fp) "
        "WHERE ssn_fp IS NOT NULL"
    )
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
    # Participants are a census as imported: never edited (a new import replaces them).
    op.execute("REVOKE UPDATE ON ebp_participants FROM abacus_app")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
