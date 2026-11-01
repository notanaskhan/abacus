"""The assurance module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# SPEC-314 (TASK-332): completion, release and archive, all insert-only and human-only.
# A-01-T05 (0134): the record-mode phase events, insert-only and human-only when recorded.
# A-01-T23 (0226): the external release and archive records, insert-only and human-only.
_HUMAN_RECORDS: frozenset[str] = frozenset(
    {"eqr_concurrences", "completion_records", "releases", "archives", "assurance_phase_events"}
    | {"assurance_external_releases", "assurance_external_archives"}
)
# A-05-T06 (0610, DEC-1861): the EBP plan audit's first tables; checks and conflicts insert-only.
EBP_TABLES: frozenset[str] = frozenset(
    {"ebp_plans", "ebp_service_providers", "ebp_provider_checks", "ebp_provisions"}
    | {"ebp_provision_conflicts"}
)
TABLES: frozenset[str] = _HUMAN_RECORDS | EBP_TABLES
INSERT_ONLY: frozenset[str] = _HUMAN_RECORDS | {"ebp_provider_checks", "ebp_provision_conflicts"}
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "eqr_concurrences": frozenset(
        {"tenant_id", "engagement_id", "digest_hash", "not_involved", "concurred_by", "actor_kind"}
    ),
    "completion_records": frozenset(
        {"tenant_id", "engagement_id", "kind", "choice", "emphasis", "document_date"}
        | {"evidence_version_id", "report_record_id", "rationale", "recorded_by", "actor_kind"}
    ),
    "releases": frozenset(
        {"tenant_id", "engagement_id", "report_record_id", "report_date", "documentation_due"}
        | {"gates", "released_by", "actor_kind"}
    ),
    "archives": frozenset(
        {"tenant_id", "engagement_id", "seal", "leaf_count", "manifest", "locked_by", "actor_kind"}
    ),
    "assurance_phase_events": frozenset(
        {"id", "tenant_id", "engagement_id", "work_item_id", "from_phase", "to_phase", "mode"}
        | {"reason_sealed", "gate_ref", "actor_kind", "actor_user_id", "mfa_at"}
    ),
    "assurance_external_releases": frozenset(
        {"work_item_id", "tenant_id", "engagement_id", "report_released_on", "report_kind"}
        | {"recorded_by", "actor_kind", "mfa_at"}
    ),
    "assurance_external_archives": frozenset(
        {"work_item_id", "tenant_id", "engagement_id", "export_id", "manifest_sha256"}
        | {"firm_tool_ref_sealed", "recorded_by", "actor_kind", "mfa_at"}
    ),
    "ebp_plans": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "plan_entity_id",
            "sponsor_entity_id",
            "plan_year_start",
            "plan_year_end",
            "plan_type",
            "safe_harbor",
            "auto_enrollment",
            "match_formula",
            "qdia",
            "recordkeeper_plan_id",
            "participants_boy_with_balances",
            "participants_eoy",
            "prior_year_filer",
            "form_5558_filed_on",
            "report_target_on",
            "fidelity_bond_amount",
            "plan_document_on",
            "opinion_letter_on",
            "latest_amendment_ref",
            "version",
            "content_hash",
        }
    ),
    "ebp_service_providers": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "org_name",
            "role",
            "contact_id",
            "grant_id",
            "ein_sealed",
            "ein_last4",
            "ein_fp",
            "soc_type",
            "soc_period_start",
            "soc_period_end",
            "soc_evaluation_id",
            "certifies",
            "certification_signed_on",
            "status",
        }
    ),
    "ebp_provider_checks": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "check_kind",
            "provider_id",
            "result",
            "facts",
            "citation_ids",
            "issue_id",
        }
    ),
    "ebp_provisions": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "workpaper_version_id",
            "provision_key",
            "value",
            "reference",
            "citation_id",
            "amendment_effective_on",
            "amendment_citation_id",
            "origin",
            "suggestion_id",
        }
    ),
    "ebp_provision_conflicts": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "provision_id",
            "kind",
            "governing_citation_id",
            "conflicting_citation_id",
            "issue_id",
        }
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "ebp_plans": frozenset(
        {
            "plan_entity_id",
            "sponsor_entity_id",
            "safe_harbor",
            "auto_enrollment",
            "match_formula",
            "qdia",
            "recordkeeper_plan_id",
            "participants_boy_with_balances",
            "participants_eoy",
            "prior_year_filer",
            "form_5558_filed_on",
            "report_target_on",
            "fidelity_bond_amount",
            "plan_document_on",
            "opinion_letter_on",
            "latest_amendment_ref",
            "version",
            "content_hash",
        }
    ),
    "ebp_service_providers": frozenset(
        {
            "org_name",
            "contact_id",
            "grant_id",
            "ein_sealed",
            "ein_last4",
            "ein_fp",
            "soc_type",
            "soc_period_start",
            "soc_period_end",
            "soc_evaluation_id",
            "certifies",
            "certification_signed_on",
            "status",
        }
    ),
    "ebp_provisions": frozenset(
        {
            "value",
            "reference",
            "citation_id",
            "amendment_effective_on",
            "amendment_citation_id",
            "origin",
            "suggestion_id",
        }
    ),
}
