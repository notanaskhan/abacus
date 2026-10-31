"""The CCH Axcess file adapter: pure functions over the engine's files (T-01-T19; T-01 §3.9,
§3.10; `docs/contracts/tax-engine-bridge.md` §6; ADR-050, ADR-052).

Parsing runs in the isolated child (`kernel.isolation`): the file is client-system content and
hostile. Nothing here touches the database, the clock or the network. `diff` is code: the engine's
value against Accrued's for each field the engine holds; equal decimals are equal however they
are written ("123223" and "123223.00"). An engine value with no Accrued value is a difference
(`engine_only`); a field Accrued holds that the engine file does not mention is left alone (the
engine file is not the whole return).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

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
SEVERITIES: Final = frozenset({"error", "warning", "informational"})
MAX_ROWS: Final = 20_000
MAX_TEXT: Final = 2000
_RETURN_ID: Final = re.compile(r"[0-9]{4}[A-Z]:[A-Za-z0-9]{1,20}")
_VERSION: Final = re.compile(r"V([0-9]{1,4})")
_FIELD: Final = re.compile(r"[A-Za-z0-9_.!:-]{1,80}")


class EngineFileInvalid(ValueError):
    """The file is not the engine's file of this kind; `code` says why (never its content)."""

    def __init__(self, code: str, row: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.row = row


@dataclass(frozen=True)
class EngineRow:
    field_key: str
    form: str
    line: str
    value: str


@dataclass(frozen=True)
class ValuesFile:
    engine_return_id: str  # `2025I:FeldJ`
    version: int
    rows: tuple[EngineRow, ...]


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    form: str
    field_key: str | None
    message: str


@dataclass(frozen=True)
class DiagnosticsFile:
    engine_return_id: str
    version: int
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class DiffRow:
    field_key: str
    accrued: dict[str, object] | None  # `{t, v}` as Accrued holds it
    engine: dict[str, object]
    cause_code: str  # `engine_value` (both hold it, they differ) · `engine_only`


def _rows(content: bytes, header: tuple[str, ...]) -> list[list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise EngineFileInvalid("not_utf8") from None
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or tuple(c.strip() for c in rows[0]) != header:
        raise EngineFileInvalid("unknown_header")
    if len(rows) - 1 > MAX_ROWS:
        raise EngineFileInvalid("too_many_rows")
    return [[c.strip() for c in r] for r in rows[1:] if any(c.strip() for c in r)]


def _head(rows: list[list[str]]) -> tuple[str, int]:
    """Every row names the same return and version."""
    if not rows:
        raise EngineFileInvalid("empty")
    ids = {(r[0], r[1]) for r in rows}
    if len(ids) != 1:
        raise EngineFileInvalid("mixed_returns")
    return_id, version = next(iter(ids))
    found = _VERSION.fullmatch(version)
    if not _RETURN_ID.fullmatch(return_id) or found is None:
        raise EngineFileInvalid("bad_return_id")
    return return_id, int(found.group(1))


def parse_values(content: bytes) -> ValuesFile:
    rows = _rows(content, VALUES_HEADER)
    for n, r in enumerate(rows, start=2):
        if len(r) != len(VALUES_HEADER) or not _FIELD.fullmatch(r[2]) or len(r[5]) > MAX_TEXT:
            raise EngineFileInvalid("bad_row", n)
    return_id, version = _head(rows)
    keys = [r[2] for r in rows]
    if len(set(keys)) != len(keys):
        raise EngineFileInvalid("duplicate_field")
    return ValuesFile(
        return_id,
        version,
        tuple(
            sorted((EngineRow(r[2], r[3], r[4], r[5]) for r in rows), key=lambda e: e.field_key)
        ),
    )


def parse_diagnostics(content: bytes) -> DiagnosticsFile:
    rows = _rows(content, DIAGNOSTICS_HEADER)
    for n, r in enumerate(rows, start=2):
        if (
            len(r) != len(DIAGNOSTICS_HEADER)
            or r[2] not in SEVERITIES
            or not 1 <= len(r[3]) <= 40
            or not 1 <= len(r[6]) <= MAX_TEXT
            or (r[5] and not _FIELD.fullmatch(r[5]))
        ):
            raise EngineFileInvalid("bad_row", n)
    return_id, version = _head(rows)
    return DiagnosticsFile(
        return_id,
        version,
        tuple(Diagnostic(r[2], r[3], r[4], r[5] or None, r[6]) for r in rows),
    )


# --- T-01-T26: the engine's PDFs and its e-file status report -------------------------------

PDF_KINDS: Final = (
    "client_copy",
    "form_8879",
    "tr_579_it",
    "voucher_1040es_q4",
    "voucher_it2105_q4",
    "k1",
)
ACKS_HEADER: Final = (
    "return_id",
    "jurisdiction",
    "submission_last4",
    "status",
    "status_at",
    "reject_code",
    "reject_text",
)
_PDF_NAME: Final = re.compile(
    r"([0-9]{4}[A-Z])_([A-Za-z0-9]{1,20})_V([0-9]{1,4})_([a-z0-9_]{1,40})\.pdf"
)
_K1_FAMILY: Final = re.compile(r"(k1|k3|state_k1_[a-z]{2}|letter)_[a-z0-9]{1,20}")
_LAST4: Final = re.compile(r"[A-Za-z0-9]{4}")
_JURISDICTION: Final = re.compile(r"federal|[A-Z]{2}")
_WHEN: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9:.+-]{5,20}Z?)?")


@dataclass(frozen=True)
class EnginePdf:
    engine_return_id: str
    version: int
    kind: str


def parse_pdf(name: str, content: bytes) -> EnginePdf:
    """A PDF the engine produced, by its name (`2025I_FeldJ_V3_k1.pdf`) and its envelope (`%PDF-`
    and a trailer). The kind is one of `PDF_KINDS`; the content is not parsed further."""
    found = _PDF_NAME.fullmatch(name)
    if found is None:
        raise EngineFileInvalid("bad_pdf_name")
    kind = found.group(4)
    if kind not in PDF_KINDS and _K1_FAMILY.fullmatch(kind):
        # T-02-T20: one file per recipient (`k1_p01`, `k3_p01`, `state_k1_il_p01`,
        # `letter_p01`) files as the K-1 family; the K-1 set names each by its file name.
        kind = "k1"
    if kind not in PDF_KINDS:
        raise EngineFileInvalid("unknown_pdf_kind")
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-64:]:
        raise EngineFileInvalid("not_a_pdf")
    return EnginePdf(f"{found.group(1)}:{found.group(2)}", int(found.group(3)), kind)


@dataclass(frozen=True)
class Ack:
    jurisdiction: str
    submission_last4: str
    status: str
    status_at: str
    reject_code: str | None
    reject_text: str | None


@dataclass(frozen=True)
class AcksFile:
    engine_return_id: str
    acks: tuple[Ack, ...]


def parse_acks(content: bytes) -> AcksFile:
    """The e-file status report: one row per jurisdiction, accepted or rejected, a rejection
    with its code. Only the submission id's last four is ever read (R-04)."""
    rows = _rows(content, ACKS_HEADER)
    if not rows:
        raise EngineFileInvalid("empty")
    ids = {r[0] for r in rows}
    if len(ids) != 1:
        raise EngineFileInvalid("mixed_returns")
    (return_id,) = ids
    if not _RETURN_ID.fullmatch(return_id):
        raise EngineFileInvalid("bad_return_id")
    acks: list[Ack] = []
    for n, r in enumerate(rows, start=2):
        if (
            len(r) != len(ACKS_HEADER)
            or not _JURISDICTION.fullmatch(r[1])
            or not _LAST4.fullmatch(r[2])
            or r[3] not in ("accepted", "rejected")
            or not _WHEN.fullmatch(r[4])
            or (r[3] == "rejected" and not 1 <= len(r[5]) <= 40)
            or len(r[6]) > MAX_TEXT
        ):
            raise EngineFileInvalid("bad_row", n)
        acks.append(Ack(r[1], r[2], r[3], r[4], r[5] or None, r[6] or None))
    return AcksFile(return_id, tuple(acks))


def typed(value: str) -> dict[str, object]:
    """An engine cell as Accrued's typed value: a plain decimal is `decimal`, anything else
    (a method, a last four) is `text`."""
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return {"t": "text", "v": value}
    if not number.is_finite():
        return {"t": "text", "v": value}
    return {"t": "decimal", "v": format(number.normalize(), "f")}


def _same(a: dict[str, object] | None, b: dict[str, object]) -> bool:
    if a is None:
        return False
    if a.get("t") == b.get("t") == "decimal":
        try:
            return Decimal(str(a.get("v"))) == Decimal(str(b.get("v")))
        except InvalidOperation:
            return False
    return a.get("t") == b.get("t") and a.get("v") == b.get("v")


def differences(accrued: dict[str, dict[str, object]], engine: ValuesFile) -> list[DiffRow]:
    """The engine's fields that differ from Accrued's, in key order (code, ADR-050)."""
    out: list[DiffRow] = []
    for row in engine.rows:
        mine = accrued.get(row.field_key)
        theirs = typed(row.value)
        if not _same(mine, theirs):
            out.append(
                DiffRow(
                    row.field_key, mine, theirs, "engine_only" if mine is None else "engine_value"
                )
            )
    return out


__all__ = [
    "DIAGNOSTICS_HEADER",
    "VALUES_HEADER",
    "Diagnostic",
    "DiagnosticsFile",
    "DiffRow",
    "EngineFileInvalid",
    "EngineRow",
    "ValuesFile",
    "differences",
    "parse_diagnostics",
    "parse_values",
    "typed",
]
