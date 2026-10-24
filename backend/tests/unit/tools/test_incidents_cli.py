"""Q-02-T33 (RB-27): `make incident-propagate` checks Accrued's facts before starting anything."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from abacus.modules.identity.api import configure_staff_verifier
from abacus_tools import incidents
from abacus_tools.fakes.identity import FakeIdentityProvider

GOOD = {
    "title": "Synthetic sub-processor incident",
    "event_kind": "vendor_incident",
    "discovered_at": "2026-09-10T14:05:00+00:00",
    "confirmed_at": "2026-09-11T09:00:00+00:00",
    "consumers_affected": 0,
    "unencrypted": False,
}


def _file(tmp_path: Path, body: object) -> Path:
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_ac39_the_facts_file_reads_as_the_route_reads_it(tmp_path: Path) -> None:
    facts = incidents.load_facts(_file(tmp_path, GOOD))
    assert facts.event_kind == "vendor_incident"
    assert facts.confirmed_at == "2026-09-11T09:00:00+00:00"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"title": ""}, "title"),
        ({"event_kind": "meteor"}, "event_kind"),
        ({"discovered_at": "2026-09-10T14:05:00"}, "offset"),
        ({"consumers_affected": -1}, "consumers_affected"),
        ({"unencrypted": "yes"}, "unencrypted"),
    ],
)
def test_ac39_bad_facts_are_refused(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    with pytest.raises(incidents.Refused, match=message):
        incidents.load_facts(_file(tmp_path, {**GOOD, **change}))


STAFF_ISSUER = "https://staff.probe.test"


@pytest.fixture
def staff_idp(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeIdentityProvider]:
    idp = FakeIdentityProvider(issuer=STAFF_ISSUER)
    configure_staff_verifier(idp.verifier())
    yield idp
    configure_staff_verifier(None)


def _argv(tmp_path: Path, staff: str, *extra: str) -> list[str]:
    return [
        "propagate",
        "--ref",
        "ACC-2026-001",
        "--firms",
        "00000000-0000-4000-8000-000000000001",
        "--facts",
        str(_file(tmp_path, GOOD)),
        "--staff",
        staff,
        "--reason",
        "Accrued SEV1 confirmed",
        *extra,
    ]


def _staff_id(subject: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{STAFF_ISSUER}#{subject}"))


def test_ac39_a_dry_run_starts_nothing_and_never_prints_the_title(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    staff_idp: FakeIdentityProvider,
) -> None:
    monkeypatch.setenv("ABACUS_STAFF_TOKEN", staff_idp.token("rb27-staff", mfa=True))
    code = incidents.main(_argv(tmp_path, _staff_id("rb27-staff"), "--dry-run"))
    out = capsys.readouterr().out
    assert code == 0 and "ACC-2026-001" in out and "Synthetic" not in out
    bad = _argv(tmp_path, _staff_id("rb27-staff"))
    bad[2] = "acc"
    assert incidents.main(bad) == 2


def test_review_the_cli_refuses_an_unknown_or_mismatched_staff_member(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    staff_idp: FakeIdentityProvider,
) -> None:
    monkeypatch.delenv("ABACUS_STAFF_TOKEN", raising=False)
    assert incidents.main(_argv(tmp_path, _staff_id("rb27-staff"), "--dry-run")) == 2
    assert "ABACUS_STAFF_TOKEN" in capsys.readouterr().err

    # A token the staff issuer did not sign (a firm user's, here another issuer's).
    other = FakeIdentityProvider(issuer="https://firm.probe.test")
    monkeypatch.setenv("ABACUS_STAFF_TOKEN", other.token("rb27-staff", mfa=True))
    assert incidents.main(_argv(tmp_path, _staff_id("rb27-staff"), "--dry-run")) == 2

    # No MFA.
    monkeypatch.setenv("ABACUS_STAFF_TOKEN", staff_idp.token("rb27-staff", mfa=False))
    assert incidents.main(_argv(tmp_path, _staff_id("rb27-staff"), "--dry-run")) == 2

    # A real staff token, but --staff names someone else (an unknown UUID).
    monkeypatch.setenv("ABACUS_STAFF_TOKEN", staff_idp.token("rb27-staff", mfa=True))
    assert incidents.main(_argv(tmp_path, str(uuid4()), "--dry-run")) == 2
    assert "--staff is not" in capsys.readouterr().err
