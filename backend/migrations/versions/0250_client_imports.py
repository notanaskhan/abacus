"""CLI-06's bulk client import (P-07-T52; P-07 §4.2 M9, Story 3.2; DEC-374, DEC-643).

- New `client_imports`: one uploaded practice-management client list (`source`
  cch_axcess_tax_export · csv), its `stage` (a code, not a registry status: DEC-374), the column
  `mapping` the parser chose and the `counts` CLI-06 g shows. The file itself is kept sealed in
  the row (`file_sealed`, envelope-encrypted per tenant, bound to the import) for 30 days
  (`erase_after`, the row's start plus 30 days, set by a BEFORE INSERT trigger), then erased
  by `client_import_files_erase()` (P-07 OQ-4: its own retention, not an evidence object
  under Object Lock; DEC-643). `file_sha256` stays as the record of what was
  uploaded.
- New `client_import_rows`: one parsed row. `parsed` holds the inert cell text the import uses
  (names, entity type code, contact name and email) and row notes as codes; a TIN is sealed at
  parse (`tin_sealed`, bound to the row), with its kind, last four and the firm's fingerprint
  for the EIN match. The best match, its score and basis; the `decision` (auto-set at or above
  0.9, else a person's: `decided_by`, and `merge_client_id` when they merge into another
  client); `applied_at` and `result_ref` once the run applied it, so a re-run skips it. A
  trigger refuses any change to an applied row's decision or result.
- `client_import_files_erase()` (SECURITY DEFINER, across firms, count only) empties the file and
  the rows' sealed TINs of imports past `erase_after`.

Revision ID: 0250
Revises: 0244
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0250"
down_revision = "0244"
branch_labels = None
depends_on = None

_STAGES = "'uploaded', 'mapped', 'reviewing', 'importing', 'done', 'failed'"
_DECISIONS = "'new', 'merge', 'keep_both', 'skip'"
_ERASE = "client_import_files_erase()"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE client_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            source text NOT NULL CHECK (source IN ('cch_axcess_tax_export', 'csv')),
            file_name text NOT NULL CHECK (char_length(file_name) BETWEEN 1 AND 255),
            file_sealed bytea NULL,
            file_sha256 text NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{{64}}$'),
            file_bytes integer NOT NULL CHECK (file_bytes > 0),
            erase_after timestamptz NOT NULL,
            erased_at timestamptz NULL,
            stage text NOT NULL DEFAULT 'uploaded' CHECK (stage IN ({_STAGES})),
            mapping jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(mapping) = 'object' AND octet_length(mapping::text) <= 8192),
            counts jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(counts) = 'object' AND octet_length(counts::text) <= 2048),
            started_by uuid NOT NULL,
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            run_by uuid NULL,
            run_at timestamptz NULL,
            completed_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CHECK (erased_at IS NULL OR file_sealed IS NULL),
            CHECK ((run_by IS NULL) = (run_at IS NULL)),
            CHECK (completed_at IS NULL OR run_at IS NOT NULL),
            FOREIGN KEY (tenant_id, started_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, run_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX client_imports_by_start ON client_imports (tenant_id, started_at DESC)"
    )
    op.execute(
        "CREATE INDEX client_imports_to_erase ON client_imports (erase_after) "
        "WHERE erased_at IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE client_import_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            import_id uuid NOT NULL,
            row_no integer NOT NULL CHECK (row_no >= 1),
            parsed jsonb NOT NULL
                CHECK (jsonb_typeof(parsed) = 'object' AND octet_length(parsed::text) <= 8192),
            tin_sealed bytea NULL,
            tin_kind text NULL CHECK (tin_kind IN ('ein', 'ssn', 'itin')),
            tin_last4 text NULL CHECK (tin_last4 ~ '^[0-9]{{4}}$'),
            tin_fingerprint bytea NULL,
            best_match_client_id uuid NULL,
            best_match_entity_id uuid NULL,
            score numeric(5, 4) NULL CHECK (score BETWEEN 0 AND 1),
            basis text NULL CHECK (basis IN ('name', 'ein')),
            decision text NULL CHECK (decision IN ({_DECISIONS})),
            merge_client_id uuid NULL,
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            applied_at timestamptz NULL,
            result_ref uuid NULL,
            error_code text NULL CHECK (error_code ~ '^[a-z0-9_]{{1,64}}$'),
            UNIQUE (import_id, row_no),
            CHECK ((tin_kind IS NULL) = (tin_last4 IS NULL)),
            CHECK (tin_sealed IS NULL OR tin_last4 IS NOT NULL),
            CHECK ((best_match_client_id IS NULL) = (score IS NULL)),
            CHECK ((score IS NULL) = (basis IS NULL)),
            CHECK (decided_by IS NULL OR decision IS NOT NULL),
            CHECK (merge_client_id IS NULL OR decision = 'merge'),
            CHECK ((decided_by IS NULL) = (decided_at IS NULL)),
            CHECK (result_ref IS NULL OR applied_at IS NOT NULL),
            FOREIGN KEY (tenant_id, import_id) REFERENCES client_imports (tenant_id, id),
            FOREIGN KEY (tenant_id, best_match_client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, merge_client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, decided_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX client_import_rows_to_review ON client_import_rows (import_id, row_no) "
        "WHERE decision IS NULL"
    )
    for table in ("client_imports", "client_import_rows"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "client_imports",
        (
            "id",
            "tenant_id",
            "source",
            "file_name",
            "file_sealed",
            "file_sha256",
            "file_bytes",
            "stage",
            "mapping",
            "counts",
            "started_by",
        ),
    )
    op.execute(
        "GRANT UPDATE (stage, counts, run_by, run_at, completed_at) "
        "ON client_imports TO abacus_app"
    )
    insert_columns(
        op,
        "client_import_rows",
        (
            "id",
            "tenant_id",
            "import_id",
            "row_no",
            "parsed",
            "tin_sealed",
            "tin_kind",
            "tin_last4",
            "tin_fingerprint",
            "best_match_client_id",
            "best_match_entity_id",
            "score",
            "basis",
            "decision",
            "error_code",
        ),
    )
    op.execute(
        "GRANT UPDATE (decision, merge_client_id, decided_by, decided_at, applied_at, result_ref, "
        "error_code) "
        "ON client_import_rows TO abacus_app"
    )
    # `erase_after` is the row's own start plus 30 days, set by the database, never the app.
    op.execute(
        """
        CREATE FUNCTION client_imports_erase_after() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            NEW.erase_after := NEW.started_at + interval '30 days';
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_imports_erase_after BEFORE INSERT ON client_imports "
        "FOR EACH ROW EXECUTE FUNCTION client_imports_erase_after()"
    )
    op.execute(
        """
        CREATE FUNCTION client_import_rows_applied() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            -- The erase (sealed TIN and fingerprint only) is the one change an applied row takes.
            IF OLD.applied_at IS NOT NULL AND (
                NEW.decision, NEW.merge_client_id, NEW.decided_by, NEW.decided_at,
                NEW.applied_at, NEW.result_ref, NEW.error_code
            ) IS DISTINCT FROM (
                OLD.decision, OLD.merge_client_id, OLD.decided_by, OLD.decided_at,
                OLD.applied_at, OLD.result_ref, OLD.error_code
            ) THEN
                RAISE EXCEPTION 'client_import_rows: an applied row is final'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_import_rows_applied BEFORE UPDATE ON client_import_rows "
        "FOR EACH ROW EXECUTE FUNCTION client_import_rows_applied()"
    )
    op.execute(
        """
        CREATE FUNCTION client_import_files_erase() RETURNS bigint
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '60s'
        AS $$
        DECLARE
            v_count bigint;
        BEGIN
            UPDATE public.client_import_rows r
               SET tin_sealed = NULL, tin_fingerprint = NULL
              FROM public.client_imports i
             WHERE r.import_id = i.id AND i.erased_at IS NULL
               AND i.erase_after <= clock_timestamp() AND r.tin_sealed IS NOT NULL;
            WITH gone AS (
                UPDATE public.client_imports
                   SET file_sealed = NULL, erased_at = clock_timestamp()
                 WHERE erased_at IS NULL AND erase_after <= clock_timestamp()
                RETURNING 1
            )
            SELECT count(*) INTO v_count FROM gone;
            RETURN v_count;
        END $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_ERASE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ERASE} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_ERASE}")
    op.execute("DROP TABLE client_import_rows")
    op.execute("DROP TABLE client_imports")
    op.execute("DROP FUNCTION client_import_rows_applied()")
    op.execute("DROP FUNCTION client_imports_erase_after()")
