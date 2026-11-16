"""T-07-T22 (S46; TASK-8079; T-07 §4, F12-F14; SPEC-656 AC-12.1 to AC-14.2): `estate_workpapers`,
expand-only, amber.

The Form 706 workpaper of an estate's return (a `tax_return` work item, form 706):

- `estate_profiles` (one per client entity): the decedent's date of death, the deceased spouse's
  unused exclusion (DSUE) carried in and its support citation, and the residence state.
- `estate_inventory_items` with insert-only `estate_inventory_item_versions`: the schedule (A-I),
  date-of-death and alternate values, the basis rule, the status (`gathering_support` · `valued`),
  the
  support and the request item asking for it. `valued` needs a citation and a human setter.
- `estate_deductions` with insert-only `estate_deduction_versions` (Schedules J, K, L, M, O; the
  §642(g) election a person records).
- `gift_history_items` (per client entity: the decedent's lifetime gifts precede the estate) with
  insert-only `gift_history_item_versions` (prior Forms 709).
- `estate_computations` (insert-only): each recompute's outputs, engine and parameter set,
  `inputs_hash` and `content_hash`, labelled "Accrued tie-out (shadow)" (DEC-77).

Every row is tenant-scoped (`tenant_table()`); the app inserts named columns only and never
updates or deletes a version. Amounts are TRI (`restricted`).

Revision ID: 0892
Revises: 0891
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0892"
down_revision = "0891"
branch_labels = None
depends_on = None

_MONEY = "numeric(18,2)"
_RETURN_COLS = "engagement_id uuid NOT NULL, work_item_id uuid NOT NULL"
_RETURN_FK = (
    "FOREIGN KEY (tenant_id, engagement_id, work_item_id) "
    "REFERENCES work_items (tenant_id, engagement_id, id)"
)
_SET_BY = (
    "set_by_kind text NOT NULL CHECK (set_by_kind = 'human'), set_by_id uuid NOT NULL, "
    "reason_sealed bytea NULL CHECK (octet_length(reason_sealed) BETWEEN 1 AND 8192)"
)
TABLES = (
    "estate_profiles",
    "estate_inventory_items",
    "estate_inventory_item_versions",
    "estate_deductions",
    "estate_deduction_versions",
    "gift_history_items",
    "gift_history_item_versions",
    "estate_computations",
)


def _lock(table: str, inserts: tuple[str, ...], updates: tuple[str, ...] = ()) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, table, inserts)
    if updates:
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    else:
        insert_only(op, table)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE estate_profiles (
            client_entity_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            date_of_death date NOT NULL,
            dsue_amount {_MONEY} NOT NULL DEFAULT 0 CHECK (dsue_amount >= 0),
            dsue_citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            residence_state text NULL CHECK (residence_state ~ '^[A-Z]{{2}}$'),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, client_entity_id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estate_inventory_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            schedule text NOT NULL
                CHECK (schedule IN ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I')),
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 200),
            basis_rule text NOT NULL
                CHECK (basis_rule IN ('stepped_up', 'ird_no_step_up', 'non_probate_excluded')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            {_RETURN_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estate_inventory_item_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            item_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            dod_value {_MONEY} NOT NULL CHECK (dod_value >= 0),
            avd_value {_MONEY} NULL CHECK (avd_value >= 0),
            status text NOT NULL CHECK (status IN ('gathering_support', 'valued')),
            support_text text NULL CHECK (length(support_text) <= 300),
            request_item_id uuid NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (item_id, seq),
            CHECK (status <> 'valued' OR cardinality(citation_ids) >= 1),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, item_id) REFERENCES estate_inventory_items (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estate_deductions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            schedule text NOT NULL
                CHECK (schedule IN ('J_funeral', 'J_administration', 'K', 'L', 'M', 'O')),
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            {_RETURN_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estate_deduction_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            deduction_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            amount {_MONEY} NOT NULL CHECK (amount >= 0),
            estimated boolean NOT NULL DEFAULT false,
            election text NOT NULL DEFAULT 'none'
                CHECK (election IN ('none', 's642g_pending', 's642g_706', 's642g_1041')),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (deduction_id, seq),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, deduction_id) REFERENCES estate_deductions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE gift_history_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            year integer NOT NULL CHECK (year BETWEEN 1976 AND 2100),
            donee_name_sealed bytea NOT NULL CHECK (octet_length(donee_name_sealed) <= 4096),
            asset text NOT NULL CHECK (length(asset) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE gift_history_item_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            gift_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            gift_amount {_MONEY} NOT NULL CHECK (gift_amount >= 0),
            form_709_status text NOT NULL
                CHECK (form_709_status IN ('filed', 'not_required', 'missing')),
            filed_on date NULL,
            evidence_version_id uuid NULL,
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (gift_id, seq),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, gift_id) REFERENCES gift_history_items (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estate_computations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            version_no integer NOT NULL CHECK (version_no > 0),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            engine_name text NOT NULL CHECK (engine_name = 'tax.estate'),
            engine_version text NOT NULL CHECK (length(engine_version) BETWEEN 1 AND 40),
            parameter_set text NOT NULL CHECK (length(parameter_set) BETWEEN 1 AND 40),
            label text NOT NULL DEFAULT 'accrued_tie_out_shadow'
                CHECK (label IN ('accrued_tie_out_shadow', 'engine_import')),
            outputs jsonb NOT NULL CHECK (jsonb_typeof(outputs) = 'object'),
            prior_computation_id uuid NULL,
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, version_no),
            {_RETURN_FK}
        )
        """
    )
    _lock(
        "estate_profiles",
        (
            "client_entity_id",
            "tenant_id",
            "date_of_death",
            "dsue_amount",
            "dsue_citation_ids",
            "residence_state",
            "created_by",
        ),
        ("dsue_amount", "dsue_citation_ids", "residence_state", "row_version"),
    )
    _lock(
        "estate_inventory_items",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "schedule",
            "description",
            "basis_rule",
            "created_by",
        ),
    )
    _lock(
        "estate_inventory_item_versions",
        (
            "tenant_id",
            "item_id",
            "seq",
            "dod_value",
            "avd_value",
            "status",
            "support_text",
            "request_item_id",
            "citation_ids",
            "set_by_kind",
            "set_by_id",
            "reason_sealed",
        ),
    )
    _lock(
        "estate_deductions",
        ("tenant_id", "engagement_id", "work_item_id", "schedule", "description", "created_by"),
    )
    _lock(
        "estate_deduction_versions",
        (
            "tenant_id",
            "deduction_id",
            "seq",
            "amount",
            "estimated",
            "election",
            "citation_ids",
            "set_by_kind",
            "set_by_id",
            "reason_sealed",
        ),
    )
    _lock(
        "gift_history_items",
        ("tenant_id", "client_entity_id", "year", "donee_name_sealed", "asset", "created_by"),
    )
    _lock(
        "gift_history_item_versions",
        (
            "tenant_id",
            "gift_id",
            "seq",
            "gift_amount",
            "form_709_status",
            "filed_on",
            "evidence_version_id",
            "set_by_kind",
            "set_by_id",
            "reason_sealed",
        ),
    )
    _lock(
        "estate_computations",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "version_no",
            "inputs_hash",
            "content_hash",
            "engine_name",
            "engine_version",
            "parameter_set",
            "label",
            "outputs",
            "prior_computation_id",
        ),
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
