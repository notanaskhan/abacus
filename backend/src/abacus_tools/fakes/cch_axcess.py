"""A fake CCH Axcess Tax for synthetic environments (T-01-T22; T-01 §3.8 to §3.13, §7.1; ADR-231).

The real bridge is file mode: staff carry Accrued's export workbook into CCH Axcess and carry the
engine's files back (`docs/contracts/tax-engine-bridge.md`, "Engine files"). This fake stands in
for the engine on the far side of that walk: it reads Accrued's export workbook and emits the
files the engine would, so the adapter (T-01-T19), the delivery packet (T-01-T26) and the e-file
record (T-01-T27) are built and demonstrated without CCH. It makes no network call and holds no
real data: every figure is the Brightwater Hale seed's (the Feld 2025 Form 1040, TAX-09 and
TAX-12), and an unknown return gets back only what it exported.

- **Values** (`values_file`): `2025I:FeldJ:V1`, `V2` and `V3`, a CSV the adapter diffs against the
  current checkpoint. V3 differs from Accrued in exactly TAX-09's five fields.
- **Diagnostics** (`diagnostics_file`): `informational` (0 errors, the two notes of TAX-09d) or
  `ip_pin` (the federal Identity Protection PIN error of TAX-09d2).
- **PDFs** (`pdf_files`): client copy, Form 8879, NY TR-579-IT, the 2026 Form 1040-ES and IT-2105
  Q4 vouchers and a K-1, each a small deterministic PDF.
- **E-file status report** (`efile_status_file`): federal, IL, CO and NY accepted on Sep 18-19,
  2026, or the federal rejection IND-181-01.

Every output is deterministic: the same inputs give the same bytes. `cch_for(tenant)` refuses
outside local, test and evaluation, and for a firm that is not synthetic (`FakeCchRefused`).
Product code never imports this (ADR-101).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from openpyxl import Workbook, load_workbook

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import is_synthetic_firm

VALUES_HEADER: Final = ("return_id", "version", "field_key", "form", "line", "value")
DIAGNOSTICS_HEADER: Final = (
    "return_id",
    "version",
    "severity",
    "code",
    "form",
    "field_key",
    "message",
)
EFILE_HEADER: Final = (
    "return_id",
    "jurisdiction",
    "submission_last4",
    "status",
    "status_at",
    "reject_code",
    "reject_text",
)
SEVERITIES: Final = ("error", "warning", "informational")
PDF_KINDS: Final = (
    "client_copy",
    "form_8879",
    "tr_579_it",
    "voucher_1040es_q4",
    "voucher_it2105_q4",
    "k1",
)
FELD: Final = "2025I:FeldJ"
_STAMP: Final = datetime(2026, 9, 16)  # the export's day in the seed; fixed, so bytes repeat

Diagnostics = Literal["informational", "ip_pin"]
Efile = Literal["accepted", "rejected"]


class FakeCchRefused(RuntimeError):
    """The fake engine is for synthetic environments and synthetic firms only."""


class ExportUnreadable(ValueError):
    """The workbook is not an Accrued export (sheets `Return` and `Fields`)."""


@dataclass(frozen=True)
class EngineValue:
    field_key: str
    form: str
    line: str
    value: str


@dataclass(frozen=True)
class Export:
    """What the fake reads from Accrued's export workbook."""

    return_id: str
    tax_year: int
    form: str
    fields: tuple[EngineValue, ...]


# --- the Feld return's engine side (TAX-09, TAX-12; the seed's pack ledger) ---------------------

_V1: Final = (
    EngineValue("f1040.total_tax", "1040", "24", "123223"),
    EngineValue("f1040.payments", "1040", "33", "123476"),
    EngineValue("f1040.refund", "1040", "35a", "253"),
)
_V2: Final = (
    *_V1,
    EngineValue("it201.tax", "IT-201", "62", "52805"),
    EngineValue("it201.payments", "IT-201", "76", "51536"),
    EngineValue("it201.balance_due", "IT-201", "80", "1269"),
    EngineValue("il1040.tax", "IL-1040", "14", "7011"),
    EngineValue("il1040.ptet_credit", "IL-1040", "21", "7011"),
    EngineValue("il1040.balance_due", "IL-1040", "30", "0"),
    EngineValue("co_dr0104pn.ptet_credit", "DR 0104", "29", "4268"),
    EngineValue("co_dr0104pn.balance_due", "DR 0104", "39", "0"),
    EngineValue("it2105_2026.voucher_amount", "IT-2105", "Q4", "7824"),
)
# V3 adds exactly TAX-09's five differing fields.
_V3: Final = (
    *_V2,
    EngineValue("f1040es_2026.voucher_amount", "1040-ES", "Q1-Q4", "19990"),
    EngineValue("f1040.direct_deposit_last4", "1040", "35b", "6620"),
    EngineValue("f8879.signature_method", "8879", "Part II", "practitioner_pin"),
    EngineValue("il1040_schnr.il_source_income", "IL-1040 Sch NR", "47", "141634"),
    EngineValue("co_dr0104pn.co_source_income", "DR 0104PN", "34", "96989"),
)
_FELD_VALUES: Final = {1: _V1, 2: _V2, 3: _V3}

_NOTES: Final = (
    (
        "informational",
        "8995A-UBIA",
        "8995-A",
        "f8995a.ubia",
        "UBIA from Statement A used for the W-2/UBIA limit",
    ),
    (
        "informational",
        "IT201-L20",
        "IT-201",
        "it201.line20",
        "Interest on other states' obligations 1,550 (source attached)",
    ),
)
_IP_PIN: Final = (
    "error",
    "EF-IPPIN-01",
    "1040",
    "f1040.ip_pin_primary",
    "Identity Protection PIN required for the primary taxpayer (Jonah Feld)",
)
_ACCEPTED: Final = (
    ("federal", "2614", "accepted", "2026-09-18T14:47:00-05:00", "", ""),
    ("IL", "8831", "accepted", "2026-09-18T16:10:00-05:00", "", ""),
    ("CO", "4407", "accepted", "2026-09-18T16:22:00-05:00", "", ""),
    ("NY", "5190", "accepted", "2026-09-19T08:55:00-05:00", "", ""),
)
_REJECTED: Final = (
    (
        "federal",
        "2614",
        "rejected",
        "2026-09-18T14:47:00-05:00",
        "IND-181-01",
        "The Identity Protection PIN for the primary taxpayer is missing or incorrect.",
    ),
)


def _csv(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode()


def _pdf(lines: list[str]) -> bytes:
    """A one-page PDF with the given lines in Helvetica: no dates, no ids, the same bytes for the
    same lines (the fake's documents are fixtures, not renderings)."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    text = "BT /F1 11 Tf 72 720 Td 14 TL " + " ".join(f"({esc(t)}) '" for t in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(text.encode('latin-1'))} >>\nstream\n{text}\nendstream",
    ]
    body = b"%PDF-1.4\n"
    offsets: list[int] = []
    for n, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{n} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return body


# --- reading Accrued's export --------------------------------------------------------------------


def read_export(workbook: bytes) -> Export:
    """Accrued's export workbook: sheet `Return` (key, value rows: return_id, tax_year, form) and
    sheet `Fields` (field_key, form, line, value)."""
    try:
        book = load_workbook(io.BytesIO(workbook), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several types for a non-workbook
        raise ExportUnreadable("not a workbook") from exc
    if "Return" not in book.sheetnames or "Fields" not in book.sheetnames:
        raise ExportUnreadable("sheets Return and Fields are required")
    head = {
        str(k): str(v)
        for k, v in book["Return"].iter_rows(min_row=2, max_col=2, values_only=True)
        if k is not None and v is not None
    }
    missing = {"return_id", "tax_year", "form"} - head.keys()
    if missing:
        raise ExportUnreadable(f"Return is missing {', '.join(sorted(missing))}")
    fields = tuple(
        EngineValue(str(k), str(f or ""), str(n or ""), str(v))
        for k, f, n, v in book["Fields"].iter_rows(min_row=2, max_col=4, values_only=True)
        if k is not None and v is not None
    )
    return Export(head["return_id"], int(head["tax_year"]), head["form"], fields)


def sample_export(return_id: str, tax_year: int, form: str, fields: list[EngineValue]) -> bytes:
    """A workbook in the export's layout, for tests and the local stack until T-01-T25's real
    export lands (fixed properties, so the same fields give the same bytes)."""
    book = Workbook()
    book.remove(book.worksheets[0])
    head = book.create_sheet("Return")
    head.append(["key", "value"])
    for row in (("return_id", return_id), ("tax_year", tax_year), ("form", form)):
        head.append(list(row))
    sheet = book.create_sheet("Fields")
    sheet.append(["field_key", "form", "line", "value"])
    for f in sorted(fields, key=lambda f: f.field_key):
        sheet.append([f.field_key, f.form, f.line, f.value])
    book.properties.creator = "Accrued"
    book.properties.created = _STAMP
    book.properties.modified = _STAMP
    raw = io.BytesIO()
    book.save(raw)
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw.getvalue())) as source,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=_STAMP.timetuple()[:6])
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, source.read(info.filename))
    return out.getvalue()


# --- the engine's files --------------------------------------------------------------------------


@dataclass(frozen=True)
class CchAxcessFake:
    """The engine, after `cch_for` has checked the environment and the firm."""

    def engine_id(self, export: Export, version: int) -> str:
        return f"{export.return_id}:V{version}"

    def values(self, export: Export, version: int) -> tuple[EngineValue, ...]:
        """What the engine holds at `version`: Accrued's exported fields, then the engine's own
        values over them (only the Feld return has any; anything else echoes its export)."""
        if version < 1:
            raise ValueError("engine versions start at 1")
        merged = {f.field_key: f for f in export.fields}
        if export.return_id == FELD:
            for v in _FELD_VALUES.get(min(version, 3), ()):
                merged[v.field_key] = v
        return tuple(merged[k] for k in sorted(merged))

    def values_file(self, export: Export, version: int) -> bytes:
        rows = [
            (export.return_id, f"V{version}", v.field_key, v.form, v.line, v.value)
            for v in self.values(export, version)
        ]
        return _csv(VALUES_HEADER, rows)

    def diagnostics_file(self, export: Export, version: int, variant: Diagnostics) -> bytes:
        found = list(_NOTES) if export.return_id == FELD else []
        if variant == "ip_pin":
            found.insert(0, _IP_PIN)
        rows = [(export.return_id, f"V{version}", *d) for d in found]
        return _csv(DIAGNOSTICS_HEADER, rows)

    def pdf_files(self, export: Export, version: int) -> dict[str, bytes]:
        """One PDF per kind, named `<return>_<kind>.pdf` (colons become underscores)."""
        stem = self.engine_id(export, version).replace(":", "_")
        title = {
            "client_copy": f"{export.tax_year} Form {export.form} - client copy",
            "form_8879": f"Form 8879 - IRS e-file Signature Authorization - TY{export.tax_year}",
            "tr_579_it": f"NY TR-579-IT - e-file Signature Authorization - TY{export.tax_year}",
            "voucher_1040es_q4": f"{export.tax_year + 1} Form 1040-ES voucher - Q4",
            "voucher_it2105_q4": f"{export.tax_year + 1} IT-2105 voucher - Q4",
            "k1": f"Schedule K-1 - TY{export.tax_year}",
        }
        return {
            f"{stem}_{kind}.pdf": _pdf(
                [title[kind], self.engine_id(export, version), "Synthetic document"]
            )
            for kind in PDF_KINDS
        }

    def efile_status_file(self, export: Export, variant: Efile) -> bytes:
        rows = [
            (export.return_id, *r) for r in (_ACCEPTED if variant == "accepted" else _REJECTED)
        ]
        return _csv(EFILE_HEADER, rows)


async def cch_for(tenant: TenantContext) -> CchAxcessFake:
    """The fake engine for a synthetic firm in a synthetic environment; refused otherwise."""
    if settings().environment not in SYNTHETIC_ENVIRONMENTS:
        raise FakeCchRefused("the fake engine runs only in local, test and evaluation")
    if not await is_synthetic_firm(tenant):
        raise FakeCchRefused("the fake engine runs only for a synthetic firm")
    return CchAxcessFake()


# --- the format the adapter reads (conformance) --------------------------------------------------


def conformance(name: str, content: bytes) -> list[str]:
    """What is wrong with an engine file against the bridge's file formats, by its kind (the
    file's header for CSVs, `%PDF-` for PDFs); empty when it conforms. The same check runs on the
    fake's files and on the partner-validated sample files (F-09-T120) when they are filed."""
    if name.endswith(".pdf"):
        return [] if content.startswith(b"%PDF-") and b"%%EOF" in content[-32:] else ["not a PDF"]
    try:
        rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
    except UnicodeDecodeError:
        return ["not UTF-8"]
    if not rows:
        return ["empty"]
    header = tuple(rows[0])
    problems: list[str] = []
    if header == VALUES_HEADER:
        for n, row in enumerate(rows[1:], start=2):
            if len(row) != len(VALUES_HEADER) or not row[2]:
                problems.append(f"row {n}: field_key and six columns are required")
            elif not row[1].startswith("V") or not row[1][1:].isdigit():
                problems.append(f"row {n}: version must read V<n>")
    elif header == DIAGNOSTICS_HEADER:
        for n, row in enumerate(rows[1:], start=2):
            if len(row) != len(DIAGNOSTICS_HEADER) or row[2] not in SEVERITIES:
                problems.append(f"row {n}: severity must be one of {', '.join(SEVERITIES)}")
    elif header == EFILE_HEADER:
        for n, row in enumerate(rows[1:], start=2):
            if len(row) != len(EFILE_HEADER) or row[3] not in ("accepted", "rejected"):
                problems.append(f"row {n}: status must be accepted or rejected")
            elif row[3] == "rejected" and not row[5]:
                problems.append(f"row {n}: a rejection carries its code")
            elif not (len(row[2]) == 4 and row[2].isalnum()):
                problems.append(f"row {n}: submission_last4 is four characters")
    else:
        problems.append("unknown header")
    return problems


__all__ = [
    "DIAGNOSTICS_HEADER",
    "EFILE_HEADER",
    "FELD",
    "PDF_KINDS",
    "VALUES_HEADER",
    "CchAxcessFake",
    "EngineValue",
    "Export",
    "ExportUnreadable",
    "FakeCchRefused",
    "cch_for",
    "conformance",
    "read_export",
    "sample_export",
]
