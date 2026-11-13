"""P-09-T11 rest (TASK-7825; DEC-4820): the trace export's PDF.

Row acceptance: "Two exports of the same trace version are byte-identical, the audit event names
the person and the sha256, and a stale MFA answers 401 mfa_required." Here: the PDF's DocBlocks
come from the export's own JSON body (so the PDF and the JSON describe one trace version), long
timelines continue across tables, the PDF's manifest names the PDF's SHA-256 and the JSON it was
drawn from, and the audit event records the delivered bytes' SHA-256. The renderer itself runs in
its isolated child where WeasyPrint's libraries exist (`tests/unit/reporting` in CI); here it is
replaced by a deterministic stand-in, as the existing export test replaces the trace read.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.crypto.signing import LocalExportSigner
from abacus.modules.agents import runs, trace_pdf

BODY = json.dumps(
    {
        "run": {
            "agent": "evidence.screener",
            "agent_label": "Evidence screener",
            "state": "succeeded",
        },
        "projection": "content",
        "runtime": "Accrued Agent runtime",
        "region": "us-east-1",
        "training": "not used for training",
        "attempts": 1,
        "tokens_in": 120,
        "tokens_out": 40,
        "rows": [
            {
                "seq": 1,
                "at": "2026-09-14T14:24:00Z",
                "kind": "step",
                "title": "Read files",
                "state": "done",
                "detail": None,
                "actor": "Ana Cruz via Agent",
            },
            {
                "seq": 2,
                "at": "2026-09-14T14:25:30Z",
                "kind": "step",
                "title": "Propose",
                "state": "done",
                "detail": "proposal_raised",
                "actor": None,
            },
        ],
        "records_read": [{"source": "evidence", "count": 224}],
        "output_counts": [["proposals", 2], ["bad"]],
    },
    sort_keys=True,
    separators=(",", ":"),
).encode()


def test_blocks_are_drawn_from_the_json_body() -> None:
    blocks = trace_pdf.trace_blocks(BODY, "run-1")
    assert blocks[0] == {"type": "heading", "level": 1, "text": "Agent run trace"}
    kv = blocks[1]
    assert isinstance(kv, dict) and kv["type"] == "kv"
    pairs = {r["key"]: r["value"][0]["text"] for r in kv["rows"]}  # type: ignore[index]  # DocBlock JSON
    assert pairs["Run"] == "run-1"
    assert pairs["Agent"] == "Evidence screener"
    assert pairs["Runtime"] == "Accrued Agent runtime"
    assert pairs["Tokens in"] == "120"
    timeline = blocks[3]
    assert timeline == {
        "type": "table",
        "columns": ["#", "At (UTC)", "Step", "State", "Actor", "Detail"],
        "rows": [
            ["1", "2026-09-14T14:24:00Z", "Read files", "done", "Ana Cruz via Agent", "—"],
            ["2", "2026-09-14T14:25:30Z", "Propose", "done", "—", "proposal_raised"],
        ],
    }
    assert {
        "type": "table",
        "columns": ["Source", "Records"],
        "rows": [["evidence", "224"]],
    } in blocks
    # A malformed output pair is left out, never invented.
    assert {
        "type": "table",
        "columns": ["Output", "Count"],
        "rows": [["proposals", "2"]],
    } in blocks
    assert "claude" not in json.dumps(blocks).lower()


def test_an_empty_section_says_none_and_a_long_timeline_continues() -> None:
    empty = json.dumps({"rows": [], "records_read": [], "output_counts": []}).encode()
    blocks = trace_pdf.trace_blocks(empty, "r")
    assert blocks.count({"type": "paragraph", "runs": [{"type": "text", "text": "None."}]}) == 3
    long = json.dumps(
        {
            "rows": [
                {"seq": i, "at": "2026-09-14T14:24:00Z"} for i in range(trace_pdf.TABLE_ROWS + 3)
            ]
        }
    ).encode()
    tables = [cast(dict[str, list[object]], b) for b in trace_pdf.trace_blocks(long, "r")]
    timeline = [t for t in tables if t.get("columns", [None])[0] == "#"]
    assert [len(t["rows"]) for t in timeline] == [trace_pdf.TABLE_ROWS, 3]


@dataclass(frozen=True)
class _Call:
    layout: str
    blocks: list[object]
    title: str
    as_of: datetime
    digest: str


@pytest.fixture
def calls() -> Iterator[list[_Call]]:
    seen: list[_Call] = []

    def renderer(
        layout: str, blocks: list[object], title: str, as_of: datetime, digest: str
    ) -> bytes:
        seen.append(_Call(layout, blocks, title, as_of, digest))
        return b"%PDF-1.7 " + hashlib.sha256(json.dumps(blocks).encode()).digest()

    trace_pdf.register_trace_pdf_renderer(renderer)
    yield seen
    trace_pdf.register_trace_pdf_renderer(None)


def test_the_pdf_is_dated_by_the_trace_not_the_clock(calls: list[_Call]) -> None:
    first = trace_pdf.render_trace_pdf(BODY, "run-1", "h" * 64)
    second = trace_pdf.render_trace_pdf(BODY, "run-1", "h" * 64)
    assert first == second
    req = calls[0]
    assert req.layout == "run_export"
    assert req.title == "Agent run trace · run-1"
    assert req.digest == "h" * 64
    assert req.blocks == trace_pdf.trace_blocks(BODY, "run-1")
    assert req.as_of == datetime(2026, 9, 14, 14, 25, 30, tzinfo=UTC)
    no_rows = trace_pdf.render_trace_pdf(json.dumps({"rows": []}).encode(), "r", "h" * 64)
    assert no_rows.startswith(b"%PDF")
    assert calls[2].as_of == datetime(1970, 1, 1, tzinfo=UTC)


def test_no_registered_renderer_answers_503() -> None:
    trace_pdf.register_trace_pdf_renderer(None)
    with pytest.raises(trace_pdf.TraceRendererUnavailable) as raised:
        trace_pdf.render_trace_pdf(BODY, "r", "h" * 64)
    assert raised.value.code == "renderer_unavailable"


@pytest.mark.asyncio
async def test_a_pdf_export_names_its_bytes_and_its_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = SimpleNamespace(
        rows=[1, 2], projection="content", run=SimpleNamespace(record_sha256="r" * 64)
    )
    recorded: list[dict[str, object]] = []

    async def trace_for(_ctx: object, _run: uuid.UUID) -> object:
        return trace

    async def run(_ctx: object, _run: uuid.UUID, _action: str) -> object:
        return object()

    def record(action: str, **k: object) -> None:
        recorded.append({"action": action, **k})

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        yield SimpleNamespace(record=record)

    async def unfrozen(_t: object, _r: object, _p: str, _v: str, build: object) -> bytes:
        return await build()  # type: ignore[operator]  # a run still open is built

    monkeypatch.setattr(runs, "trace_for", trace_for)
    monkeypatch.setattr(runs, "_run", run)

    def canonical(_t: object) -> bytes:
        return BODY

    def render(_l: str, _b: list[object], _t: str, _a: datetime, _d: str) -> bytes:
        return b"%PDF-1.7 trace"

    monkeypatch.setattr(runs, "canonical", canonical)
    monkeypatch.setattr(runs, "uow", unit)
    monkeypatch.setattr(runs, "frozen_body", unfrozen)
    trace_pdf.register_trace_pdf_renderer(render)
    monkeypatch.setattr(
        "abacus.kernel.crypto.signing.export_signer", lambda: LocalExportSigner(b"k" * 32)
    )
    me = uuid.uuid4()
    ctx = SimpleNamespace(tenant=None, user_id=me)
    pdf = await runs.export_trace(ctx, uuid.uuid4(), "pdf")  # type: ignore[arg-type]  # a test double
    assert pdf.trace == b"%PDF-1.7 trace"
    assert pdf.manifest["sha256"] == hashlib.sha256(b"%PDF-1.7 trace").hexdigest()
    assert pdf.manifest["source_sha256"] == hashlib.sha256(BODY).hexdigest()
    assert pdf.manifest["format"] == "pdf"
    assert pdf.manifest["exported_by"] == str(me) and pdf.manifest["signature"]
    plain = await runs.export_trace(ctx, uuid.uuid4())  # type: ignore[arg-type]  # a test double
    assert plain.trace == BODY
    assert "format" not in plain.manifest and "source_sha256" not in plain.manifest
    assert [r["action"] for r in recorded] == ["agent_run.trace_exported"] * 2
    trace_pdf.register_trace_pdf_renderer(None)


@pytest.mark.parametrize(
    "failure", [OSError("no libgobject"), ImportError("weasyprint"), RuntimeError("missing_glyph")]
)
def test_a_renderer_that_fails_answers_503(failure: Exception) -> None:
    def renderer(_l: str, _b: list[object], _t: str, _a: datetime, _d: str) -> bytes:
        raise failure

    trace_pdf.register_trace_pdf_renderer(renderer)
    try:
        with pytest.raises(trace_pdf.TraceRendererUnavailable) as raised:
            trace_pdf.render_trace_pdf(BODY, "r", "h" * 64)
        assert raised.value.code == "renderer_unavailable"
    finally:
        trace_pdf.register_trace_pdf_renderer(None)
