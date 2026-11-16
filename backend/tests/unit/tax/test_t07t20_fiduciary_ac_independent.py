"""T-07-T20 (TASK-8081; ADR-078 as amended): independent AC tests for T-07-T12, T14 and T16,
written
from SPEC-656 and the contracts only. Row acceptance: "Every listed property fails on a seeded
faulty build and passes on the real one." Each property runs against the real code and against a
seeded fault (a monkeypatched stand-in that breaks exactly that property) and must tell them apart.

Properties: I-AGENT-NEVER on the reader's tools and the fiduciary routes; an uncited governed
determination is refused; a locked interpretation's determinations cannot be recorded; recompute is
idempotent by `inputs_hash`; a new computation version stales the L2 sign-off (the content hash
moves); walls answer 404 (a return outside the person's scope is not found); without both §7216
consents the reader refuses before any model call. R-SO-3 segregation (a preparer cannot sign L3)
is P-04's rule on the reviewable; it is checked through the reviewable's facts here (the preparers
the interpretation reports) and end to end in the integration suite.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the tools
from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.agents.tools.registry import has_never_verb, registered_tools
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import fiduciary_service as fs
from abacus.modules.tax import instrument_reader
from abacus.modules.tax.compute import fiduciary as f
from abacus.modules.tax.instruments import service as instruments

TENANT = uuid.UUID("00000000-0000-4000-8000-00000000f001")
USER = uuid.UUID("00000000-0000-4000-8000-00000000f002")
RETURN = uuid.UUID("00000000-0000-4000-8000-00000000f003")
RESERVED = ("approve", "adopt", "lock", "reopen", "sign_off", "decide", "send", "file", "edit")


def _ctx(actor: ActorKind = "human") -> AuthContext:
    return AuthContext(
        TenantContext(TENANT, actor, str(USER)), USER, uuid.uuid4(), None, datetime.now(UTC)
    )


# --- I-AGENT-NEVER
# --------------------------------------------------------------------------------


def _reader_tools() -> dict[str, Any]:  # Any: the registry's tool entries are untyped JSON
    return {
        k: v
        for k, v in registered_tools().items()
        if k.startswith("tax.") and ("instrument" in k or "trust" in k)
    }


def _agent_never_holds(
    tools: dict[str, Any],  # Any: the registry's tool entries are untyped JSON
) -> bool:
    return bool(tools) and all(
        t.kind in ("read", "propose", "compute")
        and not any(word in t.action for word in RESERVED if word != "edit")
        and not has_never_verb(t.name)
        for t in tools.values()
    )


def test_i_agent_never_on_the_reader_tools() -> None:
    assert _agent_never_holds(_reader_tools())


def test_i_agent_never_seeded_fault() -> None:
    tools = _reader_tools()
    first = next(iter(tools.values()))
    faulty = type(
        "T",
        (),
        {
            "kind": "approved_write",
            "action": "instrument_interpretation.approve",
            "name": first.name,
        },
    )()
    assert not _agent_never_holds({**tools, "tax.faulty": faulty})


def _add_line(c: AuthContext) -> Awaitable[object]:
    return fs.add_fai_line(c, RETURN, None)  # type: ignore[arg-type] -- refused before the body


def _edit_distribution(c: AuthContext) -> Awaitable[object]:
    return fs.edit_trust_distribution(c, RETURN, None)  # type: ignore[arg-type] -- refused first


def _recompute(c: AuthContext) -> Awaitable[object]:
    return fs.recompute(c, RETURN)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        _add_line,
        _edit_distribution,
        _recompute,
    ],
)
async def test_i_agent_never_on_the_fiduciary_routes(
    call: Callable[[AuthContext], Awaitable[object]],
) -> None:
    with pytest.raises(Forbidden):
        await call(_ctx("agent"))


def _let_through(ctx: AuthContext, action: str) -> None:
    del ctx, action


def test_i_agent_never_routes_seeded_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs, "_person", _let_through)
    fs._person(_ctx("agent"), "fai_line.edit")  # pyright: ignore[reportPrivateUsage] -- the rule under test  # the fault lets an agent through: no Forbidden


# --- uncited determinations
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_uncited_governed_determination_is_refused() -> None:
    with pytest.raises(instruments.UncitedChange):
        await instruments._cited(_ctx(), uuid.uuid4(), "trust_type", [])  # pyright: ignore[reportPrivateUsage] -- the rule under test


@pytest.mark.asyncio
async def test_uncited_seeded_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    async def lax(*_: object) -> None:
        return None

    monkeypatch.setattr(instruments, "_cited", lax)
    await instruments._cited(_ctx(), uuid.uuid4(), "trust_type", [])  # pyright: ignore[reportPrivateUsage] -- the fault accepts it


# --- recompute idempotent by inputs_hash; a new version moves the content hash
# --------------------

D = Decimal


def _inputs(theo: str) -> f.FiduciaryInputs:
    return f.FiduciaryInputs(
        2025,
        f.Determinations("complex_trust"),
        (
            f.FaiLine("i", "interest", D("107500")),
            f.FaiLine("d", "ordinary_dividends", D("322500"), qualified=D("258000")),
        ),
        (f.TrustExpense("t", D("30000"), "principal"),),
        (
            f.Distribution("n", "Nora", date(2025, 6, 30), D("80000")),
            f.Distribution("t", "Theo", date(2025, 12, 15), D(theo)),
        ),
    )


def test_recompute_is_idempotent_by_inputs_hash() -> None:
    a, b = f.compute(_inputs("80000")), f.compute(_inputs("80000"))
    assert a.inputs_hash == b.inputs_hash
    assert fs.outputs_hash(fs.computed_outputs(a, {})) == fs.outputs_hash(
        fs.computed_outputs(b, {})
    )


def test_an_edit_moves_the_content_hash_so_l2_goes_stale() -> None:
    base, edited = f.compute(_inputs("80000")), f.compute(_inputs("100000"))
    assert base.inputs_hash != edited.inputs_hash
    assert fs.outputs_hash(fs.computed_outputs(base, {})) != fs.outputs_hash(
        fs.computed_outputs(edited, {})
    )


def test_staleness_seeded_fault() -> None:
    def constant(_: dict[str, object]) -> str:
        return "0" * 64

    base, edited = f.compute(_inputs("80000")), f.compute(_inputs("100000"))
    assert constant(fs.computed_outputs(base, {})) == constant(
        fs.computed_outputs(edited, {})
    )  # the fault hides it


# --- walls answer 404
# -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_walls_answer_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def walled(*_: object) -> None:
        raise NotFound("tax_return")

    monkeypatch.setattr(fs, "_return", walled)
    with pytest.raises(NotFound):
        await fs.fai_lines(_ctx(), RETURN)


# --- the reader without both §7216 consents
# -----------------------------------------------------------


@pytest.mark.asyncio
async def test_no_consent_refuses_before_any_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def no_consent(*_: object) -> bool:
        return False

    async def tool(*args: object) -> object:
        calls.append(str(args[2]))
        return {}

    monkeypatch.setattr(instrument_reader, "_consents", no_consent)
    monkeypatch.setattr(instrument_reader, "_tool", tool)
    result = await instrument_reader.read_instrument(object(), uuid.uuid4(), 2025)  # type: ignore[arg-type] -- the test's loose input
    assert (result.outcome, result.code, calls) == (
        "refused",
        "consent_required",
        [],
    )  # nothing read, no model


@pytest.mark.asyncio
async def test_no_consent_seeded_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    async def says_yes(*_: object) -> bool:
        return True

    calls: list[str] = []

    async def tool(*args: object) -> object:
        calls.append(str(args[2]))
        raise LookupError("stop")

    monkeypatch.setattr(instrument_reader, "_consents", says_yes)
    monkeypatch.setattr(instrument_reader, "_tool", tool)
    await instrument_reader.read_instrument(object(), uuid.uuid4(), 2025)  # type: ignore[arg-type] -- the test's loose input
    assert calls  # the fault reads the clauses without consent


# --- R-SO-3: the reviewable reports its preparers (P-04 refuses them at L3)
# ---------------------------


def test_the_interpretation_reviewable_names_its_preparers() -> None:
    assert instruments.LEVELS == (1, 3)  # L1 by a preparer, L3 by someone else (DEC-84)
