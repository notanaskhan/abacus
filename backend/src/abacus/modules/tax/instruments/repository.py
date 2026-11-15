"""The instrument tables' statements (T-07-T07 part, TASK-8070; migrations 0883 and 0886): the
service (`service.py`) reads and writes trust profiles, governing instruments, segmentations,
clauses, interpretations and determinations only through these, under the caller's tenant
session or unit of work (ADR-012: routes, service, repository). Identifiers, codes, hashes and
sealed values only; no statement builds SQL from strings (SQL-001)."""

from __future__ import annotations

from typing import Final

from sqlalchemy import text

RETURN: Final = text(
    "SELECT work_item_id, engagement_id, client_entity_id, form, tax_year FROM tax_returns "
    "WHERE work_item_id = :r"
)
PROFILE: Final = text(
    "SELECT fiduciary_kind, agreement_date, revocable, irrevocable_since, settlor_name_sealed, "
    "settlor_died_year, residency_state, state_form FROM trust_profiles "
    "WHERE client_entity_id = :e"
)
INSTRUMENT: Final = text(
    "SELECT id, evidence_version_id, supersedes_instrument_id, attached_by, attached_at "
    "FROM governing_instruments WHERE client_entity_id = :e "
    "AND NOT EXISTS (SELECT 1 FROM governing_instruments n WHERE n.supersedes_instrument_id = "
    "governing_instruments.id) ORDER BY attached_at DESC LIMIT 1"
)
SEGMENTATION: Final = text(
    "SELECT id, status, text_source, confidence, clause_count FROM instrument_segmentations "
    "WHERE instrument_id = :i ORDER BY created_at DESC LIMIT 1"
)
INTERPRETATION: Final = text(
    "SELECT id, status, scenario, read_run_id, version_no, content_hash, locked_at, row_version, "
    "instrument_id, segmentation_id FROM instrument_interpretations "
    "WHERE work_item_id = :w AND superseded_at IS NULL"
)
DETERMINATIONS: Final = text(
    "SELECT d.id, d.key, v.seq, v.value_code, v.value_text_sealed, v.rationale_ref, "
    "v.citation_ids, v.set_by_kind, v.set_by_id, v.suggestion_id "
    "FROM instrument_determinations d JOIN LATERAL (SELECT * FROM "
    "instrument_determination_versions x WHERE x.determination_id = d.id "
    "ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.interpretation_id = :i ORDER BY d.key"
)
CLAUSE_LABELS: Final = text(
    "SELECT c.id, c.label FROM instrument_clauses c WHERE c.segmentation_id = :s"
)
NEW_PROFILE: Final = text(
    "INSERT INTO trust_profiles (client_entity_id, tenant_id, fiduciary_kind, created_by) "
    "VALUES (:e, :t, :k, :u) ON CONFLICT (client_entity_id) DO NOTHING"
)
NEW_INSTRUMENT: Final = text(
    "INSERT INTO governing_instruments (tenant_id, client_entity_id, evidence_version_id, "
    "supersedes_instrument_id, attached_by) VALUES (:t, :e, :v, :s, :u) RETURNING id"
)
NEW_SEGMENTATION: Final = text(
    "INSERT INTO instrument_segmentations (tenant_id, instrument_id, segmentation_version, "
    "text_source, status, confidence, clause_count, layer_sha256) "
    "VALUES (:t, :i, :sv, :src, :st, :c, :n, :h) RETURNING id"
)
NEW_CLAUSE: Final = text(
    "INSERT INTO instrument_clauses (tenant_id, segmentation_id, label, heading, ordinal, "
    "parent_clause_id, page_from, page_to, regions, text_sha256, marked_by) VALUES (:t, :s, "
    ":label, :heading, :ordinal, :parent, :pf, :pt, CAST(:regions AS jsonb), :h, :by) RETURNING id"
)
SUPERSEDE_INTERPRETATION: Final = text(
    "UPDATE instrument_interpretations SET superseded_at = abacus_now(), "
    "row_version = row_version + 1 WHERE work_item_id = :w AND superseded_at IS NULL"
)
NEW_INTERPRETATION: Final = text(
    "INSERT INTO instrument_interpretations (tenant_id, engagement_id, work_item_id, "
    "instrument_id, segmentation_id) VALUES (:t, :e, :w, :i, :s) RETURNING id"
)
INSTRUMENT_BY_ID: Final = text(
    "SELECT g.id, g.client_entity_id FROM governing_instruments g WHERE g.id = :i"
)
CLAUSES: Final = text(
    "SELECT id, label, heading, ordinal, parent_clause_id, page_from, page_to, regions, "
    "text_sha256 FROM instrument_clauses WHERE segmentation_id = :s ORDER BY ordinal"
)
RETURN_OF_ENTITY: Final = text(
    "SELECT engagement_id FROM tax_returns WHERE client_entity_id = :e AND form IN ('1041', '706')"
)
DETERMINATION_OF: Final = text(
    "SELECT d.id, d.key, d.interpretation_id, i.work_item_id, i.engagement_id, i.status, "
    "(SELECT max(seq) FROM instrument_determination_versions v WHERE v.determination_id = d.id) "
    "AS seq FROM instrument_determinations d JOIN instrument_interpretations i "
    "ON i.id = d.interpretation_id WHERE d.id = :d"
)
NEW_DETERMINATION: Final = text(
    "INSERT INTO instrument_determinations (tenant_id, interpretation_id, key) "
    "VALUES (:t, :i, :k) ON CONFLICT (interpretation_id, key) DO NOTHING"
)
DETERMINATION_ID: Final = text(
    "SELECT id FROM instrument_determinations WHERE interpretation_id = :i AND key = :k"
)
NEW_VERSION: Final = text(
    "INSERT INTO instrument_determination_versions (tenant_id, determination_id, key, seq, "
    "value_code, value_text_sealed, rationale_ref, citation_ids, set_by_kind, set_by_id, "
    "reason_sealed) VALUES (:t, :d, :k, :seq, :code, :value, :rationale, :citations, 'human', "
    ":u, :reason)"
)
ADOPT: Final = text(
    "UPDATE instrument_interpretations SET status = 'adopted', version_no = version_no + 1, "
    "content_hash = :h, row_version = row_version + 1 WHERE id = :i"
)
# T-07-T03 (AC-4.1): the status before a person's write, so the move into Adopted is announced
# once (the gate and `instrument_interpretation_ready`), not on every later edit.
BEFORE_ADOPT: Final = text(
    "SELECT status, engagement_id, work_item_id FROM instrument_interpretations "
    "WHERE id = :i FOR UPDATE"
)
HASH_ROWS: Final = text(
    "SELECT d.key, v.seq, v.value_code, v.citation_ids FROM instrument_determinations d "
    "JOIN LATERAL (SELECT * FROM instrument_determination_versions x WHERE x.determination_id "
    "= d.id ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.interpretation_id = :i ORDER BY d.key"
)
INTERPRETATION_BY_ID: Final = text(
    "SELECT id, engagement_id, work_item_id, status FROM instrument_interpretations WHERE id = :i"
)
REOPEN: Final = text(
    "UPDATE instrument_interpretations SET status = 'reopened', locked_at = NULL, "
    "reopen_reason_sealed = :r, version_no = version_no + 1, row_version = row_version + 1 "
    "WHERE id = :i AND status = 'approved' RETURNING id"
)
LOCK: Final = text(
    "UPDATE instrument_interpretations SET status = 'approved', locked_at = abacus_now(), "
    "row_version = row_version + 1 WHERE id = :i AND status IN ('adopted', 'proposed') "
    "AND superseded_at IS NULL RETURNING engagement_id"
)
REVIEWABLES: Final = text(
    "SELECT i.id, i.content_hash, i.version_no, i.work_item_id, i.status FROM "
    "instrument_interpretations i WHERE i.engagement_id = :e AND i.superseded_at IS NULL"
)
REVIEWABLE: Final = text(
    "SELECT i.id, i.engagement_id, i.work_item_id, i.content_hash, i.version_no, i.status, "
    "(SELECT array_agg(DISTINCT v.set_by_id) FROM instrument_determinations d "
    "JOIN instrument_determination_versions v ON v.determination_id = d.id "
    "WHERE d.interpretation_id = i.id AND v.set_by_kind = 'human') AS preparers, "
    "(SELECT count(*) FROM instrument_determinations d WHERE d.interpretation_id = i.id) AS keys "
    "FROM instrument_interpretations i WHERE i.id = :i"
)
