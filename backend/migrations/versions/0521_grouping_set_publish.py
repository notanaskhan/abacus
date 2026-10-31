"""Grouping-set versions: the effective date, one live draft, human-only publish (A-03-T06;
A-03 §4.2 M-B as ADR-341 reshapes it; SPEC-580 AC-17).

Expand-only on SPEC-316's `grouping_set_versions` (0079):
- `effective_from` (date): set when a person publishes; a CHECK (NOT VALID, so versions published
  before it keep their null) requires it on every new publish.
- `discarded`: a re-import discards the set's earlier draft, so a set holds one live draft (the
  service enforces it in the import's unit of work; no index, since drafts imported before this
  migration may repeat and an RLS-forced migration cannot see tenant rows to tidy them).
- A guard trigger: a discarded version never changes (0079's trigger already freezes a published
  one), and a publish happens only in a person's session (INV-1), beside 0079's
  `published_actor_kind = 'human'` CHECK.

Revision ID: 0521
Revises: 0520
"""

from __future__ import annotations

from alembic import op

revision = "0521"
down_revision = "0520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE grouping_set_versions ADD COLUMN effective_from date NULL")
    op.execute(
        "ALTER TABLE grouping_set_versions DROP CONSTRAINT grouping_set_versions_status_check"
    )
    op.execute(
        "ALTER TABLE grouping_set_versions ADD CONSTRAINT grouping_set_versions_status_check "
        "CHECK (status IN ('draft', 'published', 'discarded'))"
    )
    op.execute(
        "ALTER TABLE grouping_set_versions ADD CONSTRAINT grouping_set_versions_effective "
        "CHECK (status <> 'published' OR effective_from IS NOT NULL) NOT VALID"
    )
    op.execute("GRANT UPDATE (effective_from) ON grouping_set_versions TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION grouping_set_version_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.status = 'discarded' THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.status = 'published'
               AND coalesce(current_setting('app.actor_kind', true), '') <> 'human' THEN
                RAISE EXCEPTION 'publisher_not_human' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION grouping_set_version_guard() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER grouping_set_version_guard BEFORE UPDATE ON grouping_set_versions "
        "FOR EACH ROW EXECUTE FUNCTION grouping_set_version_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER grouping_set_version_guard ON grouping_set_versions")
    op.execute("DROP FUNCTION grouping_set_version_guard()")
    op.execute("REVOKE UPDATE (effective_from) ON grouping_set_versions FROM abacus_app")
    op.execute("ALTER TABLE grouping_set_versions DROP CONSTRAINT grouping_set_versions_effective")
    op.execute(
        "ALTER TABLE grouping_set_versions DROP CONSTRAINT grouping_set_versions_status_check"
    )
    op.execute(
        "ALTER TABLE grouping_set_versions ADD CONSTRAINT grouping_set_versions_status_check "
        "CHECK (status IN ('draft', 'published')) NOT VALID"
    )
    op.execute("ALTER TABLE grouping_set_versions DROP COLUMN effective_from")
