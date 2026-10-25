"""P-04-T16 and P-03-T12: the keys two outbox consumers are idempotent on.

- `human_gates`: one row per gate subject (`human_gates_one_per_subject` on tenant, kind and
  `subject_ref`). The projector (P-04-T16, `review.gates`) reconciles an engagement's open gates
  with what each owner says waits on a person; two events about the same subject, delivered at
  once, now insert one row and the second does nothing. The row's `source_event_id` stays the
  event that first opened it.
- `citation_events`: one `moved` or `broken` event per citation and cause
  (`citation_events_once_per_cause`). The moved and broken detector (P-03-T12,
  `evidence.citations.moved`) writes `cause_ref` as `evidence_version:<successor>` or
  `withdrawn:<version>`; a redelivered event, or two relays at once, write each row once.
  `relinked` events are a person's and are not keyed here.

No data changes: both tables are new enough that no duplicates exist (the projector and the
detector are first written in this release).

Revision ID: 0152
Revises: 0151
"""

from __future__ import annotations

from alembic import op

revision = "0152"
down_revision = "0151"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX human_gates_one_per_subject ON human_gates "
        "(tenant_id, kind, subject_ref)"
    )
    op.execute(
        "CREATE UNIQUE INDEX citation_events_once_per_cause ON citation_events "
        "(tenant_id, citation_id, kind, cause_ref) WHERE kind IN ('moved', 'broken')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX citation_events_once_per_cause")
    op.execute("DROP INDEX human_gates_one_per_subject")
