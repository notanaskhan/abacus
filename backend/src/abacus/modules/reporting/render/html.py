"""DocBlocks to HTML through a code-owned layout (P-11-T07; P-11 §4.4; ADR-320 §2; SPEC-520 AC-7
to AC-12).

The input is the closed DocBlock union (`contract.py`), already validated, and a map of variable
values the kind's provider resolved from the database (P-11-T08): a consumer never passes values
from a browser. Every text node and every value goes through `text.literal` (AC-8). A declared
variable with no value refuses the whole render with `missing_variable` and its keys (AC-10): a
document never prints a blank, a placeholder or "undefined".

Clauses: a `clause` block prints when its state is enabled (`clause_states` wins over the block's
own `enabled`), and an empty clause block prints its library standard. Tables print the decimal
strings they carry; nothing sums (ADR-050). A `cite` run prints a numbered marker only; an image
prints only an `asset:` reference the fetcher resolves from the in-memory map (AC-9).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from abacus.modules.reporting.contract import (
    ClauseBlock,
    DocBlock,
    EnclosuresBlock,
    HeadingBlock,
    ImageBlock,
    KvBlock,
    LegendBlock,
    ListBlock,
    PageBreakBlock,
    ParagraphBlock,
    Run,
    SectionBlock,
    SignatureBlock,
    TableBlock,
    TextRun,
    VarRun,
)
from abacus.modules.reporting.render.head import RenderRefused, dated_head
from abacus.modules.reporting.render.layouts import Layout, Mark
from abacus.modules.reporting.render.text import literal

_NUMBER: Final = frozenset("0123456789,.-() ")


class MissingVariable(RenderRefused):
    """422 `missing_variable {keys}` (AC-10)."""

    def __init__(self, keys: Sequence[str]) -> None:
        super().__init__("missing_variable")
        self.keys = tuple(sorted(set(keys)))


@dataclass(frozen=True)
class Letterhead:
    """The firm's mark: its name and address lines (no colour; T10 avoids coloured letterheads)."""

    firm: str
    address: tuple[str, ...] = ()
    mark_asset: str | None = None  # `firm/<evidence version>.png` in the asset map


@dataclass
class _State:
    values: Mapping[str, str]
    clause_states: Mapping[str, bool]
    library: Mapping[str, Sequence[DocBlock]]
    missing: list[str] = field(default_factory=list[str])
    texts: list[str] = field(default_factory=list[str])
    legends: list[str] = field(default_factory=list[str])
    citations: dict[str, int] = field(default_factory=dict[str, int])


def _numeric(cell: str) -> bool:
    if not cell or not set(cell) <= _NUMBER:
        return False
    try:
        Decimal(cell.replace(",", "").replace("(", "-").replace(")", ""))
    except InvalidOperation:
        return False
    return True


def _text(state: _State, value: str) -> str:
    state.texts.append(value)
    return literal(value)


def _runs(state: _State, runs: Sequence[Run]) -> str:
    out: list[str] = []
    for run in runs:
        if isinstance(run, TextRun):
            out.append(_text(state, run.text))
        elif isinstance(run, VarRun):
            value = state.values.get(run.key)
            if value is None:
                state.missing.append(run.key)
                continue
            state.texts.append(value)
            out.append(
                f"<span class='var' data-field='{run.key}'>{literal(value, isolate=True)}</span>"
            )
        else:  # a CiteRun
            n = state.citations.setdefault(str(run.citation_id), len(state.citations) + 1)
            out.append(f"<sup class='cite' data-citation='{run.citation_id}'>[{n}]</sup>")
    return "".join(out)


def _blocks(state: _State, blocks: Sequence[DocBlock], *, top: bool = False) -> str:
    return "".join(_block(state, b, top=top) for b in blocks)


def _block(state: _State, block: DocBlock, *, top: bool) -> str:
    match block:
        case SectionBlock():
            cls = "section top" if top else "section"
            title = f"<h2>{_text(state, block.title)}</h2>" if block.title else ""
            inner = _blocks(state, block.blocks)
            return f"<section class='{cls}' id='s-{block.id}'>{title}{inner}</section>"
        case HeadingBlock():
            level = min(block.level + 1, 4) if block.level > 1 else 1
            return f"<h{level}>{_text(state, block.text)}</h{level}>"
        case ParagraphBlock():
            return f"<p>{_runs(state, block.runs)}</p>"
        case ClauseBlock():
            enabled = state.clause_states.get(block.clause_id, block.enabled)
            if not enabled:
                return ""
            inner = block.blocks or list(state.library.get(block.clause_id, ()))
            return f"<div class='clause' id='c-{block.clause_id}'>{_blocks(state, inner)}</div>"
        case ListBlock():
            tag = "ol" if block.ordered else "ul"
            items = "".join(f"<li>{_runs(state, item)}</li>" for item in block.items)
            return f"<{tag}>{items}</{tag}>"
        case TableBlock():
            head = "".join(f"<th>{_text(state, c)}</th>" for c in block.columns)
            rows = "".join(
                "<tr>"
                + "".join(
                    f"<td{' class="n"' if _numeric(cell) else ''}>{_text(state, cell)}</td>"
                    for cell in row
                )
                + "</tr>"
                for row in block.rows
            )
            return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
        case KvBlock():
            rows = "".join(
                f"<div><dt>{_text(state, r.key)}</dt><dd>{_runs(state, r.value)}</dd></div>"
                for r in block.rows
            )
            return f"<dl class='kv'>{rows}</dl>"
        case SignatureBlock():
            signers = "".join(
                "<div class='signer'><div class='line'></div>"
                f"<div class='who'>{_runs(state, s.name)}</div>"
                f"<div>{_text(state, s.label)}</div></div>"
                for s in block.signers
            )
            return f"<div class='signature'>{signers}</div>"
        case LegendBlock():
            state.legends.append(block.text)
            state.texts.append(block.text)
            return ""
        case ImageBlock():
            return f"<img class='image' src='asset:firm/{block.asset_id}.png' alt=''>"
        case EnclosuresBlock():
            items = "".join(f"<li>{_text(state, i)}</li>" for i in block.items)
            return f"<div class='enclosures'><p>Enclosures</p><ul>{items}</ul></div>"
        case PageBreakBlock():
            return "<div class='page-break'></div>"
    return ""


@dataclass(frozen=True)
class Html:
    document: str
    texts: tuple[str, ...]
    citations: tuple[str, ...]


def document_html(
    layout: Layout,
    blocks: Sequence[DocBlock],
    values: Mapping[str, str],
    *,
    title: str,
    as_of: datetime,
    mark: Mark | None,
    clause_states: Mapping[str, bool] | None = None,
    library: Mapping[str, Sequence[DocBlock]] | None = None,
    letterhead: Letterhead | None = None,
) -> Html:
    """The complete HTML document; raises `MissingVariable` with every missing key."""
    state = _State(values, clause_states or {}, library or {})
    body = _blocks(state, blocks, top=layout.flow == "fixed")
    if state.missing:
        raise MissingVariable(state.missing)
    parts = [
        "<!DOCTYPE html><html lang='en'><head>",
        dated_head(literal(title), as_of),
        "</head><body>",
    ]
    if mark is not None:
        parts.append(f"<div class='watermark' aria-hidden='true'>{mark}</div>")
    if state.legends:
        legend = " ".join(literal(t) for t in state.legends)
        parts.append(f"<div class='legend'>{legend}</div>")
    if layout.letterhead and letterhead is not None:
        state.texts.append(letterhead.firm)
        state.texts.extend(letterhead.address)
        mark_img = (
            f"<img class='mark' src='asset:{letterhead.mark_asset}' alt=''>"
            if letterhead.mark_asset
            else ""
        )
        lines = "".join(f"<div class='address'>{literal(a)}</div>" for a in letterhead.address)
        parts.append(
            f"<div class='letterhead'>{mark_img}<div class='firm'>{literal(letterhead.firm)}</div>"
            f"{lines}</div>"
        )
    parts.append(body)
    parts.append("</body></html>")
    return Html("".join(parts), tuple(state.texts), tuple(state.citations))
