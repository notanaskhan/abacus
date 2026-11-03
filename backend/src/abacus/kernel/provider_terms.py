"""The provider terms register, compiled (ADR-114; SPEC-036; TASK-075).

`docs/operations/provider-terms.yaml` is rendered into `_provider_terms` by
`abacus_tools.codegen.provider_terms`. A route carries client data only while an entry covers it
(`approved_on <= today <= review_by`); only `bedrock` is an eligible model route (ADR-113) and
only `textract` an eligible document service (register v2, P-11-T21).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TermsEntry:
    route: str
    provider: str
    region: str
    approved_on: date
    review_by: date
    # SPEC-036 Q4 (TASK-076): a hash of training, retention, region and subprocessors. A firm's
    # opt-in lapses when it changes; a new review date alone doesn't change it.
    material: str = ""
    retention_exceptions: tuple[tuple[str, int], ...] = ()
    subprocessors: tuple[str, ...] = ()
    # Register v2 (P-11-T21): `model_route` (Bedrock) or `document_service` (Textract), with the
    # document service's AI-services opt-out evidence and §7216 basis for TRI (None: no TRI).
    kind: str = "model_route"
    ai_services_opt_out: str | None = None
    tri_basis: str | None = None


def covering(route: str, on: date) -> TermsEntry | None:
    """The newest approved entry covering `route` on `on` (a model route or, register v2, a
    document service such as `textract`), or None. A draft entry is never compiled in."""
    from abacus.kernel._provider_terms import DOCUMENT_SERVICES, ENTRIES

    found = [
        e
        for e in (*ENTRIES, *DOCUMENT_SERVICES)
        if e.route == route and e.approved_on <= on <= e.review_by
    ]
    return max(found, key=lambda e: e.approved_on) if found else None


def version() -> str:
    """The register's fingerprint, recorded on each client-data usage record."""
    from abacus.kernel._provider_terms import VERSION

    return VERSION
