"""Frontmatter and cross-reference validator for ADRs, specs and tasks (ADR-083). PROTECTED.

Run: python -m abacus_tools.quality.validate_docs

Checks the machine contract only: frontmatter fields, enums, ids and cross-references.
Bodies are not validated. Templates (`_TEMPLATE.md`) and `README.md` files are skipped.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
ADR_DIR = REPO / "docs" / "adr"
SPEC_DIR = REPO / "docs" / "specs"
TASK_DIR = REPO / "work" / "tasks"
POLICY_FILES = (
    REPO / "docs" / "architecture" / "permission-matrix.yaml",
    REPO / "docs" / "architecture" / "dependency-allowlist.yaml",
)

RISK_ZONES = frozenset({"green", "amber", "red"})
ADR_STATUSES = frozenset({"proposed", "accepted", "deprecated"})
SUPERSEDED = re.compile(r"^superseded by (ADR-\d{3})$")
SPEC_STATUSES = frozenset({"draft", "approved", "in-progress", "done", "superseded"})
TASK_STATUSES = frozenset(
    {"todo", "planning", "awaiting-plan-approval", "in-progress", "blocked", "in-review", "done"}
)
ADR_FIELDS = ("id", "title", "status", "date", "deciders", "risk_zone")
SPEC_FIELDS = ("id", "title", "status", "owner", "risk_zone", "created", "updated")
TASK_FIELDS = (
    "id",
    "title",
    "spec",
    "acceptance_criteria",
    "risk_zone",
    "status",
    "created",
    "updated",
)
ID_IN_NAME = re.compile(r"^((?:ADR|SPEC|TASK)-\d{3})(?:-|\.md$)")
AC_ID = re.compile(r"\bAC-\d+\b")
INDEX_ROW = re.compile(r"^\|\s*\[(ADR-\d{3})\]\(([^)]+)\)\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|\s*$")

# Number blocks (F-01-T10): each founder mints ids from their own block, so two sessions never
# take the same number. Ids up to LEGACY predate the blocks and are untouched.
FOUNDERS = frozenset({"notanaskhan", "ayushkbhatia"})
LEGACY = {"ADR": 115, "SPEC": 36, "TASK": 76}
BLOCKS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "ADR": ((116, 199, "notanaskhan"), (200, 299, "ayushkbhatia")),
    "SPEC": ((37, 99, "notanaskhan"), (100, 199, "ayushkbhatia")),
    "TASK": ((77, 499, "notanaskhan"), (500, 999, "ayushkbhatia")),
}
# Accepted before handles were required (2026-10-19); immutable, so recorded here instead.
LEGACY_DECIDERS = frozenset({"ADR-131", "ADR-132"})


@dataclass(frozen=True)
class Doc:
    path: Path
    meta: Mapping[str, object]
    body: str

    @property
    def rel(self) -> str:
        return self.path.relative_to(REPO).as_posix()


@dataclass
class Report:
    errors: list[str] = field(default_factory=list[str])

    def add(self, path: Path, message: str) -> None:
        self.errors.append(f"{path.relative_to(REPO).as_posix()}: {message}")


def _documents(directory: Path, prefix: str) -> list[Path]:
    return sorted(p for p in directory.glob(f"{prefix}-*.md") if p.is_file())


def _load(path: Path, report: Report) -> Doc | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        report.add(path, "frontmatter must start at line 1 with '---'")
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        report.add(path, "frontmatter is not closed with '---'")
        return None
    try:
        meta: object = yaml.safe_load("\n".join(lines[1:end]))
    except (yaml.YAMLError, ValueError) as exc:  # ValueError: impossible dates such as 2026-13-01
        report.add(path, f"frontmatter is not valid YAML: {exc}")
        return None
    if not isinstance(meta, dict):
        report.add(path, "frontmatter must be a mapping")
        return None
    fields = {str(k): v for k, v in cast(dict[object, object], meta).items()}
    return Doc(path, fields, "\n".join(lines[end + 1 :]))


def _require(doc: Doc, names: tuple[str, ...], report: Report) -> bool:
    missing = [n for n in names if doc.meta.get(n) in (None, "")]
    for name in missing:
        report.add(doc.path, f"missing required field '{name}'")
    return not missing


def _is_date(value: object) -> bool:
    if isinstance(value, dt.date):
        return True
    try:
        dt.date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _check_common(doc: Doc, report: Report, date_fields: tuple[str, ...]) -> None:
    match = ID_IN_NAME.match(doc.path.name)
    if not match or match.group(1) != doc.meta.get("id"):
        report.add(doc.path, f"id '{doc.meta.get('id')}' does not match the filename")
    _check_block(doc, report)
    if doc.meta.get("risk_zone") not in RISK_ZONES:
        report.add(doc.path, f"risk_zone must be one of {sorted(RISK_ZONES)}")
    for name in date_fields:
        if not _is_date(doc.meta.get(name)):
            report.add(doc.path, f"'{name}' must be an ISO date (YYYY-MM-DD)")


def block_owner(doc_id: str) -> str | None:
    """The owner of the block holding an id; None for legacy ids and ids outside every block."""
    kind, _, number = doc_id.partition("-")
    n = int(number)
    if n <= LEGACY[kind]:
        return None
    return next((owner for low, high, owner in BLOCKS[kind] if low <= n <= high), None)


def _check_block(doc: Doc, report: Report) -> None:
    match = ID_IN_NAME.match(doc.path.name)
    if match is None:
        return
    doc_id = match.group(1)
    kind, _, number = doc_id.partition("-")
    if int(number) > LEGACY[kind] and block_owner(doc_id) is None:
        blocks = ", ".join(f"{lo:03d}-{hi:03d} {owner}" for lo, hi, owner in BLOCKS[kind])
        report.add(doc.path, f"{doc_id} is outside every number block ({kind}: {blocks})")


def deciders(value: object) -> list[str]:
    items = _str_list(value)
    if items is None:
        items = str(value).split(",")
    return [d.strip().removeprefix("@") for item in items for d in item.split(",") if d.strip()]


def _check_deciders(doc: Doc, report: Report) -> None:
    doc_id = str(doc.meta["id"])
    if int(doc_id.partition("-")[2]) <= LEGACY["ADR"] or doc_id in LEGACY_DECIDERS:
        return
    names = deciders(doc.meta["deciders"])
    unknown = [n for n in names if n not in FOUNDERS]
    if not names or unknown:
        report.add(
            doc.path,
            f"deciders must be GitHub handles ({', '.join(sorted(FOUNDERS))}), not "
            f"{', '.join(repr(n) for n in unknown) or 'nothing'}",
        )


def _check_unique(docs: list[Doc], report: Report) -> None:
    seen: dict[object, Path] = {}
    for doc in docs:
        key = doc.meta.get("id")
        if key in seen:
            report.add(doc.path, f"duplicate id '{key}' (also in {seen[key].name})")
        seen[key] = doc.path


def _str_list(value: object) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in cast(list[object], value)]
    return None


def _ids_on_disk(directory: Path, prefix: str) -> set[str]:
    """Ids from filenames, so a file that fails to parse is reported once, not as missing too."""
    return {m.group(1) for p in _documents(directory, prefix) if (m := ID_IN_NAME.match(p.name))}


def check_adrs(report: Report) -> dict[str, Doc]:
    docs = [d for p in _documents(ADR_DIR, "ADR") if (d := _load(p, report)) is not None]
    docs = [d for d in docs if _require(d, ADR_FIELDS, report)]
    _check_unique(docs, report)
    by_id = {str(d.meta["id"]): d for d in docs}
    on_disk = _ids_on_disk(ADR_DIR, "ADR")
    for doc in docs:
        _check_common(doc, report, ("date",))
        _check_deciders(doc, report)
        status = str(doc.meta["status"])
        superseded = SUPERSEDED.match(status)
        if superseded is None and status not in ADR_STATUSES:
            report.add(doc.path, f"status '{status}' is not valid")
        elif superseded is not None and superseded.group(1) not in on_disk:
            report.add(doc.path, f"superseding {superseded.group(1)} does not exist")
    _check_adr_index(by_id, on_disk, report)
    return by_id


def _check_adr_index(adrs: dict[str, Doc], on_disk: set[str], report: Report) -> None:
    index = ADR_DIR / "README.md"
    if not index.is_file():
        report.add(ADR_DIR, "README.md index is missing")
        return
    rows: dict[str, tuple[str, str]] = {}
    for line in index.read_text(encoding="utf-8").splitlines():
        row = INDEX_ROW.match(line)
        if row:
            rows[row.group(1)] = (row.group(2), row.group(3))
    for adr_id, doc in sorted(adrs.items()):
        if adr_id not in rows:
            report.add(index, f"{adr_id} is missing from the index")
            continue
        link, status = rows[adr_id]
        if link != doc.path.name:
            report.add(index, f"{adr_id} links to '{link}', expected '{doc.path.name}'")
        if status != str(doc.meta["status"]):
            report.add(index, f"{adr_id} status '{status}' != frontmatter '{doc.meta['status']}'")
    for adr_id in sorted(rows.keys() - on_disk):
        report.add(index, f"{adr_id} is in the index but has no ADR file")


def check_specs(report: Report) -> dict[str, Doc]:
    adrs = _ids_on_disk(ADR_DIR, "ADR")
    docs = [d for p in _documents(SPEC_DIR, "SPEC") if (d := _load(p, report)) is not None]
    docs = [d for d in docs if _require(d, SPEC_FIELDS, report)]
    _check_unique(docs, report)
    by_id = {str(d.meta["id"]): d for d in docs}
    specs = _ids_on_disk(SPEC_DIR, "SPEC")
    for doc in docs:
        _check_common(doc, report, ("created", "updated"))
        if doc.meta["status"] not in SPEC_STATUSES:
            report.add(doc.path, f"status '{doc.meta['status']}' is not valid")
        refs: list[tuple[str, Callable[[str], bool]]] = [
            ("related_adrs", lambda r: r in adrs),
            ("related_specs", lambda r: r in specs),
        ]
        for name, exists in refs:
            values = _str_list(doc.meta.get(name))
            if values is None:
                report.add(doc.path, f"'{name}' must be a list")
                continue
            for ref in values:
                if not exists(ref):
                    report.add(doc.path, f"{name} entry '{ref}' does not exist")
    return by_id


def check_tasks(specs: dict[str, Doc], report: Report) -> None:
    specs_on_disk = _ids_on_disk(SPEC_DIR, "SPEC")
    docs = [d for p in _documents(TASK_DIR, "TASK") if (d := _load(p, report)) is not None]
    docs = [d for d in docs if _require(d, TASK_FIELDS, report)]
    _check_unique(docs, report)
    for doc in docs:
        _check_common(doc, report, ("created", "updated"))
        if doc.meta["status"] not in TASK_STATUSES:
            report.add(doc.path, f"status '{doc.meta['status']}' is not valid")
        spec = specs.get(str(doc.meta["spec"]))
        if spec is None and str(doc.meta["spec"]) in specs_on_disk:
            continue  # the spec itself failed validation and is already reported
        if spec is None:
            report.add(doc.path, f"spec '{doc.meta['spec']}' does not exist")
            continue
        criteria = _str_list(doc.meta["acceptance_criteria"])
        if not criteria:
            report.add(doc.path, "'acceptance_criteria' must be a non-empty list")
            continue
        defined = set(AC_ID.findall(spec.body))
        for ac in criteria:
            if ac not in defined:
                report.add(doc.path, f"acceptance criterion '{ac}' is not defined in {spec.rel}")


def check_policies(report: Report) -> None:
    for path in POLICY_FILES:
        if not path.is_file():
            report.add(path.parent, f"{path.name} is missing")
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            report.add(path, f"does not parse: {exc}")


def validate() -> list[str]:
    report = Report()
    check_adrs(report)
    specs = check_specs(report)
    check_tasks(specs, report)
    check_policies(report)
    return report.errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(error)
    if errors:
        print(f"{len(errors)} document violation(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
