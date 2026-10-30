"""GENERATED from docs/architecture/feature-flags/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
AGENTS_CLIENT_DATA_OPTIN = Flag(
    name="agents.client_data_optin",
    kind="boolean",
    default="false",
)
AI_POLICY_V1 = Flag(
    name="ai_policy.v1",
    kind="boolean",
    default="false",
)
AUDIT_LOG_EXPLORER = Flag(
    name="audit_log.explorer",
    kind="boolean",
    default="false",
)
AUDIT_LOG_VALUES = Flag(
    name="audit_log.values",
    kind="boolean",
    default="false",
)
AUDITS_BINDER_EXPORT = Flag(
    name="audits.binder_export",
    kind="boolean",
    default="false",
)
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
CLIENTS_TAX_PROFILE = Flag(
    name="clients.tax_profile",
    kind="boolean",
    default="false",
)
COMMUNICATIONS_FIRM_SENDER_DOMAIN = Flag(
    name="communications.firm_sender_domain",
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
CONNECTIONS_LIVE_LEDGER = Flag(
    name="connections.live_ledger",
    kind="boolean",
    default="false",
)
CONNECTIONS_PORTAL_V2 = Flag(
    name="connections.portal_v2",
    kind="boolean",
    default="false",
)
CONSENTS_REGISTRY = Flag(
    name="consents.registry",
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
ENGAGEMENTS_ROLL_FORWARD_V2 = Flag(
    name="engagements.roll_forward_v2",
    kind="boolean",
    default="false",
)
EVIDENCE_CITATIONS_V2 = Flag(
    name="evidence.citations_v2",
    kind="boolean",
    default="false",
)
EVIDENCE_DUPLICATE_REVIEW = Flag(
    name="evidence.duplicate_review",
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
FILES_BROWSER = Flag(
    name="files.browser",
    kind="boolean",
    default="false",
)
FOLLOW_UPS_SCHEDULED_SEND = Flag(
    name="follow_ups.scheduled_send",
    kind="boolean",
    default="false",
)
GUIDANCE_DRAFTING = Flag(
    name="guidance.drafting",
    kind="boolean",
    default="false",
)
HOME_APPROVALS = Flag(
    name="home.approvals",
    kind="boolean",
    default="false",
)
HOME_DASHBOARD = Flag(
    name="home.dashboard",
    kind="boolean",
    default="false",
)
INBOX_FIRM_INTAKE = Flag(
    name="inbox.firm_intake",
    kind="boolean",
    default="false",
)
KNOWLEDGE_CATALOG = Flag(
    name="knowledge.catalog",
    kind="boolean",
    default="false",
)
KNOWLEDGE_FIRM_STANDARDS = Flag(
    name="knowledge.firm_standards",
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
MATCHING_FIRM_INTAKE = Flag(
    name="matching.firm_intake",
    kind="boolean",
    default="false",
)
METHODOLOGY_IMPORT_REVIEW = Flag(
    name="methodology.import_review",
    kind="boolean",
    default="false",
)
METHODOLOGY_IMPORTER = Flag(
    name="methodology.importer",
    kind="boolean",
    default="false",
)
METHODOLOGY_LIFECYCLE = Flag(
    name="methodology.lifecycle",
    kind="boolean",
    default="false",
)
METHODOLOGY_PROGRAMS = Flag(
    name="methodology.programs",
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
PORTAL_INTAKE_UPLOAD = Flag(
    name="portal.intake_upload",
    kind="boolean",
    default="false",
)
PORTAL_SETTINGS_EDITOR = Flag(
    name="portal.settings_editor",
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
QUESTIONNAIRES_V1 = Flag(
    name="questionnaires.v1",
    kind="boolean",
    default="false",
)
REPORTING_GENERATED_DOCUMENTS = Flag(
    name="reporting.generated_documents",
    kind="boolean",
    default="false",
)
RETRIEVAL_AUTO = Flag(
    name="retrieval.auto",
    kind="boolean",
    default="false",
)
REVIEW_CHECKPOINTS = Flag(
    name="review.checkpoints",
    kind="boolean",
    default="false",
)
REVIEW_GRAMMAR_API = Flag(
    name="review.grammar_api",
    kind="boolean",
    default="false",
)
RULES_REFERENCE_SETS = Flag(
    name="rules.reference_sets",
    kind="boolean",
    default="false",
)
SCREENING_CARD = Flag(
    name="screening.card",
    kind="boolean",
    default="false",
)
SECURITY_CENTER_V1 = Flag(
    name="security_center.v1",
    kind="boolean",
    default="false",
)
SIGNATURES_ENVELOPES = Flag(
    name="signatures.envelopes",
    kind="boolean",
    default="false",
)
SIGNATURES_ESIGN_PROVIDER = Flag(
    name="signatures.esign_provider",
    kind="boolean",
    default="false",
)
TAX_DELIVERY_EFILE = Flag(
    name="tax.delivery_efile",
    kind="boolean",
    default="false",
)
TAX_ENGINE_BRIDGE = Flag(
    name="tax.engine_bridge",
    kind="boolean",
    default="false",
)
TAX_K1_RELEASE = Flag(
    name="tax.k1_release",
    kind="boolean",
    default="false",
)
TAX_RETURNS_V1 = Flag(
    name="tax.returns_v1",
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
    "agents.client_data_optin": AGENTS_CLIENT_DATA_OPTIN,
    "ai_policy.v1": AI_POLICY_V1,
    "audit_log.explorer": AUDIT_LOG_EXPLORER,
    "audit_log.values": AUDIT_LOG_VALUES,
    "audits.binder_export": AUDITS_BINDER_EXPORT,
    "audits.cockpit": AUDITS_COCKPIT,
    "binders.engine": BINDERS_ENGINE,
    "clients.tax_profile": CLIENTS_TAX_PROFILE,
    "communications.firm_sender_domain": COMMUNICATIONS_FIRM_SENDER_DOMAIN,
    "compliance.firm_export": COMPLIANCE_FIRM_EXPORT,
    "compliance.incidents": COMPLIANCE_INCIDENTS,
    "compliance.legal_holds": COMPLIANCE_LEGAL_HOLDS,
    "connections.live_ledger": CONNECTIONS_LIVE_LEDGER,
    "connections.portal_v2": CONNECTIONS_PORTAL_V2,
    "consents.registry": CONSENTS_REGISTRY,
    "contacts.v2": CONTACTS_V2,
    "engagement_agent.enabled": ENGAGEMENT_AGENT_ENABLED,
    "engagements.roll_forward_v2": ENGAGEMENTS_ROLL_FORWARD_V2,
    "evidence.citations_v2": EVIDENCE_CITATIONS_V2,
    "evidence.duplicate_review": EVIDENCE_DUPLICATE_REVIEW,
    "evidence.pii_reveal": EVIDENCE_PII_REVEAL,
    "evidence.viewer_unlock": EVIDENCE_VIEWER_UNLOCK,
    "evidence.viewer_v1": EVIDENCE_VIEWER_V1,
    "evidence.withdrawal": EVIDENCE_WITHDRAWAL,
    "fieldwork.assessor": FIELDWORK_ASSESSOR,
    "fieldwork.procedures": FIELDWORK_PROCEDURES,
    "files.browser": FILES_BROWSER,
    "follow_ups.scheduled_send": FOLLOW_UPS_SCHEDULED_SEND,
    "guidance.drafting": GUIDANCE_DRAFTING,
    "home.approvals": HOME_APPROVALS,
    "home.dashboard": HOME_DASHBOARD,
    "inbox.firm_intake": INBOX_FIRM_INTAKE,
    "knowledge.catalog": KNOWLEDGE_CATALOG,
    "knowledge.firm_standards": KNOWLEDGE_FIRM_STANDARDS,
    "ledger.gl_import": LEDGER_GL_IMPORT,
    "ledger.import": LEDGER_IMPORT,
    "ledger.tb_workpaper": LEDGER_TB_WORKPAPER,
    "matching.enabled": MATCHING_ENABLED,
    "matching.firm_intake": MATCHING_FIRM_INTAKE,
    "methodology.import_review": METHODOLOGY_IMPORT_REVIEW,
    "methodology.importer": METHODOLOGY_IMPORTER,
    "methodology.lifecycle": METHODOLOGY_LIFECYCLE,
    "methodology.programs": METHODOLOGY_PROGRAMS,
    "notifications.email": NOTIFICATIONS_EMAIL,
    "notifications.v2": NOTIFICATIONS_V2,
    "portal.drop_sort": PORTAL_DROP_SORT,
    "portal.home_v2": PORTAL_HOME_V2,
    "portal.intake_upload": PORTAL_INTAKE_UPLOAD,
    "portal.settings_editor": PORTAL_SETTINGS_EDITOR,
    "portal.sign_in_v2": PORTAL_SIGN_IN_V2,
    "portal.third_party_room": PORTAL_THIRD_PARTY_ROOM,
    "prompt.evidence.screener": PROMPT_EVIDENCE_SCREENER,
    "questionnaires.v1": QUESTIONNAIRES_V1,
    "reporting.generated_documents": REPORTING_GENERATED_DOCUMENTS,
    "retrieval.auto": RETRIEVAL_AUTO,
    "review.checkpoints": REVIEW_CHECKPOINTS,
    "review.grammar_api": REVIEW_GRAMMAR_API,
    "rules.reference_sets": RULES_REFERENCE_SETS,
    "screening.card": SCREENING_CARD,
    "security_center.v1": SECURITY_CENTER_V1,
    "signatures.envelopes": SIGNATURES_ENVELOPES,
    "signatures.esign_provider": SIGNATURES_ESIGN_PROVIDER,
    "tax.delivery_efile": TAX_DELIVERY_EFILE,
    "tax.engine_bridge": TAX_ENGINE_BRIDGE,
    "tax.k1_release": TAX_K1_RELEASE,
    "tax.returns_v1": TAX_RETURNS_V1,
    "upload_review.enabled": UPLOAD_REVIEW_ENABLED,
    "uploads.processing": UPLOADS_PROCESSING,
}
