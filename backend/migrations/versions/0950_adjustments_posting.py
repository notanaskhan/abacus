"""Adjustments posting (C-02-T04; C8 v2; SPEC-700 AC-2, AC-15, AC-18, AC-19, AC-21; ADR-344;
DEC-5503). Expand-only.

- `posting_batches`: a named person's batch of approved entries to post to the client's ledger
  under the W1 capability; its status moves forward only (`failed_post -> posted` on retry).
- `posting_results` (insert-only, immutable): one attempt per entry; `posted` carries the
  provider's id and a read-back time.
- `closing_date_events` (insert-only, immutable): the client ledger's closing date, set by a
  batch or read from the ledger.
- `closing_date_conflicts`: an entry dated on or before the closing date, one open per entry.
- `proposed_entries` gains the posting columns, the `client_ledger` target and the
  `recorded_externally` status. `pe_posting_dormant` is widened (added NOT VALID, then VALIDATE):
  posted, failed_post and reversed stay refused unless A-09's elimination clause holds (kept
  verbatim) or the entry targets the client ledger, is not an attest client's, and sits in a
  batch. A tax-only entry never joins a batch (TJE-001's database half).
- `proposed_entry_decisions` gains `approval_withdrawn`, `approval_undone` and
  `recorded_externally`; `approval_batches` gains the approver's role and the class limits.

Nothing here writes to a client system: W1 stays `enabled: false` (ADR-344 §10).

Revision ID: 0950
Revises: 0948
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0950"
down_revision = "0948"
branch_labels = None
depends_on = None

STATUSES_BEFORE = (
    "proposed",
    "within_threshold",
    "review_required",
    "approved",
    "rejected",
    "client_approved",
    "client_declined",
    "posted",
    "failed_post",
    "reversed",
)
STATUSES = (*STATUSES_BEFORE, "recorded_externally")
DECISIONS_BEFORE = (
    "approved",
    "rejected",
    "sent_to_client",
    "client_accepted",
    "client_declined",
    "client_question",
    "send_undone",
)
DECISIONS = (*DECISIONS_BEFORE, "approval_withdrawn", "approval_undone", "recorded_externally")

_DECISION_CHECK = "proposed_entry_decisions_decision_check"
# 0896's widened clause, kept verbatim (C8 v1.1).
_DORMANT_BEFORE = (
    "CHECK (status NOT IN ('posted', 'failed_post', 'reversed') "
    "OR (kind = 'elimination' AND posting_target IS NOT NULL))"
)
_POSTING_AFTER = (
    "CHECK (status NOT IN ('posted', 'failed_post', 'reversed') "
    "OR (kind = 'elimination' AND posting_target IS NOT NULL) "
    "OR (posting_target = 'client_ledger' AND NOT is_attest_client "
    "AND posting_batch_id IS NOT NULL))"
)
_TARGET_BEFORE = "CHECK (posting_target = 'consolidation_layer')"
_TARGET_AFTER = "CHECK (posting_target IN ('consolidation_layer', 'client_ledger'))"
_NEEDS_ELIM_BEFORE = (
    "CHECK (posting_target IS NULL OR (kind = 'elimination' AND consolidation_id IS NOT NULL))"
)
_NEEDS_ELIM_AFTER = (
    "CHECK (posting_target IS NULL "
    "OR (posting_target = 'consolidation_layer' AND kind = 'elimination' "
    "AND consolidation_id IS NOT NULL) "
    "OR (posting_target = 'client_ledger' AND kind IN ('aje', 'rje', 'paje')))"
)

NEW_TABLES = (
    "posting_batches",
    "posting_results",
    "closing_date_events",
    "closing_date_conflicts",
)
IMMUTABLE = ("posting_results", "closing_date_events")
ENTRY_COLUMNS = (
    "posting_batch_id",
    "external_txn_ref",
    "txn_date",
    "reverses_on",
    "reversal_of_id",
    "recorded_externally_at",
    "recorded_externally_evidence_id",
    "recorded_externally_match_ref",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "posting_batches": (
        "tenant_id", "engagement_id", "work_item_id", "client_entity_id", "connection_id",
        "batch_code", "period", "entry_count", "total_amount", "closing_date_target",
        "approval_grant_id", "posted_by_user_id", "idempotency_key",
    ),
    "posting_results": (
        "tenant_id", "posting_batch_id", "proposed_entry_id", "attempt_no", "outcome",
        "external_txn_id", "external_doc_number", "provider_code", "provider_message_redacted",
        "write_operation_id", "verified_at",
    ),
    "closing_date_events": (
        "tenant_id", "client_entity_id", "connection_id", "period", "closing_date", "source",
        "set_by_user_id", "posting_batch_id", "write_operation_id",
    ),
    "closing_date_conflicts": (
        "tenant_id", "posting_batch_id", "proposed_entry_id", "ledger_closing_date",
        "entry_date",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "posting_batches": (
        "status", "closing_date_set_at", "posted_at", "first_external_ref", "last_external_ref",
        "failure_count", "resolved_failure_count", "version",
    ),
    "closing_date_conflicts": ("status", "resolved_by", "resolved_at", "communication_ref"),
    "proposed_entries": ENTRY_COLUMNS,
}  # fmt: skip
ENTRY_INSERTS = ("posting_batch_id", "txn_date", "reverses_on", "reversal_of_id")
BATCH_COLUMNS = ("approver_role", "class_limits_snapshot")


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


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


def _tables() -> None:
    op.execute(
        """
        CREATE TABLE posting_batches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            batch_code text NOT NULL CHECK (batch_code ~ '^[0-9]{4}-[0-9]{2}-[A-Z]$'),
            period text NOT NULL CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
            status text NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'posting', 'posted', 'failed_post')),
            entry_count integer NOT NULL CHECK (entry_count BETWEEN 1 AND 500),
            total_amount numeric(20, 2) NOT NULL CHECK (total_amount >= 0),
            closing_date_target date NULL,
            closing_date_set_at timestamptz NULL,
            approval_grant_id uuid NULL,
            posted_by_user_id uuid NOT NULL,
            posted_at timestamptz NULL,
            first_external_ref text NULL CHECK (char_length(first_external_ref) <= 64),
            last_external_ref text NULL CHECK (char_length(last_external_ref) <= 64),
            failure_count integer NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
            resolved_failure_count integer NOT NULL DEFAULT 0
                CHECK (resolved_failure_count BETWEEN 0 AND failure_count),
            capability_id text NOT NULL DEFAULT 'ledger_post_journal_entries'
                CHECK (capability_id = 'ledger_post_journal_entries'),
            idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 8 AND 200),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, batch_code),
            UNIQUE (tenant_id, idempotency_key),
            CHECK (status <> 'posted' OR posted_at IS NOT NULL),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id),
            FOREIGN KEY (tenant_id, posted_by_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    # The poster is the session's own human actor, bound at insert (the workflow later moves the
    # status as the system, so a column CHECK would refuse its updates).
    op.execute(
        """
        CREATE FUNCTION posting_batches_poster() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.posted_by_user_id::text
                  IS DISTINCT FROM current_setting('app.actor_id', true)
            THEN
                RAISE EXCEPTION 'posting_batch_needs_its_poster' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER posting_batches_poster BEFORE INSERT ON posting_batches "
        "FOR EACH ROW EXECUTE FUNCTION posting_batches_poster()"
    )
    # Forward only, except a retried failure: proposed -> posting -> posted | failed_post,
    # failed_post -> posting | posted.
    op.execute(
        """
        CREATE FUNCTION posting_batches_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
                (OLD.status = 'proposed' AND NEW.status = 'posting')
                OR (OLD.status = 'posting' AND NEW.status IN ('posted', 'failed_post'))
                OR (OLD.status = 'failed_post' AND NEW.status IN ('posting', 'posted'))
            ) THEN
                RAISE EXCEPTION 'posting_batch_status_backwards' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER posting_batches_forward BEFORE UPDATE OF status ON posting_batches "
        "FOR EACH ROW EXECUTE FUNCTION posting_batches_forward()"
    )
    op.execute(
        """
        CREATE TABLE posting_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            posting_batch_id uuid NOT NULL,
            proposed_entry_id uuid NOT NULL,
            attempt_no integer NOT NULL CHECK (attempt_no >= 1),
            outcome text NOT NULL CHECK (outcome IN ('posted', 'failed', 'already_posted')),
            external_txn_id text NULL CHECK (char_length(external_txn_id) <= 64),
            external_doc_number text NULL CHECK (char_length(external_doc_number) <= 64),
            provider_code text NULL CHECK (char_length(provider_code) <= 64),
            provider_message_redacted text NULL
                CHECK (char_length(provider_message_redacted) <= 500),
            write_operation_id uuid NULL,
            verified_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, posting_batch_id, proposed_entry_id, attempt_no),
            CHECK (outcome <> 'posted'
                OR (external_txn_id IS NOT NULL AND verified_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, posting_batch_id) REFERENCES posting_batches (tenant_id, id),
            FOREIGN KEY (tenant_id, proposed_entry_id) REFERENCES proposed_entries (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE closing_date_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            period text NOT NULL CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
            closing_date date NOT NULL,
            source text NOT NULL CHECK (source IN ('set_by_accrued', 'read_from_ledger')),
            set_by_user_id uuid NULL,
            posting_batch_id uuid NULL,
            write_operation_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (source <> 'set_by_accrued'
                OR (set_by_user_id IS NOT NULL AND posting_batch_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id),
            FOREIGN KEY (tenant_id, posting_batch_id) REFERENCES posting_batches (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE closing_date_conflicts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            posting_batch_id uuid NOT NULL,
            proposed_entry_id uuid NOT NULL,
            ledger_closing_date date NOT NULL,
            entry_date date NOT NULL CHECK (entry_date <= ledger_closing_date),
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'client_asked', 'redated', 'resolved')),
            resolved_by uuid NULL,
            resolved_at timestamptz NULL,
            communication_ref uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (status NOT IN ('redated', 'resolved')
                OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL)),
            CHECK (status <> 'client_asked' OR communication_ref IS NOT NULL),
            FOREIGN KEY (tenant_id, posting_batch_id) REFERENCES posting_batches (tenant_id, id),
            FOREIGN KEY (tenant_id, proposed_entry_id) REFERENCES proposed_entries (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX closing_date_conflicts_one_open ON closing_date_conflicts "
        "(tenant_id, proposed_entry_id) WHERE status IN ('open', 'client_asked')"
    )
    op.execute(
        "CREATE INDEX posting_batches_entity ON posting_batches (tenant_id, client_entity_id)"
    )
    op.execute(
        "CREATE INDEX posting_results_batch ON posting_results (tenant_id, posting_batch_id)"
    )
    op.execute(
        "CREATE INDEX closing_date_events_entity ON closing_date_events "
        "(tenant_id, client_entity_id, at DESC)"
    )


def _entries() -> None:
    op.execute(
        """
        ALTER TABLE proposed_entries
            ADD COLUMN posting_batch_id uuid NULL,
            ADD COLUMN external_txn_ref text NULL CHECK (char_length(external_txn_ref) <= 64),
            ADD COLUMN txn_date date NULL,
            ADD COLUMN reverses_on date NULL,
            ADD COLUMN reversal_of_id uuid NULL,
            ADD COLUMN recorded_externally_at timestamptz NULL,
            ADD COLUMN recorded_externally_evidence_id uuid NULL,
            ADD COLUMN recorded_externally_match_ref text NULL
                CHECK (char_length(recorded_externally_match_ref) <= 200),
            ADD CONSTRAINT pe_posting_batch_fk FOREIGN KEY (tenant_id, posting_batch_id)
                REFERENCES posting_batches (tenant_id, id),
            ADD CONSTRAINT pe_reversal_of_fk FOREIGN KEY (tenant_id, reversal_of_id)
                REFERENCES proposed_entries (tenant_id, id),
            ADD CONSTRAINT pe_tje_never_batched CHECK (kind <> 'tje' OR posting_batch_id IS NULL),
            ADD CONSTRAINT pe_recorded_externally_evidenced CHECK (
                status <> 'recorded_externally'
                OR recorded_externally_evidence_id IS NOT NULL
                OR recorded_externally_match_ref IS NOT NULL
            ),
            ADD CONSTRAINT pe_reverses_after_txn CHECK (
                reverses_on IS NULL OR txn_date IS NULL OR reverses_on > txn_date
            )
        """
    )
    op.execute("ALTER TABLE proposed_entries DROP CONSTRAINT proposed_entries_status_check")
    op.execute(
        "ALTER TABLE proposed_entries ADD CONSTRAINT proposed_entries_status_check "
        f"CHECK (status IN {_in(STATUSES)})"
    )
    for name, after in (
        ("pe_posting_target", _TARGET_AFTER),
        ("pe_target_needs_elimination", _NEEDS_ELIM_AFTER),
        ("pe_posting_dormant", _POSTING_AFTER),
    ):
        op.execute(f"ALTER TABLE proposed_entries DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE proposed_entries ADD CONSTRAINT {name} {after} NOT VALID")
        op.execute(f"ALTER TABLE proposed_entries VALIDATE CONSTRAINT {name}")
    op.execute(f"ALTER TABLE proposed_entry_decisions DROP CONSTRAINT {_DECISION_CHECK}")
    op.execute(
        f"ALTER TABLE proposed_entry_decisions ADD CONSTRAINT {_DECISION_CHECK} "
        f"CHECK (decision IN {_in(DECISIONS)})"
    )
    op.execute(
        """
        ALTER TABLE approval_batches
            ADD COLUMN approver_role text NULL CHECK (char_length(approver_role) <= 40),
            ADD COLUMN class_limits_snapshot jsonb NULL
                CHECK (class_limits_snapshot IS NULL
                    OR jsonb_typeof(class_limits_snapshot) = 'object')
        """
    )
    op.execute(
        "CREATE INDEX proposed_entries_posting_batch ON proposed_entries "
        "(tenant_id, posting_batch_id)"
    )


def upgrade() -> None:
    _tables()
    _entries()
    for table in NEW_TABLES:
        tenant_table(op, table)
        insert_columns(op, table, INSERTS[table])
    for table in IMMUTABLE:
        insert_only(op, table)
        _immutable(table)
    for table, columns in UPDATES.items():
        if table == "proposed_entries":
            continue
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute(f"GRANT INSERT ({', '.join(ENTRY_INSERTS)}) ON proposed_entries TO abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(ENTRY_COLUMNS)}) ON proposed_entries TO abacus_app")
    op.execute(f"GRANT INSERT ({', '.join(BATCH_COLUMNS)}) ON approval_batches TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE INSERT ({', '.join(BATCH_COLUMNS)}) ON approval_batches FROM abacus_app")
    op.execute(f"REVOKE UPDATE ({', '.join(ENTRY_COLUMNS)}) ON proposed_entries FROM abacus_app")
    op.execute(f"REVOKE INSERT ({', '.join(ENTRY_INSERTS)}) ON proposed_entries FROM abacus_app")
    op.execute(f"ALTER TABLE proposed_entry_decisions DROP CONSTRAINT {_DECISION_CHECK}")
    op.execute(
        f"ALTER TABLE proposed_entry_decisions ADD CONSTRAINT {_DECISION_CHECK} "
        f"CHECK (decision IN {_in(DECISIONS_BEFORE)}) NOT VALID"
    )
    op.execute(
        "ALTER TABLE approval_batches DROP COLUMN class_limits_snapshot, DROP COLUMN approver_role"
    )
    op.execute(
        "UPDATE proposed_entries SET status = 'approved' WHERE status = 'recorded_externally' "
        "OR (posting_target = 'client_ledger' AND status IN ('posted', 'failed_post', 'reversed'))"
    )
    op.execute(
        "UPDATE proposed_entries SET posting_target = NULL WHERE posting_target = 'client_ledger'"
    )
    for name, before in (
        ("pe_posting_dormant", _DORMANT_BEFORE),
        ("pe_target_needs_elimination", _NEEDS_ELIM_BEFORE),
        ("pe_posting_target", _TARGET_BEFORE),
    ):
        op.execute(f"ALTER TABLE proposed_entries DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE proposed_entries ADD CONSTRAINT {name} {before}")
    op.execute("ALTER TABLE proposed_entries DROP CONSTRAINT proposed_entries_status_check")
    op.execute(
        "ALTER TABLE proposed_entries ADD CONSTRAINT proposed_entries_status_check "
        f"CHECK (status IN {_in(STATUSES_BEFORE)})"
    )
    op.execute("DROP INDEX proposed_entries_posting_batch")
    op.execute(
        """
        ALTER TABLE proposed_entries
            DROP CONSTRAINT pe_reverses_after_txn,
            DROP CONSTRAINT pe_recorded_externally_evidenced,
            DROP CONSTRAINT pe_tje_never_batched,
            DROP CONSTRAINT pe_reversal_of_fk,
            DROP CONSTRAINT pe_posting_batch_fk,
            DROP COLUMN recorded_externally_match_ref,
            DROP COLUMN recorded_externally_evidence_id,
            DROP COLUMN recorded_externally_at,
            DROP COLUMN reversal_of_id,
            DROP COLUMN reverses_on,
            DROP COLUMN txn_date,
            DROP COLUMN external_txn_ref,
            DROP COLUMN posting_batch_id
        """
    )
    for table in (
        "closing_date_conflicts",
        "closing_date_events",
        "posting_results",
        "posting_batches",
    ):
        op.execute(f"DROP TABLE {table}")
    for fn in (
        "closing_date_events_immutable",
        "posting_results_immutable",
        "posting_batches_forward",
        "posting_batches_poster",
    ):
        op.execute(f"DROP FUNCTION {fn}()")
