"""G-04-T20 (TASK-8705; DEC-5702): `platform_console content-import` checks a content folder before
it connects and plans one write per row; nothing is read from the repository. The folder here is a
temporary one built by the test (synthetic labels), never a committed content file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools import platform_console as pc


def _folder(tmp_path: Path) -> Path:
    (tmp_path / "articles").mkdir()
    (tmp_path / "status_components.json").write_text(
        json.dumps(
            [
                {"key": "app", "label": "Accrued app", "kind": "core", "display_order": 10},
                {
                    "key": "cch_axcess_export",
                    "label": "CCH Axcess Tax export",
                    "kind": "integration",
                    "integration_key": "cch_axcess",
                },
            ]
        )
    )
    (tmp_path / "regions.json").write_text(
        json.dumps([{"code": "us", "label": "United States", "status": "live"}])
    )
    (tmp_path / "support_hours.json").write_text(
        json.dumps({"value": {"tz": "America/Chicago"}, "expected_version": 0})
    )
    (tmp_path / "articles" / "a.json").write_text(
        json.dumps({"slug": "exporting-a-return", "title": "T", "body": []})
    )
    return tmp_path


def test_ac_a_folder_plans_one_write_per_row(tmp_path: Path) -> None:
    plan = pc.content_plan(_folder(tmp_path))
    functions = [sql.split("(")[0].removeprefix("SELECT ") for sql, _ in plan]
    assert functions == [
        "status_component_upsert",
        "status_component_upsert",
        "platform_region_upsert",
        "platform_setting_put",
        "help_article_draft",
    ]


def test_ac_an_integration_row_must_name_its_integration(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    (folder / "status_components.json").write_text(
        json.dumps([{"key": "qbo_sync", "label": "QuickBooks Online sync", "kind": "integration"}])
    )
    with pytest.raises(pc.Refused):
        pc.content_plan(folder)


def test_ac_an_unknown_region_or_empty_folder_is_refused(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    (folder / "regions.json").write_text(json.dumps([{"code": "ca", "status": "live"}]))
    with pytest.raises(pc.Refused):
        pc.content_plan(folder)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(pc.Refused):
        pc.content_plan(empty)


def test_ac_dry_run_needs_no_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = _folder(tmp_path)
    code = pc.main(
        [
            "content-import",
            "--dir",
            str(folder),
            "--operator",
            "rowan",
            "--reason",
            "Production content v1 dry run",
            "--dry-run",
        ]
    )
    assert code == 0
    assert "5 writes (dry run)" in capsys.readouterr().out
