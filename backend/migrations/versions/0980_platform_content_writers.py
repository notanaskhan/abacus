"""G-04-T20 (TASK-8705; DEC-5702): the operator writes the platform content catalogue.

0920 created `status_components`, `platform_regions` and `platform_settings` with readers only:
nothing could load the production status catalogue, the region rows or the support hours without a
migration carrying the rows, which the content rule forbids (no row committed to the repository).
Three owner-only writers, executable by `abacus_ops` alone (ADR-156), each auditing to
`platform_audit_events`; the operator command `abacus_tools.platform_console content-import` runs
them from a reviewed content folder kept outside the repository:

- `status_component_upsert` adds or edits one catalogue row (key, label, kind, integration,
  order, active); a component is retired with `active = false`, never deleted (incidents cite it).
- `platform_region_upsert` adds or edits one region row (live or planned, its labels).
- `platform_setting_put` replaces one setting's value at the version read (stale →
  `stale_version`); only the keys the platform reads are accepted (`support_hours`).

Revision ID: 0980
Revises: 0969
"""

from __future__ import annotations

from alembic import op

revision = "0980"
down_revision = "0969"
branch_labels = None
depends_on = None

WRITERS = (
    "status_component_upsert(text, text, text, text, smallint, boolean, text, text)",
    "platform_region_upsert(text, text, text, text, text, text, text, text, text)",
    "platform_setting_put(text, jsonb, integer, text, text)",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION status_component_upsert(p_key text, p_label text, p_kind text,
                                                p_integration_key text, p_display_order smallint,
                                                p_active boolean, p_operator text, p_reason text)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            INSERT INTO public.status_components AS c (key, label, kind, integration_key,
                display_order, active)
            VALUES (p_key, p_label, p_kind, p_integration_key, p_display_order, p_active)
            ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label, kind = EXCLUDED.kind,
                integration_key = EXCLUDED.integration_key,
                display_order = EXCLUDED.display_order, active = EXCLUDED.active;
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, reason, facts)
            VALUES (p_operator, 'platform_admin', 'status_component.saved', 'status_component',
                    p_key, p_reason, jsonb_build_object('active', p_active));
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_region_upsert(p_code text, p_label text, p_status text,
                                               p_planned_label text, p_storage_label text,
                                               p_backup_label text, p_inference_label text,
                                               p_operator text, p_reason text)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            INSERT INTO public.platform_regions AS r (code, label, status, planned_label,
                storage_label, backup_label, inference_label)
            VALUES (p_code, p_label, p_status, p_planned_label, p_storage_label, p_backup_label,
                    p_inference_label)
            ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label, status = EXCLUDED.status,
                planned_label = EXCLUDED.planned_label, storage_label = EXCLUDED.storage_label,
                backup_label = EXCLUDED.backup_label, inference_label = EXCLUDED.inference_label;
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, reason, facts)
            VALUES (p_operator, 'platform_admin', 'platform_region.saved', 'platform_region',
                    p_code, p_reason, jsonb_build_object('status', p_status));
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_setting_put(p_key text, p_value jsonb, p_expected integer,
                                             p_operator text, p_reason text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_version integer;
        BEGIN
            IF p_key NOT IN ('support_hours') THEN
                RAISE EXCEPTION 'unknown_setting' USING ERRCODE = 'check_violation';
            END IF;
            IF p_expected = 0 THEN
                INSERT INTO public.platform_settings (key, value) VALUES (p_key, p_value)
                ON CONFLICT (key) DO NOTHING RETURNING version INTO v_version;
            ELSE
                UPDATE public.platform_settings SET value = p_value, version = version + 1,
                       updated_at = clock_timestamp()
                 WHERE key = p_key AND version = p_expected RETURNING version INTO v_version;
            END IF;
            IF v_version IS NULL THEN
                RAISE EXCEPTION 'stale_version' USING ERRCODE = 'check_violation';
            END IF;
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, reason, facts)
            VALUES (p_operator, 'platform_admin', 'platform_setting.saved', 'platform_setting',
                    p_key, p_reason, jsonb_build_object('version', v_version));
            RETURN v_version;
        END $$
        """
    )
    for signature in WRITERS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM abacus_app")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_ops")


def downgrade() -> None:
    for signature in WRITERS:
        op.execute(f"DROP FUNCTION {signature}")
