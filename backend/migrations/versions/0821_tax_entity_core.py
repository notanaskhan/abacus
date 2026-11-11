"""T-05-T17 (S37; TASK-7304; T-05 §4.2 M1; DEC-4304): the entity return core, expand-only.

Seven new tables owned by `tax` and one nullable column on T-02's `k1_packages`; no live-path code
reads them yet (they run dark). Every row carries its tenant, engagement and the return's work
item (`work_item_id` is the `tax_returns` row, 0089), so `tenant_table()` attaches forced RLS,
`tenant_isolation` and the `archived_guard`.

- `entity_return_profiles`: one per entity return, edited through the service with
  `version_no`; the EIN stays on the client entity (sealed, P-12).
- `partners` (TIN columns come with T-05-T22's M3), `ownership_periods` (percentages
  numeric(9,6) between 0 and 100; Σ profit = 100.000000 per period is code's), `interest_transfers`
  (transferred capital is E7's, never stored).
- `allocation_structures`: insert-only versions. A decision is a new version row; `approved` may
  only be written by a person (`decided_actor_kind = 'human'`, bound to the session GUCs, the 0023
  pattern). Proration takes the calendar-day convention only.
- `allocation_rungs` (per structure, by priority) and insert-only `allocation_results` (E5's
  output per partner, period and rung).
- `k1_packages.partner_id` (nullable): which partner a draft K-1 is for.

The pipeline runs it after 8 pm CT inside the window (P-29).

Revision ID: 0821
Revises: 0820
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0821"
down_revision = "0820"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT"""
_PCT = "numeric(9,6) NOT NULL CHECK ({col} >= 0 AND {col} <= 100)"
_SHA = "~ '^[0-9a-f]{64}$'"
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"

IMMUTABLE = ("allocation_structures", "allocation_results")
TABLES = (
    "entity_return_profiles",
    "partners",
    "ownership_periods",
    "interest_transfers",
    "allocation_structures",
    "allocation_rungs",
    "allocation_results",
)
_S = ("tenant_id", "engagement_id", "work_item_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "entity_return_profiles": (
        *_S, "id", "principal_activity", "business_code", "accounting_method", "books_basis",
        "partnership_representative_contact_id", "designated_individual_contact_id",
        "ledger_source", "prior_year_return_id",
    ),
    "partners": (
        *_S, "id", "kind", "display_name", "entity_kind", "admitted_on", "withdrawn_on",
        "related_client_entity_id", "portal_contact_id", "ord",
    ),
    "ownership_periods": (
        *_S, "id", "partner_id", "period_from", "period_to", "profit_pct", "loss_pct",
        "capital_pct",
    ),
    "interest_transfers": (
        *_S, "id", "transfer_date", "from_partner_id", "to_partner_id", "points", "price",
        "citation_ids",
    ),
    "allocation_structures": (
        *_S, "id", "version_no", "status", "kind", "method", "convention", "income_to_allocate",
        "distributable", "proposed_by_kind", "proposal_id", "content_hash", "engine_name",
        "engine_version", "inputs_hash", "citation_ids", "supersedes_id",
    ),
    "allocation_rungs": (
        *_S, "id", "structure_id", "priority", "rule_type", "params",
    ),
    "allocation_results": (
        *_S, "structure_id", "partner_id", "period_key", "rung_priority", "amount",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "entity_return_profiles": (
        "principal_activity", "business_code", "accounting_method", "books_basis",
        "partnership_representative_contact_id", "designated_individual_contact_id",
        "ledger_source", "prior_year_return_id", "version_no", "updated_at",
    ),
    "partners": (
        "kind", "display_name", "entity_kind", "admitted_on", "withdrawn_on",
        "related_client_entity_id", "portal_contact_id", "ord", "updated_at",
    ),
    "ownership_periods": ("period_from", "period_to", "profit_pct", "loss_pct", "capital_pct"),
    "interest_transfers": ("transfer_date", "points", "price", "citation_ids"),
    "allocation_rungs": ("priority", "rule_type", "params"),
}  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE entity_return_profiles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            principal_activity text NULL CHECK (char_length(principal_activity) <= 200),
            business_code text NULL CHECK (business_code ~ '^[0-9]{{6}}$'),
            accounting_method text NULL
                CHECK (accounting_method IN ('cash', 'accrual', 'other')),
            books_basis text NULL CHECK (books_basis IN ('income_tax', 'gaap', 'cash', 'other')),
            partnership_representative_contact_id uuid NULL,
            designated_individual_contact_id uuid NULL,
            ledger_source text NULL CHECK (ledger_source IN ('connection', 'file')),
            prior_year_return_id uuid NULL REFERENCES tax_returns (work_item_id),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id),
            FOREIGN KEY (tenant_id, partnership_representative_contact_id)
                REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, designated_individual_contact_id)
                REFERENCES contacts (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE partners (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL CHECK (kind IN ('gp', 'lp', 'member', 'shareholder')),
            display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 200),
            entity_kind text NOT NULL CHECK (entity_kind IN ('individual', 'llc', 'partnership',
                                                             'corporation', 'trust', 'estate',
                                                             'other')),
            admitted_on date NULL,
            withdrawn_on date NULL CHECK (withdrawn_on IS NULL OR admitted_on IS NULL
                                          OR withdrawn_on >= admitted_on),
            related_client_entity_id uuid NULL,
            portal_contact_id uuid NULL,
            ord integer NOT NULL DEFAULT 0 CHECK (ord >= 0),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, display_name),
            FOREIGN KEY (tenant_id, related_client_entity_id)
                REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, portal_contact_id)
                REFERENCES contacts (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ownership_periods (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            partner_id uuid NOT NULL,
            period_from date NOT NULL,
            period_to date NOT NULL CHECK (period_to >= period_from),
            profit_pct {_PCT.format(col="profit_pct")},
            loss_pct {_PCT.format(col="loss_pct")},
            capital_pct {_PCT.format(col="capital_pct")},
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (partner_id, period_from),
            FOREIGN KEY (tenant_id, partner_id) REFERENCES partners (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE interest_transfers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            transfer_date date NOT NULL,
            from_partner_id uuid NOT NULL,
            to_partner_id uuid NOT NULL CHECK (to_partner_id <> from_partner_id),
            points numeric(9,6) NOT NULL CHECK (points > 0 AND points <= 100),
            price numeric(18,2) NULL CHECK (price IS NULL OR price >= 0),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            {_CREATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, from_partner_id) REFERENCES partners (tenant_id, id),
            FOREIGN KEY (tenant_id, to_partner_id) REFERENCES partners (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE allocation_structures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            version_no integer NOT NULL CHECK (version_no >= 1),
            status text NOT NULL
                CHECK (status IN ('editing', 'pending_approval', 'approved', 'superseded')),
            kind text NOT NULL CHECK (kind IN ('straight_percentage', 'targeted_waterfall')),
            method text NOT NULL CHECK (method IN ('interim_closing', 'proration')),
            convention text NOT NULL
                CHECK (convention IN ('calendar_day', 'semi_monthly', 'monthly')),
            income_to_allocate numeric(18,2) NULL,
            distributable numeric(18,2) NULL,
            proposed_by_kind text NOT NULL CHECK (proposed_by_kind IN ('human', 'agent')),
            proposal_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            engine_name text NULL CHECK (char_length(engine_name) <= 80),
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash IS NULL OR inputs_hash {_SHA}),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            supersedes_id uuid NULL,
            decided_actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true),
            decided_actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, version_no),
            CHECK (method <> 'proration' OR convention = 'calendar_day'),
            -- Human-only approval (the 0023 pattern): an approved version is a person's own row.
            CHECK (status <> 'approved' OR (
                decided_actor_kind = 'human'
                AND decided_actor_kind = current_setting('app.actor_kind', true)
                AND decided_actor_id = current_setting('app.actor_id', true))),
            FOREIGN KEY (tenant_id, supersedes_id)
                REFERENCES allocation_structures (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE allocation_rungs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            structure_id uuid NOT NULL,
            priority integer NOT NULL CHECK (priority >= 1),
            rule_type text NOT NULL CHECK (rule_type IN ('straight_pct', 'return_of_capital',
                                                         'preferred_return', 'catch_up',
                                                         'promote', 'residual')),
            params jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(params) = 'object'),
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (structure_id, priority),
            FOREIGN KEY (tenant_id, structure_id)
                REFERENCES allocation_structures (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE allocation_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            structure_id uuid NOT NULL,
            partner_id uuid NOT NULL,
            period_key text NOT NULL CHECK (period_key ~ '^[a-z0-9][a-z0-9:_-]{{0,39}}$'),
            rung_priority integer NULL CHECK (rung_priority IS NULL OR rung_priority >= 1),
            amount numeric(18,2) NOT NULL,
            {_CREATED},
            UNIQUE (structure_id, partner_id, period_key, rung_priority),
            FOREIGN KEY (tenant_id, structure_id)
                REFERENCES allocation_structures (tenant_id, id),
            FOREIGN KEY (tenant_id, partner_id) REFERENCES partners (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION tax_entity_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: an allocation structure decision is a new version and '
                'a result is never changed' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION tax_entity_rows_immutable() FROM PUBLIC")
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table in IMMUTABLE:
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION tax_entity_rows_immutable()"
        )
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute("ALTER TABLE k1_packages ADD COLUMN partner_id uuid NULL")
    op.execute(
        "ALTER TABLE k1_packages ADD CONSTRAINT k1_packages_partner "
        "FOREIGN KEY (tenant_id, partner_id) REFERENCES partners (tenant_id, id)"
    )
    op.execute("GRANT INSERT (partner_id), UPDATE (partner_id) ON k1_packages TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE k1_packages DROP CONSTRAINT k1_packages_partner")
    op.execute("ALTER TABLE k1_packages DROP COLUMN partner_id")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION tax_entity_rows_immutable()")
