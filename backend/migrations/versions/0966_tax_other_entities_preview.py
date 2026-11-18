"""Other entity workpapers and form preview (T-06-T14; SPEC-702 F5, F7; T-06 §4.2; DEC-5625).
Amber, expand-only; the pipeline runs it after 8 pm CT inside the window (P-29).

Ten tax tables on a return's work item with forced RLS, every return figure TRI (ADR-167):
`aaa_lines` and `shareholder_allocations` (1120-S), `tax_provisions`, `rate_recon_items` and
`deferred_tax_items` (1120 ASC 740), `functional_expense_lines` and `public_support_tests` (990),
`allocation_runs` (the time-study run), `form_page_renders` (derived, rebuildable) and
`form_diagnostics` (one per checkpoint and rule). Engine figures foot by CHECK: a Part IX row's
program + management and general + fundraising equals its total; a provision's current +
deferred equals its total.

Revision ID: 0966
Revises: 0965
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0966"
down_revision = "0965"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_KEYS = """
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT"""
_M = "numeric(20, 2)"
_PCT = "numeric(7, 4)"
_S = ("tenant_id", "engagement_id", "work_item_id")

# (table, body, insert columns, update columns)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("aaa_lines", f"""
            line_no smallint NOT NULL CHECK (line_no BETWEEN 1 AND 20),
            col_aaa {_M} NOT NULL DEFAULT 0,
            col_pti {_M} NOT NULL DEFAULT 0,
            col_e_and_p {_M} NOT NULL DEFAULT 0,
            col_oaa {_M} NOT NULL DEFAULT 0,
            source_ref jsonb NULL,
            UNIQUE (work_item_id, line_no),""",
     (*_S, "line_no", "col_aaa", "col_pti", "col_e_and_p", "col_oaa", "source_ref"),
     ("col_aaa", "col_pti", "col_e_and_p", "col_oaa", "source_ref")),
    ("shareholder_allocations", f"""
            partner_id uuid NOT NULL,
            shares integer NOT NULL CHECK (shares >= 0),
            days smallint NOT NULL CHECK (days BETWEEN 0 AND 366),
            pct {_PCT} NOT NULL CHECK (pct BETWEEN 0 AND 100),
            ordinary_income {_M} NOT NULL DEFAULT 0,
            interest {_M} NOT NULL DEFAULT 0,
            nondeductible {_M} NOT NULL DEFAULT 0,
            distributions {_M} NOT NULL DEFAULT 0,
            UNIQUE (work_item_id, partner_id),""",
     (*_S, "partner_id", "shares", "days", "pct", "ordinary_income", "interest", "nondeductible",
      "distributions"),
     ("shares", "days", "pct", "ordinary_income", "interest", "nondeductible", "distributions")),
    ("tax_provisions", f"""
            pretax_book_income {_M} NOT NULL,
            permanent_total {_M} NOT NULL DEFAULT 0,
            temporary_total {_M} NOT NULL DEFAULT 0,
            taxable_income {_M} NOT NULL,
            blended_rate {_PCT} NOT NULL CHECK (blended_rate BETWEEN 0 AND 100),
            current_tax {_M} NOT NULL,
            deferred_tax {_M} NOT NULL,
            total_provision {_M} NOT NULL,
            etr {_PCT} NULL,
            recon_status text NOT NULL CHECK (recon_status IN ('tie', 'off')),
            off_amount {_M} NOT NULL DEFAULT 0,
            CONSTRAINT tax_provisions_total CHECK (current_tax + deferred_tax = total_provision),
            CONSTRAINT tax_provisions_off CHECK ((recon_status = 'tie') = (off_amount = 0)),
            UNIQUE (work_item_id),""",
     (*_S, "pretax_book_income", "permanent_total", "temporary_total", "taxable_income",
      "blended_rate", "current_tax", "deferred_tax", "total_provision", "etr", "recon_status",
      "off_amount"),
     ("pretax_book_income", "permanent_total", "temporary_total", "taxable_income",
      "blended_rate", "current_tax", "deferred_tax", "total_provision", "etr", "recon_status",
      "off_amount")),
    ("rate_recon_items", f"""
            provision_id uuid NOT NULL,
            item_key text NOT NULL CHECK (item_key ~ '^[a-z0-9_.]{{1,40}}$'),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 200),
            amount {_M} NOT NULL,
            rate_effect {_PCT} NULL,
            classification text NOT NULL
                CHECK (classification IN ('permanent', 'temporary', 'rate', 'unclassified')),
            proposal_id uuid NULL,
            UNIQUE (provision_id, item_key),
            FOREIGN KEY (tenant_id, provision_id) REFERENCES tax_provisions (tenant_id, id),""",
     (*_S, "provision_id", "item_key", "description", "amount", "rate_effect", "classification",
      "proposal_id"),
     ("description", "amount", "rate_effect", "classification", "proposal_id")),
    ("deferred_tax_items", f"""
            provision_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('dta', 'dtl')),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            temporary_difference {_M} NOT NULL,
            rate {_PCT} NOT NULL CHECK (rate BETWEEN 0 AND 100),
            amount {_M} NOT NULL,
            FOREIGN KEY (tenant_id, provision_id) REFERENCES tax_provisions (tenant_id, id),""",
     (*_S, "provision_id", "kind", "label", "temporary_difference", "rate", "amount"),
     ("temporary_difference", "rate", "amount")),
    ("functional_expense_lines", f"""
            part_ix_line text NOT NULL CHECK (part_ix_line ~ '^[0-9]{{1,2}}[a-g]?$'),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            total {_M} NOT NULL,
            program {_M} NOT NULL DEFAULT 0,
            management_general {_M} NOT NULL DEFAULT 0,
            fundraising {_M} NOT NULL DEFAULT 0,
            allocation_basis text NOT NULL
                CHECK (allocation_basis IN ('direct', 'time_study', 'square_footage', 'other')),
            time_study jsonb NULL
                CHECK (time_study IS NULL OR jsonb_typeof(time_study) = 'object'),
            source_memo_evidence_version_id uuid NULL,
            CONSTRAINT functional_expense_lines_crossfoot
                CHECK (program + management_general + fundraising = total),
            UNIQUE (work_item_id, part_ix_line),""",
     (*_S, "part_ix_line", "label", "total", "program", "management_general", "fundraising",
      "allocation_basis", "time_study", "source_memo_evidence_version_id"),
     ("label", "total", "program", "management_general", "fundraising", "allocation_basis",
      "time_study", "source_memo_evidence_version_id")),
    ("public_support_tests", f"""
            years int4range NOT NULL,
            public_support {_M} NOT NULL CHECK (public_support >= 0),
            total_support {_M} NOT NULL CHECK (total_support > 0),
            pct {_PCT} NOT NULL CHECK (pct BETWEEN 0 AND 100),
            threshold_met boolean NOT NULL,
            CONSTRAINT public_support_tests_share CHECK (public_support <= total_support),
            UNIQUE (work_item_id, years),""",
     (*_S, "years", "public_support", "total_support", "pct", "threshold_met"),
     ("public_support", "total_support", "pct", "threshold_met")),
    ("allocation_runs", """
            run_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'proposed', 'approved', 'failed')),
            proposal_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (work_item_id, run_id),""",
     (*_S, "run_id", "status", "proposal_id"), ("status", "proposal_id")),
    ("form_page_renders", """
            checkpoint_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            page_key text NOT NULL CHECK (page_key ~ '^[a-z0-9_.-]{1,60}$'),
            render_hash text NOT NULL CHECK (render_hash ~ '^[0-9a-f]{64}$'),
            generated_document_version_id uuid NULL,
            status text NOT NULL CHECK (status IN ('rendering', 'ready', 'failed')),
            UNIQUE (work_item_id, checkpoint_id, template_version_id, page_key),""",
     (*_S, "checkpoint_id", "template_version_id", "page_key", "render_hash",
      "generated_document_version_id", "status"),
     ("render_hash", "generated_document_version_id", "status")),
    ("form_diagnostics", """
            checkpoint_id uuid NOT NULL,
            rule_key text NOT NULL CHECK (rule_key ~ '^[a-z0-9_.-]{1,80}$'),
            source text NOT NULL CHECK (source IN ('accrued', 'engine')),
            severity text NOT NULL CHECK (severity IN ('blocking', 'warning', 'info')),
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'clear')),
            issue_id uuid NULL,
            facts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(facts) = 'object'),
            engine_import_id uuid NULL,
            UNIQUE (work_item_id, checkpoint_id, rule_key),""",
     (*_S, "checkpoint_id", "rule_key", "source", "severity", "status", "issue_id", "facts",
      "engine_import_id"),
     ("severity", "status", "issue_id", "facts")),
)  # fmt: skip


def upgrade() -> None:
    for table, body, _ins, _upd in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    for table, _body, ins, upd in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # Renders are derived and rebuildable (T-06 §4.2): the app may drop and rebuild them.
    op.execute("GRANT DELETE ON form_page_renders TO abacus_app")


def downgrade() -> None:
    for table, _body, _ins, _upd in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
