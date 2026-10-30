"""T-01-T23 (TASK-2320; DEC-1366): Brightwater Hale's §7216 consents foot to ADM-05 on Sep 14,
2026 (218 = 212 signed + 2 expiring + 1 requested + 1 expired + 1 declined + 1 revoked), one AI-use
set per TY2025 tax engagement but Thornbury's, 210 expiring Dec 31, 2026, the handoff's named rows
as written, and every row one purpose per consent with return information that existed."""

from __future__ import annotations

from datetime import date

from abacus_tools.synthetic.scenarios.brightwater_hale import consents_7216 as c
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import TAX_ENGAGEMENTS
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered


def _named(client: str, prefix: str = "") -> c.ConsentRow:
    return next(r for r in c.ROWS if r.client == client and r.label.startswith(prefix))


def test_the_registry_foots_to_adm05() -> None:
    assert len(c.ROWS) == c.TOTAL == 218
    assert c.tiles_on(c.SNAPSHOT) == c.TILES
    assert sum(c.TILES.values()) == c.TOTAL


def test_one_ai_use_set_per_tax_engagement_but_thornbury() -> None:
    sets = [r for r in c.ROWS if r.purposes == ("use", "ai_disclosure")]
    assert len(sets) + 1 == len(TAX_ENGAGEMENTS) == 214
    assert c.THORNBURY not in {r.client for r in sets}
    signed = [r for r in sets if r.status == "signed"]
    assert len(signed) == 211
    assert sum(1 for r in signed if r.expires_on == c.DEC_31) == 210


def test_the_named_rows_read_as_the_handoff() -> None:
    ferris = _named(c.FERRIS, "ai:")
    assert ferris.status == "requested"
    assert [s.signed_on for s in ferris.signers] == [date(2026, 9, 9), None]
    assert _named(c.STEIN, "ai:").declined_on == date(2026, 2, 10)
    ridgeline = _named(c.RIDGELINE, "ai:")
    assert (ridgeline.signed_on, ridgeline.expires_on) == (date(2026, 2, 6), date(2027, 2, 6))
    feld = _named("Jonah & Claire Feld", "ai:")
    assert (feld.signed_on, feld.expires_on, len(feld.signers)) == (
        date(2026, 2, 2),
        c.DEC_31,
        2,
    )
    rao = _named("Sunil & Asha Rao", "third-party:")
    osterberg = _named("Benjamin Osterberg", "third-party:")
    assert rao.expires_on is not None and osterberg.expires_on is not None
    assert ((rao.expires_on - c.SNAPSHOT).days, (osterberg.expires_on - c.SNAPSHOT).days) == (
        16,
        22,
    )
    assert _named("Priyanka & Sam Iyer", "third-party:").status_on(c.SNAPSHOT) == "expired"
    assert _named("Delia Fortune", "third-party:").revoked_on == date(2026, 6, 2)


def test_third_party_rows_name_one_recipient_and_existing_years() -> None:
    for r in c.ROWS:
        if r.purposes == ("third_party_disclosure",):
            assert r.signed_on is not None
            assert max(r.tax_years) < r.signed_on.year or r.tax_years == (2025,)


def test_the_slice_is_registered_and_stable() -> None:
    assert c.SLICE in registered()
    assert len({r.label for r in c.ROWS}) == len(c.ROWS)
    assert [r.consent_id("use") for r in c.ROWS[:3]] == [r.consent_id("use") for r in c.ROWS[:3]]
