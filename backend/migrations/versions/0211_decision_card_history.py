"""Decision card history and analysis requests (P-04-T23; ADR-160 clause 8; TASK-1402).

- `decision_card_versions` (insert-only): a card's numbered history. v1 `proposed` (the raise),
  then `decided` (one per card, with its decision) and any `reassessed` rows (`changed` false for
  "No change"; true when a superseding card was raised, which it names). A decided or reassessed
  row is a person's, bound to the transaction's actor.
- `decision_analysis_requests` (insert-only, human-only): "Request more analysis", sealed.
- `decisions.id` may be inserted by the app, so the sealed rationale is bound to its own row.
- `decision_cards.raised_by_*` must be the transaction's actor (a BEFORE INSERT trigger: the
  status update that follows a decision must not re-check it).

Revision ID: 0211
Revises: 0210
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0211"
down_revision = "0210"
branch_labels = None
depends_on = None

_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_TRANSACTION_ACTOR = (
    "CHECK (actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_DECISION_COLUMNS = (
    "tenant_id",
    "card_id",
    "option_key",
    "rationale_sealed",
    "factors",
    "seen_card_version",
    "decided_by",
    "mfa_at",
)


def _immutable(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION review_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION review_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE decision_card_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            card_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            event text NOT NULL CHECK (event IN ('proposed', 'decided', 'reassessed')),
            option_key text NULL CHECK (option_key ~ '^[a-z][a-z0-9_]{{0,39}}$'),
            changed boolean NULL,
            figures jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(figures) = 'object'),
            decision_id uuid NULL,
            superseded_by_card_id uuid NULL,
            actor_user_id uuid NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT decision_card_versions_once UNIQUE (tenant_id, card_id, version_no),
            CONSTRAINT decision_card_versions_actor {_TRANSACTION_ACTOR},
            CONSTRAINT decision_card_versions_people_decide
                CHECK (event = 'proposed' OR (actor_kind = 'human' AND actor_user_id IS NOT NULL)),
            CONSTRAINT decision_card_versions_decided_names_it
                CHECK (event <> 'decided' OR (decision_id IS NOT NULL AND option_key IS NOT NULL)),
            CONSTRAINT decision_card_versions_reassessed_says
                CHECK (event <> 'reassessed' OR changed IS NOT NULL),
            FOREIGN KEY (tenant_id, card_id) REFERENCES decision_cards (tenant_id, id),
            FOREIGN KEY (tenant_id, superseded_by_card_id)
                REFERENCES decision_cards (tenant_id, id)
        )
        """
    )
    tenant_table(op, "decision_card_versions")
    op.execute("REVOKE UPDATE, DELETE ON decision_card_versions FROM abacus_app")
    insert_columns(
        op,
        "decision_card_versions",
        (
            "tenant_id",
            "card_id",
            "version_no",
            "event",
            "option_key",
            "changed",
            "figures",
            "decision_id",
            "superseded_by_card_id",
            "actor_user_id",
        ),
    )
    _immutable("decision_card_versions")

    op.execute(
        f"""
        CREATE TABLE decision_analysis_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            card_id uuid NOT NULL,
            text_sealed bytea NOT NULL CHECK (octet_length(text_sealed) BETWEEN 1 AND 65536),
            requested_by uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT decision_analysis_requests_human_only CHECK (actor_kind = 'human'
                AND actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)
                AND actor_id = requested_by::text),
            FOREIGN KEY (tenant_id, card_id) REFERENCES decision_cards (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX decision_analysis_requests_by_card "
        "ON decision_analysis_requests (tenant_id, card_id, created_at)"
    )
    tenant_table(op, "decision_analysis_requests")
    op.execute("REVOKE UPDATE, DELETE ON decision_analysis_requests FROM abacus_app")
    insert_columns(
        op,
        "decision_analysis_requests",
        ("id", "tenant_id", "card_id", "text_sealed", "requested_by"),
    )
    _immutable("decision_analysis_requests")

    insert_columns(op, "decisions", ("id", *_DECISION_COLUMNS))

    op.execute(
        """
        CREATE FUNCTION decision_cards_raised_by_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF NEW.raised_by_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
               OR NEW.raised_by_id IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a decision card is raised by the transaction''s actor'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER decision_cards_raised_by_actor BEFORE INSERT ON decision_cards "
        "FOR EACH ROW EXECUTE FUNCTION decision_cards_raised_by_actor()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER decision_cards_raised_by_actor ON decision_cards")
    op.execute("DROP FUNCTION decision_cards_raised_by_actor()")
    insert_columns(op, "decisions", _DECISION_COLUMNS)
    op.execute("DROP TABLE decision_analysis_requests")
    op.execute("DROP TABLE decision_card_versions")
