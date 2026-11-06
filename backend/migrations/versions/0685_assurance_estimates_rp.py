"""A-05 M8: estimates, related parties and parties in interest (A-05-T48; A-05 §4.2; AUD-27).

AUD-27's tables, in `assurance`, ahead of the Thu Dec 23, 2027 train. Expand-only.

- `accounting_estimates` and its `estimate_components`; a conclusion is the EP's decision card.
- `related_parties`: a screen-out needs its reason. `related_party_search_runs` holds evidence
  references only, never a director's name; the agent proposes and never concludes (A-05-T56).
- `parties_in_interest` copies no amount from a late remittance. `v_prohibited_transactions` is a
  read over `ebp_late_remittances`, so a corrected figure there is the figure here.

Revision ID: 0685
Revises: 0684
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0685"
down_revision = "0684"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_MONEY = "numeric(18, 2)"
_STATUS = "text NOT NULL DEFAULT 'unevaluated'"
_BY = "created_by_kind text NOT NULL CHECK (created_by_kind IN ('human', 'agent', 'system'))"
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_UPDATED = "updated_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_VERSION = "version integer NOT NULL DEFAULT 1 CHECK (version >= 1)"
_SCOPED = ("tenant_id", "engagement_id", "work_item_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "accounting_estimates": (
        *_SCOPED, "id", "account_ref", "name", "balance", "significant_risk", "method",
        "rollforward", "retrospective", "range_low", "range_high", "bias", "disclosure_ref",
        "je_ref", "created_by_kind",
    ),
    "estimate_components": (
        *_SCOPED, "id", "estimate_id", "label", "amount", "position",
    ),
    "related_parties": (
        *_SCOPED, "id", "name_sealed", "display_ref", "source", "relationship", "inquiry_ref",
        "created_by_kind",
    ),
    "related_party_search_runs": (
        *_SCOPED, "id", "run_id", "inputs", "candidates", "vendors_searched", "customers_searched",
    ),
    "parties_in_interest": (
        *_SCOPED, "id", "name", "erisa_relationship", "transactions", "exemption", "reporting",
        "created_by_kind",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "accounting_estimates": (
        "account_ref", "balance", "significant_risk", "method", "rollforward", "retrospective",
        "range_low", "range_high", "bias", "disclosure_ref", "je_ref", "status",
        "decision_card_id", "finding_id", "version", "updated_at",
    ),
    "estimate_components": ("label", "amount", "position"),
    "related_parties": (
        "status", "screened_out_reason", "screened_out_by", "screened_out_at", "finding_id",
        "inquiry_ref", "version", "updated_at",
    ),
    "parties_in_interest": (
        "erisa_relationship", "transactions", "exemption", "reporting", "version", "updated_at",
    ),
}  # fmt: skip
_TABLES = (
    "parties_in_interest",
    "related_party_search_runs",
    "related_parties",
    "estimate_components",
    "accounting_estimates",
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE accounting_estimates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            account_ref text NULL CHECK (length(account_ref) <= 200),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
            balance {_MONEY} NULL,
            significant_risk boolean NOT NULL DEFAULT false,
            method jsonb NULL,
            rollforward jsonb NULL,
            retrospective jsonb NULL,
            range_low {_MONEY} NULL,
            range_high {_MONEY} NULL,
            bias jsonb NULL,
            disclosure_ref text NULL CHECK (length(disclosure_ref) <= 200),
            je_ref text NULL CHECK (length(je_ref) <= 200),
            status {_STATUS}
                CHECK (status IN ('unevaluated', 'evaluated', 'exception')),
            decision_card_id uuid NULL,
            finding_id uuid NULL,
            {_BY},
            {_VERSION},
            {_CREATED},
            {_UPDATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, id),{_SCOPE_FK},
            FOREIGN KEY (tenant_id, decision_card_id) REFERENCES decision_cards (tenant_id, id),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id),
            CONSTRAINT accounting_estimates_range
                CHECK (range_low IS NULL OR range_high IS NULL OR range_low <= range_high),
            CONSTRAINT accounting_estimates_exception_has_finding
                CHECK (status <> 'exception' OR finding_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estimate_components (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            estimate_id uuid NOT NULL,
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 300),
            amount {_MONEY} NOT NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            {_CREATED},
            FOREIGN KEY (tenant_id, work_item_id, estimate_id)
                REFERENCES accounting_estimates (tenant_id, work_item_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE related_parties (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            name_sealed bytea NULL,
            display_ref text NULL CHECK (length(display_ref) <= 300),
            source text NOT NULL CHECK (source IN ('client_list', 'agent_search', 'manual')),
            relationship text NULL CHECK (length(relationship) <= 200),
            status {_STATUS}
                CHECK (status IN ('unevaluated', 'evaluated', 'exception', 'screened_out')),
            screened_out_reason text NULL CHECK (length(screened_out_reason) <= 1000),
            screened_out_by uuid NULL,
            screened_out_at timestamptz NULL,
            finding_id uuid NULL,
            inquiry_ref text NULL CHECK (length(inquiry_ref) <= 200),
            {_BY},
            {_VERSION},
            {_CREATED},
            {_UPDATED},
            UNIQUE (tenant_id, id),{_SCOPE_FK},
            FOREIGN KEY (tenant_id, screened_out_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id),
            CONSTRAINT related_parties_screen_out CHECK (
                (status = 'screened_out') = (screened_out_reason IS NOT NULL)
                AND (status = 'screened_out') = (screened_out_by IS NOT NULL)
            ),
            CONSTRAINT related_parties_exception_has_finding
                CHECK (status <> 'exception' OR finding_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE related_party_search_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            run_id uuid NOT NULL,
            inputs jsonb NOT NULL,
            candidates jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(candidates) = 'array'),
            vendors_searched integer NOT NULL DEFAULT 0 CHECK (vendors_searched >= 0),
            customers_searched integer NOT NULL DEFAULT 0 CHECK (customers_searched >= 0),
            {_CREATED},
            UNIQUE (tenant_id, id),{_SCOPE_FK},
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE parties_in_interest (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
            erisa_relationship text NOT NULL CHECK (length(erisa_relationship) BETWEEN 1 AND 200),
            transactions jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(transactions) = 'array'),
            exemption text NULL CHECK (length(exemption) <= 200),
            reporting text NULL CHECK (length(reporting) <= 200),
            {_BY},
            {_VERSION},
            {_CREATED},
            {_UPDATED},
            UNIQUE (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    for table, columns in INSERTS.items():
        tenant_table(op, table)
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute("REVOKE UPDATE, DELETE ON related_party_search_runs FROM abacus_app")
    op.execute(
        """
        CREATE FUNCTION related_party_search_runs_immutable() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'related_party_search_runs is insert-only'
                USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION related_party_search_runs_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER related_party_search_runs_immutable BEFORE UPDATE OR DELETE "
        "ON related_party_search_runs FOR EACH ROW "
        "EXECUTE FUNCTION related_party_search_runs_immutable()"
    )
    op.execute(
        """
        CREATE VIEW v_prohibited_transactions WITH (security_invoker = true) AS
            SELECT tenant_id, engagement_id, work_item_id, id AS late_remittance_id, payroll_id,
                   principal, due_on, deposited_on, business_days_late, lost_earnings,
                   correction_status, form_5330_status, excise_exposure, finding_id
              FROM ebp_late_remittances
        """
    )
    op.execute("GRANT SELECT ON v_prohibited_transactions TO abacus_app")


def downgrade() -> None:
    op.execute("DROP VIEW v_prohibited_transactions")
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION related_party_search_runs_immutable()")
