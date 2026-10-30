"""The onboarding rehearsal's input files (Q-04-T018; `docs/runbooks/pilot-onboarding.md` §4, §5).

    python -m abacus_tools.synthetic.onboarding_files --out <directory> [--clients 200] \
        [--seed 2027] [--near "<existing client name>" ...]

The rehearsal (part AY) walks a firm's content in through its own screens on staging: 200 clients
through CLI-06's import (state g), a PBC template through KNW-01's importer, the POR-20 templates
published and ADM-10's sender domain from pending to published. Two of those need files a real firm
would bring; this makes synthetic ones, so the rehearsal never borrows anything real:

- `clients-<n>.csv`: a CCH Axcess Tax client-list export's headings (`Client Name`, `Entity Type`,
  `Primary Contact`, `Email Address`; `engagements.client_import_parse.HEADINGS`). Names carry the
  generator's ` (Synthetic)` marker; mail goes to the reserved `example.test` domain; no TIN column
  at all (the rehearsal firm is synthetic, but the file stays TIN-free). Each `--near` name is
  added once more with a different contact, so the import's dedupe sends that row to review (the
  `to_review` step of RB-41 §2) instead of everything landing `new`.
- `pbc-template.xlsx`: KNW-01's Workbook v2 (`Areas` and `Requests`; DEC-572) from the F-04
  generator's request list, glossary terms only.
- `manifest.json`: each file's SHA-256 and row count, for the rehearsal record.

The files go to `--out` (a scratch directory): they are rehearsal inputs, never committed and never
loaded by the seed loader (pilot-onboarding rule 1: content goes in through the screens). The same
seed gives the same bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from openpyxl import Workbook

from abacus_tools.synthetic.names import client_base, client_name
from abacus_tools.synthetic.requests import request_list
from abacus_tools.synthetic.rng import stream

# openpyxl stamps the save time into each zip entry and into docProps/core.xml; a fixed time keeps
# the same seed's bytes the same (the record's checksums).
_ZIP_TIME: Final = (2000, 1, 1, 0, 0, 0)
_STAMP: Final = re.compile(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(<)")

CLIENT_HEADINGS: Final = ("Client Name", "Entity Type", "Primary Contact", "Email Address")
# CCH's client-type words the import maps (`ENTITY_TYPE_WORDS`), in a firm-like mix.
ENTITY_TYPES: Final = (
    "Individual",
    "Individual",
    "Individual",
    "Married Filing Jointly",
    "S Corporation",
    "C Corporation",
    "LLC",
    "Partnership",
)
_GIVEN: Final = ("Avery", "Jordan", "Riley", "Casey", "Morgan", "Quinn", "Rowan", "Sasha", "Tatum")
MAIL_DOMAIN: Final = "example.test"  # RFC 2606: reserved, never delivered
AREAS: Final = (
    ("general", "General"),
    ("cash", "Cash"),
    ("receivables", "Receivables"),
    ("payables", "Payables"),
    ("inventory", "Inventory"),
    ("fixed_assets", "Fixed assets"),
    ("debt", "Debt"),
    ("payroll", "Payroll"),
    ("equity", "Equity"),
    ("revenue", "Revenue"),
)
XLSX_SHEETS: Final = ("Areas", "Requests")


def _slug(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())[:24] or "client"


def client_rows(
    count: int, seed: int, near: Sequence[str] = ()
) -> list[tuple[str, str, str, str]]:
    """`count` distinct synthetic clients, then one near duplicate per `near` name."""
    rng = stream(seed, "onboarding_clients")
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    while len(rows) < count:
        base = client_base(rng)
        name = client_name(base)
        if name in seen:
            name = client_name(f"{base} {len(rows) + 1}")
        seen.add(name)
        kind = ENTITY_TYPES[len(rows) % len(ENTITY_TYPES)]
        contact = f"{rng.choice(_GIVEN)} {base.split()[-1]}"
        email = f"{_slug(contact)}.{len(rows) + 1}@{MAIL_DOMAIN}"
        rows.append((name, kind, contact, email))
    for n, name in enumerate(near, start=1):
        rows.append((name, "Individual", f"Review Contact {n}", f"review.{n}@{MAIL_DOMAIN}"))
    return rows


def client_csv(rows: Sequence[tuple[str, str, str, str]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CLIENT_HEADINGS)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def pbc_workbook() -> tuple[bytes, int]:
    """Workbook v2's required sheets; the request count."""
    workbook = Workbook()
    areas = workbook.active
    if areas is None:  # openpyxl always makes one; the type says it may not
        raise RuntimeError("openpyxl made a workbook without a sheet")
    areas.title = "Areas"
    areas.append(("code", "name"))
    for code, name in AREAS:
        areas.append((code, name))
    requests = workbook.create_sheet("Requests")
    requests.append(("area_code", "description", "tier"))
    items = request_list().items
    for item in items:
        requests.append((item.audit_area, item.description, item.retrievability_tier))
    saved = io.BytesIO()
    workbook.save(saved)
    out = io.BytesIO()
    with zipfile.ZipFile(saved) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            body = src.read(info)
            if info.filename == "docProps/core.xml":
                body = _STAMP.sub(rb"\g<1>2000-01-01T00:00:00Z\g<2>", body)
            fixed = zipfile.ZipInfo(info.filename, date_time=_ZIP_TIME)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(fixed, body)
    return out.getvalue(), len(items)


def write(
    out_dir: Path, *, clients: int, seed: int, near: Sequence[str] = ()
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = client_rows(clients, seed, near)
    files: dict[str, tuple[bytes, int]] = {
        f"clients-{clients}.csv": (client_csv(rows), len(rows)),
        "pbc-template.xlsx": pbc_workbook(),
    }
    listed: dict[str, dict[str, object]] = {}
    for name, (body, count) in files.items():
        (out_dir / name).write_bytes(body)
        listed[name] = {"sha256": hashlib.sha256(body).hexdigest(), "rows": count}
    manifest: dict[str, object] = {"seed": seed, "files": listed}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="abacus_tools.synthetic.onboarding_files", description=__doc__
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--clients", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--near", action="append", default=[])
    args = parser.parse_args(argv)
    if not 1 <= args.clients <= 2000:
        print("--clients must be 1 to 2,000 (CLI-06's import limit)", file=sys.stderr)
        return 2
    print(json.dumps(write(args.out, clients=args.clients, seed=args.seed, near=args.near)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
