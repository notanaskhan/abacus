"""Security review of P-07-T35 and T36 (DEC-375): the database holds what the services check.

- `acceptance_records.high_risk_seen` (server-set): true once the record was ever rated High, so
  lowering the rating never skips the risk-partner review. `acceptance_records_guard` is
  redefined: the risk rating changes only while the record is a Draft, and the flag is sticky.
- `acceptance_draft_only` (answers and manual checks, insert or update): only while the record
  is a Draft. Once sent to the partner, the answers and checks are frozen.
- `acceptance_decisions_guard` (BEFORE INSERT): the record is Awaiting partner; `decided_by` is
  the acting person (`app.actor_id`), an engagement partner on the record's engagement and a
  partner-level staff member; a record ever rated High has a completed risk-partner review. A
  second decision for a record is left to the unique constraint.
- `acting_person_is` (BEFORE INSERT, the column named as the trigger's argument): the person
  column of a flag, a condition completion, a risk-partner review event, a conflict clearance
  and a screening record is the acting person.
- Re-review follow-ups: a risk-partner review is completed by someone who holds no engagement
  partner seat on the engagement (`risk_partner_reviews_independent`), and the decision guard
  refuses the person who completed the review; `acceptance_answers.updated_by` (insert and
  update), `acceptance_records.prepared_by` and `conflict_checks.run_by` are the acting person.
- Refusals here are `check_violation`, as the `actor_kind` CHECKs are.

The human-only register is unchanged (0164's list).

Revision ID: 0165
Revises: 0164
"""

from __future__ import annotations

from alembic import op

revision = "0165"
down_revision = "0164"
branch_labels = None
depends_on = None

_BOUND = (
    ("acceptance_flags", "authored_by"),
    ("acceptance_condition_events", "actor_id"),
    ("risk_partner_reviews", "actor_id"),
    ("conflict_result_events", "cleared_by"),
    ("screening_records", "recorded_by"),
)
# Re-review follow-up 3: also on update for answers (the last person to write them). Named to
# fire after the draft and lock guards, which answer first for a sent or decided record.
_BOUND_LATE = (
    ("acceptance_answers", "updated_by", "INSERT OR UPDATE"),
    ("acceptance_records", "prepared_by", "INSERT"),
    ("conflict_checks", "run_by", "INSERT"),
)

_GUARD_BODY = """
    CREATE OR REPLACE FUNCTION acceptance_records_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'acceptance records are never deleted'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF OLD.status IN ('decided', 'declined') THEN
            RAISE EXCEPTION 'acceptance record % is locked', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            IF NOT ((OLD.status = 'draft' AND NEW.status = 'awaiting_partner')
                    OR (OLD.status = 'awaiting_partner'
                        AND NEW.status IN ('decided', 'declined'))) THEN
                RAISE EXCEPTION 'acceptance record cannot move from % to %', OLD.status,
                    NEW.status USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status IN ('decided', 'declined') AND NOT EXISTS (
                SELECT 1 FROM public.acceptance_decisions d
                 WHERE d.tenant_id = NEW.tenant_id AND d.record_id = NEW.id
                   AND (d.option = 'decline') = (NEW.status = 'declined')
            ) THEN
                RAISE EXCEPTION 'acceptance record % has no matching decision', NEW.id
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;{risk}
        NEW.updated_at := clock_timestamp();
        RETURN NEW;
    END $$
"""
_RISK = """
        IF NEW.risk_rating IS DISTINCT FROM OLD.risk_rating AND OLD.status <> 'draft' THEN
            RAISE EXCEPTION 'the risk rating of record % is frozen once sent', OLD.id
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.high_risk_seen := OLD.high_risk_seen
            OR coalesce(NEW.risk_rating = 'high', false)
            OR coalesce(OLD.risk_rating = 'high', false);"""
_DRAFT_ONLY = """
    CREATE FUNCTION acceptance_draft_only() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM public.acceptance_records r
             WHERE r.tenant_id = NEW.tenant_id AND r.id = NEW.record_id AND r.status = 'draft'
        ) THEN
            RAISE EXCEPTION 'acceptance record % is no longer a draft', NEW.record_id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""
_DECISION_GUARD = """
    CREATE FUNCTION acceptance_decisions_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE v_status text;
            v_engagement uuid;
            v_high boolean;
    BEGIN
        IF EXISTS (
            SELECT 1 FROM public.acceptance_decisions d
             WHERE d.tenant_id = NEW.tenant_id AND d.record_id = NEW.record_id
        ) THEN
            RETURN NEW;  -- one decision per record: the unique constraint refuses it
        END IF;
        SELECT r.status, r.engagement_id, r.high_risk_seen
          INTO v_status, v_engagement, v_high
          FROM public.acceptance_records r
         WHERE r.tenant_id = NEW.tenant_id AND r.id = NEW.record_id;
        IF v_status IS DISTINCT FROM 'awaiting_partner' THEN
            RAISE EXCEPTION 'acceptance record % is not awaiting the partner', NEW.record_id
                USING ERRCODE = 'check_violation';
        END IF;
        IF current_setting('app.actor_id', true) IS DISTINCT FROM NEW.decided_by::text THEN
            RAISE EXCEPTION 'a decision is the acting person''s own'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.engagement_members m
             WHERE m.tenant_id = NEW.tenant_id AND m.engagement_id = v_engagement
               AND m.user_id = NEW.decided_by AND m.role = 'engagement_partner'
        ) OR NOT EXISTS (
            SELECT 1 FROM public.memberships s
             WHERE s.tenant_id = NEW.tenant_id AND s.user_id = NEW.decided_by
               AND s.status = 'active' AND s.kind = 'staff' AND s.level = 'partner'
        ) THEN
            RAISE EXCEPTION 'only a partner-level engagement partner decides acceptance'
                USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (
            SELECT 1 FROM public.risk_partner_reviews v
             WHERE v.tenant_id = NEW.tenant_id AND v.record_id = NEW.record_id
               AND v.event = 'completed' AND v.actor_id = NEW.decided_by
        ) THEN
            RAISE EXCEPTION 'the risk partner who reviewed a record does not decide it'
                USING ERRCODE = 'check_violation';
        END IF;
        IF v_high AND NOT EXISTS (
            SELECT 1 FROM public.risk_partner_reviews v
             WHERE v.tenant_id = NEW.tenant_id AND v.record_id = NEW.record_id
               AND v.event = 'completed'
        ) THEN
            RAISE EXCEPTION 'a record rated High needs a completed risk-partner review'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""
_REVIEW_GUARD = """
    CREATE FUNCTION risk_partner_reviews_independent() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NEW.event = 'completed' AND EXISTS (
            SELECT 1 FROM public.acceptance_records r
              JOIN public.engagement_members m
                ON m.tenant_id = r.tenant_id AND m.engagement_id = r.engagement_id
             WHERE r.tenant_id = NEW.tenant_id AND r.id = NEW.record_id
               AND m.user_id = NEW.actor_id AND m.role = 'engagement_partner'
        ) THEN
            RAISE EXCEPTION 'an engagement partner here is not the risk partner'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""
_ACTING_PERSON = """
    CREATE FUNCTION acting_person_is() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF current_setting('app.actor_id', true) IS DISTINCT FROM (to_jsonb(NEW) ->> TG_ARGV[0])
        THEN
            RAISE EXCEPTION '%.% is the acting person''s own', TG_TABLE_NAME, TG_ARGV[0]
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE acceptance_records ADD COLUMN high_risk_seen boolean NOT NULL DEFAULT false"
    )
    op.execute(_GUARD_BODY.replace("{risk}", _RISK))
    op.execute(_DRAFT_ONLY)
    for table in ("acceptance_answers", "acceptance_manual_checks"):
        op.execute(
            f"CREATE TRIGGER {table}_draft_only BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION acceptance_draft_only()"
        )
    op.execute(_DECISION_GUARD)
    op.execute(
        "CREATE TRIGGER acceptance_decisions_guard BEFORE INSERT ON acceptance_decisions "
        "FOR EACH ROW EXECUTE FUNCTION acceptance_decisions_guard()"
    )
    op.execute(_ACTING_PERSON)
    for table, column in _BOUND:
        op.execute(
            f"CREATE TRIGGER {table}_acting_person BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION acting_person_is('{column}')"
        )
    for table, column, events in _BOUND_LATE:
        op.execute(
            f"CREATE TRIGGER {table}_person_bound BEFORE {events} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION acting_person_is('{column}')"
        )
    op.execute(_REVIEW_GUARD)
    op.execute(
        "CREATE TRIGGER risk_partner_reviews_independent BEFORE INSERT ON risk_partner_reviews "
        "FOR EACH ROW EXECUTE FUNCTION risk_partner_reviews_independent()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER risk_partner_reviews_independent ON risk_partner_reviews")
    op.execute("DROP FUNCTION risk_partner_reviews_independent()")
    for table, _, _ in _BOUND_LATE:
        op.execute(f"DROP TRIGGER {table}_person_bound ON {table}")
    for table, _ in _BOUND:
        op.execute(f"DROP TRIGGER {table}_acting_person ON {table}")
    op.execute("DROP FUNCTION acting_person_is()")
    op.execute("DROP TRIGGER acceptance_decisions_guard ON acceptance_decisions")
    op.execute("DROP FUNCTION acceptance_decisions_guard()")
    for table in ("acceptance_answers", "acceptance_manual_checks"):
        op.execute(f"DROP TRIGGER {table}_draft_only ON {table}")
    op.execute("DROP FUNCTION acceptance_draft_only()")
    op.execute(_GUARD_BODY.replace("{risk}", ""))  # 0163's definition
    op.execute("ALTER TABLE acceptance_records DROP COLUMN high_risk_seen")
