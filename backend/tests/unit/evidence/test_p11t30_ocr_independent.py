"""P-11-T30 (ADR-078): OCR's refusals, written outside the implementing session. The gate refuses
in order and fails closed (kill switch, flag, terms, boundary, Sec. 7216), retry is a person's
alone, and no log call carries page text or a TIN."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.modules.evidence import ocr_gate, ocr_reads, ocr_step
from abacus.modules.identity.api import AuthContext, Forbidden

TENANT = SimpleNamespace(tenant_id=uuid4())
OPEN = ocr_gate.GateFacts(synthetic_firm=False, tri_scope=True, tri_consented=True)
ENTRY = SimpleNamespace(ai_services_opt_out=True, tri_basis=False)


def _world(
    monkeypatch: pytest.MonkeyPatch,
    *,
    killed: bool = False,
    flag: bool = True,
    entry: object | None = ENTRY,
) -> None:
    async def control(*_a: object, **_k: object) -> bool:
        return killed

    async def enabled(*_a: object) -> bool:
        return flag

    async def today(*_a: object) -> object:
        return None

    monkeypatch.setattr(ocr_gate, "control_active", control)
    monkeypatch.setattr(ocr_gate, "flag_enabled", enabled)
    monkeypatch.setattr(ocr_gate, "today", today)
    monkeypatch.setattr(ocr_gate, "covering", lambda *_a: entry)


async def _refusal(facts: ocr_gate.GateFacts = OPEN) -> object:
    return await ocr_gate.first_refusal(cast(ocr_gate.TenantContext, TENANT), facts)


async def test_nothing_held_against_it_is_no_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch)
    assert await _refusal() is None


async def test_the_kill_switch_refuses_ahead_of_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _world(monkeypatch, killed=True, flag=False, entry=None)
    assert await _refusal() == "kill_switch"


async def test_the_flag_off_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, flag=False, entry=None)
    assert await _refusal() == "flag_off"


async def test_no_terms_entry_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, entry=None)
    assert await _refusal() == "terms_not_covering"


async def test_a_real_firm_without_the_opt_out_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, entry=SimpleNamespace(ai_services_opt_out=False, tri_basis=True))
    assert await _refusal() == "boundary_basis"


async def test_tri_without_consent_or_a_basis_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch)
    assert await _refusal(replace(OPEN, tri_consented=False)) == "consent_missing"


def test_every_gate_refusal_has_a_contract_word() -> None:
    assert set(ocr_step.REFUSAL_WORDS) >= {
        "kill_switch",
        "flag_off",
        "terms_not_covering",
        "boundary_basis",
        "consent_missing",
    }


@pytest.mark.parametrize("kind", ["agent", "system", "support"])
async def test_retry_is_a_persons_alone(kind: str) -> None:
    ctx = cast(AuthContext, SimpleNamespace(tenant=SimpleNamespace(actor_kind=kind)))
    with pytest.raises(Forbidden):
        await ocr_reads.retry_text(ctx, uuid4())


@pytest.mark.parametrize("module", [ocr_step, ocr_reads, ocr_gate])
def test_no_log_call_names_page_text(module: object) -> None:
    source = Path(cast(str, getattr(module, "__file__"))).read_text()  # noqa: B009
    banned = {"text", "words", "value", "value_text", "tin", "last4", "page_text"}
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "_log"
        ):
            assert not banned & {k.arg for k in node.keywords if k.arg}
