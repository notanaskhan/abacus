"""Idempotency keys are claimed before the effect runs (P-04-T22 security re-review; DEC-507).

0099 stored a key's answer after the effect, so two concurrent requests with one key could both
run it. Now the first request claims the key with a pending row (no status, no response yet) in
its own short committed statement, runs, then fills the row; a request finding a pending row
with its own hash is told the first is in progress (409 `idempotency_in_progress`), one with
another hash is refused (422 `idempotency_key_reused`), and a filled row replays.

- `claim_id` names the claim that holds the row: only that claim fills or releases it.
- `status_code` and `response` are NULL together while a row is pending.
- The app may UPDATE `request_sha256`, `claim_id`, `status_code`, `response`, `created_at` and
  `expires_at`; still no DELETE. A BEFORE UPDATE trigger allows only three changes from the app:
  - fill: a pending row gets its answer, nothing else changes;
  - release: a pending row of the same claim expires now;
  - takeover: a new claim replaces an expired row, or a pending row of the same request whose
    claim is older than an hour (`PENDING_RECLAIM_S` in `kernel.uow.idempotency`).
  A completed answer is never rewritten.

Revision ID: 0214
Revises: 0213
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0214"
down_revision = "0213"
branch_labels = None
depends_on = None

_UPDATES = "request_sha256, claim_id, status_code, response, created_at, expires_at"
_INSERTS = ("tenant_id", "actor_id", "route", "key", "request_sha256", "status_code", "response")
# 0154's and 0175's precedent: the owner's paths and superuser seeding are not the application.
_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)
_GUARD = f"""
    CREATE FUNCTION idempotency_keys_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NOT ({_BY_APP}) THEN
            RETURN NEW;
        END IF;
        -- fill: the claim's answer, once
        IF OLD.status_code IS NULL AND NEW.status_code IS NOT NULL
           AND NEW.claim_id IS NOT DISTINCT FROM OLD.claim_id
           AND NEW.request_sha256 = OLD.request_sha256
           AND NEW.created_at = OLD.created_at AND NEW.expires_at = OLD.expires_at THEN
            RETURN NEW;
        END IF;
        -- release: a pending claim given up, expiring now
        IF OLD.status_code IS NULL AND NEW.status_code IS NULL AND NEW.response IS NULL
           AND NEW.claim_id IS NOT DISTINCT FROM OLD.claim_id
           AND NEW.request_sha256 = OLD.request_sha256
           AND NEW.created_at = OLD.created_at AND NEW.expires_at <= clock_timestamp() THEN
            RETURN NEW;
        END IF;
        -- takeover: a new claim on an expired row, or on a stale pending one of the same request
        IF NEW.status_code IS NULL AND NEW.response IS NULL
           AND NEW.claim_id IS DISTINCT FROM OLD.claim_id
           AND (OLD.expires_at <= clock_timestamp()
                OR (OLD.status_code IS NULL AND OLD.request_sha256 = NEW.request_sha256
                    AND OLD.created_at < clock_timestamp() - interval '3600 seconds')) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'an idempotency key is only claimed, filled once, or released'
            USING ERRCODE = 'check_violation';
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE idempotency_keys
            ADD COLUMN claim_id uuid NULL,
            ALTER COLUMN status_code DROP NOT NULL,
            ALTER COLUMN response DROP NOT NULL,
            ADD CONSTRAINT idempotency_keys_pending_or_answered
                CHECK ((status_code IS NULL) = (response IS NULL))
        """
    )
    insert_columns(op, "idempotency_keys", (*_INSERTS, "claim_id"))
    op.execute(f"GRANT UPDATE ({_UPDATES}) ON idempotency_keys TO abacus_app")
    op.execute(_GUARD)
    op.execute(
        "CREATE TRIGGER idempotency_keys_guard BEFORE UPDATE ON idempotency_keys "
        "FOR EACH ROW EXECUTE FUNCTION idempotency_keys_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER idempotency_keys_guard ON idempotency_keys")
    op.execute("DROP FUNCTION idempotency_keys_guard()")
    op.execute(f"REVOKE UPDATE ({_UPDATES}) ON idempotency_keys FROM abacus_app")
    insert_columns(op, "idempotency_keys", _INSERTS)
    op.execute("DELETE FROM idempotency_keys WHERE status_code IS NULL")
    op.execute(
        """
        ALTER TABLE idempotency_keys
            DROP CONSTRAINT idempotency_keys_pending_or_answered,
            ALTER COLUMN response SET NOT NULL,
            ALTER COLUMN status_code SET NOT NULL,
            DROP COLUMN claim_id
        """
    )
