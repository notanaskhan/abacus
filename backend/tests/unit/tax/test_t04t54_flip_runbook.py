"""T-04-T54 (TASK-7527): the M17 tax workspace flip runbook names its three flags in order, the
rollback (flags off; data persists; CCH stays authoritative), the consent and clearance condition
on `tax_agents.enabled`, and the registry-only renewal; the flags exist in the registry."""

from __future__ import annotations

from pathlib import Path

from abacus.kernel._flags import FLAGS

RUNBOOK = Path(__file__).resolve().parents[4] / "docs" / "runbooks" / "tax-workspace-flip.md"
FLAG_ORDER = ("tax.individual_workpapers", "tax.review_workspace", "tax_agents.enabled")


def test_the_runbook_names_the_flags_in_order() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    positions = [text.index(f"`{flag}`") for flag in FLAG_ORDER]
    assert positions == sorted(positions)
    for flag in FLAG_ORDER:
        assert flag in FLAGS, flag


def test_the_rollback_keeps_data_and_cch_authoritative() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for phrase in ("**Data persists**", "**CCH stays authoritative**", "reverse order"):
        assert phrase in text, phrase


def test_agents_flip_only_for_cleared_capabilities_with_consents() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "only for capabilities cleared on a signed Bedrock" in text
    assert "§7216 consents" in text
    assert "registry-only" in text and "Mon Jul 24, 2028" in text
