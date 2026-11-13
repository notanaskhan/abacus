"""Q-04-T125 (DEC-4819): the dark-merge audit lists every merged PR as dark_only, or names why not.

Acceptance (the row): "The audit lists every merged PR as dark_only with no live-path file in its
diff." Checked on a throwaway git repository: a dark PR (a default-off flag, an expand-only
migration, a non-live file), and one PR for each reason a merge is not dark.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from abacus_tools import dark_merge_audit as audit

GIT = shutil.which("git") or "/usr/bin/git"
GLOBS = ["backend/src/abacus/kernel/*", "apps/web/src/screens/HOME-*"]

FLAGS_V1 = "flags:\n  - name: a.old\n    default: true\n"
EXPAND = (
    '"""add a table"""\n\ndef upgrade():\n    op.execute("CREATE TABLE t (id uuid)")\n\n\n'
    'def downgrade():\n    op.execute("DROP TABLE t")\n'
)
CONTRACT = (
    '"""tighten"""\n\ndef upgrade():\n'
    '    op.execute("ALTER TABLE t ALTER COLUMN id SET NOT NULL")\n'
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], subject: str) -> str:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-q",
        "-m",
        subject,
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(
        tmp_path, {"docs/architecture/feature-flags/a.yaml": FLAGS_V1, "README.md": "x\n"}, "base"
    )
    return tmp_path


def test_ac_a_dark_pr_is_dark_only(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(
        repo,
        {
            "docs/architecture/feature-flags/a.yaml": FLAGS_V1
            + "  - name: a.new\n    default: false\n",
            "backend/migrations/versions/0900_t.py": EXPAND,
            "backend/src/abacus/modules/practice/new.py": "x = 1\n",
        },
        "P-05: a dark module (#901)",
    )
    [merge] = audit.audit(repo, base, "HEAD", GLOBS)
    assert merge.pr == "901"
    assert merge.findings == []
    assert merge.dark_only
    text = audit.report([merge], base[:7], "HEAD")
    assert "1 of 1 merged PRs are dark_only." in text
    assert "| #901 |" in text and "| dark_only | - |" in text


def test_ac_each_reason_a_pr_is_not_dark(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(
        repo,
        {
            "docs/architecture/feature-flags/a.yaml": FLAGS_V1
            + "  - name: a.on\n    default: true\n"
        },
        "flag on by default (#902)",
    )
    _commit(repo, {"backend/migrations/versions/0901_t.py": CONTRACT}, "tighten (#903)")
    _commit(repo, {"backend/src/abacus/kernel/clock.py": "y = 2\n"}, "kernel edit (#904)")
    _commit(repo, {"apps/web/src/screens/HOME-01/index.tsx": "z\n"}, "home edit")
    merges = audit.audit(repo, base, "HEAD", GLOBS)
    assert [m.pr for m in merges] == ["902", "903", "904", None]
    assert merges[0].findings == ["flag_default_on: a.on"]
    assert merges[1].findings == [
        "contract_migration: backend/migrations/versions/0901_t.py (not_null: SET NOT NULL)"
    ]
    assert merges[2].findings == ["live_path: backend/src/abacus/kernel/clock.py"]
    assert merges[3].findings == ["live_path: apps/web/src/screens/HOME-01/index.tsx"]
    assert not any(m.dark_only for m in merges)
    text = audit.report(merges, "a", "b")
    assert "0 of 4 merged PRs are dark_only." in text
    assert "| (no PR) |" in text and text.count("NOT dark") == 4


def test_an_existing_flag_turned_on_is_not_a_new_default(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(
        repo,
        {"docs/architecture/feature-flags/a.yaml": FLAGS_V1.replace("true", "false")},
        "x (#905)",
    )
    [merge] = audit.audit(repo, base, "HEAD", GLOBS)
    assert merge.dark_only


def test_main_exit_code_follows_the_verdict(repo: Path, tmp_path: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "deploy").mkdir()
    (repo / "deploy/live-paths.yaml").write_text("live_paths:\n  - README.md\n", encoding="utf-8")
    _commit(repo, {"README.md": "changed\n"}, "readme (#906)")
    out = tmp_path / "report.md"
    assert (
        audit.main(["--from", base, "--to", "HEAD", "--repo", str(repo), "--out", str(out)]) == 1
    )
    assert "live_path: README.md" in out.read_text(encoding="utf-8")
    assert audit.main(["--from", base, "--repo", str(repo), "--report-only"]) == 0


@pytest.mark.parametrize(
    ("sql", "found"),
    [
        ('op.execute("DROP TABLE x")', ["drop: DROP TABLE"]),
        ('op.execute("ALTER TABLE x DROP COLUMN y")', ["drop: DROP COLUMN"]),
        ('op.execute("ALTER TABLE x RENAME TO z")', ["rename: RENAME TO"]),
        (
            'op.execute("ALTER TABLE x ALTER COLUMN y TYPE text")',
            ["type_change: ALTER COLUMN y TYPE"],
        ),
        ('op.drop_table("t")', ["drop: op.drop_table"]),
        (
            'op.alter_column("t", "c", nullable=False)',
            ["not_null: op.alter_column(nullable=False)"],
        ),
        ('op.execute("CREATE INDEX ix ON t (a)")', []),
        ('op.add_column("t", sa.Column("c", sa.Text(), nullable=True))', []),
    ],
)
def test_contract_operations(sql: str, found: list[str]) -> None:
    source = f"def upgrade():\n    {sql}\n\n\ndef downgrade():\n    op.execute('DROP TABLE q')\n"
    assert audit.contract_operations(source) == found


def test_helpers() -> None:
    assert audit.contract_operations("def upgrade(:\n") == ["unparseable"]
    assert audit.contract_operations("x = 1\n") == []
    assert audit.flag_defaults(None) == {}
    assert audit.flag_defaults("[]") == {}
    assert audit.flag_defaults("flags:\n  - name: x\n    default: 'false'\n  - nope\n") == {
        "x": "false"
    }
    assert audit.default_off(False) and audit.default_off("False ")
    assert not audit.default_off(True) and not audit.default_off(None)
    assert audit.live_globs(None) == [] and audit.live_globs("x: 1") == []
    assert audit.live_globs("live_paths:\n  - a/*\n  - 3\n") == ["a/*"]
    assert audit.is_live("a/b/c.py", ["a/*"]) and not audit.is_live("b/c.py", ["a/*"])
