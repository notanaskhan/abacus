"""CV-2 (TASK-9001; DEC-6003; Q-01-T45; ADR-156): the tenants operator CLI. Main CI measured
`abacus_tools/tenants.py` at 69%: the database functions are proved by the provisioning suite, but
`main`'s dispatch, its refusals and the request checks never ran.

The database calls are replaced by recorders; what is held is which call each command makes, with
which role's URL and which arguments, and that each missing setting or bad argument is refused
(exit 2) before anything is written."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from abacus_tools import tenants as t

Call = tuple[str, tuple[Any, ...], dict[str, Any]]  # Any: a recorded call's arguments
REQUEST_ID = "provision-1"  # the provision request's idempotency id

FIRM = uuid.UUID("5b2f6a3e-1d2c-4e5f-8a9b-0c1d2e3f4a5b")
MODULE = t._MODULES[0]  # pyright: ignore[reportPrivateUsage] -- the CLI's module choices
OPS, OWNER, APP = "postgresql://ops", "postgresql://owner", "postgresql+asyncpg://app"


def _settings(**overrides: str | None) -> SimpleNamespace:
    values: dict[str, str | None] = {"ops": OPS, "owner": OWNER, "app": APP} | overrides
    return SimpleNamespace(
        ops_database_url=None if values["ops"] is None else SecretStr(values["ops"]),
        migrations_database_url=None if values["owner"] is None else SecretStr(values["owner"]),
        database_url=None if values["app"] is None else SecretStr(values["app"]),
    )


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    seen: list[Call] = []

    def recorder(name: str, answer: object = None):  # noqa: ANN202
        async def record(*args: Any, **kwargs: Any) -> object:  # noqa: ANN401
            seen.append((name, args, kwargs))
            return answer

        return record

    monkeypatch.setattr(t, "settings", lambda: _settings())
    monkeypatch.setattr(t, "set_entitlement", recorder("set_entitlement"))
    monkeypatch.setattr(t, "set_plan_module", recorder("set_plan_module"))
    monkeypatch.setattr(
        t, "backfill_retention_defaults", recorder("retention", {FIRM: 3, uuid.uuid4(): 2})
    )
    monkeypatch.setattr(
        t,
        "provision",
        recorder("provision", t.ProvisionOutcome(FIRM, "tenant-provisioning:x", False)),
    )
    monkeypatch.setattr(
        t, "status", recorder("status", {"tenant_id": str(FIRM), "state": "active"})
    )

    def engine(url: str) -> None:
        seen.append(("engine", (url,), {}))

    monkeypatch.setattr(t, "configure_engine", engine)

    async def dispose() -> None:
        seen.append(("dispose", (), {}))

    monkeypatch.setattr(t, "dispose_engine", dispose)
    return seen


def _allow(
    monkeypatch: pytest.MonkeyPatch, allowed: bool = True, why: tuple[str, ...] = ()
) -> None:
    verdict = SimpleNamespace(allowed=allowed, why=why, refs={"approved_by": "rowan"})

    def guard(flip: object) -> SimpleNamespace:
        del flip
        return verdict

    monkeypatch.setattr(t.flags_tool, "guard", guard)


def test_entitlement_writes_through_the_owner_role_with_the_guards_refs(
    calls: list[Call], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _allow(monkeypatch)
    code = t.main(
        [
            "entitlement",
            "--firm",
            str(FIRM),
            "--module",
            MODULE,
            "--enabled",
            "TRUE",
            "--seats",
            "10",
            "--operator",
            "rowan",
            "--reason",
            "pilot plan",
        ]
    )
    assert code == 0
    name, args, kwargs = calls[0]
    assert (name, args) == ("set_entitlement", (OWNER,))
    assert kwargs == {
        "firm": FIRM,
        "module": MODULE,
        "enabled": True,
        "seats": 10,
        "operator": "rowan",
        "reason": "pilot plan",
        "refs": {"approved_by": "rowan"},
    }
    assert capsys.readouterr().out == f"{MODULE} for {FIRM}: enabled=True seats=10\n"


def test_entitlement_refused_by_the_flip_guard_writes_nothing(
    calls: list[Call], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _allow(monkeypatch, allowed=False, why=("approved_by is required", "rollback is required"))
    code = t.main(
        [
            "entitlement",
            "--firm",
            str(FIRM),
            "--module",
            MODULE,
            "--enabled",
            "false",
            "--operator",
            "rowan",
            "--reason",
            "x",
        ]
    )
    assert code == 2 and calls == []
    assert capsys.readouterr().err == "approved_by is required, rollback is required\n"


@pytest.mark.parametrize(
    ("argv", "missing", "message"),
    [
        (
            [
                "entitlement",
                "--firm",
                str(FIRM),
                "--module",
                "{m}",
                "--enabled",
                "true",
                "--operator",
                "rowan",
                "--reason",
                "x",
            ],
            "owner",
            "migrations_database_url (the owner role) is not set",
        ),
        (
            ["retention-defaults", "--operator", "rowan"],
            "ops",
            "ops_database_url (the abacus_ops role) is not set",
        ),
        (
            ["plan-module", "--plan", "pilot", "--module", "{m}", "--operator", "rowan"],
            "ops",
            "ops_database_url (the abacus_ops role) is not set",
        ),
        (["status", "--tenant", str(FIRM)], "app", "database_url is not set"),
        (
            [
                "provision",
                "--name",
                "Canary & Co",
                "--slug",
                "canary-co",
                "--plan",
                "pilot",
                "--admins",
                "a@sink.example.test",
                "--idempotency-key",
                "provision-1",
                "--operator",
                "rowan",
            ],
            "ops",
            "ops_database_url (the abacus_ops role) is not set",
        ),
    ],
)
def test_each_command_refuses_without_its_role(
    calls: list[Call],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    missing: str,
    message: str,
) -> None:
    _allow(monkeypatch)
    monkeypatch.setattr(t, "settings", lambda: _settings(**{missing: None}))
    argv = [a.replace("{m}", MODULE) for a in argv]
    assert t.main(argv) == 2
    assert calls == []
    assert capsys.readouterr().err == f"{message}\n"


def test_retention_defaults_reports_firms_and_policies(
    calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    assert t.main(["retention-defaults", "--operator", "rowan"]) == 0
    assert calls[0] == ("retention", (OPS,), {"operator": "rowan"})
    assert capsys.readouterr().out == "2 firms, 5 policies applied\n"


def test_plan_module_passes_seats_and_minutes(
    calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    module = MODULE
    argv = [
        "plan-module",
        "--plan",
        "pilot",
        "--module",
        module,
        "--seats",
        "5",
        "--agent-minutes",
        "600",
        "--operator",
        "rowan",
    ]
    assert t.main(argv) == 0
    assert calls[0] == (
        "set_plan_module",
        (OPS,),
        {"plan": "pilot", "module": module, "seats": 5, "minutes": 600, "operator": "rowan"},
    )
    assert capsys.readouterr().out == f"plan pilot: {module} seats=5\n"


def test_provision_runs_on_the_app_engine_and_prints_the_outcome(
    calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "provision",
        "--name",
        "Canary & Co",
        "--slug",
        "canary-co",
        "--synthetic",
        "--plan",
        "pilot",
        "--admins",
        " a@sink.example.test , b@sink.example.test ,",
        "--idempotency-key",
        "provision-canary-1",
        "--operator",
        "rowan",
    ]
    assert t.main(argv) == 0
    assert [c[0] for c in calls] == ["engine", "provision", "dispose"]
    assert calls[0][1] == (APP,)
    request = calls[1][1][1]
    assert calls[1][1][0] == OPS
    assert (request.name, request.slug, request.synthetic, request.admins) == (
        "Canary & Co",
        "canary-co",
        True,
        ("a@sink.example.test", "b@sink.example.test"),
    )
    assert json.loads(capsys.readouterr().out) == {
        "tenant_id": str(FIRM),
        "workflow_id": "tenant-provisioning:x",
        "already_provisioned": False,
    }


def test_status_reads_on_the_app_engine(
    calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    assert t.main(["status", "--tenant", str(FIRM)]) == 0
    assert [c[0] for c in calls] == ["engine", "status", "dispose"]
    assert calls[1][1] == (FIRM,)
    assert json.loads(capsys.readouterr().out) == {"tenant_id": str(FIRM), "state": "active"}


@pytest.mark.parametrize("value", ["yes", "1", ""])
def test_enabled_is_true_or_false_only(value: str) -> None:
    with pytest.raises(SystemExit):
        t.main(
            [
                "entitlement",
                "--firm",
                str(FIRM),
                "--module",
                MODULE,
                "--enabled",
                value,
                "--operator",
                "rowan",
                "--reason",
                "x",
            ]
        )


GOOD = t.ProvisionRequest(
    name="Canary & Co",
    slug="canary-co",
    synthetic=True,
    plan="pilot",
    admins=("a@sink.example.test",),
    idempotency_key=REQUEST_ID,
    operator="rowan",
)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"name": "  "}, "--name is 1 to 200 characters"),
        ({"name": "x" * 201}, "--name is 1 to 200 characters"),
        ({"slug": "Canary"}, "--slug is lower-case letters, digits and '-'"),
        ({"plan": "Pilot"}, "--plan is a plan code"),
        ({"admins": ()}, "--admins is one or more email addresses, comma-separated"),
        ({"admins": ("a@b@c",)}, "--admins is one or more email addresses, comma-separated"),
        ({"admins": ("ab",)}, "--admins is one or more email addresses, comma-separated"),
        ({"idempotency_key": "short"}, "--idempotency-key is 8 to 200 characters"),
        ({"time_zone": "Mars/Olympus"}, "--time-zone is an IANA time zone"),
        (
            {"operator": "rowan@firm.example"},
            "--operator is a lower-case handle, never an email address",
        ),
    ],
)
def test_a_provision_request_is_checked_before_any_write(
    change: dict[str, Any],  # Any: a JSON change
    message: str,
) -> None:
    from dataclasses import replace

    with pytest.raises(t.Refused) as refused:
        replace(GOOD, **change).checked()
    assert str(refused.value) == message
    assert GOOD.checked() is GOOD


def test_a_dsn_drops_the_async_driver() -> None:
    assert t._dsn("postgresql+asyncpg://u@h/db") == "postgresql://u@h/db"  # pyright: ignore[reportPrivateUsage] -- the helper
    assert t._dsn("postgresql://u@h/db") == "postgresql://u@h/db"  # pyright: ignore[reportPrivateUsage] -- the helper
