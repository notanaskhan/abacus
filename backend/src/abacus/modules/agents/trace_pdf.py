"""The trace export's PDF (P-09-T11 rest; TASK-7825; DEC-4820).

The PDF is drawn from the export's own canonical JSON body (the frozen bytes when the run is a
v2 run that has ended), never from a second read, so the PDF and the JSON always describe the
same trace version. C11's code-owned `run_export` layout renders it in the renderer's isolated
child: no clock, no locale, no system font, so two exports of the same trace version are the same
bytes. The content hash that names the PDF is the JSON body's SHA-256. agents may not import
reporting (ADR-008), so the composition root (`abacus.api.app`) registers the renderer here
(`register_trace_pdf_renderer`), as it gives evidence its audit-trail reader.

What it shows is what the JSON holds, in the caller's projection: the runtime label, region and
training from the provider-terms register, the counts, the timeline rows (code words only), the
records read by source and the output counts. Never a model family (the runtime label is
"Accrued Agent runtime"); a metadata projection already lacks the content.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, cast

from abacus.kernel.errors import DomainUnavailable
from abacus.kernel.logging import get_logger

LAYOUT: Final = "run_export"
TABLE_ROWS: Final = 500  # C11's TableBlock holds at most 500 rows: longer timelines continue
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)

Json = dict[str, object]
_log = get_logger(__name__)


# (layout key, DocBlocks, title, as of, content hash) -> the PDF's bytes; raises when it cannot.
TracePdfRenderer = Callable[[str, list[object], str, datetime, str], bytes]
_renderer: TracePdfRenderer | None = None


def register_trace_pdf_renderer(renderer: TracePdfRenderer | None) -> None:
    """The composition root's C11 renderer (None unregisters, for tests)."""
    global _renderer
    _renderer = renderer


class TraceRendererUnavailable(DomainUnavailable):
    """The renderer could not produce the trace's PDF (C11's answer): export the JSON."""

    code = "renderer_unavailable"


def _text(value: object) -> dict[str, object]:
    return {"type": "text", "text": "—" if value is None or value == "" else str(value)}


def _kv(rows: list[tuple[str, object]]) -> dict[str, object]:
    return {"type": "kv", "rows": [{"key": k, "value": [_text(v)]} for k, v in rows]}


def _tables(columns: list[str], rows: list[list[str]]) -> list[object]:
    if not rows:
        return [{"type": "paragraph", "runs": [_text("None.")]}]
    return [
        {"type": "table", "columns": columns, "rows": rows[i : i + TABLE_ROWS]}
        for i in range(0, len(rows), TABLE_ROWS)
    ]


def _dict(value: object) -> Json:
    return cast(Json, value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def trace_blocks(body: bytes, run_id: str) -> list[object]:
    """The PDF's DocBlocks from the export's canonical JSON body."""
    trace = cast(Json, json.loads(body))
    run = _dict(trace.get("run"))
    blocks: list[object] = [
        {"type": "heading", "level": 1, "text": "Agent run trace"},
        _kv(
            [
                ("Run", run_id),
                ("Agent", run.get("agent_label") or run.get("agent")),
                ("State", run.get("state")),
                ("Projection", trace.get("projection")),
                ("Runtime", trace.get("runtime")),
                ("Region", trace.get("region")),
                ("Training", trace.get("training")),
                ("Attempts", trace.get("attempts")),
                ("Tokens in", trace.get("tokens_in")),
                ("Tokens out", trace.get("tokens_out")),
            ]
        ),
        {"type": "heading", "level": 2, "text": "Timeline"},
    ]
    rows = [_dict(r) for r in _list(trace.get("rows"))]
    blocks += _tables(
        ["#", "At (UTC)", "Step", "State", "Actor", "Detail"],
        [
            [
                str(r.get("seq", "")),
                str(r.get("at", "")),
                str(r.get("title", "")),
                str(r.get("state", "")),
                str(r.get("actor") or "—"),
                str(r.get("detail") or "—"),
            ]
            for r in rows
        ],
    )
    blocks.append({"type": "heading", "level": 2, "text": "Records read"})
    read = [_dict(r) for r in _list(trace.get("records_read"))]
    blocks += _tables(
        ["Source", "Records"], [[str(r.get("source", "")), str(r.get("count", ""))] for r in read]
    )
    blocks.append({"type": "heading", "level": 2, "text": "Outputs"})
    outputs = [_list(o) for o in _list(trace.get("output_counts"))]
    blocks += _tables(
        ["Output", "Count"], [[str(o[0]), str(o[1])] for o in outputs if len(o) == 2]
    )
    return blocks


def _as_of(body: bytes) -> datetime:
    """The trace's own last instant (its newest row), never the clock: the same bytes each time."""
    rows = [_dict(r) for r in _list(cast(Json, json.loads(body)).get("rows"))]
    instants = [str(r["at"]) for r in rows if isinstance(r.get("at"), str)]
    if not instants:
        return _EPOCH
    return datetime.fromisoformat(max(instants).replace("Z", "+00:00"))


def render_trace_pdf(body: bytes, run_id: str, content_hash: str) -> bytes:
    """The PDF, from the isolated renderer. Any refusal, or a host without the renderer's
    libraries, is C11's 503 `renderer_unavailable` (the refusal's own code is logged, never the
    trace); nothing is cached or stored here."""
    if _renderer is None:
        _log.warning("agent_run.trace_pdf_refused", error="no_renderer")
        raise TraceRendererUnavailable("the trace PDF could not be rendered")
    try:
        return _renderer(
            LAYOUT,
            trace_blocks(body, run_id),
            f"Agent run trace · {run_id}",
            _as_of(body),
            content_hash,
        )
    except Exception as exc:  # a refusal, a crash in the child or missing libraries: all 503
        _log.warning("agent_run.trace_pdf_refused", error=type(exc).__name__)
        raise TraceRendererUnavailable("the trace PDF could not be rendered") from None


__all__ = [
    "LAYOUT",
    "TABLE_ROWS",
    "TracePdfRenderer",
    "TraceRendererUnavailable",
    "register_trace_pdf_renderer",
    "render_trace_pdf",
    "trace_blocks",
]
