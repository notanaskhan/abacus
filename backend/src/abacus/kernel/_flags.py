"""GENERATED from docs/architecture/feature-flags/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
AUDITS_COCKPIT = Flag(
    name="audits.cockpit",
    kind="boolean",
    default="false",
)
BINDERS_ENGINE = Flag(
    name="binders.engine",
    kind="boolean",
    default="false",
)
CLIENTS_V2 = Flag(
    name="clients.v2",
    kind="boolean",
    default="false",
)
COMPLIANCE_FIRM_EXPORT = Flag(
    name="compliance.firm_export",
    kind="boolean",
    default="false",
)
COMPLIANCE_INCIDENTS = Flag(
    name="compliance.incidents",
    kind="boolean",
    default="false",
)
COMPLIANCE_LEGAL_HOLDS = Flag(
    name="compliance.legal_holds",
    kind="boolean",
    default="false",
)
CONTACTS_V2 = Flag(
    name="contacts.v2",
    kind="boolean",
    default="false",
)
ENGAGEMENT_AGENT_ENABLED = Flag(
    name="engagement_agent.enabled",
    kind="boolean",
    default="false",
)
ENGAGEMENTS_V2 = Flag(
    name="engagements.v2",
    kind="boolean",
    default="false",
)
ENGAGEMENTS_WORK_ITEMS_API = Flag(
    name="engagements.work_items_api",
    kind="boolean",
    default="false",
)
EVIDENCE_CITATIONS_V2 = Flag(
    name="evidence.citations_v2",
    kind="boolean",
    default="false",
)
EVIDENCE_PII_REVEAL = Flag(
    name="evidence.pii_reveal",
    kind="boolean",
    default="false",
)
EVIDENCE_VIEWER_UNLOCK = Flag(
    name="evidence.viewer_unlock",
    kind="boolean",
    default="false",
)
EVIDENCE_VIEWER_V1 = Flag(
    name="evidence.viewer_v1",
    kind="boolean",
    default="false",
)
EVIDENCE_WITHDRAWAL = Flag(
    name="evidence.withdrawal",
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
FIRM_SETTINGS_V2 = Flag(
    name="firm_settings.v2",
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
LEDGER_TB_WORKPAPER = Flag(
    name="ledger.tb_workpaper",
    kind="boolean",
    default="false",
)
MATCHING_ENABLED = Flag(
    name="matching.enabled",
    kind="boolean",
    default="false",
)
NOTIFICATIONS_EMAIL = Flag(
    name="notifications.email",
    kind="boolean",
    default="false",
)
NOTIFICATIONS_V2 = Flag(
    name="notifications.v2",
    kind="boolean",
    default="false",
)
PORTAL_DOCUMENTS_V2 = Flag(
    name="portal.documents_v2",
    kind="boolean",
    default="false",
)
PORTAL_DROP_SORT = Flag(
    name="portal.drop_sort",
    kind="boolean",
    default="false",
)
PORTAL_HOME_V2 = Flag(
    name="portal.home_v2",
    kind="boolean",
    default="false",
)
PORTAL_SIGN_IN_V2 = Flag(
    name="portal.sign_in_v2",
    kind="boolean",
    default="false",
)
PORTAL_THIRD_PARTY_ROOM = Flag(
    name="portal.third_party_room",
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
REVIEW_GRAMMAR_API = Flag(
    name="review.grammar_api",
    kind="boolean",
    default="false",
)
SCREENING_CARD = Flag(
    name="screening.card",
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
    "audits.cockpit": AUDITS_COCKPIT,
    "binders.engine": BINDERS_ENGINE,
    "clients.v2": CLIENTS_V2,
    "compliance.firm_export": COMPLIANCE_FIRM_EXPORT,
    "compliance.incidents": COMPLIANCE_INCIDENTS,
    "compliance.legal_holds": COMPLIANCE_LEGAL_HOLDS,
    "contacts.v2": CONTACTS_V2,
    "engagement_agent.enabled": ENGAGEMENT_AGENT_ENABLED,
    "engagements.v2": ENGAGEMENTS_V2,
    "engagements.work_items_api": ENGAGEMENTS_WORK_ITEMS_API,
    "evidence.citations_v2": EVIDENCE_CITATIONS_V2,
    "evidence.pii_reveal": EVIDENCE_PII_REVEAL,
    "evidence.viewer_unlock": EVIDENCE_VIEWER_UNLOCK,
    "evidence.viewer_v1": EVIDENCE_VIEWER_V1,
    "evidence.withdrawal": EVIDENCE_WITHDRAWAL,
    "fieldwork.assessor": FIELDWORK_ASSESSOR,
    "fieldwork.procedures": FIELDWORK_PROCEDURES,
    "firm_settings.v2": FIRM_SETTINGS_V2,
    "guidance.drafting": GUIDANCE_DRAFTING,
    "ledger.gl_import": LEDGER_GL_IMPORT,
    "ledger.import": LEDGER_IMPORT,
    "ledger.tb_workpaper": LEDGER_TB_WORKPAPER,
    "matching.enabled": MATCHING_ENABLED,
    "notifications.email": NOTIFICATIONS_EMAIL,
    "notifications.v2": NOTIFICATIONS_V2,
    "portal.documents_v2": PORTAL_DOCUMENTS_V2,
    "portal.drop_sort": PORTAL_DROP_SORT,
    "portal.home_v2": PORTAL_HOME_V2,
    "portal.sign_in_v2": PORTAL_SIGN_IN_V2,
    "portal.third_party_room": PORTAL_THIRD_PARTY_ROOM,
    "prompt.evidence.screener": PROMPT_EVIDENCE_SCREENER,
    "retrieval.auto": RETRIEVAL_AUTO,
    "review.grammar_api": REVIEW_GRAMMAR_API,
    "screening.card": SCREENING_CARD,
    "upload_review.enabled": UPLOAD_REVIEW_ENABLED,
    "uploads.processing": UPLOADS_PROCESSING,
}
