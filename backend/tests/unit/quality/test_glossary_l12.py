"""F-02-T07, T10: rule L12 bans the glossary's "Don't use" identifiers in what names a concept."""

from __future__ import annotations

from pathlib import Path

from abacus_tools.quality import banned_patterns as bp


def _ids(root: Path, rel: str, source: str) -> list[str]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [v.rule_id for v in bp.scan(root)]


def test_t07_the_ban_list_comes_from_the_glossary() -> None:
    bans = bp.glossary_bans()
    assert bans["reminder"] and bans["client_user"] == "contact"
    assert "pbc_item" in bans


def test_t07_a_new_reminder_items_table_fails(tmp_path: Path) -> None:
    source = 'class X:\n    __tablename__ = "reminder_items"\n'
    assert "L12" in _ids(tmp_path, "src/abacus/modules/requests/models.py", source)


def test_t07_a_banned_class_or_function_name_fails(tmp_path: Path) -> None:
    assert "L12" in _ids(
        tmp_path, "src/abacus/modules/requests/x.py", "class PbcItem:\n    pass\n"
    )
    assert "L12" in _ids(
        tmp_path, "src/abacus/modules/requests/y.py", "def reminder():\n    pass\n"
    )


def test_t10_locals_and_allowed_names_pass(tmp_path: Path) -> None:
    source = "def send_message(email: str) -> None:\n    account_code = email\n"
    assert "L12" not in _ids(tmp_path, "src/abacus/modules/requests/z.py", source)


def test_t16_the_renamed_reminder_names_now_fail_where_they_lived(tmp_path: Path) -> None:
    # F-03-T16 renamed them (follow_up_schedules, follow_up_items, /follow-ups), so the legacy
    # allowance is gone and L12 refuses them everywhere.
    source = 'class Reminder:\n    __tablename__ = "reminders"\n'
    assert "L12" in _ids(tmp_path, "src/abacus/modules/agents/models.py", source)
