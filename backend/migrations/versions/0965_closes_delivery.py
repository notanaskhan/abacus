"""Closes delivery (C-02-T16; SPEC-701; C-02 §4.2 NNNN_closes_delivery; DEC-5620). Amber,
expand-only; the pipeline runs it after 8 pm CT inside the window (P-29).

Four closes tables with forced RLS: `close_deliverables` (one per close; the package's current
state), insert-only `close_deliverable_versions` (each generated package version; its
`content_hash` is what a reviewer's sign-off covers), insert-only `close_reopenings` (a reason is
required) and insert-only `tax_handoffs` (C12 hand-offs from a locked December close). A
hand-off is never edited: a newer row supersedes it, and `superseded_by_id` is set only by the
superseding row's trigger (`tax_handoffs_supersede`), once, under a transaction-local flag that
only that trigger sets.

The CAS statement-line catalogue is template content: it loads through the methodology import
endpoint (C-02-T16 acceptance), never as rows in this migration.

Revision ID: 0965
Revises: 0964
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0965"
down_revision = "0964"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,"""
_KEYS = """
            UNIQUE (tenant_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)),"
)
_CLOSE_FK = """
            FOREIGN KEY (close_id) REFERENCES closes (work_item_id),"""

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("close_deliverables", f"""
            close_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            current_version_no integer NOT NULL DEFAULT 0 CHECK (current_version_no >= 0),
            status text NOT NULL DEFAULT 'drafting'
                CHECK (status IN ('drafting', 'draft', 'released', 'approved_by_client')),
            released_by uuid NULL,
            released_at timestamptz NULL,
            c10_deliverable_ref uuid NULL,
            c18_approval_ref uuid NULL,
            client_approved_by_contact_id uuid NULL,
            client_approved_at timestamptz NULL,
            CONSTRAINT close_deliverables_released
                CHECK ((released_at IS NULL) = (released_by IS NULL)),
            CONSTRAINT close_deliverables_client
                CHECK ((client_approved_at IS NULL) = (client_approved_by_contact_id IS NULL)),
            UNIQUE (tenant_id, close_id),{_CLOSE_FK}""",
     ("tenant_id", "close_id", "work_item_id"),
     ("current_version_no", "status", "released_by", "released_at", "c10_deliverable_ref",
      "c18_approval_ref", "client_approved_by_contact_id", "client_approved_at"), False),
    ("close_deliverable_versions", """
            deliverable_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            sections jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
            cas_answer boolean NOT NULL,
            route text NOT NULL CHECK (route IN
                ('ar_c_70_preparation', 'cas_by_product', 'standalone_letter')),
            legend_key text NULL CHECK (char_length(legend_key) <= 60),
            ssars_settings_version_id uuid NULL,
            posted_tb_ref jsonb NOT NULL CHECK (jsonb_typeof(posted_tb_ref) = 'object'),
            commentary jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(commentary) = 'object'),
            generated_document_ids uuid[] NOT NULL DEFAULT '{}',
            run_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            studio_version text NULL CHECK (char_length(studio_version) <= 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (deliverable_id, version_no),
            FOREIGN KEY (tenant_id, deliverable_id)
                REFERENCES close_deliverables (tenant_id, id),""",
     ("tenant_id", "deliverable_id", "version_no", "sections", "cas_answer", "route",
      "legend_key", "ssars_settings_version_id", "posted_tb_ref", "commentary",
      "generated_document_ids", "run_id", "content_hash", "studio_version"), (), True),
    ("close_reopenings", f"""
            close_id uuid NOT NULL,
            reopened_by uuid NOT NULL,
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 1000),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}{_CLOSE_FK}""",
     ("tenant_id", "close_id", "reopened_by", "reason"), (), True),
    ("tax_handoffs", f"""
            close_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            version_no text NOT NULL CHECK (version_no ~ '^TB v[0-9]{{1,3}}$'),
            tb_snapshot_id uuid NOT NULL,
            target_tax_return_id uuid NOT NULL,
            engine text NOT NULL CHECK (char_length(engine) BETWEEN 1 AND 40),
            schedules jsonb NOT NULL CHECK (jsonb_typeof(schedules) = 'array'),
            items jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(items) = 'array'),
            c12_ref uuid NULL,
            created_tax_issue_ids uuid[] NOT NULL DEFAULT '{{}}',
            handed_off_by uuid NOT NULL,
            handed_off_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            supersedes_id uuid NULL,
            superseded_by_id uuid NULL,
            {_HUMAN}
            CONSTRAINT tax_handoffs_not_self CHECK (supersedes_id IS DISTINCT FROM id),
            UNIQUE (tenant_id, close_id, client_entity_id, version_no),{_CLOSE_FK}""",
     ("tenant_id", "close_id", "client_entity_id", "version_no", "tb_snapshot_id",
      "target_tax_return_id", "engine", "schedules", "items", "c12_ref", "created_tax_issue_ids",
      "handed_off_by", "supersedes_id"), (), True),
)  # fmt: skip


def _immutable(table: str, *, allow_supersede: bool = False) -> None:
    allow = (
        """
            IF TG_OP = 'UPDATE' AND current_setting('app.tax_handoff_supersede', true) = 'on'
               AND OLD.superseded_by_id IS NULL AND NEW.superseded_by_id IS NOT NULL
               AND (to_jsonb(NEW) - 'superseded_by_id') = (to_jsonb(OLD) - 'superseded_by_id') THEN
                RETURN NEW;
            END IF;"""
        if allow_supersede
        else ""
    )
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN{allow}
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def upgrade() -> None:
    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    op.execute(
        "ALTER TABLE tax_handoffs ADD CONSTRAINT tax_handoffs_supersedes_fk "
        "FOREIGN KEY (tenant_id, supersedes_id) REFERENCES tax_handoffs (tenant_id, id)"
    )
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
            _immutable(table, allow_supersede=table == "tax_handoffs")
        else:
            op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
            op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # A newer hand-off marks the one it supersedes; only this trigger writes `superseded_by_id`.
    op.execute(
        """
        CREATE FUNCTION tax_handoffs_supersede() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.supersedes_id IS NOT NULL THEN
                PERFORM set_config('app.tax_handoff_supersede', 'on', true);
                UPDATE tax_handoffs SET superseded_by_id = NEW.id
                 WHERE tenant_id = NEW.tenant_id AND id = NEW.supersedes_id
                   AND superseded_by_id IS NULL;
                PERFORM set_config('app.tax_handoff_supersede', 'off', true);
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION tax_handoffs_supersede() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER tax_handoffs_supersede AFTER INSERT ON tax_handoffs "
        "FOR EACH ROW EXECUTE FUNCTION tax_handoffs_supersede()"
    )


def downgrade() -> None:
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION tax_handoffs_supersede()")
    for table, _body, _ins, _upd, io in TABLES:
        if io:
            op.execute(f"DROP FUNCTION {table}_immutable()")
