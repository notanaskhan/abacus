"""A-08-T12 (S46; TASK-8086; SPEC-657 F1, F3; ADR-400 P-58; P-57): `je_testing`, expand, amber.

Journal entry testing over a proved-complete GL population (AUD-12 JE variant):

- `je_tests`: one per work item and GL snapshot, its period, the post-close window, the firm's
  `je_risk_criteria` policy version, its status and the current score version.
- `je_test_criteria`: the criteria in force for a score version (key, params, weight), copied
  from the policy version (with any person's overrides) when a person configures the test.
- `je_posting_user_roles`: the role class of each posting user (sealed name, its SHA-256), with
  the citation that supports it; a person sets them.
- `je_score_runs` and insert-only `je_scores`: each scoring run (engine version, inputs hash,
  unique flagged) and every entry's score with its reason codes (never a score without them).
- Constraint swaps on sampling: a sample-set version may be `je_score_selection` or `monetary_unit`
  (ADR P-57) and an item may be selected `risk_score` or `unpredictable`.
- `threshold_policies.kind` gains `je_risk_criteria` and `mus_confidence_factors` (firm content,
  loaded through K-02's import, never in code).

Revision ID: 0895
Revises: 0894
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0895"
down_revision = "0894"
branch_labels = None
depends_on = None

_KINDS_BEFORE = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence', "
    "'attribute_sample_sizes', 'rmm_matrix')"
)
_KINDS_AFTER = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence', "
    "'attribute_sample_sizes', 'rmm_matrix', 'je_risk_criteria', 'mus_confidence_factors')"
)
_METHODS_BEFORE = (
    "('attribute_nonstatistical', 'attribute_statistical', 'threshold_random_stratified')"
)
_METHODS_AFTER = (
    "('attribute_nonstatistical', 'attribute_statistical', 'threshold_random_stratified', "
    "'je_score_selection', 'monetary_unit')"
)
_REASONS_BEFORE = "('random', 'threshold')"
_REASONS_AFTER = "('random', 'threshold', 'risk_score', 'unpredictable')"
TABLES = ("je_scores", "je_score_runs", "je_posting_user_roles", "je_test_criteria", "je_tests")


def _swap(table: str, constraint: str, column: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
    op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK ({column} IN {values})")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE je_tests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            gl_snapshot_id uuid NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            post_close_through date NOT NULL,
            policy_version_id uuid NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'scoring', 'scored', 'failed')),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            sample_set_id uuid NULL,
            score_version integer NOT NULL DEFAULT 0 CHECK (score_version >= 0),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, gl_snapshot_id),
            CHECK (status <> 'failed' OR failure_code IS NOT NULL),
            CHECK (period_end >= period_start AND post_close_through >= period_end),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, gl_snapshot_id) REFERENCES gl_snapshots (tenant_id, id),
            FOREIGN KEY (tenant_id, sample_set_id) REFERENCES sample_sets (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE je_test_criteria (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            je_test_id uuid NOT NULL,
            configured_version integer NOT NULL CHECK (configured_version >= 1),
            position integer NOT NULL CHECK (position >= 1),
            key text NOT NULL CHECK (key IN ('weekend_holiday', 'round_amount', 'post_close',
                'manual_by_role', 'keywords')),
            weight integer NOT NULL CHECK (weight BETWEEN 0 AND 100),
            params jsonb NOT NULL CHECK (jsonb_typeof(params) = 'object'),
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (je_test_id, configured_version, key),
            FOREIGN KEY (tenant_id, je_test_id) REFERENCES je_tests (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE je_posting_user_roles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            je_test_id uuid NOT NULL,
            posting_user_sha256 bytea NOT NULL CHECK (octet_length(posting_user_sha256) = 32),
            posting_user_sealed bytea NOT NULL,
            role_class text NOT NULL CHECK (role_class IN ('senior_management', 'accounting_staff',
                'system', 'unknown')),
            citation_id uuid NULL,
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, je_test_id) REFERENCES je_tests (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE je_score_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            je_test_id uuid NOT NULL,
            score_version integer NOT NULL CHECK (score_version >= 1),
            engine_version text NOT NULL CHECK (length(engine_version) BETWEEN 1 AND 40),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            entries_count integer NOT NULL CHECK (entries_count >= 0),
            unique_flagged integer NOT NULL CHECK (unique_flagged >= 0),
            hits jsonb NOT NULL CHECK (jsonb_typeof(hits) = 'object'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (je_test_id, score_version),
            FOREIGN KEY (tenant_id, je_test_id) REFERENCES je_tests (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE je_scores (
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            entry_ref text NOT NULL CHECK (length(entry_ref) BETWEEN 1 AND 120),
            score integer NOT NULL CHECK (score BETWEEN 0 AND 100),
            reason_codes text[] NOT NULL,
            criteria_mask integer NOT NULL CHECK (criteria_mask >= 0),
            posted_on date NOT NULL,
            amount numeric(20, 2) NOT NULL,
            account_last4 text NULL CHECK (account_last4 ~ '^[0-9]{4}$'),
            description text NOT NULL DEFAULT '' CHECK (length(description) <= 500),
            PRIMARY KEY (tenant_id, run_id, entry_ref),
            CHECK ((score = 0) = (cardinality(reason_codes) = 0)),
            FOREIGN KEY (tenant_id, run_id) REFERENCES je_score_runs (tenant_id, id)
        )
        """
    )
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(
        op, "je_tests",
        ("tenant_id", "engagement_id", "work_item_id", "gl_snapshot_id", "period_start",
         "period_end", "post_close_through", "created_by"),
    )  # fmt: skip
    op.execute(
        "GRANT UPDATE (policy_version_id, status, failure_code, sample_set_id, score_version, "
        "row_version) ON je_tests TO abacus_app"
    )
    insert_columns(
        op, "je_test_criteria",
        ("tenant_id", "je_test_id", "configured_version", "position", "key", "weight", "params",
         "set_by"),
    )  # fmt: skip
    insert_only(op, "je_test_criteria")
    insert_columns(
        op, "je_posting_user_roles",
        ("tenant_id", "je_test_id", "posting_user_sha256", "posting_user_sealed", "role_class",
         "citation_id", "set_by"),
    )  # fmt: skip
    insert_only(op, "je_posting_user_roles")
    insert_columns(
        op, "je_score_runs",
        ("tenant_id", "je_test_id", "score_version", "engine_version", "inputs_hash",
         "entries_count", "unique_flagged", "hits"),
    )  # fmt: skip
    insert_only(op, "je_score_runs")
    insert_columns(
        op, "je_scores",
        ("tenant_id", "run_id", "entry_ref", "score", "reason_codes", "criteria_mask", "posted_on",
         "amount", "account_last4", "description"),
    )  # fmt: skip
    insert_only(op, "je_scores")
    _swap("sample_set_versions", "sample_set_versions_method_check", "method", _METHODS_AFTER)
    _swap(
        "sample_items", "sample_items_selection_reason_check", "selection_reason", _REASONS_AFTER
    )
    _swap("threshold_policies", "threshold_policies_kind_check", "kind", _KINDS_AFTER)


def downgrade() -> None:
    _swap("threshold_policies", "threshold_policies_kind_check", "kind", _KINDS_BEFORE)
    _swap(
        "sample_items", "sample_items_selection_reason_check", "selection_reason", _REASONS_BEFORE
    )
    _swap("sample_set_versions", "sample_set_versions_method_check", "method", _METHODS_BEFORE)
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
