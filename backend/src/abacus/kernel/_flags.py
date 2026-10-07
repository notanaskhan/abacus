"""GENERATED from docs/architecture/feature-flags.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
PROMPT_EVIDENCE_SCREENER = Flag(
    name="prompt.evidence.screener",
    kind="variant",
    default="evidence.screen@v0",
    values=(
        "evidence.screen@v0",
    ),
)

FLAGS: dict[str, Flag] = {
    "prompt.evidence.screener": PROMPT_EVIDENCE_SCREENER,
}
