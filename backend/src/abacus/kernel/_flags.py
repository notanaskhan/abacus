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
ENGAGEMENT_AGENT_ENABLED = Flag(
    name="engagement_agent.enabled",
    kind="boolean",
    default="false",
)
RETRIEVAL_AUTO = Flag(
    name="retrieval.auto",
    kind="boolean",
    default="false",
)

FLAGS: dict[str, Flag] = {
    "prompt.evidence.screener": PROMPT_EVIDENCE_SCREENER,
    "engagement_agent.enabled": ENGAGEMENT_AGENT_ENABLED,
    "retrieval.auto": RETRIEVAL_AUTO,
}
