"""Review queues and review decisions (SPEC-004; TASK-019 design §2, D2; ADR-004, ADR-005,
ADR-054).

- `review_decisions`: a person's accept, reject or send back of one evidence version. Insert-only
  and immutable (ADR-004); one per version; the database refuses any actor that isn't human
  (ADR-005), and a reject or send back without a reason code.
- `review_assignments`: who has taken a queued version (advisory, SPEC-004 Q3). Updated on take,
  release and reassign; never deleted.
- `review_reason_codes`: the platform catalogue (Q1), seeded here; codes are retired, never
  deleted. No tenant, so no app privileges at all: the app lists codes through a SECURITY DEFINER
  function, and a SECURITY DEFINER insert trigger refuses an unknown, retired or misapplied code
  (and `other` without a note), the same pattern as the work slot ledger (TASK-018 D3).
- `request_items.status` gains `accepted` (Q2).

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_STATUSES = "('open', 'received', 'ready_for_review', 'needs_revision'"
_CODES = (
    ("wrong_period", "reject,send_back", "Wrong period", "The evidence covers another period."),
    ("wrong_entity", "reject,send_back", "Wrong entity", "The evidence is for another entity."),
    ("incomplete", "reject,send_back", "Incomplete", "Part of what was requested is missing."),
    ("illegible", "reject,send_back", "Illegible", "The evidence can't be read reliably."),
    (
        "does_not_agree",
        "reject,send_back",
        "Doesn't agree to the ledger",
        "Totals or balances don't agree to the general ledger.",
    ),
    ("unsigned", "reject,send_back", "Unsigned", "A required signature or approval is missing."),
    ("other", "reject,send_back", "Other", "Another reason, explained in the note."),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_reason_codes (
            code text NOT NULL CHECK (code ~ '^[a-z][a-z_]{0,49}$'),
            applies_to text NOT NULL CHECK (applies_to IN ('reject', 'send_back')),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 500),
            requires_note boolean NOT NULL DEFAULT false,
            active boolean NOT NULL DEFAULT true,
            PRIMARY KEY (code, applies_to)
        )
        """
    )
    catalogue = sa.table(
        "review_reason_codes",
        sa.column("code", sa.Text),
        sa.column("applies_to", sa.Text),
        sa.column("label", sa.Text),
        sa.column("description", sa.Text),
        sa.column("requires_note", sa.Boolean),
    )
    op.bulk_insert(
        catalogue,
        [
            {
                "code": code,
                "applies_to": kind,
                "label": label,
                "description": description,
                "requires_note": code == "other",
            }
            for code, kinds, label, description in _CODES
            for kind in kinds.split(",")
        ],
    )
    op.execute("REVOKE ALL ON review_reason_codes FROM PUBLIC, abacus_app")
    op.execute("ALTER TABLE review_reason_codes ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE TABLE review_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('accept', 'reject', 'send_back')),
            reason_code text NULL,
            note text NULL CHECK (length(note) BETWEEN 1 AND 2000),
            screening_result_id uuid NULL,
            corrects_proposal boolean NOT NULL,
            -- ADR-005: only a person decides; agents and system contexts never can.
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT review_decisions_once UNIQUE (tenant_id, evidence_version_id),
            CONSTRAINT review_decisions_reason
                CHECK ((decision = 'accept') = (reason_code IS NULL)),
            CONSTRAINT review_decisions_no_proposal_no_correction
                CHECK (screening_result_id IS NOT NULL OR NOT corrects_proposal),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, screening_result_id)
                REFERENCES screening_results (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX review_decisions_engagement ON review_decisions (tenant_id, engagement_id)"
    )
    op.execute(
        """
        CREATE TABLE review_assignments (
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            assignee_user_id uuid NULL,
            assigned_by uuid NOT NULL,
            assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, evidence_version_id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, assignee_user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, assigned_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX review_assignments_engagement "
        "ON review_assignments (tenant_id, engagement_id)"
    )
    for table in ("review_decisions", "review_assignments"):
        tenant_table(op, table)

    insert_only(op, "review_decisions")
    insert_columns(
        op,
        "review_decisions",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "evidence_version_id",
            "request_item_id",
            "decision",
            "reason_code",
            "note",
            "screening_result_id",
            "corrects_proposal",
            "actor_kind",
            "actor_id",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION review_decisions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'review decisions are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER review_decisions_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON review_decisions "
        "FOR EACH ROW EXECUTE FUNCTION review_decisions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER review_decisions_no_truncate BEFORE TRUNCATE ON review_decisions "
        "FOR EACH STATEMENT EXECUTE FUNCTION review_decisions_immutable()"
    )
    # The code must be in the catalogue, active, apply to the decision, and `other` needs a note.
    op.execute(
        """
        CREATE FUNCTION review_decision_reason_check() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_code public.review_reason_codes;
        BEGIN
            IF NEW.reason_code IS NULL THEN
                RETURN NEW;
            END IF;
            SELECT * INTO v_code FROM public.review_reason_codes
             WHERE code = NEW.reason_code AND applies_to = NEW.decision AND active;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'unknown or retired reason code for this decision'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF v_code.requires_note AND NEW.note IS NULL THEN
                RAISE EXCEPTION 'this reason code needs a note'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER review_decisions_reason BEFORE INSERT ON review_decisions "
        "FOR EACH ROW EXECUTE FUNCTION review_decision_reason_check()"
    )
    op.execute(
        """
        CREATE FUNCTION review_reason_codes_list(p_applies_to text)
        RETURNS TABLE (code text, label text, description text, requires_note boolean)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            SELECT c.code, c.label, c.description, c.requires_note
              FROM public.review_reason_codes c
             WHERE c.applies_to = p_applies_to AND c.active
             ORDER BY c.code
        $$
        """
    )
    for signature in ("review_decision_reason_check()", "review_reason_codes_list(text)"):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")

    op.execute("REVOKE DELETE ON review_assignments FROM abacus_app")
    op.execute("REVOKE UPDATE ON review_assignments FROM abacus_app")
    insert_columns(
        op,
        "review_assignments",
        ("tenant_id", "evidence_version_id", "engagement_id", "assignee_user_id", "assigned_by"),
    )
    op.execute(
        "GRANT UPDATE (assignee_user_id, assigned_by, assigned_at) "
        "ON review_assignments TO abacus_app"
    )

    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_status_check")
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_status_check "
        "CHECK (status IN " + _STATUSES + ", 'accepted')) NOT VALID"
    )
    op.execute("ALTER TABLE request_items VALIDATE CONSTRAINT request_items_status_check")


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM review_decisions) "
        "OR EXISTS (SELECT 1 FROM request_items WHERE status = 'accepted') THEN "
        "RAISE EXCEPTION 'refusing to downgrade: review decisions exist'; END IF; END $$"
    )
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_status_check")
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_status_check "
        "CHECK (status IN " + _STATUSES + "))"
    )
    op.execute("DROP TABLE review_assignments")
    op.execute("DROP TABLE review_decisions")
    op.execute("DROP FUNCTION review_decisions_immutable()")
    op.execute("DROP FUNCTION review_decision_reason_check()")
    op.execute("DROP FUNCTION review_reason_codes_list(text)")
    op.execute("DROP TABLE review_reason_codes")
