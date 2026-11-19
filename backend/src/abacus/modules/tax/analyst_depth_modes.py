"""`tax.return_analyst` depth modes (T-06-T27; TASK-8722; T-06 §6; SPEC-702; ADR-005, ADR-050;
DEC-5716). Red zone (an agent path).

Four modes over the entity-depth screens, each declared once here with its prompt, its tools and
the one write it may make:

- `asset_evidence` (TXP-03): a suggestion on an asset;
- `sourcing_position` (TXP-08/09): a proposal;
- `provision_explainer` (TXP-13 b2): a suggestion;
- `time_study_allocation` (TXP-13 c2): a proposal.

Every mode returns suggestions or proposals only (never an approve, override, confirm, send or
sign-off action), keeps only model sentences whose numbers are code's (`keep_sentences`), and reads
TRI only once the taxpayer has given both the `use` and the `ai_disclosure` consents for the year
(`consent_required` otherwise, before any model call). Code computes every figure (E3, E8, E9, E11,
E12); the model explains and proposes allocations code then foots.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from abacus.modules.organisations.api import TriConsentRequired as ConsentRequired
from abacus.modules.tax.analyst_modes import NEVER, keep_sentences

Mode = Literal[
    "asset_evidence", "sourcing_position", "provision_explainer", "time_study_allocation"
]
Write = Literal["suggestion.create", "proposal.create"]
REQUIRED_CONSENTS: Final = frozenset({"use", "ai_disclosure"})


@dataclass(frozen=True, slots=True)
class ModeSpec:
    mode: Mode
    screen: str
    prompt: str
    reads: tuple[str, ...]
    computes: tuple[str, ...]
    write: Write


MODES: Final[dict[Mode, ModeSpec]] = {
    "asset_evidence": ModeSpec(
        "asset_evidence", "TXP-03", "tax.return_analyst.asset_evidence@v1",
        ("tax.read_return", "tax.list_documents"), ("tax.compute_depreciation",),
        "suggestion.create",
    ),
    "sourcing_position": ModeSpec(
        "sourcing_position", "TXP-09", "tax.return_analyst.sourcing_position@v1",
        ("tax.read_return", "tax.read_pass_through_activity"), ("tax.compute_apportionment",),
        "proposal.create",
    ),
    "provision_explainer": ModeSpec(
        "provision_explainer", "TXP-13", "tax.return_analyst.provision_explainer@v1",
        ("tax.read_return",), ("tax.compute_provision",), "suggestion.create",
    ),
    "time_study_allocation": ModeSpec(
        "time_study_allocation", "TXP-13", "tax.return_analyst.time_study_allocation@v1",
        ("tax.read_return", "tax.list_documents"), ("tax.compute_functional_expenses",),
        "proposal.create",
    ),
}  # fmt: skip


def require_consents(granted: Collection[str]) -> None:
    """Before any TRI read: both consents for the year, or `consent_required`."""
    missing = REQUIRED_CONSENTS - set(granted)
    if missing:
        raise ConsentRequired(facts={"purpose": "agent_mode"})


@dataclass(frozen=True, slots=True)
class ModeOutput:
    mode: Mode
    write: Write
    text: str
    figures: tuple[Decimal, ...]


def settle(mode: Mode, model_text: str, code_figures: Sequence[Decimal]) -> ModeOutput:
    """Code's last word: the mode's one write, sentences carrying only code's numbers, and code's
    figures (never the model's)."""
    spec = MODES[mode]
    if spec.write in NEVER:
        raise ValueError(f"{mode} would write a reserved action")
    kept = keep_sentences(model_text, frozenset(code_figures))
    return ModeOutput(mode, spec.write, kept, tuple(code_figures))


__all__ = [
    "MODES",
    "REQUIRED_CONSENTS",
    "ConsentRequired",
    "Mode",
    "ModeOutput",
    "ModeSpec",
    "require_consents",
    "settle",
]
