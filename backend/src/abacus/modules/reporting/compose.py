"""From a template version and a sealed snapshot to what the renderer and the compare read
(P-11-T11; P-11 §4.3, §4.4; C11 v1 §2; DEC-1561).

`render_input` builds the renderer's plain-data input: the version's body with each overridden
section's paragraphs put in place (marked `override`), the clause states and the clause library
from the snapshot, and the snapshot's values, which code formatted before they were sealed. No
value comes from the browser or a provider here: the snapshot is the only source.

`block_texts` reads the same composition as plain text per top-level block (a section or clause
by its id, any other block by its position) for the word diff: a variable reads its value, a
citation reads nothing, a disabled clause reads empty and an empty clause reads the library's
standard text. `word_diff` is `difflib` over whitespace-split words with `autojunk` off, so the
same inputs always give the same operations.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from abacus.modules.reporting.render.core import Mode, RenderInput

DiffOp = tuple[Literal["equal", "insert", "delete"], str]


@dataclass(frozen=True)
class Composition:
    layout_key: str
    blocks: list[object]
    values: Mapping[str, str]
    clause_states: Mapping[str, bool]
    library: Mapping[str, list[object]]


def _str_map(raw: object) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    items = cast(Mapping[object, object], raw).items()
    return {str(k): str(v) for k, v in items}


def _overrides(raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if isinstance(value, list):
            out[str(key)] = [str(p) for p in cast(list[object], value)]
    return out


def _with_overrides(blocks: Sequence[object], overrides: Mapping[str, list[str]]) -> list[object]:
    placed: list[object] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            placed.append(block)
            continue
        b = dict(cast(Mapping[str, object], block))
        inner = b.get("blocks")
        if b.get("type") == "section" and str(b.get("id")) in overrides:
            b["blocks"] = [
                {"type": "paragraph", "runs": [{"type": "text", "text": p}]}
                for p in overrides[str(b["id"])]
            ]
            b["override"] = True
        elif isinstance(inner, list):
            b["blocks"] = _with_overrides(cast(list[object], inner), overrides)
        placed.append(b)
    return placed


def _library(clauses: Sequence[object]) -> dict[str, list[object]]:
    library: dict[str, list[object]] = {}
    for clause in clauses:
        if isinstance(clause, Mapping):
            c = cast(Mapping[str, object], clause)
            standard = c.get("standard")
            library[str(c.get("clause_id"))] = (
                list(cast(list[object], standard)) if isinstance(standard, list) else []
            )
    return library


def compose(
    *,
    layout_key: str,
    body: Sequence[object],
    clauses: Sequence[object],
    snapshot: Mapping[str, object],
) -> Composition:
    """The version as sealed: overrides placed, the snapshot's clause states and values."""
    states = snapshot.get("clauses")
    clause_states = (
        {str(k): bool(v) for k, v in cast(Mapping[object, object], states).items()}
        if isinstance(states, Mapping)
        else {}
    )
    return Composition(
        layout_key=layout_key,
        blocks=_with_overrides(list(body), _overrides(snapshot.get("overrides"))),
        values=_str_map(snapshot.get("variables")),
        clause_states=clause_states,
        library=_library(clauses),
    )


def standard(
    *,
    layout_key: str,
    body: Sequence[object],
    clauses: Sequence[object],
    values: Mapping[str, str],
) -> Composition:
    """The template's standard text for the same values: default clause states, no override."""
    defaults: dict[str, bool] = {}
    for clause in clauses:
        if isinstance(clause, Mapping):
            c = cast(Mapping[str, object], clause)
            defaults[str(c.get("clause_id"))] = bool(c.get("default_enabled", True))
    return Composition(
        layout_key=layout_key,
        blocks=list(body),
        values=dict(values),
        clause_states=defaults,
        library=_library(clauses),
    )


def render_input(
    composition: Composition, *, title: str, as_of: datetime, mode: Mode, content_hash: str
) -> RenderInput:
    return RenderInput(
        layout_key=composition.layout_key,
        blocks=composition.blocks,
        values=composition.values,
        title=title,
        as_of=as_of,
        mode=mode,
        content_hash=content_hash,
        clause_states=composition.clause_states,
        library=composition.library,
    )


def _runs(runs: object, values: Mapping[str, str]) -> list[str]:
    out: list[str] = []
    if not isinstance(runs, list):
        return out
    for run in cast(list[object], runs):
        if not isinstance(run, Mapping):
            continue
        r = cast(Mapping[str, object], run)
        if r.get("type") == "text":
            out.append(str(r.get("text", "")))
        elif r.get("type") == "var":
            out.append(values.get(str(r.get("key")), ""))
    return out


def _text(block: object, c: Composition) -> list[str]:
    if not isinstance(block, Mapping):
        return []
    b = cast(Mapping[str, object], block)
    kind = b.get("type")
    if kind == "heading" or kind == "legend":
        return [str(b.get("text", ""))]
    if kind == "paragraph":
        return _runs(b.get("runs"), c.values)
    if kind == "list":
        items = b.get("items")
        return [w for item in cast(list[object], items or []) for w in _runs(item, c.values)]
    if kind == "table":
        cols = [str(x) for x in cast(list[object], b.get("columns") or [])]
        rows = cast(list[object], b.get("rows") or [])
        return cols + [str(cell) for row in rows for cell in cast(list[object], row)]
    if kind == "kv":
        out: list[str] = []
        for row in cast(list[object], b.get("rows") or []):
            r = cast(Mapping[str, object], row)
            out.append(str(r.get("key", "")))
            out.extend(_runs(r.get("value"), c.values))
        return out
    if kind == "signature_block":
        out = []
        for signer in cast(list[object], b.get("signers") or []):
            s = cast(Mapping[str, object], signer)
            out.append(str(s.get("label", "")))
            out.extend(_runs(s.get("name"), c.values))
        return out
    if kind == "enclosures":
        return [str(x) for x in cast(list[object], b.get("items") or [])]
    if kind == "section":
        inner = cast(list[object], b.get("blocks") or [])
        return [str(b.get("title", ""))] + [w for x in inner for w in _text(x, c)]
    if kind == "clause":
        clause_id = str(b.get("clause_id"))
        if not c.clause_states.get(clause_id, bool(b.get("enabled", True))):
            return []
        inner = cast(list[object], b.get("blocks") or []) or c.library.get(clause_id, [])
        return [w for x in inner for w in _text(x, c)]
    return []


def block_texts(c: Composition) -> list[tuple[str, str | None, str]]:
    """(block id, clause id, text) per top-level block, in order."""
    out: list[tuple[str, str | None, str]] = []
    blocks: list[object] = c.blocks
    for n, raw in enumerate(blocks):
        b: Mapping[str, object] = (
            cast(Mapping[str, object], raw) if isinstance(raw, Mapping) else {}
        )
        if b.get("type") == "section":
            block_id, clause_id = f"section:{b.get('id')}", None
        elif b.get("type") == "clause":
            block_id, clause_id = f"clause:{b.get('clause_id')}", str(b.get("clause_id"))
        else:
            block_id, clause_id = f"block:{n + 1}", None
        out.append((block_id, clause_id, " ".join(" ".join(_text(blocks[n], c)).split())))
    return out


def word_diff(before: str, after: str) -> list[DiffOp]:
    a, b = before.split(), after.split()
    ops: list[DiffOp] = []
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append(("equal", " ".join(a[i1:i2])))
            continue
        if i2 > i1:
            ops.append(("delete", " ".join(a[i1:i2])))
        if j2 > j1:
            ops.append(("insert", " ".join(b[j1:j2])))
    return ops


def compare(before: Composition, after: Composition) -> list[tuple[str, str | None, list[DiffOp]]]:
    """Block by block, matched on block id; a block only one side has diffs against empty."""
    left = {bid: (cid, t) for bid, cid, t in block_texts(before)}
    right = block_texts(after)
    seen: set[str] = set()
    out: list[tuple[str, str | None, list[DiffOp]]] = []
    for bid, cid, text in right:
        seen.add(bid)
        was = left.get(bid, (cid, ""))[1]
        out.append((bid, cid, word_diff(was, text)))
    for bid, (cid, text) in left.items():
        if bid not in seen:
            out.append((bid, cid, word_diff(text, "")))
    return out
