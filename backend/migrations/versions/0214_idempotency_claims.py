"""Idempotency keys are claimed before the effect runs (P-04-T22 security re-review; DEC-507).

0099 stored a key's answer after the effect, so two concurrent requests with one key could both
run it. Now the first request claims the key with a pending row (no status, no response yet) in
its own short committed statement, runs, then fills the row; a request finding a pending row
with its own hash is told the first is in progress (409 `idempotency_in_progress`), one with
another hash is refused (422 `idempotency_key_reused`), and a filled row replays. A run that fails
releases its claim (expires it); a claim left by a crash is reclaimed once it is 300 seconds old;
an expired row is reclaimed by the next request, so a key never blocks forever.

- `status_code` and `response` are NULL together while a row is pending.
- The app may UPDATE `request_sha256`, `status_code`, `response`, `created_at` and `expires_at`
  (the claim's upsert, the fill and the release); still no DELETE.

Revision ID: 0214
Revises: 0213
"""

from __future__ import annotations

from alembic import op

revision = "0214"
down_revision = "0213"
branch_labels = None
depends_on = None

_UPDATES = "request_sha256, status_code, response, created_at, expires_at"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE idempotency_keys
            ALTER COLUMN status_code DROP NOT NULL,
            ALTER COLUMN response DROP NOT NULL,
            ADD CONSTRAINT idempotency_keys_pending_or_answered
                CHECK ((status_code IS NULL) = (response IS NULL))
        """
    )
    op.execute(f"GRANT UPDATE ({_UPDATES}) ON idempotency_keys TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({_UPDATES}) ON idempotency_keys FROM abacus_app")
    op.execute("DELETE FROM idempotency_keys WHERE status_code IS NULL")
    op.execute(
        """
        ALTER TABLE idempotency_keys
            DROP CONSTRAINT idempotency_keys_pending_or_answered,
            ALTER COLUMN response SET NOT NULL,
            ALTER COLUMN status_code SET NOT NULL
        """
    )
