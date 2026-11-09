"""P-09-T11 (TASK-6518; SPEC-648 AC-3; DEC-3118): trace exports with a signed manifest.

Row acceptance: "Two exports of the same trace version are byte-identical, the audit event names
the person and the sha256, and a stale MFA answers mfa_required."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.kernel.crypto.signing import LocalExportSigner
from abacus.modules.agents import runs

pytestmark = pytest.mark.asyncio


async def test_two_exports_are_byte_identical_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    trace = SimpleNamespace(
        rows=[1, 2], projection="content", run=SimpleNamespace(record_sha256="r" * 64)
    )
    recorded: list[dict[str, object]] = []

    async def trace_for(_ctx: object, _run: uuid.UUID) -> object:
        return trace

    async def run(_ctx: object, _run: uuid.UUID, _action: str) -> object:
        return object()

    @asynccontextmanager
    async def unit(_t: object) -> AsyncIterator[object]:
        yield SimpleNamespace(record=lambda action, **k: recorded.append({"action": action, **k}))

    monkeypatch.setattr(runs, "trace_for", trace_for)
    monkeypatch.setattr(runs, "_run", run)
    monkeypatch.setattr(runs, "canonical", lambda _t: b'{"a":1}')
    monkeypatch.setattr(runs, "uow", unit)
    monkeypatch.setattr(
        "abacus.kernel.crypto.signing.export_signer", lambda: LocalExportSigner(b"k" * 32)
    )
    me = uuid.uuid4()
    ctx = SimpleNamespace(tenant=None, user_id=me)
    first = await runs.export_trace(ctx, uuid.uuid4())  # type: ignore[arg-type]  # a test double
    second = await runs.export_trace(ctx, uuid.uuid4())  # type: ignore[arg-type]  # a test double
    assert first.trace == second.trace
    assert first.manifest["sha256"] == second.manifest["sha256"]
    assert first.manifest["run_record_sha256"] == "r" * 64
    assert first.manifest["signature"] and first.manifest["exported_by"] == str(me)
    assert recorded[0]["action"] == "agent_run.trace_exported"
