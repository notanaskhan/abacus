"""C-01-T11 (S45; TASK-8067; C-01 §4.2 T11; SPEC-655): `closes_v2` and `requests_cas`,
expand-only.

The close engine's computed and client-facing records:

- **Reconciliation** (CLS-05): `reconciliations` (one row per computed version of an account's
  bank reconciliation; a recompute is a new version, never an update; `engine_version`,
  `inputs_hash` and `content_hash` make a version reproducible), `reconciling_items` and their
  human `reconciling_item_resolutions` (`actor_kind = 'human'`), `statement_lines` (derived from
  P-11's extracted tables, with the page region the CLS-05 viewer highlights) and
  `reconciliation_matches`.
- **Schedules** (CLS-04): `arrangements` with insert-only `arrangement_versions` (an edit is a new
  version) and `close_schedule_results`.
- **Flux** (CLS-10): `analytic_sets`, `analytic_lines` and `analytic_explanations` (sealed text;
  an agent may draft, only a named human accepts: `accepted_actor_kind = 'human'`).
- **Recordings**: `close_entry_recordings` ("Recorded in QuickBooks"): a proposed entry matched to
  the client's ledger; a person confirms it once.
- **Client questions** (CLS-06, POR-11; owner `requests`): `transaction_questions` (template
  wording only, the client's answer sealed) and insert-only `transaction_question_events`.

Every table is tenant-scoped with forced RLS (`tenant_table()`); the app role inserts named
columns only. Insert-only tables refuse UPDATE and DELETE. The few set-later columns (an item's
issue and proposed entry, an explanation's acceptance, a recording's confirmation, a flux line's
status, a question's answer) are granted column by column and guarded by triggers: set once, or
forward only. Classification (ADR-031): client ledger and statement content `confidential`;
client answers `confidential` and sealed; nothing here is TRI.

Revision ID: 0885
Revises: 0884
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0885"
down_revision = "0884"
branch_labels = None
depends_on = None

_PERIOD = "~ '^[0-9]{4}-(0[1-9]|1[0-2])$'"
_ACCOUNT = "text NOT NULL CHECK (length(account_external_id) BETWEEN 1 AND 64)"
_HASH = "text NOT NULL CHECK (length({c}) = 64)"
_ENGINE = "text NOT NULL CHECK (length(engine_version) BETWEEN 1 AND 40)"
_CLOSE_FK = "FOREIGN KEY (close_id) REFERENCES closes (work_item_id)"
_HUMAN = "uuid NOT NULL"

_TABLES = (
    # (table, insert columns, update columns)
    ("reconciliations",
     ("tenant_id", "close_id", "account_external_id", "period", "version",
      "statement_evidence_version_id", "balance_per_bank", "adjusted_bank", "book_balance",
      "adjusted_book", "difference", "tally", "engine_version", "inputs_hash", "content_hash"),
     ()),
    ("statement_lines",
     ("tenant_id", "evidence_version_id", "page_no", "bbox", "txn_date", "description",
      "withdrawal", "deposit", "running_balance", "source_table_id", "confidence"),
     ()),
    ("reconciling_items",
     ("tenant_id", "reconciliation_id", "side", "kind", "ref", "txn_date", "days_at_period_end",
      "amount", "stale", "statement_line_id", "register_line_ref", "issue_id",
      "proposed_entry_id", "carried_from_item_id"),
     ("issue_id", "proposed_entry_id")),
    ("reconciling_item_resolutions",
     ("tenant_id", "item_id", "resolution", "note", "actor_id", "actor_kind"),
     ()),
    ("reconciliation_matches",
     ("tenant_id", "reconciliation_id", "statement_line_id", "register_line_ref", "match_rule"),
     ()),
    ("arrangements",
     ("tenant_id", "client_entity_id", "account_external_id", "kind", "created_by"),
     ()),
    ("arrangement_versions",
     ("tenant_id", "arrangement_id", "version", "description", "expense_account_ref",
      "scheduled_total", "starting_balance", "starting_on", "frequency", "start_on",
      "finish_on", "source_citation_id", "actor_id"),
     ()),
    ("close_schedule_results",
     ("tenant_id", "close_id", "arrangement_id", "period", "inflows", "aje", "ending_balance",
      "gl_balance", "tie", "engine_version", "inputs_hash"),
     ()),
    ("analytic_sets",
     ("tenant_id", "close_id", "basis", "threshold_policy_version_id", "version",
      "engine_version", "inputs_hash"),
     ()),
    ("analytic_lines",
     ("tenant_id", "set_id", "position", "line_key", "caption", "prior", "current", "change",
      "change_pct", "test", "status"),
     ("status",)),
    ("analytic_explanations",
     ("tenant_id", "close_id", "line_key", "version", "text_sealed", "drivers", "citation_ids",
      "author_kind", "suggestion_id"),
     ("accepted_by", "accepted_actor_kind", "accepted_at")),
    ("close_entry_recordings",
     ("tenant_id", "close_id", "proposed_entry_id", "ledger_snapshot_id", "external_txn_id",
      "match_rule"),
     ("confirmed_by", "confirmed_at")),
    ("transaction_questions",
     ("tenant_id", "work_item_id", "request_list_id", "issue_id", "template_id",
      "template_version", "client_wording", "context", "asked_by", "assignee_contact_id"),
     ("status", "answer_sealed", "answered_by_contact_id", "answered_at",
      "fulfils_request_item_id", "row_version")),
    ("transaction_question_events",
     ("tenant_id", "question_id", "kind", "actor_kind", "actor_id", "contact_id"),
     ()),
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE reconciliations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            account_external_id {_ACCOUNT},
            period text NOT NULL CHECK (period {_PERIOD}),
            version integer NOT NULL CHECK (version > 0),
            statement_evidence_version_id uuid NULL,
            balance_per_bank numeric(18, 2) NULL,
            adjusted_bank numeric(18, 2) NULL,
            book_balance numeric(18, 2) NOT NULL,
            adjusted_book numeric(18, 2) NULL,
            difference numeric(18, 2) NULL,
            tally text NOT NULL CHECK (tally IN ('pending', 'tie', 'off')),
            engine_version {_ENGINE},
            inputs_hash {_HASH.format(c="inputs_hash")},
            content_hash {_HASH.format(c="content_hash")},
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (close_id, account_external_id, version),
            -- A tie means the adjusted sides agree to the cent; "pending" has no statement yet.
            CHECK (tally <> 'tie' OR difference = 0),
            CHECK (tally <> 'off' OR difference <> 0),
            CHECK (tally = 'pending' OR (balance_per_bank IS NOT NULL
                AND adjusted_bank IS NOT NULL AND adjusted_book IS NOT NULL
                AND difference IS NOT NULL)),
            {_CLOSE_FK},
            FOREIGN KEY (tenant_id, statement_evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE statement_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            page_no integer NOT NULL CHECK (page_no > 0),
            bbox jsonb NOT NULL CHECK (jsonb_typeof(bbox) = 'array'),
            txn_date date NOT NULL,
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 500),
            withdrawal numeric(18, 2) NULL CHECK (withdrawal >= 0),
            deposit numeric(18, 2) NULL CHECK (deposit >= 0),
            running_balance numeric(18, 2) NULL,
            source_table_id uuid NOT NULL,
            confidence numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((withdrawal IS NULL) <> (deposit IS NULL)),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, source_table_id) REFERENCES extracted_tables (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE reconciling_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            reconciliation_id uuid NOT NULL,
            side text NOT NULL CHECK (side IN ('bank', 'book')),
            kind text NOT NULL CHECK (kind IN ('deposit_in_transit', 'outstanding_check',
                'unrecorded_deposit', 'unrecorded_withdrawal', 'bank_error', 'book_error')),
            ref text NULL CHECK (length(ref) <= 64),
            txn_date date NOT NULL,
            days_at_period_end integer NOT NULL CHECK (days_at_period_end >= 0),
            amount numeric(18, 2) NOT NULL CHECK (amount <> 0),
            stale boolean NOT NULL DEFAULT false,
            statement_line_id uuid NULL,
            register_line_ref text NULL CHECK (length(register_line_ref) <= 128),
            issue_id uuid NULL,
            proposed_entry_id uuid NULL,
            carried_from_item_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- The bank side's items sit on the statement; the book side's in the register.
            CHECK (side <> 'bank' OR kind IN ('deposit_in_transit', 'outstanding_check',
                'bank_error')),
            CHECK (side <> 'book' OR kind IN ('unrecorded_deposit', 'unrecorded_withdrawal',
                'book_error')),
            FOREIGN KEY (tenant_id, reconciliation_id) REFERENCES reconciliations (tenant_id, id),
            FOREIGN KEY (tenant_id, statement_line_id) REFERENCES statement_lines (tenant_id, id),
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id),
            FOREIGN KEY (tenant_id, proposed_entry_id) REFERENCES proposed_entries (tenant_id, id),
            FOREIGN KEY (tenant_id, carried_from_item_id)
                REFERENCES reconciling_items (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE reconciling_item_resolutions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            item_id uuid NOT NULL,
            resolution text NOT NULL CHECK (resolution IN ('carry_forward', 'cleared')),
            note text NOT NULL CHECK (length(btrim(note)) BETWEEN 1 AND 1000),
            actor_id {_HUMAN},
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (item_id),
            FOREIGN KEY (tenant_id, item_id) REFERENCES reconciling_items (tenant_id, id),
            FOREIGN KEY (tenant_id, actor_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE reconciliation_matches (
            tenant_id uuid NOT NULL,
            reconciliation_id uuid NOT NULL,
            statement_line_id uuid NOT NULL,
            register_line_ref text NOT NULL CHECK (length(register_line_ref) BETWEEN 1 AND 128),
            match_rule text NOT NULL CHECK (match_rule ~ '^[a-z][a-z0-9_]{1,39}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (reconciliation_id, statement_line_id, register_line_ref),
            FOREIGN KEY (tenant_id, reconciliation_id) REFERENCES reconciliations (tenant_id, id),
            FOREIGN KEY (tenant_id, statement_line_id) REFERENCES statement_lines (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE arrangements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            account_external_id {_ACCOUNT},
            kind text NOT NULL
                CHECK (kind IN ('prepaid', 'fixed_asset', 'accrual', 'deferred_revenue')),
            created_by {_HUMAN},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE arrangement_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            arrangement_id uuid NOT NULL,
            version integer NOT NULL CHECK (version > 0),
            description text NOT NULL CHECK (length(btrim(description)) BETWEEN 1 AND 200),
            expense_account_ref text NULL CHECK (length(expense_account_ref) <= 64),
            scheduled_total numeric(18, 2) NOT NULL,
            starting_balance numeric(18, 2) NOT NULL DEFAULT 0,
            starting_on date NULL,
            frequency text NOT NULL CHECK (frequency IN ('monthly', 'quarterly', 'annual')),
            start_on date NOT NULL,
            finish_on date NOT NULL,
            source_citation_id uuid NULL,
            actor_id {_HUMAN},
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (arrangement_id, version),
            CHECK (finish_on >= start_on),
            FOREIGN KEY (tenant_id, arrangement_id) REFERENCES arrangements (tenant_id, id),
            FOREIGN KEY (tenant_id, source_citation_id) REFERENCES citations (tenant_id, id),
            FOREIGN KEY (tenant_id, actor_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE close_schedule_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            arrangement_id uuid NOT NULL,
            period text NOT NULL CHECK (period {_PERIOD}),
            inflows numeric(18, 2) NOT NULL DEFAULT 0,
            aje numeric(18, 2) NOT NULL DEFAULT 0,
            ending_balance numeric(18, 2) NOT NULL,
            gl_balance numeric(18, 2) NOT NULL,
            tie text NOT NULL CHECK (tie IN ('tie', 'off', 'ties_once_posted', 'recorded')),
            engine_version {_ENGINE},
            inputs_hash {_HASH.format(c="inputs_hash")},
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (tie <> 'tie' OR ending_balance = gl_balance),
            {_CLOSE_FK},
            FOREIGN KEY (tenant_id, arrangement_id) REFERENCES arrangements (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE analytic_sets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            basis text NOT NULL CHECK (basis IN ('mom', 'yoy', 'budget')),
            threshold_policy_version_id uuid NULL,
            version integer NOT NULL CHECK (version > 0),
            engine_version {_ENGINE},
            inputs_hash {_HASH.format(c="inputs_hash")},
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (close_id, basis, version),
            {_CLOSE_FK},
            FOREIGN KEY (tenant_id, threshold_policy_version_id)
                REFERENCES threshold_policy_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE analytic_lines (
            tenant_id uuid NOT NULL,
            set_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            line_key text NOT NULL CHECK (line_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'),
            caption text NOT NULL CHECK (length(caption) BETWEEN 1 AND 200),
            prior numeric(18, 2) NULL,
            current numeric(18, 2) NOT NULL,
            change numeric(18, 2) NULL,
            change_pct numeric(9, 4) NULL,
            test text NOT NULL CHECK (test IN ('within', 'over_both', 'not_comparable')),
            status text NOT NULL CHECK (status IN ('within_threshold', 'unexplained',
                'explained_draft', 'explained', 'accepted')),
            PRIMARY KEY (set_id, position),
            UNIQUE (set_id, line_key),
            -- No prior: nothing to compare (a new account). Within: nothing to explain.
            CHECK ((prior IS NULL) = (test = 'not_comparable')),
            CHECK (test <> 'within' OR status = 'within_threshold'),
            FOREIGN KEY (tenant_id, set_id) REFERENCES analytic_sets (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE analytic_explanations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            line_key text NOT NULL CHECK (line_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'),
            version integer NOT NULL CHECK (version > 0),
            text_sealed bytea NOT NULL,
            drivers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(drivers) = 'array'),
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            author_kind text NOT NULL CHECK (author_kind IN ('human', 'agent')),
            suggestion_id uuid NULL,
            accepted_by uuid NULL,
            accepted_actor_kind text NULL CHECK (accepted_actor_kind = 'human'),
            accepted_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (close_id, line_key, version),
            -- An agent's draft arrives as a P-35 suggestion; a person's edit has none.
            CHECK ((author_kind = 'agent') = (suggestion_id IS NOT NULL)),
            CHECK ((accepted_by IS NULL) = (accepted_at IS NULL)),
            CHECK ((accepted_by IS NULL) = (accepted_actor_kind IS NULL)),
            FOREIGN KEY (close_id) REFERENCES closes (work_item_id),
            FOREIGN KEY (tenant_id, suggestion_id) REFERENCES suggestions (tenant_id, id),
            FOREIGN KEY (tenant_id, accepted_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE close_entry_recordings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            close_id uuid NOT NULL,
            proposed_entry_id uuid NOT NULL,
            ledger_snapshot_id uuid NOT NULL,
            external_txn_id text NOT NULL CHECK (length(external_txn_id) BETWEEN 1 AND 64),
            match_rule text NOT NULL CHECK (match_rule ~ '^[a-z][a-z0-9_]{{1,39}}$'),
            confirmed_by uuid NULL,
            confirmed_at timestamptz NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (proposed_entry_id, ledger_snapshot_id),
            CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL)),
            {_CLOSE_FK},
            FOREIGN KEY (tenant_id, proposed_entry_id) REFERENCES proposed_entries (tenant_id, id),
            FOREIGN KEY (tenant_id, ledger_snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, id),
            FOREIGN KEY (tenant_id, confirmed_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE transaction_questions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            request_list_id uuid NOT NULL,
            issue_id uuid NULL,
            template_id text NOT NULL CHECK (template_id ~ '^[a-z][a-z0-9_.-]{1,79}$'),
            template_version integer NOT NULL CHECK (template_version > 0),
            client_wording text NOT NULL CHECK (length(btrim(client_wording)) BETWEEN 1 AND 2000),
            context jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(context) = 'object'),
            asked_by uuid NOT NULL,
            asked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            assignee_contact_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'answered', 'withdrawn')),
            answer_sealed bytea NULL,
            answered_by_contact_id uuid NULL,
            answered_at timestamptz NULL,
            fulfils_request_item_id uuid NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            UNIQUE (tenant_id, id),
            CHECK ((status = 'answered') = (answer_sealed IS NOT NULL)),
            CHECK ((status = 'answered') = (answered_at IS NOT NULL)),
            CHECK ((status = 'answered') = (answered_by_contact_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id),
            FOREIGN KEY (tenant_id, request_list_id) REFERENCES request_lists (tenant_id, id),
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id),
            FOREIGN KEY (tenant_id, asked_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, assignee_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, answered_by_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, fulfils_request_item_id)
                REFERENCES request_items (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX transaction_questions_open ON transaction_questions "
        "(tenant_id, work_item_id) WHERE status = 'open'"
    )
    op.execute(
        """
        CREATE TABLE transaction_question_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            question_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('asked', 'reminded', 'answered', 'withdrawn')),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'client', 'system')),
            actor_id uuid NULL,
            contact_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- A firm person asks and withdraws; a client contact answers; the system reminds.
            CHECK (kind NOT IN ('asked', 'withdrawn') OR (actor_kind = 'human'
                AND actor_id IS NOT NULL)),
            CHECK (kind <> 'answered' OR (actor_kind = 'client' AND contact_id IS NOT NULL)),
            CHECK (kind <> 'reminded' OR actor_kind = 'system'),
            FOREIGN KEY (tenant_id, question_id) REFERENCES transaction_questions (tenant_id, id),
            FOREIGN KEY (tenant_id, actor_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    for index in (
        "reconciliations (tenant_id, close_id, account_external_id, version DESC)",
        "statement_lines (tenant_id, evidence_version_id, page_no)",
        "reconciling_items (tenant_id, reconciliation_id)",
        "arrangement_versions (tenant_id, arrangement_id, version DESC)",
        "close_schedule_results (tenant_id, close_id, arrangement_id)",
        "analytic_sets (tenant_id, close_id, basis, version DESC)",
        "analytic_explanations (tenant_id, close_id, line_key, version DESC)",
        "close_entry_recordings (tenant_id, close_id)",
        "transaction_question_events (tenant_id, question_id, at)",
    ):
        name = index.split(" (")[0] + "_lookup"
        op.execute(f"CREATE INDEX {name} ON {index}")

    for table, inserts, updates in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, inserts)
        if updates:
            op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
        else:
            insert_only(op, table)

    # Set-once columns: an item's issue or entry, an explanation's acceptance, a recording's
    # confirmation. Once a value is written it never changes or clears.
    op.execute(
        """
        CREATE FUNCTION closes_set_once() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_col text;
            v_old jsonb := to_jsonb(OLD);
            v_new jsonb := to_jsonb(NEW);
        BEGIN
            FOREACH v_col IN ARRAY TG_ARGV LOOP
                IF v_old ->> v_col IS NOT NULL
                   AND (v_new ->> v_col) IS DISTINCT FROM (v_old ->> v_col) THEN
                    RAISE EXCEPTION '% is set once', v_col USING ERRCODE = 'check_violation';
                END IF;
            END LOOP;
            RETURN NEW;
        END;
        $$
        """
    )
    for table, columns in (
        ("reconciling_items", "'issue_id', 'proposed_entry_id'"),
        ("analytic_explanations", "'accepted_by', 'accepted_actor_kind', 'accepted_at'"),
        ("close_entry_recordings", "'confirmed_by', 'confirmed_at'"),
    ):
        op.execute(
            f"CREATE TRIGGER {table}_set_once BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION closes_set_once({columns})"
        )
    # A flux line's status only moves toward acceptance; a recompute is a new set.
    op.execute(
        """
        CREATE FUNCTION analytic_line_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_rank constant jsonb := '{"within_threshold": 0, "unexplained": 1,
                "explained_draft": 2, "explained": 3, "accepted": 4}';
        BEGIN
            IF OLD.status = 'within_threshold' AND NEW.status <> OLD.status THEN
                RAISE EXCEPTION 'a line within threshold has nothing to explain'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'accepted' AND NEW.status <> OLD.status THEN
                RAISE EXCEPTION 'an accepted flux line is final' USING ERRCODE = 'check_violation';
            END IF;
            -- explained_draft may fall back to unexplained when its draft is discarded.
            IF (v_rank ->> NEW.status)::int < (v_rank ->> OLD.status)::int
               AND NOT (OLD.status = 'explained_draft' AND NEW.status = 'unexplained') THEN
                RAISE EXCEPTION 'flux line status moves forward only'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER analytic_line_forward BEFORE UPDATE ON analytic_lines "
        "FOR EACH ROW EXECUTE FUNCTION analytic_line_forward()"
    )
    # A question is answered or withdrawn once; the answer is never rewritten.
    op.execute(
        """
        CREATE FUNCTION transaction_question_final() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.status <> 'open' AND (NEW.status IS DISTINCT FROM OLD.status
                OR NEW.answer_sealed IS DISTINCT FROM OLD.answer_sealed
                OR NEW.answered_by_contact_id IS DISTINCT FROM OLD.answered_by_contact_id
                OR NEW.answered_at IS DISTINCT FROM OLD.answered_at) THEN
                RAISE EXCEPTION 'question_closed' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.fulfils_request_item_id IS NOT NULL
               AND NEW.fulfils_request_item_id IS DISTINCT FROM OLD.fulfils_request_item_id THEN
                RAISE EXCEPTION 'fulfils_request_item_id is set once'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER transaction_question_final BEFORE UPDATE ON transaction_questions "
        "FOR EACH ROW EXECUTE FUNCTION transaction_question_final()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER transaction_question_final ON transaction_questions")
    op.execute("DROP TRIGGER analytic_line_forward ON analytic_lines")
    for table in ("close_entry_recordings", "analytic_explanations", "reconciling_items"):
        op.execute(f"DROP TRIGGER {table}_set_once ON {table}")
    for table, _inserts, _updates in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    for function in (
        "transaction_question_final()",
        "analytic_line_forward()",
        "closes_set_once()",
    ):
        op.execute(f"DROP FUNCTION {function}")
