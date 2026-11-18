"""S50 immutability triggers to the ADR-004 shape (S50 follow-up; DEC-5641). Red, expand-only.

0964 and 0965 folded one permitted write into the immutability function itself (`RETURN NEW` on
the evidence tombstone and on a tax hand-off's supersede), so the function no longer always
refuses and the schema check cannot count it. As 0144 did for the trust-kit tables, the function
goes back to refusing only, and the one permitted write moves into the UPDATE trigger's `WHEN`:

- `evidence_versions`: the destruction tombstone (Q-05-T06): `destroyed_at` and
  `destruction_certificate_id` set once, nothing else changed, under
  `app.archived_write = destruction_tombstone`.
- `tax_handoffs`: the supersede mark (C-02-T16): `superseded_by_id` set once, nothing else
  changed, under `app.tax_handoff_supersede = on` (set only by `tax_handoffs_supersede()`).
- `filing_deadline_alerts` (0962) had a BEFORE UPDATE trigger only: DELETE and TRUNCATE are
  refused too (the table is insert-only in the practice registry).

Revision ID: 0968
Revises: 0966
"""

from __future__ import annotations

from alembic import op

revision = "0968"
down_revision = "0966"
branch_labels = None
depends_on = None

_TOMBSTONE = (
    "current_setting('app.archived_write', true) = 'destruction_tombstone'"
    " AND OLD.destroyed_at IS NULL AND NEW.destroyed_at IS NOT NULL"
    " AND OLD.destruction_certificate_id IS NULL AND NEW.destruction_certificate_id IS NOT NULL"
    " AND (to_jsonb(NEW) - 'destroyed_at' - 'destruction_certificate_id')"
    " = (to_jsonb(OLD) - 'destroyed_at' - 'destruction_certificate_id')"
)
_SUPERSEDE = (
    "current_setting('app.tax_handoff_supersede', true) = 'on'"
    " AND OLD.superseded_by_id IS NULL AND NEW.superseded_by_id IS NOT NULL"
    " AND (to_jsonb(NEW) - 'superseded_by_id') = (to_jsonb(OLD) - 'superseded_by_id')"
)


def _strict(function: str, message: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {function}() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{message}' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )


def upgrade() -> None:
    # The reviewed SECURITY DEFINER rule: the app role may execute it (a trigger function can't be
    # called outside its trigger, so this grants nothing callable).
    op.execute("GRANT EXECUTE ON FUNCTION tax_handoffs_supersede() TO abacus_app")
    _strict("evidence_versions_immutable", "evidence versions are immutable (ADR-004)")
    op.execute("DROP TRIGGER evidence_versions_no_update_or_delete ON evidence_versions")
    op.execute(
        "CREATE TRIGGER evidence_versions_no_delete BEFORE DELETE ON evidence_versions "
        "FOR EACH ROW EXECUTE FUNCTION evidence_versions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER evidence_versions_no_update BEFORE UPDATE ON evidence_versions "
        f"FOR EACH ROW WHEN (NOT ({_TOMBSTONE})) EXECUTE FUNCTION evidence_versions_immutable()"
    )

    _strict("tax_handoffs_immutable", "tax_handoffs is insert-only")
    op.execute("DROP TRIGGER tax_handoffs_immutable ON tax_handoffs")
    op.execute(
        "CREATE TRIGGER tax_handoffs_immutable BEFORE DELETE ON tax_handoffs "
        "FOR EACH ROW EXECUTE FUNCTION tax_handoffs_immutable()"
    )
    op.execute(
        "CREATE TRIGGER tax_handoffs_no_update BEFORE UPDATE ON tax_handoffs "
        f"FOR EACH ROW WHEN (NOT ({_SUPERSEDE})) EXECUTE FUNCTION tax_handoffs_immutable()"
    )

    op.execute("DROP TRIGGER filing_deadline_alerts_immutable ON filing_deadline_alerts")
    op.execute(
        "CREATE TRIGGER filing_deadline_alerts_immutable BEFORE UPDATE OR DELETE "
        "ON filing_deadline_alerts FOR EACH ROW "
        "EXECUTE FUNCTION filing_deadline_alerts_immutable()"
    )
    op.execute(
        "CREATE TRIGGER filing_deadline_alerts_no_truncate BEFORE TRUNCATE "
        "ON filing_deadline_alerts FOR EACH STATEMENT "
        "EXECUTE FUNCTION filing_deadline_alerts_immutable()"
    )


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION tax_handoffs_supersede() FROM abacus_app")
    op.execute("DROP TRIGGER filing_deadline_alerts_no_truncate ON filing_deadline_alerts")
    op.execute("DROP TRIGGER filing_deadline_alerts_immutable ON filing_deadline_alerts")
    op.execute(
        "CREATE TRIGGER filing_deadline_alerts_immutable BEFORE UPDATE ON filing_deadline_alerts "
        "FOR EACH ROW EXECUTE FUNCTION filing_deadline_alerts_immutable()"
    )
    op.execute("DROP TRIGGER tax_handoffs_no_update ON tax_handoffs")
    op.execute("DROP TRIGGER tax_handoffs_immutable ON tax_handoffs")
    op.execute(
        "CREATE TRIGGER tax_handoffs_immutable BEFORE UPDATE OR DELETE ON tax_handoffs "
        "FOR EACH ROW EXECUTE FUNCTION tax_handoffs_immutable()"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION tax_handoffs_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND {_SUPERSEDE} THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'tax_handoffs is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("DROP TRIGGER evidence_versions_no_update ON evidence_versions")
    op.execute("DROP TRIGGER evidence_versions_no_delete ON evidence_versions")
    op.execute(
        "CREATE TRIGGER evidence_versions_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON evidence_versions "
        "FOR EACH ROW EXECUTE FUNCTION evidence_versions_immutable()"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION evidence_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND {_TOMBSTONE} THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'evidence versions are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
