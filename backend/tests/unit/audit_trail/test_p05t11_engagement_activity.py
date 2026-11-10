"""P-05-T11 (SPEC-650 AC-32, AC-33, AC-35, AC-38): AUD-29's catalogue, segments and CSV, as code.

The HTTP behaviour (12 + 11 + 0 = 23, search in the body, export with fresh MFA) is the P-05-T08
AC suite's (`tests/integration/backfill/test_p05t08_activity_ac.py`).
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from abacus.modules.audit_trail import engagement_activity as activity
from abacus.modules.audit_trail.activity_catalogue import activity_of
from abacus.modules.audit_trail.audit_log_contract import (
    AuditActorOut,
    AuditEventRow,
    AuditPersonOut,
    AuditTargetOut,
)


def test_ac35_rows_route_by_kind() -> None:
    assert activity.link_of("agent_run.completed").link_kind == "run"
    assert activity.link_of("sign_off.recorded").link_kind == "sign_off"
    assert activity.link_of("materiality.decided").link_kind == "materiality"
    assert activity.link_of("document.uploaded").link_kind == "document"
    assert activity.link_of("risk.assessed").link_kind == "risk"
    assert activity.link_of("gate.passed").link_kind == "gate"
    assert activity.link_of("todo.deleted").link_kind == "todo"
    # An action with no entry still appears, with no link (a planned link, never a dead click).
    assert activity.link_of("engagement.note_added") == activity.ActivityLink()


def test_oq4_collaboration_stays_out_except_deletions_and_redactions() -> None:
    assert not activity.link_of("comment.created").in_activity
    assert not activity.link_of("comment_thread.opened").in_activity
    assert not activity.link_of("todo.created").in_activity
    assert activity.link_of("todo.deleted").in_activity
    assert activity.link_of("comment.redacted").in_activity
    sql = str(
        activity.in_activity_list().compile(
            # Named parameters: the pyformat default renders a literal `%` as `%%`.
            dialect=postgresql.dialect(paramstyle="named"),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "'todo.deleted'" in sql and "'comment.redacted'" in sql
    assert "LIKE 'comment.%'" in sql or "like 'comment.%'" in sql.lower()


def test_ac32_segment_classification() -> None:
    sql = str(activity.SEGMENT.compile(dialect=postgresql.dialect()))
    assert "via_agent" in sql and "policy" in sql and "human" in sql
    assert "run_id" in sql and "agent_run_id" in sql


def test_ac33_no_activity_entry_turns_an_agent_action_into_a_decision() -> None:
    # The explorer downgrades `ok` for any non-person actor; AUD-29's own entries add none.
    for key in activity.ACTIVITY_LINKS:
        if key.endswith("."):
            continue
        assert activity_of(key).category in {
            "decision",
            "change",
            "access",
            "run",
            "sign_in",
            "communication",
            "export",
        }
    assert activity_of("audit_event.exported").category == "export"


def test_ac38_the_filter_fingerprint_is_a_sha256_and_never_the_text() -> None:
    where = activity.ActivityFilter(engagement_id=uuid4(), q="Materiality")
    fingerprint = where.fingerprint()
    assert len(fingerprint) == 64 and "Materiality" not in fingerprint
    assert (
        fingerprint
        == activity.ActivityFilter(
            engagement_id=where.engagement_id, q="Materiality"
        ).fingerprint()
    )
    assert fingerprint != activity.ActivityFilter(engagement_id=where.engagement_id).fingerprint()


def test_ac38_csv_cells_are_neutralised() -> None:
    person = AuditPersonOut(user_id=uuid4(), display_name='=HYPERLINK("x")')
    row = AuditEventRow(
        seq=7,
        effective_at=datetime(2026, 9, 14, 16, 12, tzinfo=UTC),
        action="materiality.decided",
        category="decision",
        mark="ok",
        actor=AuditActorOut(kind="person", person=person),
        target=AuditTargetOut(type="materiality", id="m1", label="+1 Materiality"),
        detail_facts={"version": 2},
        link_kind="materiality",
    )
    buffer = io.StringIO()
    csv.writer(buffer).writerow(activity._csv_cells(row))  # pyright: ignore[reportPrivateUsage] -- the CSV row helper under test
    cells = next(csv.reader(io.StringIO(buffer.getvalue())))
    assert cells[0] == "7"
    assert cells[6] == '\'=HYPERLINK("x")'
    assert cells[13] == "'+1 Materiality"
    assert cells[-1] == "materiality"
    assert len(cells) == len(activity.EXPORT_COLUMNS)


def test_register_activity_links_refuses_a_second_entry() -> None:
    activity.register_activity_links({"test_p05t11.": activity.ActivityLink("none", ("x",))})
    try:
        activity.register_activity_links({"test_p05t11.": activity.ActivityLink("todo")})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("a second entry must be refused")
