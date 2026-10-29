"""DEC-1011: the staging persona binder refuses anywhere but staging and refuses bad inputs before
it connects (the database refusals are covered by the integration fixture at the end review)."""

from __future__ import annotations

import pytest

from abacus_tools import staging_personas


@pytest.mark.parametrize("environment", ["local", "test", "production"])
def test_it_runs_on_staging_only(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    with pytest.raises(staging_personas.BindRefused, match="staging only"):
        staging_personas.guard_environment()


def test_main_refuses_outside_staging_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "production")
    code = staging_personas.main(
        [
            "bind",
            "--email",
            "grace@example.test",
            "--issuer",
            "https://idp.example.test",
            "--subject",
            "user_1",
            "--operator",
            "builder",
        ]
    )
    assert code == 1
    assert "staging only" in capsys.readouterr().err


def test_a_non_https_issuer_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "staging")
    with pytest.raises(staging_personas.BindRefused, match="https"):
        import asyncio

        asyncio.run(staging_personas.bind("g@example.test", "http://x.test", "user_1", "b"))
