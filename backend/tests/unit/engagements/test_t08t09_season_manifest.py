"""T-08-T09 (TASK-8724; DEC-5718): cohorts by office and segment foot to the manifest's tallies;
exception rules flag exactly the rows that need an answer (ENG-07: Osterberg, Farouk and Barlow in
cohort 5); prospects never enter a manifest."""

from __future__ import annotations

from abacus.modules.engagements.season_manifest import Candidate, build, tally


def _c(name: str, office: str, segment: str, **kw: object) -> Candidate:
    return Candidate(name, office, segment, 1, 1, "OB", "SI", **kw)  # type: ignore[arg-type]  # flags only


def test_ac_cohorts_foot_and_flag_exceptions() -> None:
    cands = [
        _c("Abbott", "Chicago", "individual"),
        _c("Baker", "Chicago", "individual"),
        _c("Osterberg", "Denver", "fiduciary", consent_on_file=False),
        _c("Farouk", "Denver", "fiduciary", letter_current=False),
        _c("Barlow", "Denver", "fiduciary", active=False),
        _c("Prospect Co.", "Denver", "fiduciary", prospect=True),
    ]
    cohorts = build(cands, [("Chicago", "individual"), ("Denver", "fiduciary")])
    assert [(c.office, c.segment, c.engagements) for c in cohorts] == [
        ("Chicago", "individual", 2),
        ("Denver", "fiduciary", 3),
    ]
    assert set(cohorts[1].exceptions) == {"Osterberg", "Farouk", "Barlow"}
    t = tally(cohorts)
    assert (t.engagements, t.returns, t.binders, t.exceptions) == (5, 5, 5, 3)
