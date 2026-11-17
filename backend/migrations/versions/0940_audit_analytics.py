"""Audit analytics (A-08-T21; A-08 §6 M7; SPEC-657 F5, AC-5.1 to AC-5.6; AUD-13 a to e; DEC-5400).

- `analytics_sets`: one version of a flux run over a TB layer against prior-year figures, its
  dual threshold (percentage **and** amount, the amount from the materiality version's PM, the
  provisional flag) and its stamp. A recompute is a new version; the earlier one reads
  Superseded. One computing and one current set per work item, kind and stage.
- `analytics_lines` (insert-only per version): code's change, change %, evaluated, over, derived,
  the TB accounts each FS line adds up (SHL-09 provenance).
- `analytics_explanations` (insert-only): an explanation counts only with >= 1 verified citation,
  or, for a client answer, the question it answers; acceptance stamps `accepted_by` /
  `accepted_at` once, never by the author.
- `analytics_expectations` (SSARS expectation ranges, A-08-T22).
- `prior_year_figures` (insert-only imports, numbered per work item).
- `analytics_questions` (insert-only): the line each sent client question asks about.
- `questionnaires.kind` gains `analytics_question` and `ssars_inquiry` (T-02's table).

Revision ID: 0940
Revises: 0933
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0940"
down_revision = "0933"
branch_labels = None
depends_on = None

_KINDS_BEFORE = "('organizer', 'team_questions', 'inquiry')"
_KINDS_AFTER = "('organizer', 'team_questions', 'inquiry', 'analytics_question', 'ssars_inquiry')"

SET_INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "kind", "stage", "version_no",
    "cy_trial_balance_id", "cy_layer", "py_source", "threshold_pct", "threshold_amount",
    "materiality_version_id", "threshold_policy_version_id", "provisional", "engine_version",
    "basis_label", "created_by", "run_parameters",
)  # fmt: skip
SET_UPDATES = (
    "status", "superseded_by", "inputs_hash", "content_hash", "computed_at", "tb_balanced",
    "failure_code",
)  # fmt: skip
LINE_INSERTS = (
    "tenant_id", "set_id", "position", "fs_line_key", "caption", "group_key", "cy", "py",
    "change", "change_pct", "evaluated", "over", "derived", "status", "sources", "cell",
)  # fmt: skip
EXPLANATION_INSERTS = (
    "tenant_id", "set_id", "line_position", "text", "citation_ids", "source", "suggestion_id",
    "question_id", "answered_by_contact_id", "authored_by", "carried_from_id", "accepted_by",
    "accepted_at",
)  # fmt: skip
EXPECTATION_INSERTS = (
    "tenant_id", "set_id", "line_position", "low", "high", "pct_low", "pct_high", "basis",
    "citation_ids", "set_by",
)  # fmt: skip
PY_INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "import_no", "source", "fs_line_key", "amount",
    "citation_id", "imported_by",
)  # fmt: skip
QUESTION_INSERTS = (
    "tenant_id", "set_id", "line_position", "questionnaire_id", "question_id", "template_key",
    "sent_by",
)  # fmt: skip


def _kinds(values: str) -> None:
    op.execute("ALTER TABLE questionnaires DROP CONSTRAINT questionnaires_kind_check")
    op.execute(
        "ALTER TABLE questionnaires ADD CONSTRAINT questionnaires_kind_check "
        f"CHECK (kind IN {values})"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE analytics_sets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('audit_flux', 'ssars_review')),
            stage text NOT NULL CHECK (stage IN ('preliminary', 'substantive', 'final', 'review')),
            version_no integer NOT NULL CHECK (version_no >= 1),
            cy_trial_balance_id uuid NOT NULL,
            cy_layer text NOT NULL CHECK (cy_layer IN ('unadjusted', 'adjusted')),
            py_source text NOT NULL CHECK (py_source IN ('prior_engagement', 'import')),
            threshold_pct numeric(7, 2) NOT NULL CHECK (threshold_pct > 0),
            threshold_amount numeric(20, 2) NOT NULL CHECK (threshold_amount >= 0),
            materiality_version_id uuid NULL,
            threshold_policy_version_id uuid NULL,
            provisional boolean NOT NULL,
            engine_version text NOT NULL,
            basis_label text NOT NULL CHECK (length(basis_label) BETWEEN 1 AND 120),
            run_parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            content_hash text NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            tb_balanced boolean NULL,
            status text NOT NULL DEFAULT 'computing'
                CHECK (status IN ('computing', 'current', 'out_of_date', 'superseded')),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z0-9_]{0,63}$'),
            superseded_by uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            computed_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, kind, stage, version_no),
            CHECK ((status = 'superseded') = (superseded_by IS NOT NULL)),
            CHECK (status = 'computing' OR failure_code IS NOT NULL OR content_hash IS NOT NULL),
            -- An SSARS review set is only ever the review stage, and an audit set never is.
            CHECK ((kind = 'ssars_review') = (stage = 'review')),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    # One compute at a time and one current set per work item, kind and stage; the compute
    # supersedes the current set and becomes current in one transaction.
    for name, status in (("one_computing", "computing"), ("one_current", "current")):
        op.execute(
            f"CREATE UNIQUE INDEX analytics_sets_{name} ON analytics_sets "
            f"(tenant_id, work_item_id, kind, stage) WHERE status = '{status}'"
        )
    tenant_table(op, "analytics_sets")
    insert_columns(op, "analytics_sets", SET_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON analytics_sets FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(SET_UPDATES)}) ON analytics_sets TO abacus_app")

    op.execute(
        """
        CREATE TABLE analytics_lines (
            tenant_id uuid NOT NULL,
            set_id uuid NOT NULL,
            position integer NOT NULL CHECK (position BETWEEN 1 AND 500),
            fs_line_key text NOT NULL CHECK (length(fs_line_key) BETWEEN 1 AND 120),
            caption text NOT NULL CHECK (length(caption) BETWEEN 1 AND 200),
            group_key text NOT NULL CHECK (length(group_key) BETWEEN 1 AND 120),
            cy numeric(20, 2) NOT NULL,
            py numeric(20, 2) NOT NULL,
            change numeric(20, 2) NOT NULL,
            change_pct numeric(12, 1) NULL,
            evaluated boolean NOT NULL,
            over boolean NOT NULL,
            derived boolean NOT NULL,
            status text NULL CHECK (status IN ('within', 'unexplained')),
            sources text[] NOT NULL DEFAULT '{}' CHECK (cardinality(sources) <= 500),
            cell text NOT NULL CHECK (cell ~ '^[A-Z]{1,3}[0-9]{1,5}$'),
            PRIMARY KEY (tenant_id, set_id, position),
            CHECK (change = cy - py),
            -- Subtotals are derived and never evaluated; only an evaluated line can be over.
            CHECK (NOT (derived AND evaluated)),
            CHECK (evaluated OR NOT over),
            CHECK ((status IS NULL) = derived),
            CHECK (status IS NULL OR (status = 'unexplained') = over),
            FOREIGN KEY (tenant_id, set_id) REFERENCES analytics_sets (tenant_id, id)
        )
        """
    )
    tenant_table(op, "analytics_lines")
    insert_columns(op, "analytics_lines", LINE_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON analytics_lines FROM abacus_app")

    op.execute(
        """
        CREATE TABLE analytics_explanations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            set_id uuid NOT NULL,
            line_position integer NOT NULL,
            text text NOT NULL CHECK (length(btrim(text)) BETWEEN 1 AND 1000),
            citation_ids uuid[] NOT NULL DEFAULT '{}' CHECK (cardinality(citation_ids) <= 20),
            source text NOT NULL CHECK (source IN ('agent', 'staff', 'client_answer')),
            suggestion_id uuid NULL,
            question_id uuid NULL,
            answered_by_contact_id uuid NULL,
            authored_by uuid NULL,
            carried_from_id uuid NULL,
            accepted_by uuid NULL,
            accepted_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- INV-2 (AC-5.3): a firm explanation names >= 1 verified citation; a client answer
            -- names the question it answers (the answer itself is the source).
            CHECK (cardinality(citation_ids) >= 1
                OR (source = 'client_answer' AND question_id IS NOT NULL)),
            CHECK ((source = 'client_answer') = (authored_by IS NULL)),
            CHECK (source <> 'agent' OR suggestion_id IS NOT NULL),
            CHECK ((accepted_by IS NULL) = (accepted_at IS NULL)),
            -- I-SEGREGATION: the acceptor is never the author.
            CHECK (accepted_by IS NULL OR accepted_by IS DISTINCT FROM authored_by),
            FOREIGN KEY (tenant_id, set_id, line_position)
                REFERENCES analytics_lines (tenant_id, set_id, position),
            FOREIGN KEY (tenant_id, authored_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, accepted_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX analytics_explanations_line ON analytics_explanations "
        "(tenant_id, set_id, line_position, created_at DESC)"
    )
    tenant_table(op, "analytics_explanations")
    insert_columns(op, "analytics_explanations", EXPLANATION_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON analytics_explanations FROM abacus_app")
    op.execute("GRANT UPDATE (accepted_by, accepted_at) ON analytics_explanations TO abacus_app")
    # Accepted once: the stamp moves from NULL to a person and never changes again.
    op.execute(
        """
        CREATE FUNCTION analytics_explanations_accept_once() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.accepted_by IS NOT NULL THEN
                RAISE EXCEPTION 'analytics explanation already accepted'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER analytics_explanations_accept_once BEFORE UPDATE ON "
        "analytics_explanations FOR EACH ROW EXECUTE FUNCTION analytics_explanations_accept_once()"
    )

    op.execute(
        """
        CREATE TABLE analytics_expectations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            set_id uuid NOT NULL,
            line_position integer NOT NULL,
            low numeric(20, 2) NULL,
            high numeric(20, 2) NULL,
            pct_low numeric(9, 2) NULL,
            pct_high numeric(9, 2) NULL,
            basis text NOT NULL CHECK (length(btrim(basis)) BETWEEN 1 AND 300),
            citation_ids uuid[] NOT NULL DEFAULT '{}' CHECK (cardinality(citation_ids) <= 20),
            set_by uuid NOT NULL,
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (low IS NULL OR high IS NULL OR low <= high),
            CHECK (pct_low IS NULL OR pct_high IS NULL OR pct_low <= pct_high),
            FOREIGN KEY (tenant_id, set_id, line_position)
                REFERENCES analytics_lines (tenant_id, set_id, position),
            FOREIGN KEY (tenant_id, set_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX analytics_expectations_line ON analytics_expectations "
        "(tenant_id, set_id, line_position, set_at DESC)"
    )
    tenant_table(op, "analytics_expectations")
    insert_columns(op, "analytics_expectations", EXPECTATION_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON analytics_expectations FROM abacus_app")

    op.execute(
        """
        CREATE TABLE prior_year_figures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            import_no integer NOT NULL CHECK (import_no >= 1),
            source text NOT NULL CHECK (source IN ('prior_engagement', 'import')),
            fs_line_key text NOT NULL CHECK (length(fs_line_key) BETWEEN 1 AND 120),
            amount numeric(20, 2) NOT NULL,
            citation_id uuid NULL,
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, work_item_id, import_no, fs_line_key),
            CHECK (source = 'prior_engagement' OR citation_id IS NOT NULL),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "prior_year_figures")
    insert_columns(op, "prior_year_figures", PY_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON prior_year_figures FROM abacus_app")

    op.execute(
        """
        CREATE TABLE analytics_questions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            set_id uuid NOT NULL,
            line_position integer NOT NULL,
            questionnaire_id uuid NOT NULL,
            question_id uuid NOT NULL,
            template_key text NOT NULL CHECK (length(template_key) BETWEEN 1 AND 120),
            sent_by uuid NOT NULL,
            sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, question_id),
            FOREIGN KEY (tenant_id, set_id, line_position)
                REFERENCES analytics_lines (tenant_id, set_id, position),
            FOREIGN KEY (tenant_id, sent_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "analytics_questions")
    insert_columns(op, "analytics_questions", QUESTION_INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON analytics_questions FROM abacus_app")

    _kinds(_KINDS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM questionnaires WHERE kind IN ('analytics_question', 'ssars_inquiry')")
    _kinds(_KINDS_BEFORE)
    op.execute("DROP TABLE analytics_questions")
    op.execute("DROP TABLE prior_year_figures")
    op.execute("DROP TABLE analytics_expectations")
    op.execute("DROP TRIGGER analytics_explanations_accept_once ON analytics_explanations")
    op.execute("DROP FUNCTION analytics_explanations_accept_once()")
    op.execute("DROP TABLE analytics_explanations")
    op.execute("DROP TABLE analytics_lines")
    op.execute("DROP TABLE analytics_sets")
