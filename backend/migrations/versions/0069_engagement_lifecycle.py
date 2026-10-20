"""The engagement lifecycle (F-03-T12; plan migration "0057_engagement_lifecycle").

- `engagements.type`: the 14 types; `audit` is rewritten to `fs_audit` (no alias). `single_audit`
  and `yellow_book` stay out (DEC-19).
- `engagements.service_line` (audit, tax, cas, advisory), derived from the type at insert;
  `office_id` and `standards_set_id` (nullable; their tables arrive later).
- `engagements.status`: the registry's 8 lifecycle codes; existing rows keep active or archived.
- `methodology_templates.engagement_types`: the same rewrite and the 14 types.
- `assurance_work_items.assurance_type` rewritten; new engagements get an assurance work item only
  for the attest families (tax, CAS, notice and advisory engagements hold other kinds).
- `gate_policy_overrides`: a firm may add or tighten a gate, never loosen one (DEC-39, enforced in
  `engagements.gate_policy`).

Revision ID: 0069
Revises: 0068
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

TYPES = (
    "fs_audit",
    "ebp_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
    "readiness",
    "internal_audit",
    "tax_compliance",
    "cas_monthly_close",
    "notice_response",
    "advisory",
)
_TYPES = "(" + ", ".join(f"'{t}'" for t in TYPES) + ")"
_ARRAY = "ARRAY[" + ", ".join(f"'{t}'" for t in TYPES) + "]::text[]"
_STATUSES = (
    "('prospect', 'accepted', 'declined', 'contracted', 'active', 'on_hold', 'delivered', "
    "'archived')"
)
_OLD_TYPES = "('audit', 'review', 'compilation', 'agreed_upon_procedures')"


# Attest families hold an assurance work item; the others hold kinds of their own.
_TRIGGER_ATTEST = """
        CREATE OR REPLACE FUNCTION engagement_work_item_defaults() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            item uuid;
        BEGIN
            INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_entity_id, 'primary');
            IF NEW.type NOT IN ('fs_audit', 'ebp_audit', 'review', 'compilation', 'preparation',
                                'agreed_upon_procedures', 'soc1', 'soc2', 'readiness',
                                'internal_audit') THEN
                RETURN NULL;
            END IF;
            INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind,
                                    name, period_start, period_end, created_by)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_id, NEW.client_entity_id, 'assurance',
                    NEW.name, NEW.fiscal_period_start, NEW.fiscal_period_end, NEW.created_by)
            RETURNING id INTO item;
            INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id,
                                              assurance_type)
            VALUES (item, NEW.tenant_id, NEW.id, NEW.type);
            RETURN NULL;
        END;
        $$
"""
# 0068's trigger, for the downgrade.
_TRIGGER_ALL = """
        CREATE OR REPLACE FUNCTION engagement_work_item_defaults() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            item uuid;
        BEGIN
            INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_entity_id, 'primary');
            INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind,
                                    name, period_start, period_end, created_by)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_id, NEW.client_entity_id, 'assurance',
                    NEW.name, NEW.fiscal_period_start, NEW.fiscal_period_end, NEW.created_by)
            RETURNING id INTO item;
            INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id,
                                              assurance_type)
            VALUES (item, NEW.tenant_id, NEW.id, NEW.type);
            RETURN NULL;
        END;
        $$
"""


def upgrade() -> None:
    tables = ("engagements", "methodology_templates", "assurance_work_items")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE engagements DROP CONSTRAINT engagements_type_check")
    op.execute("UPDATE engagements SET type = 'fs_audit' WHERE type = 'audit'")
    op.execute(
        f"ALTER TABLE engagements ALTER COLUMN type SET DEFAULT 'fs_audit', "
        f"ADD CONSTRAINT engagements_type_check CHECK (type IN {_TYPES})"
    )
    op.execute(
        "ALTER TABLE engagements "
        "ADD COLUMN service_line text NULL, "
        "ADD COLUMN office_id uuid NULL, "
        "ADD COLUMN standards_set_id uuid NULL"
    )
    op.execute(
        "UPDATE engagements SET service_line = CASE "
        "WHEN type = 'tax_compliance' OR type = 'notice_response' THEN 'tax' "
        "WHEN type = 'cas_monthly_close' THEN 'cas' WHEN type = 'advisory' THEN 'advisory' "
        "ELSE 'audit' END"
    )
    op.execute(
        "ALTER TABLE engagements ALTER COLUMN service_line SET NOT NULL, "
        "ADD CONSTRAINT engagements_service_line_check "
        "CHECK (service_line IN ('audit', 'tax', 'cas', 'advisory'))"
    )
    # The service line follows the type; the app never sets it.
    op.execute(
        """
        CREATE FUNCTION engagement_service_line() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.service_line := CASE
                WHEN NEW.type IN ('tax_compliance', 'notice_response') THEN 'tax'
                WHEN NEW.type = 'cas_monthly_close' THEN 'cas'
                WHEN NEW.type = 'advisory' THEN 'advisory'
                ELSE 'audit' END;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagements_service_line BEFORE INSERT ON engagements "
        "FOR EACH ROW EXECUTE FUNCTION engagement_service_line()"
    )
    op.execute("GRANT INSERT (office_id, standards_set_id) ON engagements TO abacus_app")
    op.execute(
        "ALTER TABLE engagements DROP CONSTRAINT engagements_status_check, "
        f"ADD CONSTRAINT engagements_status_check CHECK (status IN {_STATUSES})"
    )
    op.execute(
        "ALTER TABLE methodology_templates DROP CONSTRAINT "
        "methodology_templates_engagement_types_check"
    )
    op.execute(
        "UPDATE methodology_templates SET engagement_types = "
        "array_replace(engagement_types, 'audit', 'fs_audit')"
    )
    op.execute(
        "ALTER TABLE methodology_templates ALTER COLUMN engagement_types "
        "SET DEFAULT '{fs_audit}', ADD CONSTRAINT methodology_templates_engagement_types_check "
        f"CHECK (cardinality(engagement_types) BETWEEN 1 AND 14 "
        f"AND engagement_types <@ {_ARRAY})"
    )
    op.execute(
        "UPDATE assurance_work_items SET assurance_type = 'fs_audit' "
        "WHERE assurance_type = 'audit'"
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(_TRIGGER_ATTEST)
    op.execute(
        """
        CREATE TABLE gate_policy_overrides (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            type_family text NOT NULL CHECK (type_family IN
                ('attest', 'compilation_preparation', 'tax', 'cas', 'notice', 'advisory')),
            gate text NOT NULL CHECK (gate ~ '^G[1-9]$'),
            requirement text NOT NULL CHECK (requirement IN ('required', 'strict')),
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, type_family, gate)
        )
        """
    )
    tenant_table(op, "gate_policy_overrides")
    op.execute("REVOKE UPDATE, DELETE ON gate_policy_overrides FROM abacus_app")
    insert_columns(
        op, "gate_policy_overrides", ("tenant_id", "type_family", "gate", "requirement", "set_by")
    )


def downgrade() -> None:
    op.execute("DROP TABLE gate_policy_overrides")
    op.execute(_TRIGGER_ALL)
    tables = ("engagements", "methodology_templates", "assurance_work_items")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE assurance_work_items SET assurance_type = 'audit' "
        "WHERE assurance_type = 'fs_audit'"
    )
    op.execute(
        "ALTER TABLE methodology_templates DROP CONSTRAINT "
        "methodology_templates_engagement_types_check"
    )
    op.execute(
        "UPDATE methodology_templates SET engagement_types = "
        "array_replace(engagement_types, 'fs_audit', 'audit')"
    )
    op.execute(
        "ALTER TABLE methodology_templates ALTER COLUMN engagement_types SET DEFAULT '{audit}', "
        "ADD CONSTRAINT methodology_templates_engagement_types_check "
        "CHECK (cardinality(engagement_types) BETWEEN 1 AND 4 AND engagement_types <@ "
        "ARRAY['audit', 'review', 'compilation', 'agreed_upon_procedures']::text[])"
    )
    op.execute(
        "ALTER TABLE engagements DROP CONSTRAINT engagements_status_check, "
        "ADD CONSTRAINT engagements_status_check CHECK (status IN ('active', 'archived'))"
    )
    op.execute("REVOKE INSERT (office_id, standards_set_id) ON engagements FROM abacus_app")
    op.execute("DROP TRIGGER engagements_service_line ON engagements")
    op.execute("DROP FUNCTION engagement_service_line()")
    op.execute(
        "ALTER TABLE engagements DROP COLUMN service_line, DROP COLUMN office_id, "
        "DROP COLUMN standards_set_id"
    )
    op.execute("ALTER TABLE engagements DROP CONSTRAINT engagements_type_check")
    op.execute("UPDATE engagements SET type = 'audit' WHERE type = 'fs_audit'")
    op.execute(
        "ALTER TABLE engagements ALTER COLUMN type SET DEFAULT 'audit', "
        f"ADD CONSTRAINT engagements_type_check CHECK (type IN {_OLD_TYPES})"
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
