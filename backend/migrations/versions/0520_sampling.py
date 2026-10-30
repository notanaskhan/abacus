"""The sampling engine's tables (A-03-T05; A-03 §4.2 M-A; SPEC-580 AC-13 to AC-15; ADR-340).

Expand-only. Every table has forced RLS. Money is numeric(20,2).
- `sample_populations` and `sample_population_records` (insert-only): what a population was built
  from, its canonical rows' SHA-256 and total, and its records (display fields only; Restricted
  columns are refused at parse). Records join their population only in the transaction that
  created it. Fieldwork's journal-entry `populations` (0057, ADR-132) are a different table.
- `completeness_ties` (insert-only): code's comparison with its result (tie, off, check).
- `sample_sets`: several per work item (DF-05); the app may update the title, purpose and step.
- `sample_set_versions`: drawn versions. A trigger keeps them frozen: inserted as `drawing`
  (numbered 1, 2, 3 per set); while drawing only the outcome may be written (draft or failed,
  the items and content hashes, a failure code); a draft may only move to approved or superseded
  with the approval stamps; an approved version only to superseded; superseded and failed never
  change; nothing is deleted. Approval needs `approved_actor_kind = 'human'` (a CHECK) and a
  person's session (the trigger); one approved version per set (a partial unique index); an
  override below the computed size needs a rationale.
- `sample_strata` and `sample_items` (insert-only): written only while their version is drawing,
  so the draw's transaction that moves it to draft is the last that can add one.
- `threshold_policies.kind` gains `attribute_sample_sizes` (K-02's table; the size table is firm
  content, ADR-340 §6).

Revision ID: 0520
Revises: 0468
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0520"
down_revision = "0468"
branch_labels = None
depends_on = None

_KINDS_BEFORE = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence')"
)
_KINDS_AFTER = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence', "
    "'attribute_sample_sizes')"
)
_TABLES = (
    "sample_items",
    "sample_strata",
    "sample_set_versions",
    "sample_sets",
    "completeness_ties",
    "sample_population_records",
    "sample_populations",
)
_INSERT_ONLY = (
    "sample_populations",
    "sample_population_records",
    "completeness_ties",
    "sample_strata",
    "sample_items",
)
INSERT = {
    "sample_populations": (
        "id",
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "source_kind",
        "evidence_version_id",
        "gl_snapshot_id",
        "query",
        "column_map",
        "record_count",
        "record_unit",
        "amount_total",
        "sha256",
        "sampling_unit",
        "deviation_definition",
        "pulled_at",
        "created_by",
    ),
    "sample_population_records": (
        "tenant_id",
        "population_id",
        "ordinal",
        "record_key",
        "amount",
        "display",
    ),
    "completeness_ties": (
        "id",
        "tenant_id",
        "population_id",
        "position",
        "label",
        "left_amount",
        "comparisons",
        "difference",
        "result",
        "explanation",
        "engine_version",
        "inputs_hash",
        "created_by",
    ),
    "sample_sets": (
        "id",
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "title",
        "purpose",
        "program_step_key",
        "created_by",
    ),
    "sample_set_versions": (
        "id",
        "tenant_id",
        "sample_set_id",
        "version_no",
        "population_id",
        "method",
        "parameters",
        "size_policy_version_id",
        "computed_size",
        "statistical_crosscheck_size",
        "override_size",
        "override_rationale",
        "final_size",
        "seed",
        "seed_source",
        "sampler_version",
        "inputs_hash",
        "created_by",
    ),
    "sample_strata": (
        "tenant_id",
        "sample_set_version_id",
        "position",
        "min_amount",
        "max_amount",
        "population_count",
        "population_amount",
        "test_rule",
        "random_count",
        "selected_count",
    ),
    "sample_items": (
        "tenant_id",
        "sample_set_version_id",
        "position",
        "population_record_ordinal",
        "record_key",
        "stratum_position",
        "selection_reason",
        "display",
    ),
}
UPDATE = {
    "sample_sets": ("title", "purpose", "program_step_key", "row_version"),
    "sample_set_versions": (
        "status",
        "items_hash",
        "content_hash",
        "failure_code",
        "approved_by",
        "approved_at",
        "approved_actor_kind",
        "superseded_by",
        "row_version",
    ),
}

_DDL = (
    """
    CREATE TABLE sample_populations (
        id uuid NOT NULL DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL,
        engagement_id uuid NOT NULL,
        work_item_id uuid NOT NULL,
        source_kind text NOT NULL CHECK (source_kind IN ('upload', 'general_ledger')),
        evidence_version_id uuid NULL,
        gl_snapshot_id uuid NULL,
        query jsonb NULL CHECK (query IS NULL OR jsonb_typeof(query) = 'object'),
        column_map jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(column_map) = 'object'),
        record_count integer NOT NULL CHECK (record_count > 0),
        record_unit text NOT NULL CHECK (char_length(record_unit) BETWEEN 1 AND 60),
        amount_total numeric(20, 2) NULL,
        sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        sampling_unit text NOT NULL CHECK (char_length(sampling_unit) BETWEEN 1 AND 120),
        deviation_definition text NULL CHECK (char_length(deviation_definition) BETWEEN 1 AND 500),
        pulled_at timestamptz NULL,
        created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT abacus_now(),
        PRIMARY KEY (tenant_id, id),
        FOREIGN KEY (tenant_id, engagement_id, work_item_id)
            REFERENCES work_items (tenant_id, engagement_id, id),
        FOREIGN KEY (tenant_id, evidence_version_id) REFERENCES evidence_versions (tenant_id, id),
        FOREIGN KEY (tenant_id, gl_snapshot_id) REFERENCES gl_snapshots (tenant_id, id),
        FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
        CHECK (
            (source_kind = 'upload' AND evidence_version_id IS NOT NULL
             AND gl_snapshot_id IS NULL AND query IS NULL)
            OR (source_kind = 'general_ledger' AND gl_snapshot_id IS NOT NULL
                AND query IS NOT NULL AND evidence_version_id IS NULL)
        ),
        CHECK (source_kind = 'upload' OR pulled_at IS NOT NULL)
    )
    """,
    """
    CREATE TABLE sample_population_records (
        tenant_id uuid NOT NULL,
        population_id uuid NOT NULL,
        ordinal integer NOT NULL CHECK (ordinal >= 0),
        record_key text NOT NULL CHECK (char_length(record_key) BETWEEN 1 AND 200),
        amount numeric(20, 2) NULL,
        display jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(display) = 'object'),
        PRIMARY KEY (tenant_id, population_id, ordinal),
        FOREIGN KEY (tenant_id, population_id) REFERENCES sample_populations (tenant_id, id)
    )
    """,
    """
    CREATE TABLE completeness_ties (
        id uuid NOT NULL DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL,
        population_id uuid NOT NULL,
        position integer NOT NULL CHECK (position >= 1),
        label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
        left_amount numeric(20, 2) NULL,
        comparisons jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(comparisons) = 'array'),
        difference numeric(20, 2) NULL,
        result text NOT NULL CHECK (result IN ('tie', 'off', 'check')),
        explanation text NULL CHECK (char_length(explanation) BETWEEN 1 AND 500),
        engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
        inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
        created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT abacus_now(),
        PRIMARY KEY (tenant_id, id),
        UNIQUE (tenant_id, population_id, position),
        FOREIGN KEY (tenant_id, population_id) REFERENCES sample_populations (tenant_id, id),
        FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
        CHECK (result <> 'tie' OR difference IS NULL OR difference = 0),
        CHECK (result <> 'off' OR (difference IS NOT NULL AND difference <> 0))
    )
    """,
    """
    CREATE TABLE sample_sets (
        id uuid NOT NULL DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL,
        engagement_id uuid NOT NULL,
        work_item_id uuid NOT NULL,
        title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 120),
        purpose text NULL CHECK (char_length(purpose) BETWEEN 1 AND 300),
        program_step_key text NULL CHECK (char_length(program_step_key) BETWEEN 1 AND 120),
        created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT abacus_now(),
        row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
        PRIMARY KEY (tenant_id, id),
        FOREIGN KEY (tenant_id, engagement_id, work_item_id)
            REFERENCES work_items (tenant_id, engagement_id, id),
        FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
    )
    """,
    """
    CREATE TABLE sample_set_versions (
        id uuid NOT NULL DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL,
        sample_set_id uuid NOT NULL,
        version_no integer NOT NULL CHECK (version_no >= 1),
        population_id uuid NOT NULL,
        method text NOT NULL CHECK (method IN ('attribute_nonstatistical',
            'attribute_statistical', 'threshold_random_stratified')),
        parameters jsonb NOT NULL CHECK (jsonb_typeof(parameters) = 'object'),
        size_policy_version_id uuid NULL,
        computed_size integer NOT NULL CHECK (computed_size >= 1),
        statistical_crosscheck_size integer NULL CHECK (statistical_crosscheck_size >= 1),
        override_size integer NULL CHECK (override_size >= 1),
        override_rationale text NULL CHECK (char_length(override_rationale) BETWEEN 1 AND 1000),
        final_size integer NOT NULL CHECK (final_size >= 1),
        seed integer NOT NULL CHECK (seed BETWEEN 0 AND 16777215),
        seed_source text NOT NULL CHECK (seed_source IN ('server', 'scenario')),
        sampler_version text NOT NULL CHECK (char_length(sampler_version) BETWEEN 1 AND 20),
        inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
        items_hash text NULL CHECK (items_hash ~ '^[0-9a-f]{64}$'),
        content_hash text NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
        status text NOT NULL DEFAULT 'drawing'
            CHECK (status IN ('drawing', 'draft', 'approved', 'superseded', 'failed')),
        failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
        approved_by uuid NULL,
        approved_at timestamptz NULL,
        approved_actor_kind text NULL
            CHECK (approved_actor_kind IS NULL OR approved_actor_kind = 'human'),
        superseded_by uuid NULL,
        created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT abacus_now(),
        row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
        PRIMARY KEY (tenant_id, id),
        UNIQUE (tenant_id, sample_set_id, version_no),
        FOREIGN KEY (tenant_id, sample_set_id) REFERENCES sample_sets (tenant_id, id),
        FOREIGN KEY (tenant_id, population_id) REFERENCES sample_populations (tenant_id, id),
        FOREIGN KEY (tenant_id, size_policy_version_id)
            REFERENCES threshold_policy_versions (tenant_id, id),
        FOREIGN KEY (tenant_id, superseded_by) REFERENCES sample_set_versions (tenant_id, id),
        FOREIGN KEY (tenant_id, approved_by) REFERENCES memberships (tenant_id, user_id),
        FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
        CHECK (override_size IS NULL
               OR (override_rationale IS NOT NULL AND override_size < computed_size)),
        CHECK (override_rationale IS NULL OR override_size IS NOT NULL),
        CHECK (final_size = coalesce(override_size, computed_size)),
        CHECK (status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL
                                        AND approved_actor_kind IS NOT NULL)),
        CHECK (status NOT IN ('drawing', 'draft', 'failed')
               OR (approved_by IS NULL AND approved_at IS NULL AND approved_actor_kind IS NULL)),
        CHECK (status <> 'failed' OR failure_code IS NOT NULL),
        CHECK (status IN ('drawing', 'failed') OR items_hash IS NOT NULL)
    )
    """,
    """
    CREATE TABLE sample_strata (
        tenant_id uuid NOT NULL,
        sample_set_version_id uuid NOT NULL,
        position integer NOT NULL CHECK (position >= 1),
        min_amount numeric(20, 2) NULL,
        max_amount numeric(20, 2) NULL,
        population_count integer NOT NULL CHECK (population_count >= 0),
        population_amount numeric(20, 2) NOT NULL,
        test_rule text NOT NULL CHECK (test_rule IN ('all', 'random', 'none')),
        random_count integer NULL CHECK (random_count >= 0),
        selected_count integer NOT NULL CHECK (selected_count >= 0),
        PRIMARY KEY (tenant_id, sample_set_version_id, position),
        FOREIGN KEY (tenant_id, sample_set_version_id)
            REFERENCES sample_set_versions (tenant_id, id),
        CHECK ((test_rule = 'random') = (random_count IS NOT NULL)),
        CHECK (min_amount IS NULL OR max_amount IS NULL OR min_amount < max_amount)
    )
    """,
    """
    CREATE TABLE sample_items (
        tenant_id uuid NOT NULL,
        sample_set_version_id uuid NOT NULL,
        position integer NOT NULL CHECK (position >= 1),
        population_record_ordinal integer NOT NULL CHECK (population_record_ordinal >= 0),
        record_key text NOT NULL CHECK (char_length(record_key) BETWEEN 1 AND 200),
        stratum_position integer NULL CHECK (stratum_position >= 1),
        selection_reason text NOT NULL CHECK (selection_reason IN ('random', 'threshold')),
        display jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(display) = 'object'),
        PRIMARY KEY (tenant_id, sample_set_version_id, position),
        UNIQUE (tenant_id, sample_set_version_id, population_record_ordinal),
        FOREIGN KEY (tenant_id, sample_set_version_id)
            REFERENCES sample_set_versions (tenant_id, id)
    )
    """,
)

_FUNCTIONS = (
    """
    CREATE FUNCTION sample_population_records_with_population() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM public.sample_populations p
            WHERE p.tenant_id = NEW.tenant_id AND p.id = NEW.population_id
              AND p.xmin::text::bigint = (txid_current() % 4294967296)
        ) THEN
            RAISE EXCEPTION 'population records can only be added with their population'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
    """,
    """
    CREATE FUNCTION sample_rows_while_drawing() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM public.sample_set_versions v
            WHERE v.tenant_id = NEW.tenant_id AND v.id = NEW.sample_set_version_id
              AND v.status = 'drawing'
        ) THEN
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
    """,
    """
    CREATE FUNCTION sample_set_versions_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    DECLARE
        v_next integer;
        v_outcome constant text[] := ARRAY['status', 'items_hash', 'content_hash',
                                           'failure_code', 'row_version'];
        v_decision constant text[] := ARRAY['status', 'approved_by', 'approved_at',
                                            'approved_actor_kind', 'superseded_by', 'row_version'];
        v_supersede constant text[] := ARRAY['status', 'superseded_by', 'row_version'];
    BEGIN
        IF TG_OP = 'TRUNCATE' THEN
            RAISE EXCEPTION 'sample set versions cannot be truncated'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'drawing' THEN
                RAISE EXCEPTION 'not_drawing' USING ERRCODE = 'check_violation';
            END IF;
            SELECT coalesce(max(version_no), 0) + 1 INTO v_next
              FROM public.sample_set_versions
             WHERE tenant_id = NEW.tenant_id AND sample_set_id = NEW.sample_set_id;
            IF NEW.version_no <> v_next THEN
                RAISE EXCEPTION 'version_not_next' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END IF;
        -- UPDATE: which columns may change depends on where the version is.
        IF OLD.status = 'drawing' AND NEW.status IN ('drawing', 'draft', 'failed') THEN
            IF (to_jsonb(NEW) - v_outcome) IS DISTINCT FROM (to_jsonb(OLD) - v_outcome) THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
        ELSIF OLD.status = 'draft' AND NEW.status IN ('approved', 'superseded') THEN
            IF (to_jsonb(NEW) - v_decision) IS DISTINCT FROM (to_jsonb(OLD) - v_decision) THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
        ELSIF OLD.status = 'approved' AND NEW.status = 'superseded' THEN
            IF (to_jsonb(NEW) - v_supersede) IS DISTINCT FROM (to_jsonb(OLD) - v_supersede) THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
        ELSE
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- INV-1: an approval happens in a person's session, whatever the service writes.
        IF NEW.status = 'approved'
           AND coalesce(current_setting('app.actor_kind', true), '') <> 'human' THEN
            RAISE EXCEPTION 'approver_not_human' USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
    """,
)


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)
    op.execute(
        "CREATE UNIQUE INDEX sample_set_versions_one_approved ON sample_set_versions "
        "(tenant_id, sample_set_id) WHERE status = 'approved'"
    )
    op.execute("CREATE INDEX sample_sets_work_item ON sample_sets (tenant_id, work_item_id)")
    op.execute(
        "CREATE INDEX sample_populations_work_item ON sample_populations (tenant_id, work_item_id)"
    )
    for statement in _FUNCTIONS:
        op.execute(statement)
    for table in reversed(_TABLES):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERT[table])
    for table, columns in UPDATE.items():
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute(
        "CREATE TRIGGER sample_population_records_with_population BEFORE INSERT ON "
        "sample_population_records FOR EACH ROW EXECUTE FUNCTION "
        "sample_population_records_with_population()"
    )
    for table in ("sample_strata", "sample_items"):
        op.execute(
            f"CREATE TRIGGER {table}_while_drawing BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION sample_rows_while_drawing()"
        )
    op.execute(
        "CREATE TRIGGER sample_set_versions_guard BEFORE INSERT OR UPDATE OR DELETE ON "
        "sample_set_versions FOR EACH ROW EXECUTE FUNCTION sample_set_versions_guard()"
    )
    op.execute(
        "CREATE TRIGGER sample_set_versions_no_truncate BEFORE TRUNCATE ON sample_set_versions "
        "FOR EACH STATEMENT EXECUTE FUNCTION sample_set_versions_guard()"
    )
    for function in (
        "sample_population_records_with_population()",
        "sample_rows_while_drawing()",
        "sample_set_versions_guard()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute("ALTER TABLE threshold_policies DROP CONSTRAINT threshold_policies_kind_check")
    op.execute(
        "ALTER TABLE threshold_policies ADD CONSTRAINT threshold_policies_kind_check "
        f"CHECK (kind IN {_KINDS_AFTER})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE threshold_policies DROP CONSTRAINT threshold_policies_kind_check")
    op.execute(
        "ALTER TABLE threshold_policies ADD CONSTRAINT threshold_policies_kind_check "
        f"CHECK (kind IN {_KINDS_BEFORE})"
    )
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION sample_set_versions_guard()")
    op.execute("DROP FUNCTION sample_rows_while_drawing()")
    op.execute("DROP FUNCTION sample_population_records_with_population()")
