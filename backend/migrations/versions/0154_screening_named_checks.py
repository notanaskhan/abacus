"""The screening aggregate (P-06-T20; DEC-48, DEC-324; P-06 §4.2 `screening_named_checks`).

`screening_results` (0010) holds one agent run's proposal on one evidence version. The SHL-20
card's aggregate spans a request batch, is composed by code, has no confidence or rationale, may
have no run at all (`not_screened`) and is recomposed on every change, so this migration relaxes
0010's constraints for a new `subject_kind` and for nothing else:

1. `subject_kind` `version` (every existing row) or `request_batch`.
2. `agent_run_id`, `evidence_version_id`, `action`, `confidence` and `rationale` drop NOT NULL.
   A `version` row has all five, and a `request_batch` row has none (two CHECKs).
3. `screening_results_once_per_run` becomes a partial unique index on `version` rows.
4. `created_by_kind` pairs `version` with `agent` (ADR-005) and `request_batch` with `system`
   (ADR-050).
5. The aggregate columns are required on `request_batch` rows and NULL on `version` rows:
   - `request_item_id`, and `batch_no` (1, 2, … per item; unique);
   - `source_result_ids` and `source_review_ids` (the per-version rows and upload reviews it
     composed);
   - `evidence_version_ids` (the item's live, non-withdrawn versions);
   - `checks`, `file_flags` and `verdict`;
   - `supersedes_id` (the item's previous aggregate; unique).
6. The table stays insert-only. A guard on `request_batch` inserts requires the `system` actor,
   `batch_no` one past the item's highest, and `supersedes_id` naming that row, and it sets
   `created_by_kind` to `system`. The app still never supplies `created_by_kind` (SPEC-011 AC-14).
7. `review_decisions.screening_result_id` may name only `version` rows. This is a separate insert
   trigger, so 0132's `review_decision_reason_check` body is not copied a fourth time.
8. `insert_columns` lists the new columns.

**New** `screening_feedback`: a person's thumbs up or down on a `request_batch` row (SHL-20 f).
It is insert-only, and a thumbs-down needs a reason. The writer is the session's own human actor,
and the note is sealed.

The downgrade refuses while any `request_batch` row exists.

Revision ID: 0154
Revises: 0146
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0154"
down_revision = "0146"
branch_labels = None
depends_on = None

_PER_RUN = ("agent_run_id", "evidence_version_id", "action", "confidence", "rationale")
_AGGREGATE = (
    "request_item_id",
    "batch_no",
    "source_result_ids",
    "source_review_ids",
    "evidence_version_ids",
    "checks",
    "file_flags",
    "verdict",
)
_COLUMNS_0010 = (
    "id",
    "tenant_id",
    "engagement_id",
    "evidence_version_id",
    "agent_run_id",
    "action",
    "confidence",
    "rationale",
    "citations",
    "unverified",
)


def _all(columns: tuple[str, ...], test: str) -> str:
    return " AND ".join(f"{c} {test}" for c in columns)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE screening_results "
        "ADD COLUMN subject_kind text NOT NULL DEFAULT 'version', "
        "ADD COLUMN request_item_id uuid NULL, "
        "ADD COLUMN batch_no integer NULL, "
        "ADD COLUMN source_result_ids uuid[] NULL, "
        "ADD COLUMN source_review_ids uuid[] NULL, "
        "ADD COLUMN evidence_version_ids uuid[] NULL, "
        "ADD COLUMN checks jsonb NULL, "
        "ADD COLUMN file_flags jsonb NULL, "
        "ADD COLUMN verdict text NULL, "
        "ADD COLUMN supersedes_id uuid NULL"
    )
    for column in _PER_RUN:
        op.execute(f"ALTER TABLE screening_results ALTER COLUMN {column} DROP NOT NULL")
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_subject_kind "
        "CHECK (subject_kind IN ('version', 'request_batch'))"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_version_shape "
        f"CHECK (subject_kind = 'request_batch' OR ({_all(_PER_RUN, 'IS NOT NULL')} "
        f"AND {_all((*_AGGREGATE, 'supersedes_id'), 'IS NULL')}))"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_batch_shape "
        f"CHECK (subject_kind = 'version' OR ({_all(_PER_RUN, 'IS NULL')} "
        f"AND {_all(_AGGREGATE, 'IS NOT NULL')}))"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_batch_values CHECK ("
        "(batch_no IS NULL OR batch_no >= 1) "
        "AND (verdict IS NULL OR verdict IN ('passed', 'flagged', 'not_screened')) "
        "AND (checks IS NULL OR jsonb_typeof(checks) = 'array') "
        "AND (file_flags IS NULL OR jsonb_typeof(file_flags) = 'array') "
        "AND (supersedes_id IS NULL OR batch_no > 1))"
    )
    op.execute("ALTER TABLE screening_results DROP CONSTRAINT screening_results_once_per_run")
    op.execute(
        "CREATE UNIQUE INDEX screening_results_once_per_run "
        "ON screening_results (tenant_id, agent_run_id) WHERE subject_kind = 'version'"
    )
    op.execute(
        "ALTER TABLE screening_results DROP CONSTRAINT screening_results_created_by_kind_check"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_created_by_kind_check "
        "CHECK ((subject_kind = 'version' AND created_by_kind = 'agent') "
        "OR (subject_kind = 'request_batch' AND created_by_kind = 'system'))"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_request_item_fkey "
        "FOREIGN KEY (tenant_id, engagement_id, request_item_id) "
        "REFERENCES request_items (tenant_id, engagement_id, id)"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_supersedes_fkey "
        "FOREIGN KEY (tenant_id, supersedes_id) REFERENCES screening_results (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_supersedes_once "
        "UNIQUE (tenant_id, supersedes_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX screening_results_batch_once "
        "ON screening_results (tenant_id, request_item_id, batch_no) "
        "WHERE subject_kind = 'request_batch'"
    )
    # (6) Code composes aggregates, in a system context: never an agent run or a person. Each
    # supersedes the item's newest, so the rows form one chain per item.
    op.execute(
        """
        CREATE FUNCTION screening_results_batch_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            v_head record;
        BEGIN
            IF NEW.subject_kind IS DISTINCT FROM 'request_batch' THEN
                RETURN NEW;
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'a screening aggregate is composed by code (ADR-050)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT s.id, s.batch_no INTO v_head FROM screening_results s
             WHERE s.tenant_id = NEW.tenant_id AND s.request_item_id = NEW.request_item_id
               AND s.subject_kind = 'request_batch'
             ORDER BY s.batch_no DESC LIMIT 1;
            IF NEW.batch_no IS DISTINCT FROM coalesce(v_head.batch_no, 0) + 1
               OR NEW.supersedes_id IS DISTINCT FROM v_head.id THEN
                RAISE EXCEPTION 'screening_superseded'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'screening_results_batch_chain';
            END IF;
            -- Who created it is the database's to say, never the app's (SPEC-011 AC-14): the
            -- column stays out of the app's insert grant, and an aggregate is code's.
            NEW.created_by_kind := 'system';
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER screening_results_batch_guard BEFORE INSERT ON screening_results "
        "FOR EACH ROW EXECUTE FUNCTION screening_results_batch_guard()"
    )
    insert_columns(
        op,
        "screening_results",
        (*_COLUMNS_0010, "subject_kind", *_AGGREGATE, "supersedes_id"),
    )
    # (7) A person's decision corrects an agent's proposal on a version, never an aggregate.
    op.execute(
        """
        CREATE FUNCTION review_decisions_screening_kind() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.screening_result_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM screening_results s
                 WHERE s.tenant_id = NEW.tenant_id AND s.id = NEW.screening_result_id
                   AND s.subject_kind = 'version'
            ) THEN
                RAISE EXCEPTION 'a review decision names a per-version screening result'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER review_decisions_screening_kind BEFORE INSERT ON review_decisions "
        "FOR EACH ROW EXECUTE FUNCTION review_decisions_screening_kind()"
    )

    op.execute(
        """
        CREATE TABLE screening_feedback (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            screening_result_id uuid NOT NULL,
            user_id uuid NOT NULL,
            thumb text NOT NULL CHECK (thumb IN ('up', 'down')),
            reason_code text NULL CHECK (
                reason_code IN ('wrong_request_match', 'wrong_period', 'unclear_file', 'other')
            ),
            note_sealed bytea NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT screening_feedback_down_needs_a_reason
                CHECK (thumb = 'up' OR reason_code IS NOT NULL),
            FOREIGN KEY (tenant_id, screening_result_id)
                REFERENCES screening_results (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX screening_feedback_by_result "
        "ON screening_feedback (tenant_id, screening_result_id, user_id)"
    )
    tenant_table(op, "screening_feedback")
    insert_only(op, "screening_feedback")
    op.execute("REVOKE TRUNCATE ON screening_feedback FROM abacus_app")
    insert_columns(
        op,
        "screening_feedback",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "screening_result_id",
            "user_id",
            "thumb",
            "reason_code",
            "note_sealed",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION screening_feedback_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.user_id::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'feedback is given by the session''s own person (ADR-005)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM screening_results s
                 WHERE s.tenant_id = NEW.tenant_id AND s.id = NEW.screening_result_id
                   AND s.subject_kind = 'request_batch' AND s.engagement_id = NEW.engagement_id
            ) THEN
                RAISE EXCEPTION 'feedback is given on a screening aggregate of its engagement'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER screening_feedback_guard BEFORE INSERT ON screening_feedback "
        "FOR EACH ROW EXECUTE FUNCTION screening_feedback_guard()"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM screening_results "
        "WHERE subject_kind = 'request_batch') THEN "
        "RAISE EXCEPTION 'refusing to downgrade: screening aggregates exist'; "
        "END IF; END $$"
    )
    op.execute("ALTER TABLE screening_feedback NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP TABLE screening_feedback")
    op.execute("DROP FUNCTION screening_feedback_guard()")
    op.execute("DROP TRIGGER review_decisions_screening_kind ON review_decisions")
    op.execute("DROP FUNCTION review_decisions_screening_kind()")
    op.execute("DROP TRIGGER screening_results_batch_guard ON screening_results")
    op.execute("DROP FUNCTION screening_results_batch_guard()")
    insert_columns(op, "screening_results", _COLUMNS_0010)
    op.execute("DROP INDEX screening_results_batch_once")
    for name in (
        "screening_results_supersedes_once",
        "screening_results_supersedes_fkey",
        "screening_results_request_item_fkey",
        "screening_results_created_by_kind_check",
        "screening_results_batch_values",
        "screening_results_batch_shape",
        "screening_results_version_shape",
        "screening_results_subject_kind",
    ):
        op.execute(f"ALTER TABLE screening_results DROP CONSTRAINT {name}")
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_created_by_kind_check "
        "CHECK (created_by_kind = 'agent')"
    )
    op.execute("DROP INDEX screening_results_once_per_run")
    op.execute(
        "ALTER TABLE screening_results ADD CONSTRAINT screening_results_once_per_run "
        "UNIQUE (tenant_id, agent_run_id)"
    )
    for column in _PER_RUN:
        op.execute(f"ALTER TABLE screening_results ALTER COLUMN {column} SET NOT NULL")
    op.execute(
        "ALTER TABLE screening_results "
        + ", ".join(f"DROP COLUMN {c}" for c in (*_AGGREGATE, "supersedes_id", "subject_kind"))
    )
