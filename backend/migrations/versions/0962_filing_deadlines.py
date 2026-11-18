"""Filing deadlines (T-08-T07; SPEC-710 AC-9 to AC-20, AC-35; T-08 §4.2; DEC-5606). Expand-only;
the pipeline runs it after 8 pm CT inside the window (P-29).

Two practice tables with forced RLS. `filing_deadlines` is a read model upserted only by the
recompute, keyed by (tenant, source kind, source ref, filing label) and idempotent on
`inputs_hash`; it carries metadata only (client, filing, dates, stage, owners), never TRI or an
amount, and no risk tier or days left (computed on read in the firm's zone). The source kinds
are `platform.filing_deadline_sources.SOURCE_KINDS`. `filing_deadline_alerts` is insert-only,
one row per (deadline, threshold, due date): the T-7 and T-1 notices' idempotency.

Revision ID: 0962
Revises: 0961
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0962"
down_revision = "0961"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,"""
_KEYS = """
            UNIQUE (tenant_id, id)"""
_KINDS = (
    "('tax_return', 'extension', 'estimate_batch', 'fiduciary_statement', 'election_window', "
    "'notice_response', 'envelope', 'close', 'assurance_report', 'form_5500', 'consent')"
)
_FD_COLUMNS = (
    "tenant_id",
    "source_kind",
    "source_ref",
    "client_id",
    "office_id",
    "service_line",
    "filing_label",
    "rule_key",
    "reference_set_version_ids",
    "original_due_on",
    "extension_form",
    "extension_filed_on",
    "extended_due_on",
    "due_on",
    "postponement_notice_id",
    "postponed_from",
    "internal_target_on",
    "owner_user_ids",
    "signer_user_id",
    "stage_code",
    "done_at",
    "work_item_id",
    "inputs_hash",
)

_KEYED = ("tenant_id", "source_kind", "source_ref", "filing_label")
_FD_UPDATE = (*(c for c in _FD_COLUMNS if c not in _KEYED), "computed_at")

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("filing_deadlines", f"""
            source_kind text NOT NULL CHECK (source_kind IN {_KINDS}),
            source_ref text NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 120),
            client_id uuid NULL,
            office_id uuid NULL,
            service_line text NOT NULL CHECK (service_line IN ('tax', 'audit', 'cas', 'advisory')),
            filing_label text NOT NULL CHECK (char_length(filing_label) BETWEEN 1 AND 80),
            rule_key text NULL CHECK (char_length(rule_key) <= 80),
            reference_set_version_ids uuid[] NOT NULL DEFAULT '{{}}',
            original_due_on date NOT NULL,
            extension_form text NULL CHECK (char_length(extension_form) <= 20),
            extension_filed_on date NULL,
            extended_due_on date NULL,
            due_on date NOT NULL,
            postponement_notice_id uuid NULL,
            postponed_from date NULL,
            internal_target_on date NULL,
            owner_user_ids uuid[] NOT NULL DEFAULT '{{}}',
            signer_user_id uuid NULL,
            stage_code text NOT NULL CHECK (stage_code ~ '^[a-z][a-z0-9_]{{0,39}}$'),
            done_at timestamptz NULL,
            work_item_id uuid NULL,
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT filing_deadlines_postponed
                CHECK ((postponement_notice_id IS NULL) = (postponed_from IS NULL)),
            CONSTRAINT filing_deadlines_extension
                CHECK (extended_due_on IS NULL OR extension_form IS NOT NULL),
            UNIQUE (tenant_id, source_kind, source_ref, filing_label),""",
     _FD_COLUMNS, _FD_UPDATE, False),
    ("filing_deadline_alerts", """
            filing_deadline_id uuid NOT NULL,
            threshold text NOT NULL CHECK (threshold IN ('t_minus_7', 't_minus_1')),
            due_on date NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (filing_deadline_id, threshold, due_on),
            FOREIGN KEY (tenant_id, filing_deadline_id)
                REFERENCES filing_deadlines (tenant_id, id),""",
     ("tenant_id", "filing_deadline_id", "threshold", "due_on"), (), True),
)  # fmt: skip


def upgrade() -> None:
    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    op.execute("CREATE INDEX filing_deadlines_window ON filing_deadlines (tenant_id, due_on)")
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
        else:
            op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
            op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # A row whose source disappeared is dropped by the recompute (T-08 §4.5): the read model is
    # the one practice table the app may delete from.
    op.execute(
        """
        CREATE FUNCTION filing_deadline_alerts_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'filing_deadline_alerts is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER filing_deadline_alerts_immutable BEFORE UPDATE ON filing_deadline_alerts "
        "FOR EACH ROW EXECUTE FUNCTION filing_deadline_alerts_immutable()"
    )


def downgrade() -> None:
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION filing_deadline_alerts_immutable()")
