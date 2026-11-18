"""Tax practice tools (T-08-T06; SPEC-710 AC-21 to AC-30, AC-35; T-08 §4.2; DEC-5605).
Expand-only; the pipeline runs it after 8 pm CT inside the window (P-29).

Thirteen new tax tables with forced RLS and one widened. Two-year: insert-only
`variance_explanation_versions` (TRI) and human-only `variance_explanation_acceptances`
(staleness = the current values hash differs from the stored one, computed on read). Standards
runs: `standards_runs`, `standards_run_items`, insert-only `standards_check_results` (no outcome
is ever written by a model) and human-only `standards_check_confirmations`. Planning: insert-only
`planning_screens` and `planning_opportunity_events`; T-05's `planning_opportunities` (0830, memo
rows, `open` only) is widened additively: rule rows, the six statuses, the consent basis (a
non-tax product needs a consent), the code's savings and its basis. Amendments: `amendments`,
insert-only `amendment_explanation_versions` (TRI), insert-only `return_supersessions` (the
original row is never updated), `aar_adjustments` (TRI) and the human-only insert-only
`aar_elections`.

`tax_return_accepted_frozen` refuses a write to an accepted return's identity fields (AC6.7:
409 `return_accepted` in the service, the trigger behind it); its status, sync and hold fields
stay with their owners. Δ, Δ%, flags, tallies and savings are never stored except the code's
`est_savings` with its basis.

Revision ID: 0961
Revises: 0960
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0961"
down_revision = "0960"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,"""
_WI = """
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_WI_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT,"""
_KEYS = """
            UNIQUE (tenant_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)),"
)
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy') "
    "AND actor_kind = current_setting('app.actor_kind', true)),"
)
_MONEY = "numeric(20, 2)"
_HASH = "text NOT NULL CHECK ({c} ~ '^[0-9a-f]{{64}}$')"
_PO = "planning_opportunities"
_OPP = "('open', 'raised', 'accepted', 'declined', 'not_screened', 'dismissed')"
_WIC = ("tenant_id", "engagement_id", "work_item_id")

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("variance_explanation_versions", f"""{_WI}
            line_key text NOT NULL CHECK (line_key ~ '^[a-z0-9_.]{{1,40}}$'),
            version_no integer NOT NULL CHECK (version_no >= 1),
            text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 600),
            citations jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(citations) = 'array'),
            author_kind text NOT NULL CHECK (author_kind IN ('agent', 'human')),
            suggestion_id uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT variance_explanation_versions_agent
                CHECK (author_kind = 'human' OR suggestion_id IS NOT NULL),
            UNIQUE (work_item_id, line_key, version_no),{_WI_FK}""",
     (*_WIC, "line_key", "version_no", "text", "citations", "author_kind", "suggestion_id",
      "created_by"), (), True),
    ("variance_explanation_acceptances", f"""
            version_id uuid NOT NULL,
            values_hash {_HASH.format(c="values_hash")},
            threshold_source jsonb NOT NULL CHECK (jsonb_typeof(threshold_source) = 'object'),
            accepted_by uuid NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES variance_explanation_versions (tenant_id, id),""",
     ("tenant_id", "version_id", "values_hash", "threshold_source", "accepted_by"), (), True),
    ("standards_runs", """
            standard_version_id uuid NOT NULL,
            form text NOT NULL CHECK (form IN ('1040', '1041', '1065', '1120s', '1120', '990')),
            started_by uuid NOT NULL,
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'complete', 'failed')),
            completed_at timestamptz NULL,""",
     ("tenant_id", "standard_version_id", "form", "started_by"),
     ("status", "completed_at"), False),
    ("standards_run_items", f"""{_WI}
            run_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'passed', 'exceptions', 'failed')),
            checks_total integer NOT NULL DEFAULT 0 CHECK (checks_total >= 0),
            checks_passed integer NOT NULL DEFAULT 0
                CHECK (checks_passed BETWEEN 0 AND checks_total),
            completed_at timestamptz NULL,
            UNIQUE (run_id, work_item_id),
            FOREIGN KEY (tenant_id, run_id) REFERENCES standards_runs (tenant_id, id),{_WI_FK}""",
     (*_WIC, "run_id", "checks_total"),
     ("status", "checks_total", "checks_passed", "completed_at"), False),
    ("standards_check_results", f"""
            run_item_id uuid NOT NULL,
            check_key text NOT NULL
                CHECK (check_key ~ '^[0-9a-z]{{3,6}}-v[0-9]{{1,3}}/[A-Z]-[0-9]{{2,3}}$'),
            outcome text NOT NULL
                CHECK (outcome IN ('pass', 'exception', 'manual_pending', 'not_applicable')),
            difference {_MONEY} NULL,
            anchor jsonb NULL CHECK (anchor IS NULL OR jsonb_typeof(anchor) = 'object'),
            linked_issue_id uuid NULL,
            created_issue_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_ACTOR}
            CONSTRAINT standards_check_results_no_model CHECK (actor_kind <> 'agent'),
            CONSTRAINT standards_check_results_one_issue
                CHECK (linked_issue_id IS NULL OR created_issue_id IS NULL),
            UNIQUE (run_item_id, check_key),
            FOREIGN KEY (tenant_id, run_item_id)
                REFERENCES standards_run_items (tenant_id, id),""",
     ("tenant_id", "run_item_id", "check_key", "outcome", "difference", "anchor",
      "linked_issue_id", "created_issue_id"), (), True),
    ("standards_check_confirmations", f"""
            result_id uuid NOT NULL UNIQUE,
            outcome text NOT NULL CHECK (outcome IN ('pass', 'exception')),
            note text NULL CHECK (char_length(note) <= 1000),
            confirmed_by uuid NOT NULL,
            confirmed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            FOREIGN KEY (tenant_id, result_id)
                REFERENCES standards_check_results (tenant_id, id),""",
     ("tenant_id", "result_id", "outcome", "note", "confirmed_by"), (), True),
    ("planning_screens", """
            work_item_id uuid NULL,
            partner_user_id uuid NOT NULL,
            trigger text NOT NULL CHECK (trigger IN
                ('return_approved', 'return_accepted', 'consent_completed', 'manual')),
            rules_version text NOT NULL CHECK (char_length(rules_version) BETWEEN 1 AND 40),
            agent_run_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id)
                ON DELETE RESTRICT,""",
     ("tenant_id", "work_item_id", "partner_user_id", "trigger", "rules_version", "agent_run_id"),
     (), True),
    ("planning_opportunity_events", f"""
            opportunity_id uuid NOT NULL,
            from_status text NULL CHECK (from_status IN {_OPP}),
            to_status text NOT NULL CHECK (to_status IN {_OPP}),
            event text NOT NULL CHECK (event ~ '^[a-z][a-z_]{{1,39}}$'),
            reason text NULL CHECK (reason IN
                ('not_suitable', 'already_in_place', 'client_declined', 'other')),
            note text NULL CHECK (char_length(note) <= 1000),
            actor_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_ACTOR}
            CONSTRAINT planning_opportunity_events_dismiss_reason
                CHECK (to_status <> 'dismissed' OR reason IS NOT NULL),
            CONSTRAINT planning_opportunity_events_human_moves CHECK (
                to_status NOT IN ('raised', 'declined', 'dismissed') OR actor_kind = 'human'
            ),
            FOREIGN KEY (tenant_id, opportunity_id)
                REFERENCES planning_opportunities (tenant_id, id),""",
     ("tenant_id", "opportunity_id", "from_status", "to_status", "event", "reason", "note",
      "actor_id"), (), True),
    ("amendments", f"""{_WI}
            original_work_item_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('amended_return', 'bba_aar')),
            jurisdictions text[] NOT NULL CHECK (cardinality(jurisdictions) BETWEEN 1 AND 10),
            baseline_checkpoint_id uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            CONSTRAINT amendments_not_self CHECK (original_work_item_id <> work_item_id),
            UNIQUE (work_item_id),
            FOREIGN KEY (original_work_item_id) REFERENCES tax_returns (work_item_id)
                ON DELETE RESTRICT,{_WI_FK}""",
     (*_WIC, "original_work_item_id", "kind", "jurisdictions", "baseline_checkpoint_id",
      "created_by"), ("baseline_checkpoint_id", "row_version"), False),
    ("amendment_explanation_versions", """
            amendment_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 4000),
            author_kind text NOT NULL CHECK (author_kind IN ('agent', 'human')),
            suggestion_id uuid NULL,
            edit_diff jsonb NULL CHECK (edit_diff IS NULL OR jsonb_typeof(edit_diff) = 'object'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT amendment_explanation_versions_agent
                CHECK (author_kind = 'human' OR suggestion_id IS NOT NULL),
            UNIQUE (amendment_id, version_no),
            FOREIGN KEY (tenant_id, amendment_id) REFERENCES amendments (tenant_id, id),""",
     ("tenant_id", "amendment_id", "version_no", "text", "author_kind", "suggestion_id",
      "edit_diff", "created_by"), (), True),
    ("return_supersessions", """
            original_work_item_id uuid NOT NULL,
            superseded_by_work_item_id uuid NOT NULL,
            ack_id uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT return_supersessions_not_self
                CHECK (original_work_item_id <> superseded_by_work_item_id),
            UNIQUE (tenant_id, original_work_item_id),
            FOREIGN KEY (original_work_item_id) REFERENCES tax_returns (work_item_id)
                ON DELETE RESTRICT,
            FOREIGN KEY (superseded_by_work_item_id) REFERENCES tax_returns (work_item_id)
                ON DELETE RESTRICT,""",
     ("tenant_id", "original_work_item_id", "superseded_by_work_item_id", "ack_id"), (), True),
    ("aar_adjustments", f"""
            amendment_id uuid NOT NULL,
            reviewed_year integer NOT NULL CHECK (reviewed_year BETWEEN 2018 AND 2100),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 200),
            amount {_MONEY} NOT NULL,
            position smallint NOT NULL CHECK (position BETWEEN 1 AND 999),
            UNIQUE (amendment_id, position),
            FOREIGN KEY (tenant_id, amendment_id) REFERENCES amendments (tenant_id, id),""",
     ("tenant_id", "amendment_id", "reviewed_year", "description", "amount", "position"),
     ("description", "amount"), False),
    ("aar_elections", f"""
            amendment_id uuid NOT NULL UNIQUE,
            decision_id uuid NOT NULL,
            route text NOT NULL CHECK (route IN ('pay_imputed_underpayment', 'push_out')),
            imputed_underpayment {_MONEY} NOT NULL CHECK (imputed_underpayment >= 0),
            iu_source text NOT NULL CHECK (iu_source IN ('engine', 'shadow')),
            decided_by uuid NOT NULL,
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            FOREIGN KEY (tenant_id, amendment_id) REFERENCES amendments (tenant_id, id),""",
     ("tenant_id", "amendment_id", "decision_id", "route", "imputed_underpayment", "iu_source",
      "decided_by"), (), True),
)  # fmt: skip

# T-05's memo table (0830) widened additively for rule rows and the six statuses (T-08 §4.2).
_PLANNING_ADD = (
    "client_id uuid NULL",
    "screen_id uuid NULL",
    "rule_key text NULL CHECK (rule_key ~ '^[a-z][a-z0-9_.]{0,59}$')",
    "category text NULL CHECK (char_length(category) BETWEEN 1 AND 60)",
    "product_kind text NOT NULL DEFAULT 'tax_service' "
    "CHECK (product_kind IN ('tax_service', 'non_tax_product'))",
    f"previous_status text NULL CHECK (previous_status IN {_OPP})",
    f"est_savings {_MONEY} NULL CHECK (est_savings IS NULL OR est_savings >= 0)",
    "savings_basis jsonb NULL "
    "CHECK (savings_basis IS NULL OR jsonb_typeof(savings_basis) = 'object')",
    "consent_basis text NOT NULL DEFAULT '301_7216_2h' "
    "CHECK (consent_basis IN ('301_7216_2h', 'other_services_use'))",
    "consent_id uuid NULL",
    "rationale_suggestion_id uuid NULL",
    "talking_points_suggestion_id uuid NULL",
    "client_draft_suggestion_id uuid NULL",
    "owner_user_id uuid NULL",
    "project_engagement_id uuid NULL",
    "raised_message_id uuid NULL",
    "row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1)",
)
PLANNING_INSERT = (
    "client_id",
    "screen_id",
    "rule_key",
    "category",
    "product_kind",
    "est_savings",
    "savings_basis",
    "consent_basis",
    "consent_id",
    "rationale_suggestion_id",
    "talking_points_suggestion_id",
    "client_draft_suggestion_id",
    "owner_user_id",
)
PLANNING_UPDATE = (
    "status", "previous_status", "est_savings", "savings_basis", "rationale_suggestion_id",
    "talking_points_suggestion_id", "client_draft_suggestion_id", "owner_user_id",
    "project_engagement_id", "raised_message_id", "row_version",
)  # fmt: skip

# AC6.7: an accepted return's identity never changes (its status, sync and hold stay live).
_FROZEN = (
    "form",
    "tax_year",
    "fiscal_year_end",
    "jurisdictions",
    "filing_status",
    "engine_return_id",
    "prior_year_return_id",
    "amends_return_id",
)


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def upgrade() -> None:
    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
            _immutable(table)
        else:
            op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
            if upd:
                op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # T-05's planning_opportunities, widened (expand-only: new nullable or defaulted columns and
    # wider CHECKs; T-05's memo rows stay valid).
    for column in _PLANNING_ADD:
        op.execute(f"ALTER TABLE {_PO} ADD COLUMN {column}")
    op.execute(f"ALTER TABLE {_PO} DROP CONSTRAINT {_PO}_status_check")
    op.execute(f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_status_check CHECK (status IN {_OPP})")
    op.execute(f"ALTER TABLE {_PO} DROP CONSTRAINT {_PO}_source_kind_check")
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_source_kind_check "
        "CHECK (source_kind IN ('memo', 'rule', 'manual'))"
    )
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_non_tax_consent "
        "CHECK (product_kind = 'tax_service' OR consent_id IS NOT NULL)"
    )
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_rule_row "
        "CHECK (source_kind <> 'rule' OR (rule_key IS NOT NULL AND client_id IS NOT NULL "
        "AND owner_user_id IS NOT NULL))"
    )
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_savings_basis "
        "CHECK ((est_savings IS NULL) = (savings_basis IS NULL))"
    )
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_screen_fk "
        "FOREIGN KEY (tenant_id, screen_id) REFERENCES planning_screens (tenant_id, id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX planning_opportunities_rule ON planning_opportunities "
        "(work_item_id, rule_key) WHERE rule_key IS NOT NULL"
    )
    op.execute(
        f"GRANT INSERT ({', '.join(PLANNING_INSERT)}) ON planning_opportunities TO abacus_app"
    )
    op.execute(
        f"GRANT UPDATE ({', '.join(PLANNING_UPDATE)}) ON planning_opportunities TO abacus_app"
    )
    changed = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in _FROZEN)
    op.execute(
        f"""
        CREATE FUNCTION tax_return_accepted_frozen() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.status = 'accepted' AND ({changed}) THEN
                RAISE EXCEPTION 'return_accepted' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER tax_return_accepted_frozen BEFORE UPDATE ON tax_returns "
        "FOR EACH ROW EXECUTE FUNCTION tax_return_accepted_frozen()"
    )


def downgrade() -> None:
    op.execute("DROP INDEX planning_opportunities_rule")
    for name in ("screen_fk", "savings_basis", "rule_row", "non_tax_consent"):
        op.execute(f"ALTER TABLE {_PO} DROP CONSTRAINT {_PO}_{name}")
    for column in reversed(_PLANNING_ADD):
        op.execute(f"ALTER TABLE {_PO} DROP COLUMN {column.split(' ', 1)[0]}")
    op.execute(f"ALTER TABLE {_PO} DROP CONSTRAINT {_PO}_status_check")
    op.execute(f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_status_check CHECK (status IN ('open'))")
    op.execute(f"ALTER TABLE {_PO} DROP CONSTRAINT {_PO}_source_kind_check")
    op.execute(
        f"ALTER TABLE {_PO} ADD CONSTRAINT {_PO}_source_kind_check CHECK (source_kind IN ('memo'))"
    )
    op.execute("DROP TRIGGER tax_return_accepted_frozen ON tax_returns")
    op.execute("DROP FUNCTION tax_return_accepted_frozen()")
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    for table, _body, _ins, _upd, io in TABLES:
        if io:
            op.execute(f"DROP FUNCTION {table}_immutable()")
