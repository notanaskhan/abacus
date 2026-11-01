# ac-test-author: ayushkbhatia
"""T-01-T04 (TASK-2111; SPEC-501 AC-10): C7 as T-01 consumes it. T-01 registers two envelope
sources (`tax_return` for the 8879 family, `consent_set` for §7216 consents) and reads signer-level
facts; record mode serves consents signed outside Accrued. The superseded-by-change marker and the
retention-extension call are T-01's requests of N-02, held as strict xfails until N-02 ships them.
"""

from __future__ import annotations

import dataclasses

import pytest

from abacus.modules.signatures import api as signatures


def test_ac10_an_envelope_source_names_what_t01_needs() -> None:
    fields = {f.name for f in dataclasses.fields(signatures.EnvelopeSource)}
    assert {"kind", "documents", "signers", "retention_record_type", "gate", "checks"} <= fields


def test_ac10_a_source_registers_through_the_slot_and_unknown_kinds_fail_closed() -> None:
    assert callable(signatures.register_envelope_source)
    assert issubclass(signatures.UnknownEnvelopeSource, Exception)


def test_ac10_signer_level_counts_reach_the_consumer() -> None:
    fields = {f.name for f in dataclasses.fields(signatures.EnvelopeSummary)}
    assert {"signed", "total"} <= fields


@pytest.mark.xfail(
    strict=True,
    reason="TASK-2111: N-02 has not shipped the superseded_by_change marker (T-01 §3.12)",
)
def test_ac10_a_superseded_8879_carries_the_marker() -> None:
    assert hasattr(signatures, "SUPERSEDED_BY_CHANGE")


def test_ac10_signatures_extends_retention_on_filing() -> None:
    # TASK-2111's finding closed: N-02 ships the retention-extension call (T-01 §4.5).
    assert hasattr(signatures, "extend_retention")
