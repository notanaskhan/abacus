"""Tax entity depth (T-06-T10; SPEC-702 F1 to F4; T-06 §4.2; DEC-5519). Expand-only; the pipeline
runs it after 8 pm CT inside the window (P-29).

Thirteen tax tables on a return's work item, every one TRI (ADR-167) with forced RLS:
`tax_properties`, `fixed_assets` (the current row) with insert-only `fixed_asset_versions` (each
approved change's full row image) and `fixed_asset_dispositions`, `book_tax_items`,
`basis_schedules`, `liability_shares`, `state_apportionments`, `sourcing_positions`,
`ptet_elections`, insert-only `ptet_payments`, `ptet_partner_credits` and `nexus_facts`.

The CHECKs the engines' figures must meet: `accum_eop = accum_bop + current_year` on every asset;
(a) + (b) + (c) = (d) on every book-tax row; a share between 0 and 100. Engine outputs carry
`engine_name`, `engine_version`, `inputs_hash` and `computed_at` (chapter 03 §10.1). An approved
row is never edited in place: a new `fixed_asset_versions` row is inserted and the current row
replaced with `version + 1` in the same unit of work.

Revision ID: 0952
Revises: 0951
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0952"
down_revision = "0951"
branch_labels = None
depends_on = None

_SCOPE = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_KEYS = """
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT"""
_ENGINE = """
            engine_name text NOT NULL CHECK (engine_name ~ '^E[0-9]{1,2}$'),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),"""
_MONEY = "numeric(20, 2)"
_STATE = "text NOT NULL CHECK (state ~ '^[A-Z]{2}$')"

TABLES: dict[str, str] = {
    "tax_properties": f"""
            code text NOT NULL CHECK (code ~ '^[a-z][a-z0-9_]{{0,39}}$'),
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
            city text NULL CHECK (char_length(city) <= 100),
            state text NULL CHECK (state ~ '^[A-Z]{{2}}$'),
            use text NOT NULL CHECK (use IN ('commercial', 'residential', 'mixed', 'land_only')),
            land_value {_MONEY} NOT NULL DEFAULT 0 CHECK (land_value >= 0),
            form8825_property_no integer NULL CHECK (form8825_property_no >= 1),
            source_ref jsonb NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (work_item_id, code),""",
    "fixed_assets": f"""
            property_id uuid NULL,
            asset_no integer NOT NULL CHECK (asset_no >= 1),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 200),
            placed_in_service_on date NOT NULL,
            acquired_on date NULL,
            binding_contract_on date NULL,
            date_citation_id uuid NULL,
            cost {_MONEY} NOT NULL CHECK (cost >= 0),
            recovery_class text NOT NULL CHECK (recovery_class IN
                ('3', '5', '7', '10', '15', '20', '27_5', '39', 'land', 'nondepreciable')),
            method text NOT NULL CHECK (method IN ('sl', 'db150', 'db200')),
            convention text NOT NULL CHECK (convention IN ('mm', 'hy', 'mq')),
            bonus_pct numeric(5, 2) NOT NULL DEFAULT 0 CHECK (bonus_pct BETWEEN 0 AND 100),
            sec179 {_MONEY} NOT NULL DEFAULT 0 CHECK (sec179 >= 0 AND sec179 <= cost),
            accum_bop {_MONEY} NOT NULL DEFAULT 0 CHECK (accum_bop >= 0),
            current_year {_MONEY} NOT NULL DEFAULT 0 CHECK (current_year >= 0),
            accum_eop {_MONEY} NOT NULL DEFAULT 0,
            book_equals_tax boolean NOT NULL DEFAULT true,
            status text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'flag', 'check')),
            status_reason_code text NULL CHECK (char_length(status_reason_code) <= 60),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),{_ENGINE}
            CONSTRAINT fixed_assets_crossfoot CHECK (accum_eop = accum_bop + current_year),
            CONSTRAINT fixed_assets_real_property_sl_mm CHECK (
                recovery_class NOT IN ('27_5', '39') OR (method = 'sl' AND convention = 'mm')
            ),
            UNIQUE (work_item_id, asset_no),""",
    "fixed_asset_versions": """
            asset_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            image jsonb NOT NULL CHECK (jsonb_typeof(image) = 'object'),
            proposal_id uuid NULL,
            changed_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, asset_id, version),""",
    "fixed_asset_dispositions": f"""
            asset_id uuid NOT NULL,
            disposed_on date NOT NULL,
            proceeds {_MONEY} NOT NULL CHECK (proceeds >= 0),
            gain_loss {_MONEY} NOT NULL,
            recapture_1245 {_MONEY} NOT NULL DEFAULT 0 CHECK (recapture_1245 >= 0),
            unrecaptured_1250 {_MONEY} NOT NULL DEFAULT 0 CHECK (unrecaptured_1250 >= 0),
            created_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),""",
    "book_tax_items": f"""
            schedule text NOT NULL CHECK (schedule IN ('m3_part2', 'm3_part3', 'm1')),
            line_key text NOT NULL CHECK (line_key ~ '^[a-z0-9_.]{{1,40}}$'),
            account_no text NULL CHECK (char_length(account_no) <= 40),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 200),
            col_a {_MONEY} NOT NULL DEFAULT 0,
            col_b {_MONEY} NOT NULL DEFAULT 0,
            col_c {_MONEY} NOT NULL DEFAULT 0,
            col_d {_MONEY} NOT NULL DEFAULT 0,
            kind text NOT NULL CHECK (kind IN ('temporary', 'permanent')),
            source_ref jsonb NULL,{_ENGINE}
            CONSTRAINT book_tax_items_foot CHECK (col_a + col_b + col_c = col_d),""",
    "basis_schedules": f"""
            partner_id uuid NOT NULL,
            tax_capital {_MONEY} NOT NULL,
            s752_share {_MONEY} NOT NULL,
            outside_basis {_MONEY} NOT NULL,
            inside_share {_MONEY} NOT NULL,
            difference {_MONEY} NOT NULL,
            s743b_placeholder {_MONEY} NOT NULL DEFAULT 0,
            status text NOT NULL CHECK (status IN ('reconciled', 'off')),{_ENGINE}
            CONSTRAINT basis_schedules_difference
                CHECK (difference = outside_basis - inside_share),
            CONSTRAINT basis_schedules_status CHECK ((status = 'reconciled') = (difference = 0)),
            UNIQUE (work_item_id, partner_id),""",
    "liability_shares": f"""
            partner_id uuid NOT NULL,
            liability_kind text NOT NULL
                CHECK (liability_kind IN ('qualified_nonrecourse', 'nonrecourse', 'recourse')),
            share_bop {_MONEY} NOT NULL,
            share_eop {_MONEY} NOT NULL,
            method text NOT NULL CHECK (char_length(method) BETWEEN 1 AND 60),
            UNIQUE (work_item_id, partner_id, liability_kind),""",
    "state_apportionments": f"""
            state {_STATE},
            property_id uuid NULL,
            numerator {_MONEY} NOT NULL,
            denominator {_MONEY} NOT NULL CHECK (denominator <> 0),
            share numeric(7, 4) NOT NULL CHECK (share BETWEEN 0 AND 100),
            nexus_basis text NULL CHECK (char_length(nexus_basis) <= 200),
            return_form text NULL CHECK (char_length(return_form) <= 60),
            status text NOT NULL DEFAULT 'in_review' CHECK (status IN ('in_review', 'approved')),
            UNIQUE NULLS NOT DISTINCT (work_item_id, state, property_id),""",
    "sourcing_positions": """
            method text NOT NULL CHECK (char_length(method) BETWEEN 1 AND 60),
            proposal_id uuid NULL,
            status text NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'approved', 'rejected', 'undone')),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            CHECK (status = 'proposed' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)),""",
    "ptet_elections": f"""
            state {_STATE},
            election text NOT NULL CHECK (election IN ('elected', 'recommend', 'not_elected')),
            rate numeric(7, 4) NULL CHECK (rate BETWEEN 0 AND 100),
            base {_MONEY} NULL,
            amount {_MONEY} NULL CHECK (amount >= 0),
            rounding_rule text NOT NULL DEFAULT 'largest_remainder'
                CHECK (rounding_rule IN ('largest_remainder', 'half_up_override')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (work_item_id, state),""",
    "ptet_payments": f"""
            state {_STATE},
            paid_on date NOT NULL,
            amount {_MONEY} NOT NULL CHECK (amount > 0),
            with_extension boolean NOT NULL DEFAULT false,
            evidence_version_id uuid NULL,
            recorded_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),""",
    "ptet_partner_credits": f"""
            partner_id uuid NOT NULL,
            state {_STATE},
            amount {_MONEY} NOT NULL CHECK (amount >= 0),
            rounding_rule text NOT NULL
                CHECK (rounding_rule IN ('largest_remainder', 'half_up_override')),
            override_reason text NULL CHECK (char_length(override_reason) <= 500),
            CHECK (rounding_rule = 'largest_remainder' OR override_reason IS NOT NULL),
            UNIQUE (work_item_id, partner_id, state),""",
    "nexus_facts": f"""
            state {_STATE},
            fact text NOT NULL CHECK (char_length(fact) BETWEEN 1 AND 500),
            evidence_version_id uuid NULL,
            conclusion text NOT NULL CHECK (char_length(conclusion) BETWEEN 1 AND 200),
            owner_user_id uuid NULL,""",
}
INSERT_ONLY = ("fixed_asset_versions", "fixed_asset_dispositions", "ptet_payments")
# The current row of each table moves through the tax services; insert-only tables never do.
UPDATES: dict[str, tuple[str, ...]] = {
    "tax_properties": ("name", "city", "state", "use", "land_value", "form8825_property_no",
                       "source_ref", "version"),
    "fixed_assets": ("property_id", "description", "placed_in_service_on", "acquired_on",
                     "binding_contract_on", "date_citation_id", "cost", "recovery_class",
                     "method", "convention", "bonus_pct", "sec179", "accum_bop", "current_year",
                     "accum_eop", "book_equals_tax", "status", "status_reason_code", "version",
                     "engine_name", "engine_version", "inputs_hash", "computed_at"),
    "book_tax_items": ("description", "col_a", "col_b", "col_c", "col_d", "kind", "source_ref",
                       "engine_name", "engine_version", "inputs_hash", "computed_at"),
    "basis_schedules": ("tax_capital", "s752_share", "outside_basis", "inside_share",
                        "difference", "s743b_placeholder", "status", "engine_name",
                        "engine_version", "inputs_hash", "computed_at"),
    "liability_shares": ("share_bop", "share_eop", "method"),
    "state_apportionments": ("numerator", "denominator", "share", "nexus_basis", "return_form",
                             "status"),
    "sourcing_positions": ("status", "decided_by", "decided_at"),
    "ptet_elections": ("election", "rate", "base", "amount", "rounding_rule", "version"),
    "ptet_partner_credits": ("amount", "rounding_rule", "override_reason"),
    "nexus_facts": ("fact", "evidence_version_id", "conclusion", "owner_user_id"),
}  # fmt: skip


def _columns(body: str) -> list[str]:
    """The columns a body declares at column depth (12 spaces), less server-set ones: the id,
    clock defaults and a defaulted `version`."""
    names: list[str] = []
    for line in body.splitlines():
        if not line.startswith(" " * 12) or line.startswith(" " * 13):
            continue
        word = line.strip().split(" ", 1)[0]
        if not word.islower() or not word.replace("_", "").isalnum() or word == "id":
            continue
        if word in ("constraint", "unique", "check", "foreign"):
            continue
        if "DEFAULT clock_timestamp()" in line or (word == "version" and "DEFAULT 1" in line):
            continue
        names.append(word)
    return names


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
    for table, body in TABLES.items():
        op.execute(f"CREATE TABLE {table} ({_SCOPE}{body}{_SCOPE_KEYS}\n        )")
    op.execute(
        "ALTER TABLE fixed_assets ADD CONSTRAINT fixed_assets_property_fk "
        "FOREIGN KEY (tenant_id, property_id) REFERENCES tax_properties (tenant_id, id)"
    )
    for table in ("fixed_asset_versions", "fixed_asset_dispositions"):
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_asset_fk "
            "FOREIGN KEY (tenant_id, asset_id) REFERENCES fixed_assets (tenant_id, id)"
        )
    op.execute(
        "ALTER TABLE state_apportionments ADD CONSTRAINT state_apportionments_property_fk "
        "FOREIGN KEY (tenant_id, property_id) REFERENCES tax_properties (tenant_id, id)"
    )
    for table, body in TABLES.items():
        tenant_table(op, table)
        insert_columns(op, table, ["tenant_id", "engagement_id", "work_item_id", *_columns(body)])
    for table in INSERT_ONLY:
        insert_only(op, table)
        _immutable(table)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    for table in INSERT_ONLY:
        op.execute(f"DROP FUNCTION {table}_immutable()")
