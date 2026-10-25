"""Q-01-T11, T34: release records and gates (`abacus_tools.release`). The manifest is
deterministic; a record names every input by digest; the production gate refuses without staging
verification, replay, a clean or excepted Inspector record, or a hand-applied infra change; the
runtime config and ops requests keep their contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools import release
from abacus_tools.release import Refused, check, gate, inspector, ops_request, runtime_config

SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
GOOD: dict[str, object] = {
    "git_sha": SHA,
    "image_digest": DIGEST,
    "spa_manifest_sha256": "c" * 64,
    "alembic_head": "0157",
    "openapi_sha256": "d" * 64,
    "infra_sha": "e" * 40,
}


def test_the_manifest_lists_every_file_and_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    first = release.write_manifest(tmp_path)
    second = release.write_manifest(tmp_path)  # the manifest itself is left out
    assert first == second
    lines = (tmp_path / "manifest.sha256").read_text().splitlines()
    assert [line.split("  ")[1] for line in lines] == ["assets/app-123.js", "index.html"]
    (tmp_path / "index.html").write_text("<html>changed</html>")
    assert release.write_manifest(tmp_path) != first


def test_a_record_carries_the_six_digests(tmp_path: Path) -> None:
    found = release.record(
        git_sha=SHA, image_digest=DIGEST, spa_manifest_sha256="c" * 64, infra_sha="e" * 40
    )
    assert set(found) == release.RELEASE_KEYS
    assert found["alembic_head"] == release.alembic_head()
    out = tmp_path / "release.json"
    assert release.main(
        [
            "record",
            "--git-sha", SHA,
            "--image-digest", DIGEST,
            "--spa-manifest-sha256", "c" * 64,
            "--infra-sha", "e" * 40,
            "--out", str(out),
        ]
    ) == 0  # fmt: skip
    assert json.loads(out.read_text())["image_digest"] == DIGEST


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("image_digest", "abacus-backend:latest"),
        ("image_digest", f"repo@{DIGEST}"),
        ("image_digest", "sha256:short"),
        ("git_sha", "main"),
        ("spa_manifest_sha256", None),
        ("alembic_head", "head"),
        ("infra_sha", "e" * 39),
    ],
)
def test_anything_but_a_digest_is_refused(key: str, value: object) -> None:
    with pytest.raises(Refused):
        check({**GOOD, key: value})


def test_unknown_or_missing_keys_are_refused() -> None:
    with pytest.raises(Refused):
        check({**GOOD, "image_tag": "v1"})
    with pytest.raises(Refused):
        check({k: v for k, v in GOOD.items() if k != "openapi_sha256"})
    with pytest.raises(Refused):
        check({**GOOD, "infra_applied_sha": "e" * 40})  # only a production release records it
    check({**GOOD, "infra_applied_sha": "e" * 40}, production=True)


def test_the_placeholder_deploys_nothing(tmp_path: Path) -> None:
    placeholder = Path(__file__).resolve().parents[4] / "deploy/production/release.json"
    loaded = json.loads(placeholder.read_text())
    assert release.is_placeholder(loaded)
    assert set(loaded) == release.RELEASE_KEYS
    assert release.main(["check", str(placeholder), "--production"]) == 0


def _finding(severity: str, fix: str, arn: str, status: str = "ACTIVE") -> dict[str, str]:
    return {
        "severity": severity,
        "fixAvailable": fix,
        "status": status,
        "findingArn": f"arn:aws:inspector2:us-east-2:000000000000:finding/{arn}",
    }


def test_inspector_counts_only_active_fixable_critical_and_high() -> None:
    record = inspector(
        {
            "findings": [
                _finding("CRITICAL", "YES", "f1"),
                _finding("HIGH", "YES", "f2"),
                _finding("HIGH", "NO", "f3"),  # no fix yet: does not block
                _finding("MEDIUM", "YES", "f4"),
                _finding("CRITICAL", "YES", "f5", status="CLOSED"),
            ]
        },
        DIGEST,
    )
    assert (record.fixable_critical, record.fixable_high, record.finding_ids) == (
        1,
        1,
        ("f1", "f2"),
    )
    assert not record.promotable
    assert inspector({"findings": [_finding("HIGH", "NO", "f3")]}, DIGEST).promotable


def _verified(**extra: object) -> dict[str, object]:
    return {"git_sha": SHA, "image_digest": DIGEST, "smoke": "passed", **extra}


def _clean() -> dict[str, object]:
    return {"image_digest": DIGEST, "promotable": True, "finding_ids": []}


def _gate(rel: dict[str, object] | None = None, **facts: object) -> list[str]:
    return gate(
        rel or GOOD,
        staging_verified=facts.get("staging", _verified()),  # type: ignore[arg-type]  # test facts
        replay=facts.get("replay", {"git_sha": SHA, "passed": True}),  # type: ignore[arg-type]  # test facts
        inspector_record=facts.get("inspector", _clean()),  # type: ignore[arg-type]  # test facts
        current_infra_sha=facts.get("infra", "e" * 40),  # type: ignore[arg-type]  # test facts
    )


def test_a_verified_replayed_clean_release_is_promotable() -> None:
    assert _gate() == []


def test_staging_must_have_verified_this_sha_and_digest_with_a_green_smoke() -> None:
    assert _gate(staging=None) == ["staging_not_verified"]
    assert _gate(staging=_verified(git_sha="f" * 40)) == ["staging_not_verified"]
    assert _gate(staging=_verified(image_digest="sha256:" + "0" * 64)) == ["staging_not_verified"]
    assert _gate(staging=_verified(smoke="failed")) == ["staging_not_verified"]


def test_replay_must_have_passed_for_this_sha() -> None:
    assert _gate(replay=None) == ["replay_not_passed"]
    assert _gate(replay={"git_sha": SHA, "passed": False}) == ["replay_not_passed"]


def test_inspector_findings_need_an_exception_naming_each() -> None:
    dirty = {"image_digest": DIGEST, "promotable": False, "finding_ids": ["f1", "f2"]}
    assert _gate(inspector=dirty) == ["inspector_unpromotable"]
    partial = {
        **GOOD,
        "inspector_exception": {"reason": "base image fix lands Monday", "finding_ids": ["f1"]},
    }
    assert _gate(partial, inspector=dirty) == ["inspector_unpromotable"]
    full = {
        **GOOD,
        "inspector_exception": {
            "reason": "base image fix lands Monday",
            "finding_ids": ["f1", "f2"],
        },
    }
    assert _gate(full, inspector=dirty) == []
    assert _gate(inspector=None) == ["inspector_missing"]


def test_a_changed_infra_sha_needs_the_hand_apply_recorded() -> None:
    assert _gate(infra="0" * 40) == ["infra_not_applied"]
    assert _gate({**GOOD, "infra_applied_sha": "e" * 40}, infra="0" * 40) == []
    assert _gate(infra=None) == []  # the first production release


def test_runtime_config_follows_the_contract() -> None:
    config = runtime_config(
        environment="staging",
        release=SHA,
        authority="https://auth.example.test",
        client_id="client_example",
        portal_base_domain="portal.example.test",
    )
    assert set(config) == {"environment", "oidc", "release", "portal_base_domain"}
    with_sentry = runtime_config(
        environment="production",
        release=SHA,
        authority="https://auth.example.test",
        client_id="client_example",
        portal_base_domain="portal.example.test",
        sentry_dsn="https://key@o0.ingest.example.test/0",
    )
    assert with_sentry["sentry"] == {
        "dsn": "https://key@o0.ingest.example.test/0",
        "tunnel": "/v1/telemetry/errors",
    }
    for bad in (
        {"authority": "http://auth.example.test"},
        {"release": "main"},
        {"environment": "dev"},
    ):
        args = {
            "environment": "staging",
            "release": SHA,
            "authority": "https://auth.example.test",
            "client_id": "client_example",
            "portal_base_domain": "portal.example.test",
            **bad,
        }
        with pytest.raises(Refused):
            runtime_config(**args)


def test_an_ops_request_is_one_allowlisted_command() -> None:
    found = ops_request(
        {
            "command": "abacus_tools.tenants status",
            "args": ["--tenant", "00000000-0000-4000-8000-000000000000"],
            "operator": "builder",
            "reason": "R1 canary key check",
        }
    )
    assert found.argv() == [
        "python",
        "-m",
        "abacus_tools.tenants",
        "status",
        "--tenant",
        "00000000-0000-4000-8000-000000000000",
    ]
    for bad in (
        {"command": "abacus_tools.tenants drop"},
        {"command": "bash -c rm"},
        {"operator": "builder@example.test"},
        {"args": "--tenant x"},
        {"reason": ""},
        {"extra": "x"},
    ):
        raw: dict[str, object] = {
            "command": "abacus_tools.schedules show",
            "args": list[str](),
            "operator": "builder",
            "reason": "check",
            **bad,
        }
        with pytest.raises(Refused):
            ops_request(raw)
