"""TASK-7101 (Q-04-T008; DEC-4100): `make pilot-metrics` registers every metric source.

Found running Q-04-T050 on PF-X1: the platform writes only registered metrics (fail closed), and
the owners register on import of their api. The CLI imported only identity and platform, so a
rerun wrote nothing however much the week held. The command must register W4 to W7 before it
computes, the way the worker does.
"""

from __future__ import annotations

import importlib

from abacus.modules import MODULES
from abacus.modules.platform import pilot_metrics


def test_every_module_api_is_imported_so_w4_to_w7_register(monkeypatch: object) -> None:
    import abacus_tools.pilots as p

    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package: str | None = None) -> object:
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)  # type: ignore[attr-defined] -- an untyped monkeypatch
    p.register_metric_sources()
    assert seen == [f"abacus.modules.{m}.api" for m in MODULES]
    # The owners of W4 to W7 are among them, and once imported each has registered.
    assert {"engagements", "requests", "audit_trail", "agents"} <= set(MODULES)
    assert {"w4", "w5", "w6", "w7"} <= set(pilot_metrics._SOURCES)  # pyright: ignore[reportPrivateUsage] -- the registry under test


def test_main_registers_before_it_computes(monkeypatch: object) -> None:
    import abacus_tools.pilots as p

    calls: list[str] = []

    async def fake_compute(firm: object, week: object) -> int:
        calls.append("compute")
        return 0

    def fake_register() -> None:
        calls.append("register")

    mp = monkeypatch  # pytest's MonkeyPatch
    mp.setattr(p, "register_metric_sources", fake_register)  # type: ignore[attr-defined] -- an untyped monkeypatch
    mp.setattr(p, "compute_pilot_week", fake_compute)  # type: ignore[attr-defined] -- an untyped monkeypatch
    firm = "293fc3e7-be13-4767-ae6a-ce245b2dbda9"
    assert p.main(["metrics", "--firm", firm, "--week", "2026-09-14"]) == 0
    assert calls == ["register", "compute"]
