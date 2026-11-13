"""The dark-merge audit (Q-04-T125; P-29, ADR-151; DEC-4819).

Inside a release window a change merges dark: new modules behind default-off flags, migrations
expand-only, and no live-path file touched except to fix a defect. This audit reads the merged
pull requests between two refs on main (one squash commit each, first parent) and reports, per
PR, why it is not dark, or that it is:

    python -m abacus_tools.dark_merge_audit --from <ref> --to <ref> \
        [--live-paths deploy/live-paths.yaml]

- `flag_default_on`: a flag the PR adds to `docs/architecture/feature-flags/*.yaml` whose
  `default` is not false.
- `contract_migration`: a migration the PR adds with a contract operation in its upgrade, by
  `abacus_tools.quality.expand_only`'s rules (drop, rename, type change, not null, value removal).
- `live_path`: a changed file matching a glob in `deploy/live-paths.yaml`.

Output is a Markdown table (`--out` writes it to a file too). Identifiers and paths only. Exit 0
when every PR is dark_only, 1 when any is not (`--report-only` always exits 0), 2 when a ref is
not a commit or no live-path glob loads (it never passes open).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

import yaml

from abacus_tools.quality import expand_only

GIT = shutil.which("git") or "/usr/bin/git"
FLAGS_DIR: Final = "docs/architecture/feature-flags/"
MIGRATIONS_DIR: Final = "backend/migrations/versions/"
DEFAULT_LIVE_PATHS: Final = "deploy/live-paths.yaml"
_PR: Final = re.compile(r"\(#(\d+)\)\s*$")


@dataclass
class Merge:
    sha: str
    subject: str
    pr: str | None
    findings: list[str] = field(default_factory=list[str])

    @property
    def dark_only(self) -> bool:
        return not self.findings


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def _show(repo: Path, ref: str, path: str) -> str | None:
    result = subprocess.run(
        [GIT, "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def contract_operations(source: str) -> list[str]:
    """The contract operations in a migration's upgrade, by `expand_only`'s rules (Q-03-T081):
    one implementation of what expand-only means."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "migration.py"
        path.write_text(source, encoding="utf-8")
        try:
            found = expand_only.operations(path)
        except SyntaxError:
            return ["unparseable"]
    return [f"{op.kind}: {' '.join(op.text.split())}" for op in found]


def flag_defaults(text: str | None) -> dict[str, object]:
    """{flag name: default} from one registry file; an unreadable or absent file is none."""
    if not text:
        return {}
    loaded = cast(object, yaml.safe_load(text))
    if not isinstance(loaded, dict):
        return {}
    flags = cast(dict[str, object], loaded).get("flags")
    out: dict[str, object] = {}
    if isinstance(flags, list):
        for entry in cast(list[object], flags):
            if isinstance(entry, dict):
                item = cast(dict[str, object], entry)
                name = item.get("name")
                if isinstance(name, str):
                    out[name] = item.get("default")
    return out


def default_off(value: object) -> bool:
    return value is False or (isinstance(value, str) and value.strip().lower() == "false")


def live_globs(text: str | None) -> list[str]:
    if not text:
        return []
    loaded = cast(object, yaml.safe_load(text))
    globs = cast(dict[str, object], loaded).get("live_paths") if isinstance(loaded, dict) else None
    return (
        [g for g in cast(list[object], globs) if isinstance(g, str)]
        if isinstance(globs, list)
        else []
    )


def is_live(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def audit_commit(repo: Path, sha: str, globs: list[str]) -> Merge:
    subject = _git(repo, "log", "-1", "--format=%s", sha).strip()
    found = _PR.search(subject)
    merge = Merge(sha, subject, found.group(1) if found else None)
    parent = f"{sha}^"
    for line in _git(
        repo, "diff-tree", "--no-commit-id", "--name-status", "-r", parent, sha
    ).splitlines():
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        if path.startswith(FLAGS_DIR) and path.endswith(".yaml"):
            before = flag_defaults(_show(repo, parent, path))
            for name, value in flag_defaults(_show(repo, sha, path)).items():
                # A new flag defaulting on, or an existing one flipped on (TASK-7828).
                was_off = name not in before or default_off(before[name])
                if was_off and not default_off(value):
                    merge.findings.append(f"flag_default_on: {name}")
        # Added, modified or renamed (TASK-7828): an edit that adds a drop is a contract step too.
        if path.startswith(MIGRATIONS_DIR) and path.endswith(".py") and status[:1] in "AMR":
            ops = contract_operations(_show(repo, sha, path) or "")
            if ops:
                merge.findings.append(f"contract_migration: {path} ({'; '.join(ops)})")
        if is_live(path, globs):
            merge.findings.append(f"live_path: {path}")
    return merge


class AuditRefused(ValueError):
    """A ref git cannot resolve to a commit, or no live-path globs: the audit never passes open."""


def resolve(repo: Path, ref: str) -> str:
    """The commit a ref names, or refused. `--end-of-options` keeps a ref that starts with `-`
    from being read as a git option (TASK-7828)."""
    result = subprocess.run(
        [GIT, "-C", str(repo), "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise AuditRefused(f"not a commit: {ref!r}")
    return sha


def audit(repo: Path, start: str, end: str, globs: list[str]) -> list[Merge]:
    if not globs:
        raise AuditRefused("no live-path globs: every PR would read dark_only")
    first, last = resolve(repo, start), resolve(repo, end)
    shas = _git(repo, "rev-list", "--first-parent", "--reverse", f"{first}..{last}").split()
    return [audit_commit(repo, sha, globs) for sha in shas]


def report(merges: list[Merge], start: str, end: str) -> str:
    rows = [
        f"## Dark-merge audit {start}..{end}",
        "",
        f"{sum(m.dark_only for m in merges)} of {len(merges)} merged PRs are dark_only.",
        "",
        "| PR | Commit | Verdict | Findings |",
        "|---|---|---|---|",
    ]
    for m in merges:
        pr = f"#{m.pr}" if m.pr else "(no PR)"
        verdict = "dark_only" if m.dark_only else "NOT dark"
        rows.append(f"| {pr} | {m.sha[:9]} | {verdict} | {'<br>'.join(m.findings) or '-'} |")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.dark_merge_audit")
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", default="HEAD")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--live-paths", default=DEFAULT_LIVE_PATHS)
    parser.add_argument("--out")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(cast(str, args.repo))
    globs_file = repo / cast(str, args.live_paths)
    globs = live_globs(globs_file.read_text(encoding="utf-8") if globs_file.exists() else None)
    try:
        merges = audit(repo, cast(str, args.start), cast(str, args.end), globs)
    except AuditRefused as refused:
        sys.stderr.write(f"dark-merge audit refused: {refused}\n")
        return 2
    text = report(merges, cast(str, args.start), cast(str, args.end))
    sys.stdout.write(text)
    if args.out:
        Path(cast(str, args.out)).write_text(text, encoding="utf-8")
    return 0 if args.report_only or all(m.dark_only for m in merges) else 1


if __name__ == "__main__":
    raise SystemExit(main())
