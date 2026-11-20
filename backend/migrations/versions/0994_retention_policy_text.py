"""Q-05-T13 (S52; TASK-8817; ADR-179; red): a policy's text and effective date ride its versions.

`retention_policies` gains `policy_text` and `effective_from` (insert and update granted), and
`retention_policy_history()` copies them into the insert-only `retention_policy_versions` (0964
added the version columns; the app never writes versions). Expand-only.

Revision ID: 0994
Revises: 0993
"""

from __future__ import annotations

from alembic import op

revision = "0994"
down_revision = "0993"
branch_labels = None
depends_on = None

_HISTORY_V2 = """
CREATE OR REPLACE FUNCTION retention_policy_history() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    INSERT INTO public.retention_policy_versions (tenant_id, record_type, service_line,
        version, firm_years, clock_start_event, lock, basis, changed_by, policy_text,
        effective_from)
    VALUES (NEW.tenant_id, NEW.record_type, NEW.service_line, NEW.version,
        NEW.firm_years, NEW.clock_start_event, NEW.lock, NEW.basis, NEW.updated_by,
        NEW.policy_text, NEW.effective_from);
    RETURN NULL;
END $$
"""
_HISTORY_V1 = """
CREATE OR REPLACE FUNCTION retention_policy_history() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    INSERT INTO public.retention_policy_versions (tenant_id, record_type, service_line,
        version, firm_years, clock_start_event, lock, basis, changed_by)
    VALUES (NEW.tenant_id, NEW.record_type, NEW.service_line, NEW.version,
        NEW.firm_years, NEW.clock_start_event, NEW.lock, NEW.basis, NEW.updated_by);
    RETURN NULL;
END $$
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE retention_policies ADD COLUMN policy_text text NULL "
        "CHECK (char_length(policy_text) <= 4000)"
    )
    op.execute("ALTER TABLE retention_policies ADD COLUMN effective_from date NULL")
    op.execute("GRANT INSERT (policy_text, effective_from) ON retention_policies TO abacus_app")
    op.execute("GRANT UPDATE (policy_text, effective_from) ON retention_policies TO abacus_app")
    op.execute(_HISTORY_V2)


def downgrade() -> None:
    op.execute(_HISTORY_V1)
    op.execute("ALTER TABLE retention_policies DROP COLUMN effective_from")
    op.execute("ALTER TABLE retention_policies DROP COLUMN policy_text")
