"""Q-05-T31 (TASK-8712; DEC-5708; K-02 R9; red): evidence's retention floor reads C21's
`retention_minimums` reference set once switched; built dark.

- `retention_minimums_in_effect()`: the rows of the published `retention_minimums` version in
  effect today (the latest effective on or before today), as the floor reader's shape.
- `retention_floor_differences()`: every (record type, service line) whose published Q-02 floor and
  `retention_minimums` row differ (years or anchor, or one side missing): the pre-switch check.
- `retention_floor_of` and `retention_floors_published` read the source named by the platform
  setting `retention_floor_source` (`retention_floors` until switched, `retention_minimums` after),
  so a policy save's floor guard and every eligibility read follow the switch together.
- `platform_setting_put` accepts `retention_floor_source`, and refuses the switch to
  `retention_minimums` while any floor differs (`floors_differ`).

The contract step (Q-02's `retention_floors` as a read-only view over the set) follows the
switch in the Oct 24 train with both approvals (Q-03-T081); it is not in this migration.

Revision ID: 0982
Revises: 0981
"""

from __future__ import annotations

from alembic import op

revision = "0982"
down_revision = "0981"
branch_labels = None
depends_on = None

_IN_EFFECT = """
        CREATE FUNCTION retention_minimums_in_effect()
        RETURNS TABLE (set_version integer, record_type text, service_line text,
                       legal_floor_years numeric, anchor text, authority text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            WITH v AS (
                SELECT rv.version, rv.payload FROM public.reference_set_versions rv
                  JOIN public.reference_sets rs ON rs.key = rv.set_key
                 WHERE rs.kind = 'retention_minimums' AND rv.status = 'published'
                   AND rv.effective_from <= current_date
                 ORDER BY rv.effective_from DESC, rv.version DESC LIMIT 1
            )
            SELECT v.version, r->>'record_type', r->>'service_line',
                   (r->>'floor_years')::numeric, r->>'anchor', r->>'authority'
              FROM v, jsonb_array_elements(v.payload->'rows') r
             ORDER BY 2, 3
        $$
"""
_DIFFERENCES = """
        CREATE FUNCTION retention_floor_differences()
        RETURNS TABLE (record_type text, service_line text, floors_years numeric,
                       minimums_years numeric)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT coalesce(f.record_type, m.record_type),
                   coalesce(f.service_line, m.service_line),
                   f.legal_floor_years, m.legal_floor_years
              FROM (SELECT * FROM public.retention_floors WHERE status = 'published') f
              FULL OUTER JOIN public.retention_minimums_in_effect() m
                ON m.record_type = f.record_type AND m.service_line = f.service_line
             WHERE f.record_type IS NULL OR m.record_type IS NULL
                OR f.legal_floor_years IS DISTINCT FROM m.legal_floor_years
                OR f.anchor IS DISTINCT FROM m.anchor
        $$
"""
_SOURCE = """
        CREATE FUNCTION retention_floor_source() RETURNS text
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT coalesce((SELECT s.value->>'source' FROM public.platform_settings s
                              WHERE s.key = 'retention_floor_source'), 'retention_floors')
        $$
"""
_FLOOR_OF = """
        CREATE OR REPLACE FUNCTION retention_floor_of(p_record_type text, p_line text)
        RETURNS numeric
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT x.years FROM (
                SELECT f.legal_floor_years AS years, (f.service_line = p_line) AS exact
                  FROM public.retention_floors f
                 WHERE public.retention_floor_source() = 'retention_floors'
                   AND f.status = 'published' AND f.record_type = p_record_type
                   AND f.service_line IN (p_line, 'any')
                UNION ALL
                SELECT m.legal_floor_years, (m.service_line = p_line)
                  FROM public.retention_minimums_in_effect() m
                 WHERE public.retention_floor_source() = 'retention_minimums'
                   AND m.record_type = p_record_type AND m.service_line IN (p_line, 'any')
            ) x ORDER BY x.exact DESC LIMIT 1
        $$
"""
_PUBLISHED = """
        CREATE OR REPLACE FUNCTION retention_floors_published()
        RETURNS TABLE (set_version integer, record_type text, service_line text,
                       legal_floor_years numeric, anchor text, authority text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.set_version, f.record_type, f.service_line, f.legal_floor_years, f.anchor,
                   f.authority
              FROM public.retention_floors f
             WHERE public.retention_floor_source() = 'retention_floors' AND f.status = 'published'
            UNION ALL
            SELECT * FROM public.retention_minimums_in_effect()
             WHERE public.retention_floor_source() = 'retention_minimums'
             ORDER BY 2, 3
        $$
"""
_PUT = """
        CREATE OR REPLACE FUNCTION platform_setting_put(p_key text, p_value jsonb,
                                                        p_expected integer, p_operator text,
                                                        p_reason text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_version integer;
        BEGIN
            IF p_key NOT IN ('support_hours', 'retention_floor_source') THEN
                RAISE EXCEPTION 'unknown_setting' USING ERRCODE = 'check_violation';
            END IF;
            IF p_key = 'retention_floor_source' THEN
                IF p_value->>'source' NOT IN ('retention_floors', 'retention_minimums') THEN
                    RAISE EXCEPTION 'unknown_source' USING ERRCODE = 'check_violation';
                END IF;
                IF p_value->>'source' = 'retention_minimums'
                   AND EXISTS (SELECT 1 FROM public.retention_floor_differences()) THEN
                    RAISE EXCEPTION 'floors_differ' USING ERRCODE = 'check_violation';
                END IF;
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
_NEW = (
    "retention_minimums_in_effect()",
    "retention_floor_differences()",
    "retention_floor_source()",
)
_OLD_FLOOR_OF = """
        CREATE OR REPLACE FUNCTION retention_floor_of(p_record_type text, p_line text)
        RETURNS numeric
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.legal_floor_years FROM public.retention_floors f
             WHERE f.status = 'published' AND f.record_type = p_record_type
               AND f.service_line IN (p_line, 'any')
             ORDER BY (f.service_line = p_line) DESC LIMIT 1
        $$
"""
_OLD_PUBLISHED = """
        CREATE OR REPLACE FUNCTION retention_floors_published()
        RETURNS TABLE (set_version integer, record_type text, service_line text,
                       legal_floor_years numeric, anchor text, authority text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.set_version, f.record_type, f.service_line, f.legal_floor_years, f.anchor,
                   f.authority
              FROM public.retention_floors f WHERE f.status = 'published'
             ORDER BY f.record_type, f.service_line
        $$
"""


def upgrade() -> None:
    for sql in (_IN_EFFECT, _DIFFERENCES, _SOURCE):
        op.execute(sql)
    for signature in _NEW:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    # The check is the operator's and the app's (FIL-02 shows the floor source before the switch).
    op.execute("GRANT EXECUTE ON FUNCTION retention_floor_differences() TO abacus_app, abacus_ops")
    op.execute("GRANT EXECUTE ON FUNCTION retention_floor_source() TO abacus_app")
    op.execute("GRANT EXECUTE ON FUNCTION retention_minimums_in_effect() TO abacus_app")
    for sql in (_FLOOR_OF, _PUBLISHED, _PUT):
        op.execute(sql)


def downgrade() -> None:
    op.execute("DELETE FROM platform_settings WHERE key = 'retention_floor_source'")
    op.execute(_OLD_FLOOR_OF)
    op.execute(_OLD_PUBLISHED)
    op.execute(_PUT.replace(", 'retention_floor_source')", ")"))
    for signature in _NEW:
        op.execute(f"DROP FUNCTION {signature}")
