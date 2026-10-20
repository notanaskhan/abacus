"""GENERATED from docs/architecture/feature-flags/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
ENGAGEMENT_AGENT_ENABLED = Flag(
    name="engagement_agent.enabled",
    kind="boolean",
    default="false",
)
FIELDWORK_ASSESSOR = Flag(
    name="fieldwork.assessor",
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
LEDGER_IMPORT = Flag(
    name="ledger.import",
    kind="boolean",
    default="false",
)
MATCHING_ENABLED = Flag(
    name="matching.enabled",
    kind="boolean",
    default="false",
)
PROMPT_EVIDENCE_SCREENER = Flag(
    name="prompt.evidence.screener",
    kind="variant",
    default="evidence.screen@v0",
    values=(
        "evidence.screen@v0",
    ),
)
RETRIEVAL_AUTO = Flag(
    name="retrieval.auto",
    kind="boolean",
    default="false",
)
UPLOAD_REVIEW_ENABLED = Flag(
    name="upload_review.enabled",
    kind="boolean",
    default="false",
)
UPLOADS_PROCESSING = Flag(
    name="uploads.processing",
    kind="boolean",
    default="false",
)

FLAGS: dict[str, Flag] = {
    "engagement_agent.enabled": ENGAGEMENT_AGENT_ENABLED,
    "fieldwork.assessor": FIELDWORK_ASSESSOR,
    "fieldwork.procedures": FIELDWORK_PROCEDURES,
    "guidance.drafting": GUIDANCE_DRAFTING,
    "ledger.gl_import": LEDGER_GL_IMPORT,
    "ledger.import": LEDGER_IMPORT,
    "matching.enabled": MATCHING_ENABLED,
    "prompt.evidence.screener": PROMPT_EVIDENCE_SCREENER,
    "retrieval.auto": RETRIEVAL_AUTO,
    "upload_review.enabled": UPLOAD_REVIEW_ENABLED,
    "uploads.processing": UPLOADS_PROCESSING,
}
