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
UPLOAD_REVIEW_ENABLED = Flag(
    name="upload_review.enabled",
    kind="boolean",
    default="false",
)
FIELDWORK_PROCEDURES = Flag(
    name="fieldwork.procedures",
    kind="boolean",
    default="false",
)
GUIDANCE_DRAFTING = Flag(
    name="guidance.drafting",
    kind="boolean",
    default="false",
)
LEDGER_GL_IMPORT = Flag(
    name="ledger.gl_import",
    kind="boolean",
    default="false",
)
MATCHING_ENABLED = Flag(
    name="matching.enabled",
    kind="boolean",
    default="false",
)
UPLOADS_PROCESSING = Flag(
    name="uploads.processing",
    kind="boolean",
    default="false",
)
LEDGER_IMPORT = Flag(
    name="ledger.import",
    kind="boolean",
    default="false",
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
    "upload_review.enabled": UPLOAD_REVIEW_ENABLED,
    "fieldwork.procedures": FIELDWORK_PROCEDURES,
    "guidance.drafting": GUIDANCE_DRAFTING,
    "ledger.gl_import": LEDGER_GL_IMPORT,
    "matching.enabled": MATCHING_ENABLED,
    "uploads.processing": UPLOADS_PROCESSING,
    "ledger.import": LEDGER_IMPORT,
    "engagement_agent.enabled": ENGAGEMENT_AGENT_ENABLED,
    "retrieval.auto": RETRIEVAL_AUTO,
}
