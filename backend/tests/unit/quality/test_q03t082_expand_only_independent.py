# ac-test-author: ayushkbhatia
"""Q-03-T082 (ADR-078; Q-03 F4; DEC-06, ADR-091): the independent suite for the expand-only
migration guard, written from the row and Q-03 F4, not from the code.

The row: "Each refused pattern and the approved exception have passing tests." So:
- each refused pattern (DROP, RENAME, type narrowing, NOT NULL without default, enum value
  removal) fails stage 1 after Jun 1, 2027, through the guard's own command line;
- the exception: the `contract-step` label lets a contract step through stage 1;
- the date switch: May 31, 2027 passes, Jun 1, 2027 refuses;
- window mode refuses a labelled contract step on an in-window date (Sep 7, 2027, autumn window,
  a firm live on EBP work), through the guard's command line and through the release window gate.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml

from abacus_tools import release_windows as rw
from abacus_tools.quality import expand_only
from abacus_tools.release import window_gate

CT = ZoneInfo("America/Chicago")
IN_WINDOW = "2027-09-07T19:30:00-05:00"  # Tuesday of the autumn-2027 window, in the slot
OUT_OF_WINDOW = "2027-08-03T19:30:00-05:00"
RELEASE: dict[str, object] = {
    "git_sha": "a" * 40,
    "image_digest": "sha256:" + "b" * 64,
    "spa_manifest_sha256": "c" * 64,
    "alembic_head": "0291",
    "openapi_sha256": "d" * 64,
    "infra_sha": "e" * 40,
    "window_mode": "defect_only",
    "rollback": "docs/runbooks/RB-01-deploy-and-rollback.md#rollback",
}

REFUSED: dict[str, tuple[str, str]] = {
    "drop_table": ('op.execute("DROP TABLE engagement_notes")', "pass"),
    "drop_column": ('op.execute("ALTER TABLE clients DROP COLUMN legacy_code")', "pass"),
    "drop_column_op": ('op.drop_column("clients", "legacy_code")', "pass"),
    "rename_table": ('op.execute("ALTER TABLE clients RENAME TO customers")', "pass"),
    "rename_column": ('op.execute("ALTER TABLE clients RENAME COLUMN name TO title")', "pass"),
    "narrowing": (
        'op.execute("ALTER TABLE clients ALTER COLUMN code TYPE varchar(8)")',
        "pass",
    ),
    "not_null_set": ('op.execute("ALTER TABLE clients ALTER COLUMN code SET NOT NULL")', "pass"),
    "not_null_add": ('op.execute("ALTER TABLE clients ADD COLUMN code text NOT NULL")', "pass"),
    "enum_value_removal": (
        "op.execute(\"ALTER TABLE items ADD CONSTRAINT items_state_check CHECK (state IN ('open', "
        "'closed'))\")",
        "op.execute(\"ALTER TABLE items ADD CONSTRAINT items_state_check CHECK (state IN ('open', "
        "'closed', 'archived'))\")",
    ),
}


def _write(tmp_path: Path, name: str, up: str, down: str) -> Path:
    path = tmp_path / f"9{abs(hash(name)) % 1000:03d}_{name}.py"
    path.write_text(
        f"from alembic import op\n\n\ndef upgrade() -> None:\n    {up}\n\n\n"
        f"def downgrade() -> None:\n    {down}\n",
        encoding="utf-8",
    )
    return path


def _stage_1(path: Path, today: str, *labels: str) -> int:
    args = ["check", "--file", str(path), "--today", today]
    for label in labels:
        args += ["--label", label]
    return expand_only.main(args)


@pytest.fixture
def windows(tmp_path: Path) -> Path:
    """The real calendar with a firm live on EBP work from Jun 1, 2027 (both windows apply)."""
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(rw.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {
            "tenant_id": "00000000-0000-4000-8000-0000000000a1",
            "code": "PF-T1",
            "real_data_since": "2027-06-01",
            "autumn_window": True,
        }
    ]
    path = tmp_path / "windows.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_ac1_each_refused_pattern_fails_stage_1_after_jun_1(tmp_path: Path, name: str) -> None:
    up, down = REFUSED[name]
    assert _stage_1(_write(tmp_path, name, up, down), "2027-06-01") == 1


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_ac2_the_contract_step_label_is_the_exception(tmp_path: Path, name: str) -> None:
    up, down = REFUSED[name]
    assert _stage_1(_write(tmp_path, name, up, down), "2027-06-01", "contract-step") == 0


@pytest.mark.parametrize("label", ["contract step", "Contract-Step", "contract-steps", "expand"])
def test_ac2_only_the_exact_label_counts(tmp_path: Path, label: str) -> None:
    path = _write(tmp_path, "drop_table", *REFUSED["drop_table"])
    assert _stage_1(path, "2027-06-02", label) == 1


def test_ac3_the_date_switch_is_jun_1_2027(tmp_path: Path) -> None:
    path = _write(tmp_path, "drop_table", *REFUSED["drop_table"])
    assert _stage_1(path, "2027-05-31") == 0
    assert _stage_1(path, "2027-06-01") == 1


@pytest.mark.parametrize(
    "up",
    [
        'op.execute("ALTER TABLE clients ADD COLUMN code text NULL")',
        "op.execute(\"ALTER TABLE clients ADD COLUMN code text NOT NULL DEFAULT ''\")",
        'op.execute("CREATE INDEX clients_code ON clients (code)")',
        'op.execute("CREATE TABLE notes (id uuid PRIMARY KEY)")',
    ],
)
def test_ac3_an_expand_only_migration_passes_after_jun_1(tmp_path: Path, up: str) -> None:
    assert _stage_1(_write(tmp_path, "expand", up, "pass"), "2027-06-02") == 0


def test_ac4_window_mode_refuses_a_labelled_contract_step_in_window(
    tmp_path: Path, windows: Path
) -> None:
    path = _write(tmp_path, "drop_table", *REFUSED["drop_table"])
    args = ["window", "--file", str(path), "--windows", str(windows), "--label", "contract-step"]
    assert expand_only.main([*args, "--at", IN_WINDOW]) == 1
    assert expand_only.main([*args, "--at", OUT_OF_WINDOW]) == 0


def test_ac4_the_release_window_gate_refuses_it_too(tmp_path: Path, windows: Path) -> None:
    path = _write(tmp_path, "drop_table", *REFUSED["drop_table"])
    cal = rw.load(windows)
    at = datetime.fromisoformat(IN_WINDOW)
    refused = window_gate(RELEASE, cal, at, [path]).why
    assert any(w.startswith("contract_operation_in_window") for w in refused)
    expand = _write(tmp_path, "expand", 'op.execute("CREATE TABLE notes (id uuid)")', "pass")
    assert not any(
        w.startswith("contract_operation") for w in window_gate(RELEASE, cal, at, [expand]).why
    )
