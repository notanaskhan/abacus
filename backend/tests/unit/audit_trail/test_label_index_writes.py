"""Security review L6 (G-02-T10, DEC-436): UOW-001 and UOW-002 exempt `audit_trail/labels.py`
so the label projection can commit without an audit event. The exemption is held to its
purpose: the file writes `audit_event_labels` and nothing else, with no raw SQL."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

SOURCE: Final = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "abacus"
    / "modules"
    / "audit_trail"
    / "labels.py"
)
_WRITES: Final = frozenset({"insert", "update", "delete"})


def _calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_l6_labels_writes_only_audit_event_labels() -> None:
    tree = ast.parse(SOURCE.read_text("utf-8"))
    writes = [c for c in _calls(tree) if _name(c.func) in _WRITES]
    assert writes, "the indexer's upsert is found"
    for call in writes:
        assert _name(call.func) == "insert", ast.unparse(call)
        assert [ast.unparse(a) for a in call.args] == ["AUDIT_EVENT_LABELS"], ast.unparse(call)
    tables = [
        c.args[0].value
        for c in _calls(tree)
        if _name(c.func) == "Table" and c.args and isinstance(c.args[0], ast.Constant)
    ]
    assert tables == ["audit_event_labels"]


def test_l6_labels_runs_no_raw_sql() -> None:
    tree = ast.parse(SOURCE.read_text("utf-8"))
    assert not [c for c in _calls(tree) if _name(c.func) == "text"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            head = node.value.lstrip().upper()
            assert not head.startswith(("INSERT", "UPDATE", "DELETE", "TRUNCATE")), node.value
