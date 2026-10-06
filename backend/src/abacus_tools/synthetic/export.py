"""CSV, JSON and XLSX exports (SPEC-001 AC-1, AC-12, AC-15).

All three are byte-identical for identical input on any platform: no timestamps, sorted keys, `\\n`
line endings, and an XLSX written with the standard library as an uncompressed (stored) zip with
fixed entry times. Files are named after the period they are meant to cover, so a flawed artefact
(e.g. a stale trial balance) never collides with another file.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import re
import zipfile
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast
from xml.sax.saxutils import escape

from abacus_tools.synthetic.flaws import last_statement_index
from abacus_tools.synthetic.model import ClientEntity, SyntheticClient

Rows = list[list[str]]
_AMOUNT = re.compile(r"-?\d+\.\d{2}")
AMOUNT_COLUMNS = frozenset(
    {
        "debit",
        "credit",
        "amount",
        "balance",
        "current",
        "days_1_30",
        "days_31_60",
        "days_61_90",
        "over_90",
        "total",
    }
)
# XML 1.0 cannot carry these; OOXML writes them as _xHHHH_ (a literal _xHHHH_ as
# _x005F_xHHHH_).
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
_OOXML_ESCAPE = re.compile(r"_(x[0-9A-Fa-f]{4}_)")
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _amount(value: Decimal) -> str:
    return "0.00" if value == 0 else format(value, "f")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _unreadable(client: SyntheticClient) -> set[str]:
    return {f.artefact for f in client.manifest.flaws if f.category == "unreadable"}


def _tables(client: SyntheticClient) -> Iterator[tuple[str, str | None, Rows]]:
    """(relative path, artefact name if flaw-targetable, rows) for every CSV file."""
    for entity in client.client_entities:
        yield from _entity_tables(entity, slug(entity.name))
    rows: Rows = [["id", "description", "audit_area", "retrievability_tier", "artefact"]]
    rows += [
        [i.id, i.description, i.audit_area, i.retrievability_tier, i.artefact or ""]
        for i in client.request_list.items
    ]
    yield "request_list.csv", None, rows


def _entity_tables(entity: ClientEntity, folder: str) -> Iterator[tuple[str, str | None, Rows]]:
    yield (
        f"{folder}/chart_of_accounts.csv",
        None,
        [["code", "name", "type"]] + [[a.code, a.name, a.type] for a in entity.accounts],
    )
    gl: Rows = [
        [
            "entry_id",
            "date",
            "memo",
            "line",
            "account_code",
            "debit",
            "credit",
            "description",
            "counterparty",
        ]
    ]
    for e in entity.journal_entries:
        for n, ln in enumerate(e.lines, start=1):
            gl.append(
                [
                    e.id,
                    e.date.isoformat(),
                    e.memo,
                    str(n),
                    ln.account_code,
                    _amount(ln.debit),
                    _amount(ln.credit),
                    ln.description,
                    ln.counterparty or "",
                ]
            )
    yield f"{folder}/general_ledger.csv", "general_ledger", gl
    slots = _month_slots(entity)
    last = len(entity.trial_balances) - 1
    for n, tb in enumerate(entity.trial_balances):
        rows: Rows = [
            ["as_of", "client_entity", "account_code", "account_name", "debit", "credit"]
        ]
        rows += [
            [
                tb.as_of.isoformat(),
                tb.client_entity,
                ln.account_code,
                ln.account_name,
                _amount(ln.debit),
                _amount(ln.credit),
            ]
            for ln in tb.lines
        ]
        yield (
            f"{folder}/trial_balance_{slots[n].isoformat()}.csv",
            "trial_balance" if n == last else None,
            rows,
        )
    flawed = last_statement_index(entity)
    per_account: dict[str, int] = {}
    for n, s in enumerate(entity.bank_statements):
        index = per_account.get(s.account_number, 0)
        per_account[s.account_number] = index + 1
        rows = [["record_type", "date", "description", "amount", "balance", "currency"]]
        rows.append(
            ["opening", s.period_start.isoformat(), "", "", _amount(s.opening_balance), s.currency]
        )
        rows += [
            [
                "line",
                ln.date.isoformat(),
                ln.description,
                _amount(ln.amount),
                _amount(ln.balance),
                s.currency,
            ]
            for ln in s.lines
        ]
        rows.append(
            ["closing", s.period_end.isoformat(), "", "", _amount(s.closing_balance), s.currency]
        )
        rows += [
            [item.kind, "", item.description, _amount(item.amount), "", s.currency]
            for item in s.reconciling_items
        ]
        name = f"bank_statement_{s.account_number}_{slots[index]:%Y-%m}.csv"
        yield f"{folder}/{name}", "bank_statement" if n == flawed else None, rows
    for artefact, ag in (("ar_aging", entity.ar_aging), ("ap_aging", entity.ap_aging)):
        rows = [
            [
                "as_of",
                "counterparty",
                "current",
                "days_1_30",
                "days_31_60",
                "days_61_90",
                "over_90",
                "total",
            ]
        ]
        rows += [
            [
                ag.as_of.isoformat(),
                ln.counterparty,
                _amount(ln.current),
                _amount(ln.days_1_30),
                _amount(ln.days_31_60),
                _amount(ln.days_61_90),
                _amount(ln.over_90),
                _amount(ln.total),
            ]
            for ln in ag.lines
        ]
        yield f"{folder}/{artefact}.csv", artefact, rows


def _month_slots(entity: ClientEntity) -> list[date]:
    """The period each month-end artefact is meant to cover, independent of any flaw."""
    slots: list[date] = []
    year, month = entity.period_start.year, entity.period_start.month
    while len(slots) < len(entity.trial_balances):
        nxt = date(year + month // 12, month % 12 + 1, 1)
        slots.append(date.fromordinal(nxt.toordinal() - 1))
        year, month = nxt.year, nxt.month
    return slots


def _readable_tables(client: SyntheticClient) -> Iterator[tuple[str, Rows | None]]:
    first = slug(client.client_entities[0].name) + "/"
    for path, artefact, rows in _tables(client):
        empty = path.startswith(first) and artefact is not None and artefact in _unreadable(client)
        yield path, None if empty else rows


def _csv_bytes(rows: Rows) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _manifest(client: SyntheticClient) -> dict[str, object]:
    return {
        "flaws": [dataclasses.asdict(f) for f in client.manifest.flaws],
        "adversarial": [dataclasses.asdict(a) for a in client.manifest.adversarial],
    }


def to_csv(client: SyntheticClient, directory: Path) -> tuple[Path, ...]:
    written: list[Path] = []
    for rel, rows in _readable_tables(client):
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"" if rows is None else _csv_bytes(rows))
        written.append(path)
    manifest = directory / "manifest.json"
    manifest.write_bytes(_json_bytes(_manifest(client)))
    written.append(manifest)
    return tuple(sorted(written))


_FIELDS: dict[type, tuple[str, ...]] = {}


def _field_names(kind: type) -> tuple[str, ...]:
    names = _FIELDS.get(kind)
    if names is None:
        names = tuple(f.name for f in dataclasses.fields(kind))
        _FIELDS[kind] = names
    return names


def _plain(value: object) -> object:
    if isinstance(value, str | int | None):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {name: _plain(getattr(value, name)) for name in _field_names(type(value))}
    if isinstance(value, tuple):
        return [_plain(v) for v in cast(tuple[object, ...], value)]
    if isinstance(value, Decimal):
        return _amount(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _json_bytes(data: object) -> bytes:
    # No `indent`: with it, json falls back to its pure-Python encoder (10x slower on a GL).
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def to_json(client: SyntheticClient, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "client.json"
    path.write_bytes(_json_bytes(_plain(client)))
    return path


# --- XLSX ---------------------------------------------------------------------------------------


def _column(n: int) -> str:
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _xml_text(value: str) -> str:
    value = _OOXML_ESCAPE.sub(r"_x005F_\1", value)
    value = _XML_ILLEGAL.sub(lambda m: f"_x{ord(m.group()):04X}_", value)
    return escape(value)


def _sheet_xml(rows: Rows) -> bytes:
    columns = [_column(c) for c in range(1, max((len(r) for r in rows), default=0) + 1)]
    numeric = {c for c, name in enumerate(rows[0] if rows else []) if name in AMOUNT_COLUMNS}
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    ]
    for r, row in enumerate(rows, start=1):
        out.append(f'<row r="{r}">')
        for c, value in enumerate(row):
            ref = f"{columns[c]}{r}"
            if r > 1 and c in numeric and _AMOUNT.fullmatch(value):
                out.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                out.append(
                    f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
                    f"{_xml_text(value)}</t></is></c>"
                )
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out).encode("utf-8")


def _sheet_names(paths: list[str]) -> list[str]:
    names: list[str] = []
    entity_folders: dict[str, int] = {}
    for path in paths:
        folder, _, file = path.rpartition("/")
        stem = file.removesuffix(".csv")
        if folder:
            index = entity_folders.setdefault(folder, len(entity_folders))
            stem = (
                f"{index}-{stem.replace('trial_balance', 'tb').replace('bank_statement', 'bank')}"
            )
        base = re.sub(r"[\[\]:*?/\\]", "-", stem)[:31]
        name, n = base, 2
        while name in names:
            suffix = f"~{n}"
            name, n = base[: 31 - len(suffix)] + suffix, n + 1
        names.append(name)
    return names


def _manifest_rows(client: SyntheticClient) -> Rows:
    rows: Rows = [
        [
            "kind",
            "category",
            "artefact",
            "client_entity",
            "field",
            "location",
            "detection",
            "payload",
        ]
    ]
    rows += [
        ["flaw", f.category, f.artefact, f.client_entity, "", f.location, f.detection, ""]
        for f in client.manifest.flaws
    ]
    rows += [
        ["adversarial", a.category, a.artefact, "", a.field, a.location, "", a.payload]
        for a in client.manifest.adversarial
    ]
    return rows


def to_xlsx(client: SyntheticClient, path: Path) -> Path:
    """One sheet per CSV file plus a `manifest` sheet.

    Cells keep every value exactly (AC-12). The `oversized_field` payload exceeds Excel's
    32,767-character cell limit on purpose; Excel repairs such a file on open, other readers don't.
    """
    tables = [(rel, rows) for rel, rows in _readable_tables(client) if rows is not None]
    tables.append(("manifest.csv", _manifest_rows(client)))
    names = _sheet_names([rel for rel, _ in tables])
    sheets = "".join(
        f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{n}" r:id="rId{n}"/>'
        for n, name in enumerate(names, start=1)
    )
    rels = "".join(
        f'<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/worksheet" Target="worksheets/sheet{n}.xml"/>'
        for n in range(1, len(names) + 1)
    )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{n}.xml" ContentType="application/'
        f'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for n in range(1, len(names) + 1)
    )
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    parts: list[tuple[str, bytes]] = [
        (
            "[Content_Types].xml",
            (
                f'{head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                f"{overrides}</Types>"
            ).encode(),
        ),
        (
            "_rels/.rels",
            (
                f'{head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
            ).encode(),
        ),
        (
            "xl/workbook.xml",
            (
                f"{head}<workbook "
                'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f"<sheets>{sheets}</sheets></workbook>"
            ).encode(),
        ),
        (
            "xl/_rels/workbook.xml.rels",
            (
                f'{head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f"{rels}</Relationships>"
            ).encode(),
        ),
    ]
    parts += [
        (f"xl/worksheets/sheet{n}.xml", _sheet_xml(rows))
        for n, (_, rows) in enumerate(tables, start=1)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return path
