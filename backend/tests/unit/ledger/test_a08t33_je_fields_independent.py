"""A-08-T33 (ADR-078 independent AC tests; TASK-8087; SPEC-657 AC-0.7, AC-1.3; ADR-400 P-58):
the T09 GL journal-entry fields, written against the spec, not the implementation.

- The migration is expand-only: every statement adds nullable or constant-default columns and
  grants; nothing updates, deletes, drops, retypes or tightens an existing column.
- Each format's column map names each JE field at most once, never a column the format already
  reads for something else, and only formats whose export can carry the field map it.
- The unavailable path: a snapshot without the fields makes every criterion that needs them
  unavailable and names what is missing.
- No posting user or approver value reaches a log line, a parse error or a scoring error.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from abacus.modules.connections.gl_formats import GL_FORMATS, JE_FIELDS
from abacus.modules.connections.gl_parse import parse_gl_to_file, read_entries
from abacus.modules.ledger.api import JeFieldFacts
from abacus.modules.sampling.compute import je_scoring as js

_MIGRATION = Path(__file__).parents[3] / "migrations" / "versions" / "0888_gl_je_fields.py"
_POSTER = "zq-poster-77x1"  # a sentinel posting user: it must never appear in any output
_APPROVER = "zq-approver-55y2"
_FORBIDDEN_SQL = ("UPDATE ", "DELETE ", "DROP ", "TRUNCATE", " TYPE ", "SET NOT NULL", "RENAME")


def _statements(function: str) -> list[str]:
    tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
    body = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    out: list[str] = []
    for node in ast.walk(body):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "execute":
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append(arg.value)
            elif isinstance(arg, ast.JoinedStr):
                out.append(
                    "".join(
                        v.value
                        for v in arg.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)
                    )
                )
    return out


def test_the_upgrade_only_adds_and_grants() -> None:
    statements = _statements("upgrade")
    assert statements
    for sql in statements:
        upper = " ".join(sql.upper().split())
        assert not any(word in f" {upper} " for word in _FORBIDDEN_SQL), sql
        assert upper.startswith(("ALTER TABLE", "GRANT ")), sql
        if upper.startswith("ALTER TABLE"):
            for clause in upper.split("ADD COLUMN")[1:]:
                assert " NULL" in clause or "DEFAULT" in clause, clause


def test_every_new_column_is_nullable_or_defaults_to_unavailable() -> None:
    added = " ".join(_statements("upgrade")).upper()
    for field in JE_FIELDS:
        assert f"ADD COLUMN {field.upper()} " in added
    assert "JE_FIELDS_AVAILABLE TEXT[] NOT NULL DEFAULT '{}'" in " ".join(added.split())


def test_the_downgrade_drops_exactly_what_the_upgrade_added() -> None:
    dropped = " ".join(_statements("downgrade")).upper()
    for column in (*JE_FIELDS, "je_fields_available"):
        assert f"DROP COLUMN {column.upper()}" in dropped
    assert dropped.count("DROP COLUMN") == len(JE_FIELDS) + 1


@pytest.mark.parametrize("format_id", sorted(GL_FORMATS))
def test_each_format_maps_each_je_field_at_most_once_and_never_onto_a_base_column(
    format_id: str,
) -> None:
    fmt = GL_FORMATS[format_id]
    headers = fmt.je_headers
    assert set(headers) <= set(JE_FIELDS)
    assert len(set(headers.values())) == len(headers)  # one column, one field
    base = {
        fmt.date_header,
        fmt.kind_header,
        fmt.reference_header,
        fmt.counterparty_header,
        fmt.description_header,
        fmt.amount_header,
        fmt.debit_header,
        fmt.credit_header,
        fmt.balance_header,
        fmt.account_header,
        fmt.code_header,
    } - {None}
    assert not {h.casefold() for h in headers.values()} & {str(b).casefold() for b in base}


def test_at_least_one_format_carries_all_four_and_one_carries_none() -> None:
    carried = [set(f.je_headers) for f in GL_FORMATS.values()]
    assert set(JE_FIELDS) in carried
    assert set() in carried


def test_the_unavailable_path_names_what_is_missing() -> None:
    nothing = JeFieldFacts(snapshot_id=uuid.uuid4(), available=frozenset())
    assert nothing.missing(("posted_by", "source")) == ("posted_by", "source")
    usable, missing = js.available("manual_by_role", nothing.available)
    assert not usable and missing == ("posted_by", "source")
    for key in ("weekend_holiday", "round_amount", "post_close", "keywords"):
        assert js.available(key, nothing.available) == (True, ())  # need only what every GL has


def test_an_unavailable_criterion_hits_nothing_whatever_the_entries_say() -> None:
    entry = js.JeEntry(
        "JE-1", date(2026, 6, 27), Decimal("5000"), ("x",), posted_by=_POSTER, source="manual"
    )
    inputs = js.Inputs(
        criteria=(js.Criterion("manual_by_role", 40, {"role_class": "senior_management"}),),
        holidays=js.HolidaySet("none", frozenset()),
        period_end=date(2026, 6, 30),
        roles={_POSTER: "senior_management"},
        fields_available=frozenset(),
    )
    scored = js.score(inputs, [entry])
    assert scored.criteria[0].available is False and scored.criteria[0].hit_count == 0
    assert scored.scores[0].score == 0 and scored.scores[0].reason_codes == ()


def _export() -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    for line in (["Probe Co"], ["General Ledger"], ["Jul 2025 - Jun 2026"], []):
        w.writerow(line)
    w.writerow(
        [
            "Account",
            "Date",
            "Type",
            "Document Number",
            "Name",
            "Memo",
            "Debit",
            "Credit",
            "Created By",
            "Date Created",
            "Source",
            "Approved By",
        ]
    )
    for account, debit, credit in (
        ("2100 - Accrued", "", "250.00"),
        ("7100 - Interest", "250.00", ""),
    ):
        w.writerow(
            [
                account,
                "06/27/2026",
                "Journal",
                "JE-9",
                "",
                "Probe",
                debit,
                credit,
                _POSTER,
                "06/27/2026 10:00 AM",
                "Manual",
                _APPROVER,
            ]
        )
    return out.getvalue().encode("utf-8")


def test_no_posting_user_or_approver_value_reaches_a_log_or_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    out = tmp_path / "entries.csv"
    with capture_logs() as logs:
        summary = parse_gl_to_file(
            _export(), "netsuite_gl_csv", date(2025, 7, 1), date(2026, 6, 30), str(out)
        )
        entries = list(read_entries(str(out)))
        assert {e.posted_by for e in entries} == {_POSTER}
        inputs = js.Inputs(
            criteria=(
                js.Criterion("manual_by_role", 40, {"role_class": "senior_management"}),
                js.Criterion("round_amount", 10, {"unit": "not-a-number"}),
            ),
            holidays=js.HolidaySet("none", frozenset()),
            period_end=date(2026, 6, 30),
            roles={_POSTER: "senior_management"},
            fields_available=summary.je_fields_available,
        )
        engine = [
            js.JeEntry(
                "JE-9", date(2026, 6, 27), Decimal("250"), posted_by=_POSTER, source="manual"
            )
        ]
        with pytest.raises(js.InvalidCriteria) as refused:
            js.score(inputs, engine)
    seen = json.dumps(logs, default=str) + capsys.readouterr().out + capsys.readouterr().err
    seen += caplog.text + str(refused.value) + repr(refused.value)
    assert _POSTER not in seen and _APPROVER not in seen
