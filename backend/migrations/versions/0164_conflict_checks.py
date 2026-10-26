"""P-07-T36 (M6): conflict checks and screening records, organisations (P-07 §4.2 M6; SPEC-332
AC-23 to AC-26; DEC-373).

- `conflict_checks` (insert-only): what was searched for (a client, client entity or draft
  subject), the names sealed per tenant, how many, who ran it and the outcome at run time.
- `conflict_results` (insert-only): one row per matched client, entity or contact and match kind
  (exact, trigram, relationship, counterparty), with the matched client, the score and, for a
  counterparty, the role it holds. Names are never stored here: they are read at display time,
  and a match on a client the reader is walled from is redacted then.
- `conflict_result_events` (insert-only, `actor_kind = 'human'`): a person's assessment of a
  result with a sealed reason; the newest event is the result's assessment.
- `screening_records` (insert-only, `actor_kind = 'human'`): a person's recorded screening
  result (OFAC SDN, adverse media, restricted entities) with an optional evidence link and a
  sealed note. Nothing is looked up.
- The human-only register gains `conflict.cleared` (0163's 35 entries plus it); the downgrade
  restores 0163's list.

Revision ID: 0164
Revises: 0163
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0164"
down_revision = "0163"
branch_labels = None
depends_on = None

# The register as 0163 left it (35 entries).
_HUMAN_ONLY_0163 = sorted(
    [
        "acceptance.decided",
        "acceptance.review_completed",
        "assurance.phase_recorded",
        "contact.unlocked",
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
        "eqr.eligibility_approved",
        "evidence.accepted",
        "firm.ai_client_data_opted_in",
        "firm_export.approved",
        "firm_export.declined",
        "follow_up.sent",
        "fulfilment.voided",
        "going_concern.decided",
        "guidance_draft.approved",
        "independence.confirmed",
        "independence.declined",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
        "portal_mfa.reset",
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "review_decision.created",
        "review_decision.undone",
        "risk.approved",
        "sample.approved",
        "sign_off.recorded",
        "statement.approved",
        "team.approved",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0163, "conflict.cleared"])

_TABLES = ("conflict_checks", "conflict_results", "conflict_result_events", "screening_records")
_SUBJECT = "('client', 'client_entity', 'engagement_draft', 'client_intake_draft')"
_HUMAN = (
    "text NOT NULL DEFAULT current_setting('app.actor_kind', true) CHECK (actor_kind = 'human')"
)


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE conflict_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            subject_kind text NOT NULL CHECK (subject_kind IN {_SUBJECT}),
            subject_id uuid NOT NULL,
            names_sealed bytea NOT NULL CHECK (octet_length(names_sealed) <= 65536),
            names_count smallint NOT NULL CHECK (names_count BETWEEN 1 AND 50),
            status text NOT NULL CHECK (status IN ('pending', 'clear', 'hits')),
            run_by uuid NOT NULL,
            run_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE conflict_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            check_id uuid NOT NULL,
            name_index smallint NOT NULL CHECK (name_index BETWEEN 0 AND 49),
            matched_ref_type text NOT NULL
                CHECK (matched_ref_type IN ('client', 'client_entity', 'contact')),
            matched_ref_id uuid NOT NULL,
            matched_client_id uuid NOT NULL,
            match_kind text NOT NULL
                CHECK (match_kind IN ('exact', 'trigram', 'relationship', 'counterparty')),
            score numeric(5, 4) NOT NULL CHECK (score > 0 AND score <= 1),
            counterparty_role text NULL CHECK (counterparty_role ~ '^[a-z_]{1,40}$'),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, check_id, matched_ref_type, matched_ref_id, match_kind),
            FOREIGN KEY (tenant_id, check_id) REFERENCES conflict_checks (tenant_id, id),
            FOREIGN KEY (tenant_id, matched_client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE conflict_result_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            result_id uuid NOT NULL,
            assessment text NOT NULL CHECK (assessment IN (
                'clear', 'same_family_not_adverse', 'not_adverse', 'counterparty_review',
                'conflict'
            )),
            reason_sealed bytea NOT NULL CHECK (octet_length(reason_sealed) <= 65536),
            cleared_by uuid NOT NULL,
            cleared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind {_HUMAN},
            FOREIGN KEY (tenant_id, result_id) REFERENCES conflict_results (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE screening_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            subject_kind text NOT NULL CHECK (subject_kind IN {_SUBJECT}),
            subject_id uuid NOT NULL,
            list text NOT NULL
                CHECK (list IN ('ofac_sdn', 'adverse_media', 'restricted_entities')),
            result text NOT NULL CHECK (result IN ('no_match', 'match', 'not_applicable')),
            evidence_version_id uuid NULL,
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind {_HUMAN}
        )
        """
    )
    op.execute("CREATE INDEX conflict_results_by_check ON conflict_results (tenant_id, check_id)")
    op.execute(
        "CREATE INDEX conflict_result_events_by_result ON conflict_result_events "
        "(tenant_id, result_id, cleared_at)"
    )
    op.execute(
        "CREATE INDEX screening_records_by_subject ON screening_records "
        "(tenant_id, subject_kind, subject_id, recorded_at)"
    )
    for table in _TABLES:
        op.execute(
            f"""
            CREATE FUNCTION {table}_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
            END $$
            """
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
        )
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "conflict_checks",
        (
            "id",
            "tenant_id",
            "subject_kind",
            "subject_id",
            "names_sealed",
            "names_count",
            "status",
            "run_by",
        ),
    )
    insert_columns(
        op,
        "conflict_results",
        (
            "tenant_id",
            "check_id",
            "name_index",
            "matched_ref_type",
            "matched_ref_id",
            "matched_client_id",
            "match_kind",
            "score",
            "counterparty_role",
        ),
    )
    insert_columns(
        op,
        "conflict_result_events",
        ("id", "tenant_id", "result_id", "assessment", "reason_sealed", "cleared_by"),
    )
    insert_columns(
        op,
        "screening_records",
        (
            "id",
            "tenant_id",
            "subject_kind",
            "subject_id",
            "list",
            "result",
            "evidence_version_id",
            "note_sealed",
            "recorded_by",
        ),
    )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0163)
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
        op.execute(f"DROP FUNCTION {table}_immutable()")
