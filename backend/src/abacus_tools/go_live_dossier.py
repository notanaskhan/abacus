"""A firm's go-live dossier, `docs/ops/go-live/<pilot-code>.md` (Q-04-T021, T022; chapter 06 §8.3;
Q-04 AC-6.5; `docs/runbooks/pilot-onboarding.md` §0.1 and §12).

    python -m abacus_tools.go_live_dossier new PF-A1                 # from the template
    make go-live-check FIRM=<tenant_id> LEVEL=shadow > report.json   # the ops task's output
    python -m abacus_tools.go_live_dossier fill PF-A1 --report report.json
    python -m abacus_tools.go_live_dossier check                     # every dossier (check-fast)
    python -m abacus_tools.go_live_dossier check PF-A1 --ready       # before both founders sign

The dossier is chapter 06 §8.3's checklist for one firm, by section and owner: N signs off tenant
and identity, data protection, AI and operations (T021); AY communications, content and
integrations (T022); F-09 contract and legal. Each section has two parts:

- **Read by `make go-live-check`**: the generated block between `<!-- dossier:<key> -->` markers,
  one row per check the tool ran for the section (pass, fail or manual, with the value it read).
  `fill` rewrites only these blocks; a person never edits them.
- **By hand**: §8.3's items the tool cannot read, each with its evidence (a screen state, a CLI
  line, a vault reference) and a state, `green`, `red` or `—`.

`check` keeps every dossier honest in git: the file name is a pilot code, it holds no email
address or phone number, every section and the sign-off table are there. `--ready` is the
acceptance: every generated row `pass` (a `manual` row's by-hand twin green), every by-hand row
`green`, the shadow-rules acknowledgement recorded, and the go-live check run within 7 days.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, cast

ROOT: Final = Path(__file__).resolve().parents[2].parent
DOSSIERS: Final = ROOT / "docs" / "ops" / "go-live"
PILOT: Final = re.compile(r"PF-[ATC]\d{1,2}|PC\d{2}-\d{2}")
_EMAIL: Final = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE: Final = re.compile(r"(?<![\d-])\+?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
REPORT_MAX_AGE: Final = timedelta(days=7)


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    owner: str
    by_hand: tuple[str, ...]  # chapter 06 §8.3's items the go-live check cannot read


SECTIONS: Final[tuple[Section, ...]] = (
    Section(
        "contract",
        "Contract and legal",
        "F-09 (AY)",
        (
            "MSA, DPA and pilot terms signed: shadow mode, autonomy 0, no client-facing messages, "
            "US-only processing, 72 h incident notice, data return and deletion on exit",
            "Tax data in scope: §7216 templates approved by counsel; per-taxpayer consents or "
            "those "
            "taxpayers agents-off",
            "No PHI-bearing engagement types enabled",
            "The firm received the SOC 2 Type I report (NDA), the pen-test letter, the "
            "sub-processor "
            "list and the Pub 5708 controls section",
        ),
    ),
    Section(
        "identity",
        "Tenant and identity",
        "N",
        (
            "KMS MRK and replica verified by a decrypt test in us-west-2",
            "Roles mapped (P-10); walls configured (ADM-03); offshore group consent-gated if used",
            "Support-session toggle set by the firm (ADM-06); TRI support US-located only",
        ),
    ),
    Section(
        "data",
        "Data protection",
        "N",
        (
            "Retention policies for every record type in scope; legal-hold place and lift tested "
            "on the canary",
            "Audit-log read works; hash-chain verification green for 7 days",
            "Engagement export (dual approval) tested on the canary; RB-13 rehearsed on the "
            "canary",
        ),
    ),
    Section(
        "ai",
        "AI",
        "N",
        (
            "The firm's AI opt-in recorded in the product against the current disclosure (the "
            "briefing is F-09-T127's)",
            "Platform AI pause and per-firm pause tested in production",
        ),
    ),
    Section(
        "operations",
        "Operations",
        "N",
        (
            "On-call 24x7 for SEV1; both founders trained on RB-01, RB-08, RB-10, RB-12, RB-22, "
            "RB-27; the firm's QI contact recorded (vault)",
            "Per-firm dashboard live; Sentry release markers; status-page subscribers for the "
            "firm's admins",
            "Restore drill and game day within the quarter",
            "P-29 on: windows published; production releases follow the windowed rules",
            "R4 (LEVEL=season): RB-16's R4 checklist worked through, each step's evidence here "
            "(docs/runbooks/RB-16-busy-season-readiness.md)",
        ),
    ),
    Section(
        "communications",
        "Communications",
        "AY",
        (
            "No client-facing email in shadow; staff email from the verified platform domain",
            "The firm's sender domain verified ahead of R3 (ADM-10 f)",
        ),
    ),
    Section(
        "content",
        "Content",
        "AY",
        (
            "The firm's clients, PBC templates and email templates loaded through its own screens "
            "(CLI-06, KNW-01, POR-20); none through a commit or the seed loader",
        ),
    ),
    Section(
        "integrations",
        "Integrations",
        "AY",
        (
            "Only built connectors shown as Available; POR-16 shows Export instead",
            "Production keys and approvals for the connectors this firm uses; reconnect tested",
        ),
    ),
)
_BY_KEY: Final = {s.key: s for s in SECTIONS}


def section_of(item_id: str, tool_section: str) -> str:
    """The dossier section a go-live check's row belongs to."""
    if item_id.startswith("communications."):
        return "communications"
    return {
        "Contract and legal": "contract",
        "Tenant": "identity",
        "Identity": "identity",
        "Data protection": "data",
        "AI": "ai",
        "Operations": "operations",
        "Integrations": "integrations",
    }.get(tool_section, "operations")


def start_marker(key: str) -> str:
    return f"<!-- dossier:{key} (generated by abacus_tools.go_live_dossier fill) -->"


def end_marker(key: str) -> str:
    return f"<!-- /dossier:{key} -->"


def template(pilot: str) -> str:
    parts = [
        f"# Go-live dossier · {pilot}\n\n",
        "Chapter 06 §8.3 for one firm (Q-04-T021, T022). Pilot code only: no firm name, person "
        "name, email address, phone number, host or account id. Evidence is a screen state, a CLI "
        "line or a vault reference (`V-…`), never a screenshot of client data.\n\n",
        "| Field | Value |\n|---|---|\n| Level | shadow |\n| Go-live check | not run |\n"
        "| Pinned SHA | — |\n\n",
    ]
    for section in SECTIONS:
        parts.append(f"## {section.title} ({section.owner})\n\n")
        parts.append("Read by `make go-live-check`:\n\n")
        parts.append(f"{start_marker(section.key)}\n_not run yet_\n{end_marker(section.key)}\n\n")
        parts.append("By hand:\n\n| # | Item | Evidence | State |\n|---|---|---|---|\n")
        for n, item in enumerate(section.by_hand, start=1):
            parts.append(f"| {section.key}-{n} | {item} | — | — |\n")
        parts.append("\n")
    parts.append(
        "## Shadow rules acknowledged (AY)\n\n"
        "The firm admin's written acknowledgement of `docs/ops/pilot/shadow-briefing.md` (no "
        "client "
        "email, nothing client-facing, agents in shadow). Record the date and where it lives "
        "(vault), never the person's name.\n\n"
        "| Acknowledged on | Briefing version | Vault entry |\n|---|---|---|\n| — | — | — |\n\n"
        "## Sign-off\n\n| Founder | Sections | Signed on |\n|---|---|---|\n"
        "| N (notanaskhan) | Tenant and identity, Data protection, AI, Operations | not signed |\n"
        "| AY (ayushkbhatia) | Contract and legal, Communications, Content, Integrations "
        "| not signed |\n"
    )
    return "".join(parts)


def _rows(items: Sequence[Mapping[str, object]], key: str) -> str:
    rows = [
        f"| `{i.get('id')}` | {i.get('status')} | {str(i.get('value', '')).replace('|', '/')} |"
        f" {i.get('dossier') or '—'} |\n"
        for i in items
        if section_of(str(i.get("id", "")), str(i.get("section", ""))) == key
    ]
    if not rows:
        return "_no check at this level_\n"
    return "| Check | Status | Read | Where by hand |\n|---|---|---|---|\n" + "".join(rows)


def fill(text: str, report: Mapping[str, object]) -> str:
    items = cast(list[Mapping[str, object]], report.get("items", []))
    for section in SECTIONS:
        start, end = start_marker(section.key), end_marker(section.key)
        head, rest = text.split(start, 1)
        _old, tail = rest.split(end, 1)
        text = f"{head}{start}\n{_rows(items, section.key)}{end}{tail}"
    failed = ", ".join(map(str, cast(list[object], report.get("failed", []))))
    outcome = "passed |" if report.get("passed") else f"failed: {failed} |"
    stamp = f"| Go-live check | {report.get('level')} at {report.get('at')}, {outcome}"
    return re.sub(r"^\| Go-live check \|.*\|$", stamp.rstrip(), text, count=1, flags=re.MULTILINE)


def problems_of(name: str, text: str) -> list[str]:
    found: list[str] = []
    if not PILOT.fullmatch(name):
        found.append(f"{name}: the file is named by its pilot code (PF-A1.md)")
    for pattern, what in ((_EMAIL, "an email address"), (_PHONE, "a phone number")):
        if pattern.search(text):
            found.append(f"{name}: holds {what} (contacts live in the vault)")
    for section in SECTIONS:
        if f"## {section.title}" not in text:
            found.append(f"{name}: no '{section.title}' section")
        if start_marker(section.key) not in text or end_marker(section.key) not in text:
            found.append(f"{name}: the '{section.title}' generated block is missing")
    for heading in ("## Shadow rules acknowledged", "## Sign-off"):
        if heading not in text:
            found.append(f"{name}: no '{heading[3:]}' section")
    return found


def _table_rows(text: str, after: str) -> list[list[str]]:
    rows: list[list[str]] = []
    block = text.split(after, 1)[1] if after in text else ""
    for line in block.splitlines():
        if line.startswith("## "):
            break
        if line.startswith("|") and not set(line) <= {"|", "-", " "}:
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[1:]  # the header


def not_ready(name: str, text: str, today: date) -> list[str]:
    """What stands between the dossier and both signatures (the acceptance)."""
    found: list[str] = []
    stamp = re.search(r"^\| Go-live check \| (\w+) at (\S+), (passed|failed)", text, re.MULTILINE)
    if stamp is None:
        found.append(f"{name}: the go-live check has not been filled in")
    else:
        when = datetime.fromisoformat(stamp.group(2)).date()
        if today - when > REPORT_MAX_AGE:
            found.append(f"{name}: the go-live check is older than 7 days ({when.isoformat()})")
        if stamp.group(3) != "passed":
            found.append(f"{name}: the go-live check failed")
    for section in SECTIONS:
        block = text.split(f"## {section.title}", 1)[-1]
        for row in _table_rows(block, "By hand:"):
            if len(row) >= 4 and row[3].lower() != "green":
                found.append(f"{name}: {row[0]} is not green")
    ack = _table_rows(text, "## Shadow rules acknowledged")
    if not ack or ack[0][0] in ("—", ""):
        found.append(f"{name}: the shadow rules are not acknowledged in writing")
    return found


def _path(pilot: str) -> Path:
    return DOSSIERS / f"{pilot}.md"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.go_live_dossier", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new_cmd = commands.add_parser("new")
    new_cmd.add_argument("pilot")
    fill_cmd = commands.add_parser("fill")
    fill_cmd.add_argument("pilot")
    fill_cmd.add_argument("--report", type=Path, required=True)
    check_cmd = commands.add_parser("check")
    check_cmd.add_argument("pilot", nargs="?")
    check_cmd.add_argument("--ready", action="store_true")
    args = parser.parse_args(argv)

    if args.command in ("new", "fill") and not PILOT.fullmatch(args.pilot):
        print("a dossier is named by its pilot code (PF-A1, PC28-07)", file=sys.stderr)
        return 2
    if args.command == "new":
        if _path(args.pilot).exists():
            print(f"{_path(args.pilot)} exists", file=sys.stderr)
            return 2
        DOSSIERS.mkdir(parents=True, exist_ok=True)
        _path(args.pilot).write_text(template(args.pilot), encoding="utf-8")
        return 0
    if args.command == "fill":
        report = cast(dict[str, object], json.loads(args.report.read_text(encoding="utf-8")))
        if report.get("pilot_code") not in (None, args.pilot):
            print("the report is for another firm", file=sys.stderr)
            return 2
        path = _path(args.pilot)
        path.write_text(fill(path.read_text(encoding="utf-8"), report), encoding="utf-8")
        return 0
    paths = [_path(args.pilot)] if args.pilot else sorted(DOSSIERS.glob("*.md"))
    problems: list[str] = []
    for path in paths:
        if path.name.startswith("_"):
            continue  # the template
        text = path.read_text(encoding="utf-8")
        problems += problems_of(path.stem, text)
        if args.ready:
            from abacus.kernel.clock import system_now

            problems += not_ready(path.stem, text, system_now().date())
    for problem in problems:
        print(f"dossier: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
