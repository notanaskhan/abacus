"""The signatures module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. N-02-T07 (0292): C7's
twelve tables.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "envelopes",
        "envelope_numbers",
        "envelope_documents",
        "envelope_signers",
        "envelope_fields",
        "envelope_events",
        "envelope_provider_calls",
        "signature_evidence",
        "envelope_policies",
        "signing_sessions",
        "esign_disclosures",
        "esign_acceptances",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004); each also carries a
# `signatures_rows_immutable` trigger (I-IMMUTABLE).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "envelope_events",
        "envelope_provider_calls",
        "signature_evidence",
        "esign_disclosures",
        "esign_acceptances",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "envelope_numbers": frozenset({"tenant_id", "next_value"}),
    "signing_sessions": frozenset(
        {"tenant_id", "envelope_id", "signer_id", "principal_id", "presentation"}
        | {"expires_at", "return_token_hash"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "envelope_numbers": frozenset({"next_value"}),  # the row-locked counter
    "signing_sessions": frozenset({"state"}),  # returned, confirmed or abandoned
}
