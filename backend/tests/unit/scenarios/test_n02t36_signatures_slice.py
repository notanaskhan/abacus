"""N-02-T36 (TASK-2528; N-02 §9; SIG-01 at E0; DEC-1573): the signatures slice foots to the hub
the handoff draws, and the committed export the TypeScript scenarios are held to is current.

`make seed-demo --slice signatures` writes these rows; SIG-01's counts are computed from them here
without a database (as `tax_board`'s footing tests do).
"""

from __future__ import annotations

import json
from datetime import date, datetime

from abacus_tools.synthetic.fixture_export import EXPORTED, scenario_files
from abacus_tools.synthetic.scenarios.brightwater_hale import signatures as sig
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import NAMED, ROSTER
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered, slice_events


def test_ac_sig01_counts_at_e0_foot_to_the_handoff() -> None:
    counts = sig.hub_counts()
    assert (counts["out"], counts["toSend"], counts["expired"]) == (17, 2, 1)
    assert counts["tiles"] == {"sent": 8, "viewed": 5, "partially_signed": 4, "dueWithin7": 4}
    assert counts["byType"] == {"efile": 10, "letters": 4, "rep": 2, "consents": 1}
    assert counts["dueWithin7"] == ["E3", "E7", "E14", "E11"]
    assert [e.key for e in sig.OUT] == sorted(
        (e.key for e in sig.OUT),
        key=lambda k: ((sig.BY_KEY[k].due or date.max).isoformat(), int(k[1:])),
    )
    assert len(sig.COMPLETED) == 6
    assert all((date(2026, 9, 14) - (e.completed or date.min)).days <= 30 for e in sig.COMPLETED)


def test_ac_the_committed_export_is_the_scenarios() -> None:
    for name, text in scenario_files().items():
        committed = (EXPORTED / name).read_text(encoding="utf-8")
        assert json.loads(committed) == json.loads(text), f"run make fixtures: {name} is stale"


def test_the_timeline_reads_as_the_handoff() -> None:
    assert datetime(2026, 9, 14, 9, 40, tzinfo=sig.CT) == sig.E18_AT
    assert [(t.hour, t.minute) for t in sig.KOWAL_FAILURES] == [(20, 6), (20, 10), (20, 14)]
    irene = next(s for s in sig.BY_KEY["E2"].signers if s.name == "Irene")
    assert irene.kba_locked and not irene.signed
    copperleaf = sig.COPPERLEAF
    assert [s.signed_on for s in copperleaf.signers] == [date(2026, 3, 2), date(2026, 3, 3)]
    assert copperleaf.signers[1].firm and copperleaf.status == "completed"
    assert sig.BY_KEY["D2"].drafted_by == "agent" and sig.BY_KEY["D2"].status == "draft"
    assert sig.BY_KEY["X1"].expired == date(2026, 8, 30)


def test_every_envelope_belongs_to_a_scenario_client() -> None:
    clients = {n.name for n in NAMED} | {r[0] for r in ROSTER}
    for e in sig.ALL:
        assert e.scenario_client in clients, e.key


def test_the_slice_is_registered_stable_and_starts_with_the_disclosure() -> None:
    assert sig.SLICE in registered()
    first, second = slice_events(sig.SLICE), slice_events(sig.SLICE)
    assert [e.label for e in first] == [e.label for e in second]
    assert first[0].kind == "signatures.disclosure_imported"
    assert sum(1 for e in first if e.kind == "signatures.envelope_recorded") == len(sig.ALL)
    assert len({e.label for e in first}) == len(first)
