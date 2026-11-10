"""P-11-T33: per-tenant daily OCR page caps (P-11 §cost, AC7.2, R9; OQ-10; DEC-2715).

The OCR gate's daily cap was one constant for every firm (P-11-T25: 5,000 pages, OQ-10). A firm's
cap may now differ: each change is a new insert-only `ocr_daily_caps` row and the latest row is
the firm's cap (no row: the default). R9 says a cap is raised "by both founders", so a row above
the default names two distinct operators; lowering needs one. Only a platform operator's ops
command writes it: `set_by_kind` defaults from the session's `app.actor_kind`, the app role may
not insert it, and the CHECK refuses anything but `system`, so no firm session (a person or the
Agent) can raise its own cap. Bounds 1 to 100,000 pages a day.

Revision ID: 0714
Revises: 0713
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0714"
down_revision = "0713"
branch_labels = None
depends_on = None

DEFAULT_CAP = 5000  # OQ-10; abacus.modules.evidence.ocr_gate.DAILY_PAGE_CAP
INSERTS = ("tenant_id", "daily_pages", "raised_by", "second_by", "reason")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ocr_daily_caps (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            daily_pages integer NOT NULL CHECK (daily_pages BETWEEN 1 AND 100000),
            raised_by text NOT NULL CHECK (char_length(raised_by) BETWEEN 1 AND 100),
            second_by text NULL CHECK (char_length(second_by) BETWEEN 1 AND 100),
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 10 AND 500),
            set_by_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true),
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT ocr_daily_caps_platform_only CHECK (set_by_kind = 'system'),
            CONSTRAINT ocr_daily_caps_raise_needs_two CHECK (
                daily_pages <= {DEFAULT_CAP}
                OR (second_by IS NOT NULL AND lower(second_by) <> lower(raised_by))
            )
        )
        """
    )
    tenant_table(op, "ocr_daily_caps")
    insert_only(op, "ocr_daily_caps")
    insert_columns(op, "ocr_daily_caps", INSERTS)
    op.execute("REVOKE TRUNCATE ON ocr_daily_caps FROM abacus_app")
    op.execute(
        "CREATE TRIGGER ocr_daily_caps_immutable BEFORE UPDATE OR DELETE ON ocr_daily_caps "
        "FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
    )
    op.execute(
        "CREATE TRIGGER ocr_daily_caps_no_truncate BEFORE TRUNCATE ON ocr_daily_caps "
        "FOR EACH STATEMENT EXECUTE FUNCTION trust_kit_immutable()"
    )
    op.execute("CREATE INDEX ocr_daily_caps_latest ON ocr_daily_caps (tenant_id, set_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE ocr_daily_caps")
