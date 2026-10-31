"""The sampling module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
# A-03-T05 (0520; ADR-340): the sampling engine's tables. Fieldwork's journal-entry `populations`
# (0057) are fieldwork's; these are the sample sets' own (DEC-1554).
TABLES: frozenset[str] = frozenset(
    {
        "sample_populations",
        "sample_population_records",
        "completeness_ties",
        "sample_sets",
        "sample_set_versions",
        "sample_strata",
        "sample_items",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "sample_populations",
        "sample_population_records",
        "completeness_ties",
        "sample_strata",
        "sample_items",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "sample_populations": frozenset(
        {
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "source_kind",
            "evidence_version_id",
            "gl_snapshot_id",
            "query",
            "column_map",
            "record_count",
            "record_unit",
            "amount_total",
            "sha256",
            "sampling_unit",
            "deviation_definition",
            "pulled_at",
            "created_by",
        }
    ),
    "sample_population_records": frozenset(
        {"tenant_id", "population_id", "ordinal", "record_key", "amount", "display"}
    ),
    "completeness_ties": frozenset(
        {
            "id",
            "tenant_id",
            "population_id",
            "position",
            "label",
            "left_amount",
            "comparisons",
            "difference",
            "result",
            "explanation",
            "engine_version",
            "inputs_hash",
            "created_by",
        }
    ),
    "sample_sets": frozenset(
        {
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "title",
            "purpose",
            "program_step_key",
            "created_by",
        }
    ),
    "sample_set_versions": frozenset(
        {
            "id",
            "tenant_id",
            "sample_set_id",
            "version_no",
            "population_id",
            "method",
            "parameters",
            "size_policy_version_id",
            "computed_size",
            "statistical_crosscheck_size",
            "override_size",
            "override_rationale",
            "final_size",
            "seed",
            "seed_source",
            "sampler_version",
            "inputs_hash",
            "created_by",
        }
    ),
    "sample_strata": frozenset(
        {
            "tenant_id",
            "sample_set_version_id",
            "position",
            "min_amount",
            "max_amount",
            "population_count",
            "population_amount",
            "test_rule",
            "random_count",
            "selected_count",
        }
    ),
    "sample_items": frozenset(
        {
            "tenant_id",
            "sample_set_version_id",
            "position",
            "population_record_ordinal",
            "record_key",
            "stratum_position",
            "selection_reason",
            "display",
        }
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "sample_sets": frozenset({"title", "purpose", "program_step_key", "row_version"}),
    "sample_set_versions": frozenset(
        {
            "status",
            "items_hash",
            "content_hash",
            "failure_code",
            "approved_by",
            "approved_at",
            "approved_actor_kind",
            "superseded_by",
            "row_version",
        }
    ),
}
