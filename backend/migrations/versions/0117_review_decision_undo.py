"""Evidence decision Undo (P-01-T13; DEC-24, ADR-161 clause 6; DEC-214).

Migration 0015 allowed one decision per version and a reason on every non-accept row, so an Undo
row and a re-decision could not be stored. Now:

- `decision` gains `undone`. Each row has a `decision_seq` (existing rows are 1): decisions take
  odd numbers, undo rows even ones, one row per number per version. The **effective decision**
  of a version is its highest-numbered row when that number is odd.
- An `undone` row names the decision it undoes (`undoes_decision_id`, at most one undo each),
  carries no reason, note, screening result or correction, and is refused by the insert trigger
  unless it undoes the row just before it on the same version and item, by the same actor, within
  10 seconds of business time (`abacus_now()`, the clock that stamped the decision).
- A decision records what it changed, so its Undo puts it back: the version's assignee when it
  was decided (`prior_assignee_user_id`) and each item's status then (`prior_item_statuses`, an
  object of item id to `uploaded` or `returned`). An undone row carries neither.
- The insert trigger (`review_decision_reason_check`, SECURITY DEFINER) also requires
  `decision_seq` to be one more than the version's current maximum, so a second decision while
  one is effective is refused (the parity CHECK), as is a stale sequence number.
- The human-only register gains `review_decision.created` and `review_decision.undone` (the
  register named `review.decided`, a log line, so the decision's audit action was unguarded).

The table stays insert-only. Downgrade refuses while any row has `decision_seq > 1`.

Revision ID: 0117
Revises: 0116
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None

_COLUMNS = (
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
)

_HUMAN_ONLY_0097 = [
    "engagement.accepted",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.confirmed",
    "legal_hold.placed",
    "materiality.decided",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "review.decided",
    "review.released",
    "risk.approved",
    "sample.approved",
    "sign_off.recorded",
    "statement.approved",
]
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0097, "review_decision.created", "review_decision.undone"])

# 0015's trigger body, kept for the downgrade.
_REASON_CHECK_0015 = """
CREATE OR REPLACE FUNCTION review_decision_reason_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_code public.review_reason_codes;
BEGIN
    IF NEW.actor_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
       OR NEW.actor_id IS DISTINCT FROM current_setting('app.actor_id', true) THEN
        RAISE EXCEPTION 'a review decision is made by the session''s own actor'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
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

_REASON_CHECK = """
CREATE OR REPLACE FUNCTION review_decision_reason_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_code public.review_reason_codes;
    v_max smallint;
    v_prior record;
BEGIN
    IF NEW.actor_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
       OR NEW.actor_id IS DISTINCT FROM current_setting('app.actor_id', true) THEN
        RAISE EXCEPTION 'a review decision is made by the session''s own actor'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- P-01-T13: one row per number, in order, on each version.
    SELECT max(d.decision_seq) INTO v_max FROM public.review_decisions d
     WHERE d.tenant_id = NEW.tenant_id AND d.evidence_version_id = NEW.evidence_version_id;
    IF NEW.decision_seq IS DISTINCT FROM coalesce(v_max, 0) + 1 THEN
        RAISE EXCEPTION 'already_decided'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'review_decisions_seq_next';
    END IF;
    -- DEC-24 / ADR-161: an undo reverses the version's effective decision, by the person who
    -- made it, within 10 seconds of business time.
    IF NEW.decision = 'undone' THEN
        SELECT d.evidence_version_id, d.request_item_id, d.decision, d.decision_seq,
               d.actor_kind, d.actor_id, d.created_at
          INTO v_prior FROM public.review_decisions d
         WHERE d.tenant_id = NEW.tenant_id AND d.id = NEW.undoes_decision_id;
        IF NOT FOUND
           OR v_prior.evidence_version_id <> NEW.evidence_version_id
           OR v_prior.request_item_id <> NEW.request_item_id
           OR v_prior.decision = 'undone'
           OR v_prior.decision_seq <> NEW.decision_seq - 1 THEN
            RAISE EXCEPTION 'undo_window_closed'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'review_decisions_undo_window';
        END IF;
        IF v_prior.actor_kind IS DISTINCT FROM NEW.actor_kind
           OR v_prior.actor_id IS DISTINCT FROM NEW.actor_id THEN
            RAISE EXCEPTION 'only the person who decided may undo'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF public.abacus_now() - v_prior.created_at > interval '10 seconds' THEN
            RAISE EXCEPTION 'undo_window_closed'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'review_decisions_undo_window';
        END IF;
        RETURN NEW;
    END IF;
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


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    op.execute("ALTER TABLE review_decisions DROP CONSTRAINT review_decisions_decision_check")
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_decision_check "
        "CHECK (decision IN ('accept', 'reject', 'send_back', 'undone'))"
    )
    op.execute(
        "ALTER TABLE review_decisions "
        "ADD COLUMN decision_seq smallint NOT NULL DEFAULT 1, "
        "ADD COLUMN undoes_decision_id uuid NULL, "
        "ADD COLUMN prior_assignee_user_id uuid NULL, "
        "ADD COLUMN prior_item_statuses jsonb NULL"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_prior_item_statuses "
        "CHECK (prior_item_statuses IS NULL OR jsonb_typeof(prior_item_statuses) = 'object')"
    )
    op.execute("ALTER TABLE review_decisions DROP CONSTRAINT review_decisions_once")
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_seq_once "
        "UNIQUE (tenant_id, evidence_version_id, decision_seq)"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_seq_positive "
        "CHECK (decision_seq >= 1)"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_undo_parity "
        "CHECK ((decision = 'undone') = (decision_seq % 2 = 0))"
    )
    op.execute("ALTER TABLE review_decisions DROP CONSTRAINT review_decisions_reason")
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_reason "
        "CHECK ((decision IN ('accept', 'undone')) = (reason_code IS NULL))"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_undo_names_its_decision "
        "CHECK ((decision = 'undone') = (undoes_decision_id IS NOT NULL))"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_undo_is_bare "
        "CHECK (decision <> 'undone' OR (note IS NULL AND screening_result_id IS NULL "
        "AND NOT corrects_proposal AND prior_assignee_user_id IS NULL "
        "AND prior_item_statuses IS NULL))"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_undoes_fkey "
        "FOREIGN KEY (tenant_id, undoes_decision_id) REFERENCES review_decisions (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_undone_once "
        "UNIQUE (tenant_id, undoes_decision_id)"
    )
    op.execute(_REASON_CHECK)
    insert_columns(
        op,
        "review_decisions",
        (
            *_COLUMNS,
            "decision_seq",
            "undoes_decision_id",
            "prior_assignee_user_id",
            "prior_item_statuses",
        ),
    )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM review_decisions WHERE decision_seq > 1) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: review decisions were undone or re-decided'; "
        "END IF; END $$"
    )
    _human_only(_HUMAN_ONLY_0097)
    insert_columns(op, "review_decisions", _COLUMNS)
    op.execute(_REASON_CHECK_0015)
    for name in (
        "review_decisions_undone_once",
        "review_decisions_undoes_fkey",
        "review_decisions_undo_is_bare",
        "review_decisions_prior_item_statuses",
        "review_decisions_undo_names_its_decision",
        "review_decisions_reason",
        "review_decisions_undo_parity",
        "review_decisions_seq_positive",
        "review_decisions_seq_once",
    ):
        op.execute(f"ALTER TABLE review_decisions DROP CONSTRAINT {name}")
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_reason "
        "CHECK ((decision = 'accept') = (reason_code IS NULL))"
    )
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_once "
        "UNIQUE (tenant_id, evidence_version_id)"
    )
    op.execute(
        "ALTER TABLE review_decisions DROP COLUMN prior_item_statuses, "
        "DROP COLUMN prior_assignee_user_id, DROP COLUMN undoes_decision_id, "
        "DROP COLUMN decision_seq"
    )
    op.execute("ALTER TABLE review_decisions DROP CONSTRAINT review_decisions_decision_check")
    op.execute(
        "ALTER TABLE review_decisions ADD CONSTRAINT review_decisions_decision_check "
        "CHECK (decision IN ('accept', 'reject', 'send_back'))"
    )
