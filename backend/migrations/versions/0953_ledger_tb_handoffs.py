"""Ledger TB hand-offs (T-06-T11; C12 v1; SPEC-702 F6, AC-29, AC-30; DEC-66, ADR-158;
DEC-5520). Expand-only.

- `tb_handoffs` (insert-only): one immutable version of a released or locked source's TB
  published to a tax return; a person's only (the actor GUCs, ADR-005); `UNIQUE (tenant_id,
  target_work_item_id, version_no)`. The current version is the highest with no supersession.
- `tb_handoff_supersessions`, `tb_handoff_account_choices`, `tb_handoff_schedules`,
  `tb_handoff_tax_items` (insert-only): what superseded a version and what travelled with it.

The hand-off references the source snapshot and never copies it (P-40); it writes nothing into
the source engagement, so P-43's archive guard on that engagement is untouched. Only
`ledger/tb_handoff.py` writes these tables (HANDOFF-001).

Revision ID: 0953
Revises: 0952
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0953"
down_revision = "0952"
branch_labels = None
depends_on = None

_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true))"
)
_CHILD = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            handoff_id uuid NOT NULL,"""
_CHILD_KEYS = """
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, handoff_id) REFERENCES tb_handoffs (tenant_id, id)"""
TABLES = (
    "tb_handoffs",
    "tb_handoff_supersessions",
    "tb_handoff_account_choices",
    "tb_handoff_schedules",
    "tb_handoff_tax_items",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "tb_handoffs": (
        "tenant_id", "client_id", "source_kind", "source_engagement_id", "source_work_item_id",
        "source_snapshot_id", "target_work_item_id", "version_no", "preview_hash",
        "book_income", "counts", "handed_off_by",
    ),
    "tb_handoff_supersessions": (
        "tenant_id", "handoff_id", "superseded_by_handoff_id", "reason", "detected_snapshot_id",
    ),
    "tb_handoff_account_choices": (
        "tenant_id", "handoff_id", "account_no", "account_name", "balance", "tax_line_code",
        "source", "suggestion_id", "needs_review",
    ),
    "tb_handoff_schedules": (
        "tenant_id", "handoff_id", "kind", "carried", "facts", "leadsheet_ref",
    ),
    "tb_handoff_tax_items": (
        "tenant_id", "handoff_id", "item_kind", "source_ref", "amount", "create_issue", "issue_id",
    ),
}  # fmt: skip


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
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
    op.execute(
        f"""
        CREATE TABLE tb_handoffs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            source_kind text NOT NULL
                CHECK (source_kind IN ('audit_release', 'review_release', 'close_lock')),
            source_engagement_id uuid NOT NULL,
            source_work_item_id uuid NOT NULL,
            source_snapshot_id uuid NOT NULL,
            target_work_item_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            preview_hash text NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{{64}}$'),
            book_income jsonb NOT NULL CHECK (jsonb_typeof(book_income) = 'object'),
            counts jsonb NOT NULL CHECK (jsonb_typeof(counts) = 'object'),
            handed_off_by uuid NOT NULL
                CHECK (handed_off_by::text = current_setting('app.actor_id', true)),
            handed_off_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, target_work_item_id, version_no),
            CHECK (source_work_item_id <> target_work_item_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, source_snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, id),
            FOREIGN KEY (target_work_item_id) REFERENCES tax_returns (work_item_id)
                ON DELETE RESTRICT,
            FOREIGN KEY (tenant_id, handed_off_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tb_handoff_supersessions ({_CHILD}
            superseded_by_handoff_id uuid NULL,
            reason text NOT NULL CHECK (reason IN ('tb_changed_after_release', 'rehandoff')),
            detected_snapshot_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, handoff_id),
            CHECK (superseded_by_handoff_id IS NULL OR superseded_by_handoff_id <> handoff_id),
            FOREIGN KEY (tenant_id, superseded_by_handoff_id)
                REFERENCES tb_handoffs (tenant_id, id),{_CHILD_KEYS}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tb_handoff_account_choices ({_CHILD}
            account_no text NOT NULL CHECK (char_length(account_no) BETWEEN 1 AND 64),
            account_name text NOT NULL CHECK (char_length(account_name) BETWEEN 1 AND 200),
            balance numeric(20, 2) NOT NULL,
            tax_line_code text NULL CHECK (char_length(tax_line_code) <= 80),
            source text NOT NULL CHECK (source IN ('prior_year', 'suggested', 'blank')),
            suggestion_id uuid NULL,
            needs_review boolean NOT NULL DEFAULT false,
            UNIQUE (tenant_id, handoff_id, account_no),
            CHECK (source <> 'blank' OR tax_line_code IS NULL),
            CHECK (source <> 'suggested' OR suggestion_id IS NOT NULL),{_CHILD_KEYS}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tb_handoff_schedules ({_CHILD}
            kind text NOT NULL
                CHECK (kind IN ('fixed_assets', 'accrued_liabilities', 'passed_adjustments')),
            carried boolean NOT NULL,
            facts jsonb NOT NULL CHECK (jsonb_typeof(facts) = 'object'),
            leadsheet_ref text NULL CHECK (char_length(leadsheet_ref) <= 80),
            UNIQUE (tenant_id, handoff_id, kind),{_CHILD_KEYS}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tb_handoff_tax_items ({_CHILD}
            item_kind text NOT NULL CHECK (item_kind IN ('passed_adjustment', 'book_tax_expense')),
            source_ref jsonb NOT NULL CHECK (jsonb_typeof(source_ref) = 'object'),
            amount numeric(20, 2) NOT NULL,
            create_issue boolean NOT NULL,
            issue_id uuid NULL,
            CHECK (create_issue OR issue_id IS NULL),{_CHILD_KEYS}
        )
        """
    )
    op.execute(
        "CREATE INDEX tb_handoffs_target ON tb_handoffs "
        "(tenant_id, target_work_item_id, version_no DESC)"
    )
    op.execute("CREATE INDEX tb_handoffs_source ON tb_handoffs (tenant_id, source_engagement_id)")
    for table in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, INSERTS[table])
        insert_only(op, table)
        _immutable(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    for table in TABLES:
        op.execute(f"DROP FUNCTION {table}_immutable()")
