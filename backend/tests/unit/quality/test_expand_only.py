"""Q-03-T081 (TASK-2002; DEC-1052): the expand-only migration guard.

Acceptance (the task row): "A migration with a DROP after Jun 1 fails stage 1 unless labelled
contract-step [...], the same labelled migration fails in window mode on a simulated in-window
date". The rehearsal on the perf stack is an ops run (DEC-1052), not a unit.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from abacus_tools.quality import expand_only

AFTER = date(2027, 6, 2)
BEFORE = date(2027, 5, 31)


def _migration(tmp_path: Path, up: str, down: str = "    pass\n") -> Path:
    path = tmp_path / "9999_probe.py"
    path.write_text(
        "from alembic import op\n\n\ndef upgrade() -> None:\n"
        + up
        + "\n\ndef downgrade() -> None:\n"
        + down,
        encoding="utf-8",
    )
    return path


def test_ac1_a_drop_after_jun_1_fails_without_the_label(tmp_path: Path) -> None:
    path = _migration(tmp_path, '    op.execute("ALTER TABLE t DROP COLUMN c")\n')
    verdict = expand_only.judge([path], today=AFTER)
    assert not verdict.ok and verdict.refused == ("contract_step_label_missing",)
    assert [o.kind for o in verdict.operations] == ["drop"]


def test_ac1_the_label_lets_it_through(tmp_path: Path) -> None:
    path = _migration(tmp_path, '    op.execute("ALTER TABLE t DROP COLUMN c")\n')
    assert expand_only.judge([path], labels=["contract-step"], today=AFTER).ok


def test_ac1_before_jun_1_the_guard_is_inert(tmp_path: Path) -> None:
    path = _migration(tmp_path, '    op.execute("DROP TABLE t")\n')
    assert expand_only.judge([path], today=BEFORE).ok


def test_ac2_window_mode_refuses_a_labelled_contract_step(tmp_path: Path) -> None:
    path = _migration(tmp_path, '    op.execute("DROP TABLE t")\n')
    verdict = expand_only.judge(
        [path], labels=["contract-step"], today=AFTER, window="autumn-2027"
    )
    assert verdict.refused == ("contract_operation_in_window:autumn-2027",)


def test_ac2_window_mode_lets_an_expand_only_migration_through(tmp_path: Path) -> None:
    path = _migration(tmp_path, '    op.execute("ALTER TABLE t ADD COLUMN c text NULL")\n')
    assert expand_only.judge([path], today=AFTER, window="autumn-2027").ok


@pytest.mark.parametrize(
    ("up", "kind"),
    [
        ('    op.execute("DROP TABLE t")\n', "drop"),
        ('    op.drop_column("t", "c")\n', "drop"),
        ('    op.execute("TRUNCATE TABLE t")\n', "drop"),
        ('    op.execute("ALTER TABLE t RENAME TO u")\n', "rename"),
        ('    op.execute("ALTER TABLE t RENAME COLUMN a TO b")\n', "rename"),
        ('    op.alter_column("t", "a", new_column_name="b")\n', "rename"),
        ('    op.execute("ALTER TABLE t ALTER COLUMN a TYPE smallint")\n', "type_change"),
        ('    op.execute("ALTER TABLE t ALTER COLUMN a SET NOT NULL")\n', "not_null"),
        ('    op.execute("ALTER TABLE t ADD COLUMN a text NOT NULL")\n', "not_null"),
        ('    op.alter_column("t", "a", nullable=False)\n', "not_null"),
    ],
)
def test_each_contract_pattern_is_found(tmp_path: Path, up: str, kind: str) -> None:
    assert [o.kind for o in expand_only.operations(_migration(tmp_path, up))] == [kind]


@pytest.mark.parametrize(
    "up",
    [
        "    op.execute(\"ALTER TABLE t ADD COLUMN a text NOT NULL DEFAULT 'x'\")\n",
        '    op.execute("CREATE TRIGGER g BEFORE TRUNCATE ON t EXECUTE FUNCTION f()")\n',
        '    op.execute("DROP INDEX t_idx")\n',
        '    op.execute("CREATE TABLE t (id uuid PRIMARY KEY)")\n',
    ],
)
def test_expand_operations_pass(tmp_path: Path, up: str) -> None:
    assert expand_only.operations(_migration(tmp_path, up)) == []


def test_an_enum_value_removed_is_found_from_the_downgrade(tmp_path: Path) -> None:
    up = (
        '    op.execute("ALTER TABLE t DROP CONSTRAINT t_kind_check")\n'
        "    op.execute(\"ALTER TABLE t ADD CONSTRAINT t_kind_check CHECK (kind IN ('a', "
        "'b'))\")\n"
    )
    down = (
        '    op.execute("ALTER TABLE t DROP CONSTRAINT t_kind_check")\n'
        "    op.execute(\"ALTER TABLE t ADD CONSTRAINT t_kind_check CHECK (kind IN ('a', 'b', "
        "'c'))\")\n"
    )
    [found] = expand_only.operations(_migration(tmp_path, up, down))
    assert found.kind == "value_removal" and "c" in found.text


def test_an_enum_value_added_passes(tmp_path: Path) -> None:
    up = "    op.execute(\"ALTER TABLE t ADD CONSTRAINT k CHECK (kind IN ('a', 'b', 'c'))\")\n"
    down = "    op.execute(\"ALTER TABLE t ADD CONSTRAINT k CHECK (kind IN ('a', 'b'))\")\n"
    assert expand_only.operations(_migration(tmp_path, up, down)) == []
