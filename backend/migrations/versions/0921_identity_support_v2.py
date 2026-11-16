"""G-04 migration B: support sessions v2 and the firm's console fields (G-04-T05; SPEC-681;
DEC-72; ADR-028, ADR-145; DEC-5205). Modelled on 0023. Expand only: every tightened rule is a
`NOT VALID` CHECK, so historic rows (including any emergency session) stay legal and readable.

`support_sessions`:
- `scope` gains `integration_settings`; a `content` session names one object (`scope_ref_kind`
  `work_item` or `engagement`, `scope_ref_id`), required on new content rows;
- `status` gains `declined` (terminal), with `declined_by` and `declined_at`;
- `approved_by_kind` gains `security_admin`, and new rows can never be staff-approved (OQ-1: the
  emergency second-staff approval is removed);
- at most 120 minutes on new rows; an emergency row is metadata-only;
- `conversation_id` (the firm user's support thread; service-checked, no cross-module FK) and
  `staff_us_located` (the requester's attestation, D-OPS-21, RK-26).
`support_sessions_approved` is replaced so a declined request (never approved, never started)
is legal; nothing else about it changes.

`firms`: `tenant_code` (unique; backfilled `tnt_` + the name's initials + a two-digit sequence),
`onboarding_state` (`invited`, `first_admin_signed_in`, `ready`; existing firms `ready`),
`provisioned_by_staff`, `provisioned_at`. `sandbox_of_firm_id` already exists (0091). The app may
update `onboarding_state` only (first-admin sign-in); provisioning sets the rest as the owner.

Revision ID: 0921
Revises: 0920
"""

from __future__ import annotations

from alembic import op

revision = "0921"
down_revision = "0920"
branch_labels = None
depends_on = None

_INSERTS = (
    "id, tenant_id, staff_id, staff_subject, reason, scope, duration_minutes, emergency, "
    "scope_ref_kind, scope_ref_id, conversation_id, staff_us_located"
)
_OLD_INSERTS = "id, tenant_id, staff_id, staff_subject, reason, scope, duration_minutes, emergency"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE support_sessions "
        "ADD COLUMN scope_ref_kind text NULL "
        "CHECK (scope_ref_kind IN ('work_item', 'engagement')), "
        "ADD COLUMN scope_ref_id uuid NULL, "
        "ADD COLUMN declined_by uuid NULL, "
        "ADD COLUMN declined_at timestamptz NULL, "
        "ADD COLUMN conversation_id uuid NULL, "
        "ADD COLUMN staff_us_located boolean NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_scope_check")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_scope_check "
        "CHECK (scope IN ('metadata', 'content', 'integration_settings'))"
    )
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_status_check")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_status_check "
        "CHECK (status IN ('requested', 'active', 'ended', 'revoked', 'expired', 'declined'))"
    )
    op.execute(
        "ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_approved_by_kind_check"
    )
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_approved_by_kind_check "
        "CHECK (approved_by_kind IN ('firm_admin', 'staff', 'security_admin'))"
    )
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_approved")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_approved CHECK ("
        "(status = 'requested') = (approved_by IS NULL AND starts_at IS NULL) "
        "OR status IN ('revoked', 'declined'))"
    )
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_declined "
        "CHECK ((status = 'declined') = (declined_at IS NOT NULL AND declined_by IS NOT NULL)) "
        "NOT VALID"
    )
    for name, rule in (
        ("support_sessions_content_ref", "scope <> 'content' OR scope_ref_id IS NOT NULL"),
        ("support_sessions_ref_kind", "(scope_ref_id IS NULL) = (scope_ref_kind IS NULL)"),
        ("support_sessions_ref_content_only", "scope = 'content' OR scope_ref_id IS NULL"),
        ("support_sessions_no_staff_approval", "approved_by_kind IS DISTINCT FROM 'staff'"),
        ("support_sessions_two_hours", "duration_minutes <= 120"),
        ("support_sessions_emergency_metadata", "NOT emergency OR scope = 'metadata'"),
    ):
        op.execute(f"ALTER TABLE support_sessions ADD CONSTRAINT {name} CHECK ({rule}) NOT VALID")
    op.execute(f"REVOKE INSERT ({_OLD_INSERTS}) ON support_sessions FROM abacus_app")
    op.execute(f"GRANT INSERT ({_INSERTS}) ON support_sessions TO abacus_app")
    op.execute("GRANT UPDATE (declined_by, declined_at) ON support_sessions TO abacus_app")

    op.execute(
        "ALTER TABLE firms "
        "ADD COLUMN tenant_code text NULL, "
        "ADD COLUMN onboarding_state text NOT NULL DEFAULT 'ready' "
        "CHECK (onboarding_state IN ('invited', 'first_admin_signed_in', 'ready')), "
        "ADD COLUMN provisioned_by_staff text NULL "
        "CHECK (char_length(provisioned_by_staff) BETWEEN 1 AND 200), "
        "ADD COLUMN provisioned_at timestamptz NULL"
    )
    # Backfill as the owner, with forced RLS lifted for this statement only (the 0029 pattern):
    # `tnt_` + up to three initials of the firm's name + a two-digit sequence per initials.
    op.execute("ALTER TABLE firms NO FORCE ROW LEVEL SECURITY")
    op.execute(
        r"""
        WITH initials AS (
            SELECT f.tenant_id,
                   coalesce(nullif(left(lower(regexp_replace(
                       (SELECT string_agg(left(w, 1), '')
                          FROM regexp_split_to_table(f.name, '\s+') AS w),
                       '[^a-zA-Z0-9]', '', 'g')), 3), ''), 'f') AS letters,
                   f.created_at
              FROM firms f
        ), numbered AS (
            SELECT tenant_id, letters,
                   row_number() OVER (PARTITION BY letters ORDER BY created_at, tenant_id) AS n
              FROM initials
        )
        UPDATE firms f
           SET tenant_code = 'tnt_' || numbered.letters || lpad(numbered.n::text, 2, '0')
          FROM numbered
         WHERE f.tenant_id = numbered.tenant_id
        """
    )
    op.execute("ALTER TABLE firms FORCE ROW LEVEL SECURITY")
    # New firms (signup, provisioning, seeds and tests) get their code the same way unless the
    # inserter names one: the smallest free two-digit sequence for the initials.
    op.execute(
        r"""
        CREATE FUNCTION firms_tenant_code_default() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_letters text;
            v_n integer := 1;
        BEGIN
            IF NEW.tenant_code IS NOT NULL THEN
                RETURN NEW;
            END IF;
            SELECT coalesce(nullif(left(lower(regexp_replace(string_agg(left(w, 1), ''),
                                                             '[^a-zA-Z0-9]', '', 'g')), 3), ''),
                            'f')
              INTO v_letters
              FROM regexp_split_to_table(NEW.name, '\s+') AS w;
            LOOP
                NEW.tenant_code := 'tnt_' || v_letters || lpad(v_n::text, 2, '0');
                EXIT WHEN NOT EXISTS (SELECT 1 FROM public.firms f
                                       WHERE f.tenant_code = NEW.tenant_code);
                v_n := v_n + 1;
            END LOOP;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION firms_tenant_code_default() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER firms_tenant_code_default BEFORE INSERT ON firms "
        "FOR EACH ROW EXECUTE FUNCTION firms_tenant_code_default()"
    )
    op.execute("ALTER TABLE firms ALTER COLUMN tenant_code SET NOT NULL")
    op.execute(
        "ALTER TABLE firms ADD CONSTRAINT firms_tenant_code_format "
        "CHECK (tenant_code ~ '^tnt_[a-z0-9-]{2,40}$')"
    )
    op.execute("CREATE UNIQUE INDEX firms_tenant_code ON firms (tenant_code)")
    op.execute("GRANT UPDATE (onboarding_state) ON firms TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (onboarding_state) ON firms FROM abacus_app")
    op.execute("DROP TRIGGER firms_tenant_code_default ON firms")
    op.execute("DROP FUNCTION firms_tenant_code_default()")
    op.execute("DROP INDEX firms_tenant_code")
    op.execute(
        "ALTER TABLE firms DROP CONSTRAINT firms_tenant_code_format, "
        "DROP COLUMN provisioned_at, DROP COLUMN provisioned_by_staff, "
        "DROP COLUMN onboarding_state, DROP COLUMN tenant_code"
    )
    op.execute("REVOKE UPDATE (declined_by, declined_at) ON support_sessions FROM abacus_app")
    op.execute(f"REVOKE INSERT ({_INSERTS}) ON support_sessions FROM abacus_app")
    op.execute(f"GRANT INSERT ({_OLD_INSERTS}) ON support_sessions TO abacus_app")
    for name in (
        "support_sessions_emergency_metadata",
        "support_sessions_two_hours",
        "support_sessions_no_staff_approval",
        "support_sessions_ref_content_only",
        "support_sessions_ref_kind",
        "support_sessions_content_ref",
        "support_sessions_declined",
    ):
        op.execute(f"ALTER TABLE support_sessions DROP CONSTRAINT {name}")
    # Rows that only v2 allows have no v1 meaning: a declined request was never granted, and
    # an integration-settings session reads as metadata.
    op.execute("ALTER TABLE support_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute("DELETE FROM support_sessions WHERE status = 'declined'")
    op.execute(
        "UPDATE support_sessions SET scope = 'metadata' WHERE scope = 'integration_settings'"
    )
    op.execute(
        "UPDATE support_sessions SET approved_by_kind = 'firm_admin' "
        "WHERE approved_by_kind = 'security_admin'"
    )
    op.execute("ALTER TABLE support_sessions FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_approved")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_approved CHECK ("
        "(status = 'requested') = (approved_by IS NULL AND starts_at IS NULL) "
        "OR status = 'revoked')"
    )
    op.execute(
        "ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_approved_by_kind_check"
    )
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_approved_by_kind_check "
        "CHECK (approved_by_kind IN ('firm_admin', 'staff'))"
    )
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_status_check")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_status_check "
        "CHECK (status IN ('requested', 'active', 'ended', 'revoked', 'expired'))"
    )
    op.execute("ALTER TABLE support_sessions DROP CONSTRAINT support_sessions_scope_check")
    op.execute(
        "ALTER TABLE support_sessions ADD CONSTRAINT support_sessions_scope_check "
        "CHECK (scope IN ('metadata', 'content'))"
    )
    op.execute(
        "ALTER TABLE support_sessions DROP COLUMN staff_us_located, DROP COLUMN conversation_id, "
        "DROP COLUMN declined_at, DROP COLUMN declined_by, DROP COLUMN scope_ref_id, "
        "DROP COLUMN scope_ref_kind"
    )
