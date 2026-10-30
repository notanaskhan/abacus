"""The tax profile's records (T-01-T43; T-01 §4.2 `00NN_tax_profile`; DEC-1651; CLI-05).

Owned by `tax` (the plan named `organisations`, which imports only `identity`: filing a transcript
as evidence, reading the return as filed from `review` and the transcript compute are tax's, as
for T-01-T10's capture and T-01-T19's engine records). Every table is a tenant table with forced
row-level security.

- `tax_profile_files`: a transcript or scanned form a person uploaded, scanned before storage
  (SPEC-029 AC-1) and kept encrypted in the evidence bucket; consumed once by the transcript or
  authorization that files it (`consumed_by`, set once by a trigger).
- `tax_authorizations`: Forms 8821, 2848 and state forms on file or requested. `designees` holds
  each designee's user id, sealed CAF number (`kernel.crypto`, Restricted) and last four; only
  the status columns change after insert.
- `tax_elections`: one row per entity, kind, jurisdiction and year (§754, PTET by state, BBA,
  §163(j), accounting method); the amount is TRI. Upserted by a person with `seen_version`.
- `transcripts`, `transcript_lines`, `transcript_comparisons`: an IRS transcript a person pulled
  and uploaded (filed as `retrieved` evidence), the lines the parser read and each comparison with
  the return as filed, computed by code (T-01-T45; ADR-050). Insert-only and immutable: a new
  pull or a new comparison is a new row. Lines, amounts and comparisons are TRI.

Revision ID: 0550
Revises: 0406
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0550"
down_revision = "0406"
branch_labels = None
depends_on = None

_TABLES = (
    "tax_profile_files",
    "tax_authorizations",
    "tax_elections",
    "transcripts",
    "transcript_lines",
    "transcript_comparisons",
)
_IMMUTABLE = ("transcripts", "transcript_lines", "transcript_comparisons")

FILE_INSERT = (
    "id",
    "tenant_id",
    "client_entity_id",
    "uploaded_by",
    "file_name",
    "media_type",
    "size_bytes",
    "sha256",
    "storage_key",
    "storage_version_id",
)
AUTHORIZATION_INSERT = (
    "id",
    "tenant_id",
    "client_entity_id",
    "form",
    "state_form_code",
    "designees",
    "tax_matters",
    "forms_covered",
    "tax_years",
    "received_on",
    "expires_on",
    "status",
    "envelope_id",
    "evidence_version_id",
    "created_by",
)
AUTHORIZATION_UPDATE = ("status", "envelope_id", "evidence_version_id", "row_version")
ELECTION_INSERT = (
    "id",
    "tenant_id",
    "client_entity_id",
    "kind",
    "jurisdiction",
    "tax_year",
    "amount",
    "status_code",
    "decided_by_return_id",
    "updated_by",
)
ELECTION_UPDATE = ("amount", "status_code", "decided_by_return_id", "updated_by", "row_version")
TRANSCRIPT_INSERT = (
    "id",
    "tenant_id",
    "client_entity_id",
    "kind",
    "tax_year",
    "pulled_at",
    "pulled_by",
    "authorization_id",
    "evidence_version_id",
    "file_id",
    "parse_status",
    "problems",
    "account_balance",
)
LINE_INSERT = (
    "tenant_id",
    "transcript_id",
    "line_no",
    "form",
    "payer_name",
    "amount",
    "tc_code",
    "tc_date",
)
COMPARISON_INSERT = (
    "id",
    "tenant_id",
    "transcript_id",
    "return_id",
    "checkpoint_id",
    "result",
    "difference_total",
    "lines",
    "agreeing",
    "engine_version",
    "computed_by",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_profile_files (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_entity_id uuid NOT NULL,
            uploaded_by uuid NOT NULL,
            file_name text NOT NULL CHECK (char_length(file_name) BETWEEN 1 AND 255),
            media_type text NOT NULL CHECK (char_length(media_type) BETWEEN 3 AND 100),
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL CHECK (char_length(storage_key) BETWEEN 1 AND 512),
            storage_version_id text NOT NULL CHECK (char_length(storage_version_id) <= 200),
            consumed_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, uploaded_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION tax_profile_files_consumed_once() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.consumed_by IS NOT NULL OR NEW.consumed_by IS NULL THEN
                RAISE EXCEPTION 'a tax profile file is consumed once'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER tax_profile_files_consumed_once BEFORE UPDATE ON tax_profile_files "
        "FOR EACH ROW EXECUTE FUNCTION tax_profile_files_consumed_once()"
    )
    op.execute(
        """
        CREATE TABLE tax_authorizations (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_entity_id uuid NOT NULL,
            form text NOT NULL CHECK (form IN ('8821', '2848', 'state')),
            state_form_code text NULL CHECK (char_length(state_form_code) BETWEEN 1 AND 20),
            designees jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(designees) = 'array'),
            tax_matters text[] NOT NULL DEFAULT '{}',
            forms_covered text[] NOT NULL DEFAULT '{}',
            tax_years integer[] NOT NULL CHECK (cardinality(tax_years) > 0),
            received_on date NULL,
            expires_on date NULL,
            status text NOT NULL CHECK (status IN ('requested', 'on_file', 'expired', 'revoked')),
            envelope_id uuid NULL,
            evidence_version_id uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id) REFERENCES evidence_versions (tenant_id, id),
            -- a state form names its code; a federal form never does
            CHECK ((form = 'state') = (state_form_code IS NOT NULL)),
            -- on file means received, with the scanned form
            CHECK (status <> 'on_file' OR received_on IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX tax_authorizations_entity ON tax_authorizations "
        "(tenant_id, client_entity_id, status)"
    )
    op.execute(
        """
        CREATE TABLE tax_elections (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_entity_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z][a-z0-9_]{1,59}$'),
            jurisdiction text NULL CHECK (char_length(jurisdiction) BETWEEN 1 AND 20),
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            amount numeric(18, 2) NULL,
            status_code text NOT NULL CHECK (char_length(status_code) BETWEEN 1 AND 40),
            decided_by_return_id uuid NULL,
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    # One election per entity, kind, jurisdiction and year (NULL jurisdiction: federal).
    op.execute(
        "CREATE UNIQUE INDEX tax_elections_one ON tax_elections "
        "(tenant_id, client_entity_id, kind, coalesce(jurisdiction, ''), tax_year)"
    )
    op.execute(
        """
        CREATE TABLE transcripts (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_entity_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('wage_income', 'account', 'record_of_account')),
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            pulled_at timestamptz NOT NULL,
            pulled_by uuid NOT NULL,
            authorization_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            file_id uuid NOT NULL,
            parse_status text NOT NULL CHECK (parse_status IN ('parsed', 'failed')),
            problems jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(problems) = 'array'),
            account_balance numeric(18, 2) NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, authorization_id) REFERENCES tax_authorizations (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id) REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, file_id) REFERENCES tax_profile_files (tenant_id, id),
            FOREIGN KEY (tenant_id, pulled_by) REFERENCES memberships (tenant_id, user_id),
            UNIQUE (tenant_id, file_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX transcripts_entity ON transcripts (tenant_id, client_entity_id, tax_year)"
    )
    op.execute(
        """
        CREATE TABLE transcript_lines (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            transcript_id uuid NOT NULL,
            line_no integer NOT NULL CHECK (line_no >= 1),
            form text NULL CHECK (char_length(form) BETWEEN 1 AND 12),
            payer_name text NULL CHECK (char_length(payer_name) BETWEEN 1 AND 120),
            amount numeric(18, 2) NULL,
            tc_code text NULL CHECK (tc_code ~ '^[0-9]{3}$'),
            tc_date date NULL,
            PRIMARY KEY (tenant_id, transcript_id, line_no),
            FOREIGN KEY (tenant_id, transcript_id) REFERENCES transcripts (tenant_id, id),
            -- an information return (form) or a transaction (code and date), never both
            CHECK ((form IS NULL) = (tc_code IS NOT NULL)),
            CHECK ((tc_code IS NULL) = (tc_date IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE transcript_comparisons (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            transcript_id uuid NOT NULL,
            return_id uuid NOT NULL,
            checkpoint_id uuid NOT NULL,
            result text NOT NULL CHECK (result IN ('agrees', 'differences')),
            difference_total numeric(18, 2) NOT NULL,
            lines jsonb NOT NULL CHECK (jsonb_typeof(lines) = 'array'),
            agreeing jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(agreeing) = 'array'),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 40),
            computed_by uuid NOT NULL,
            computed_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, transcript_id) REFERENCES transcripts (tenant_id, id),
            FOREIGN KEY (tenant_id, computed_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX transcript_comparisons_latest ON transcript_comparisons "
        "(tenant_id, transcript_id, computed_at DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION transcripts_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in _IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION transcripts_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION transcripts_immutable()"
        )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, "tax_profile_files", FILE_INSERT)
    op.execute("GRANT UPDATE (consumed_by) ON tax_profile_files TO abacus_app")
    insert_columns(op, "tax_authorizations", AUTHORIZATION_INSERT)
    op.execute(
        f"GRANT UPDATE ({', '.join(AUTHORIZATION_UPDATE)}) ON tax_authorizations TO abacus_app"
    )
    insert_columns(op, "tax_elections", ELECTION_INSERT)
    op.execute(f"GRANT UPDATE ({', '.join(ELECTION_UPDATE)}) ON tax_elections TO abacus_app")
    for table, columns in (
        ("transcripts", TRANSCRIPT_INSERT),
        ("transcript_lines", LINE_INSERT),
        ("transcript_comparisons", COMPARISON_INSERT),
    ):
        insert_only(op, table)
        insert_columns(op, table, columns)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION transcripts_immutable()")
    op.execute("DROP FUNCTION tax_profile_files_consumed_once()")
