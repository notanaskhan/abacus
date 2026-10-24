# ac-test-author: ayushkbhatia
"""F-04-T36: independent AC tests (ADR-078) for N's red F-04 tasks T11, T17, T18, T19 and T28.

The rows promise: the scanner fake's verdict injection (T18) and the fake-model registry (T19)
are refused outside the synthetic environments (local, test, evaluation), so never on staging or
production, and the EICAR and archive-bomb verdicts are unchanged whatever is injected; CLOCK-001
(T17) fails on a new direct `now()` outside `kernel/clock.py` and passes on main, which is also
T11's "every red-zone now() uses clock.now or system_now"; business time follows `kernel.clock`
(frozen in a replay) while `system_now` stays real for security windows (T11); and no CI job
points at a hosted database (T28). The ESLint half of T17 is
`apps/web/src/lint/f04t36-clock.test.ts`.

Boundary: the public functions of `kernel.scanning`, `kernel.clock`, `ai_gateway.FakeModel`, the
scenario response loader and `banned_patterns.scan`, and the workflow files as data.
Expectations from the F-04 rows and ADR-143, never from the bodies.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from abacus.ai_gateway import FakeModel
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.scanning import (
    InjectionRefused,
    LocalScanner,
    forget_injected,
    inject_verdict,
)
from abacus_tools.quality import banned_patterns as bp

REPO: Final = Path(__file__).resolve().parents[4]
BACKEND: Final = REPO / "backend"
EICAR: Final = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
NOT_SYNTHETIC: Final = ("staging", "production")


def _sha(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _bomb() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
        archive.writestr("xl/worksheets/sheet1.xml", bytes(8 * 1024 * 1024))
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def clean() -> Iterator[None]:
    forget_injected()
    yield
    forget_injected()
    settings.cache_clear()


# What a deployed environment must configure before settings load; fake values, as
# tests/unit/api/test_app_gates.py has them.
DEPLOYED: Final = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "RELAY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_ISSUER": "https://idp.example.test",
    "IDENTITY_AUDIENCE": "abacus-api",
    "IDENTITY_JWKS": '{"keys": []}',
    "S3_ENDPOINT_URL": "http://s3.example.test",
    "S3_ACCESS_KEY": "k",
    "S3_SECRET_KEY": "s",
    "TEMPORAL_TARGET": "t:7233",
    "TRUSTED_HOSTS": "api.example.test",
    "KMS_PLATFORM_KEY_ALIAS": "alias/abacus/platform",
    "TEMPORAL_PAYLOAD_KEYS": '{"platform-v1": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs"}',
    "TEMPORAL_PAYLOAD_CURRENT": "platform-v1",
    "SCANNER_ENDPOINT": "scanner.abacus.internal:3310",
    "SES_CONFIGURATION_SET": "abacus-staging",
    "SES_FROM_ADDRESS": "notifications@mail.example.test",
    "TEMPORAL_PAYLOAD_KEY": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
    "TEMPORAL_TLS": "true",
    "TEMPORAL_API_KEY": "test-temporal-api-key",
    "EVIDENCE_BUCKET": "test-evidence-bucket",
}


def _environment(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", name)
    if name in NOT_SYNTHETIC:
        for key, value in DEPLOYED.items():
            monkeypatch.setenv(f"ABACUS_{key}", value)
    settings.cache_clear()
    assert settings().environment == name


# --- T18: the scanner fake -----------------------------------------------------------------------


@pytest.mark.parametrize("environment", NOT_SYNTHETIC)
def test_t18_verdict_injection_is_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    with pytest.raises(InjectionRefused):
        inject_verdict(_sha(b"a statement"), "infected")


@pytest.mark.parametrize("environment", ["local", "test", "evaluation"])
def test_t18_injected_verdicts_are_what_the_scanner_answers_in_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    infected, broken, plain = b"infected one", b"broken one", b"plain one"
    inject_verdict(_sha(infected), "infected")
    inject_verdict(_sha(broken), "error")
    scanner = LocalScanner()
    assert scanner.scan(infected).clean is False
    assert scanner.scan(infected).reason == "malware"
    assert scanner.scan(broken).clean is False
    assert scanner.scan(plain).clean is True


def test_t18_no_injection_clears_eicar_or_a_bomb() -> None:
    """The existing checks come first: a 'pending' (then clean) verdict changes nothing."""
    bomb = _bomb()
    for content in (EICAR, bomb):
        inject_verdict(_sha(content), "pending", delay_seconds=0.0)
    scanner = LocalScanner()
    assert (scanner.scan(EICAR).clean, scanner.scan(EICAR).reason) == (False, "malware")
    assert (scanner.scan(bomb).clean, scanner.scan(bomb).reason) == (False, "archive_bomb")


def test_t18_an_injection_is_bounded() -> None:
    with pytest.raises(ValueError):
        inject_verdict(_sha(b"x"), "pending", delay_seconds=11.0)
    with pytest.raises(ValueError):
        inject_verdict(_sha(b"x"), "clean")  # type: ignore[arg-type]  # not a verdict: refused


# --- T19: the fake-model registry ----------------------------------------------------------------


@pytest.mark.parametrize("environment", NOT_SYNTHETIC)
def test_t19_the_fake_model_is_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    with pytest.raises(RuntimeError):
        FakeModel()


def test_t19_recorded_responses_are_keyed_by_prompt_and_a_sha256() -> None:
    fake = FakeModel()
    fake.record("evidence.screen@v0", _sha(b"doc"), '{"action": "none"}')
    with pytest.raises(ValueError):
        fake.record("evidence.screen@v0", "not-a-digest", "{}")


def test_t19_the_scenario_responses_load_from_data_files() -> None:
    from abacus_tools.synthetic.scenarios.brightwater_hale import responses

    loaded = responses.load()
    assert loaded, "the E0 set has responses"
    for prompt_ref, digest, _text in loaded:
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+@v\d+", prompt_ref), prompt_ref
        assert re.fullmatch(r"[0-9a-f]{64}", digest), digest
    files = sorted(p.name for p in responses.DIRECTORY.glob("*.json"))
    assert len(files) == len(loaded)  # one data file per response, nothing from code
    assert responses.install(FakeModel()) is not None


# --- T17 and T11: CLOCK-001 ----------------------------------------------------------------------

DIRECT_NOW: Final = (
    "from datetime import datetime\nx = datetime.now()\n",
    "import datetime\nx = datetime.datetime.utcnow()\n",
    "from datetime import date\nx = date.today()\n",
    "import time\nx = time.time()\n",
)


@pytest.mark.parametrize("source", DIRECT_NOW)
@pytest.mark.parametrize(
    "where",
    [
        "src/abacus/modules/evidence/service.py",
        "src/abacus/modules/identity/service.py",
        "src/abacus/modules/agents/runs.py",
        "src/abacus/ai_gateway/budget.py",
        "src/abacus/modules/connections/service.py",
    ],
)
def test_t17_clock001_fails_on_a_new_direct_now_in_a_red_module(
    tmp_path: Path, where: str, source: str
) -> None:
    path = tmp_path / where
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    assert "CLOCK-001" in [v.rule_id for v in bp.scan(tmp_path)]


def test_t17_clock001_allows_the_clock_itself_and_its_two_doors(tmp_path: Path) -> None:
    kernel = tmp_path / "src/abacus/kernel/clock.py"
    kernel.parent.mkdir(parents=True)
    kernel.write_text("from datetime import datetime, UTC\nx = datetime.now(UTC)\n", "utf-8")
    module = tmp_path / "src/abacus/modules/evidence/service.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "from abacus.kernel import clock\n"
        "async def f(t):\n    return await clock.now(t), clock.system_now()\n",
        "utf-8",
    )
    assert "CLOCK-001" not in [v.rule_id for v in bp.scan(tmp_path)]


def test_t11_t17_main_has_no_direct_now_anywhere_in_src() -> None:
    found = [v for v in bp.scan(BACKEND) if v.rule_id == "CLOCK-001"]
    assert found == []


# --- T11: business time and security time --------------------------------------------------------


async def test_t11_business_time_follows_the_kernel_clock_and_security_time_stays_real() -> None:
    replay = datetime(2026, 9, 14, 14, 41, tzinfo=UTC)
    tenant = TenantContext(uuid.uuid4(), "system", "f04t36")
    with clock.frozen(replay):
        assert await clock.now(tenant) == replay
        assert await clock.now() == replay
        real = clock.system_now()
    assert abs(real - datetime.now(UTC)) < timedelta(seconds=5)  # MFA, TTL and locks read this
    assert real.tzinfo is not None
    with pytest.raises(ValueError), clock.frozen(datetime(2026, 9, 14, 9, 41)):  # needs a zone
        pass


# --- T28: no CI job points at a hosted database --------------------------------------------------

_DB_NAME: Final = re.compile(
    r"(DATABASE|POSTGRES|PG(HOST|URL|PASSWORD)|SUPABASE|_DSN\b|DB_URL)", re.I
)
_LOCAL_HOSTS: Final = ("127.0.0.1", "localhost", "postgres", "db", "[::1]")


def _env_entries(node: object, path: str = "") -> Iterator[tuple[str, str, str]]:
    """Every (where, name, value) under an `env:` mapping anywhere in a workflow."""
    if isinstance(node, dict):
        mapping = cast(dict[object, object], node)
        for key, value in mapping.items():
            here = f"{path}/{key}"
            if key == "env" and isinstance(value, dict):
                for name, setting in cast(dict[object, object], value).items():
                    yield here, str(name), str(setting)
            else:
                yield from _env_entries(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(cast(list[object], node)):
            yield from _env_entries(value, f"{path}[{index}]")


def _hosted_db_problems(workflows: list[Path]) -> list[str]:
    found: list[str] = []
    for workflow in workflows:
        loaded = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for where, name, value in _env_entries(loaded):
            if _DB_NAME.search(name) and "secrets." in value:
                found.append(f"{workflow.name}{where}: {name} comes from a secret")
            for url in re.findall(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]+", value):
                host = url.split("@")[-1].split("/")[0].split(":")[0]
                if host not in _LOCAL_HOSTS:
                    found.append(f"{workflow.name}{where}: {name} points at {host}")
        text = workflow.read_text(encoding="utf-8")
        for match in re.finditer(r"secrets\.([A-Z0-9_]+)", text):
            if _DB_NAME.search(match.group(1)):
                found.append(f"{workflow.name}: reads secrets.{match.group(1)}")
    return found


def test_t28_no_ci_job_points_at_a_hosted_database() -> None:
    workflows = sorted((REPO / ".github/workflows").glob("*.yml"))
    assert workflows
    assert _hosted_db_problems(workflows) == []


def test_t28_the_check_catches_a_job_that_would(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        "jobs:\n  seed:\n    env:\n"
        "      ABACUS_DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}\n"
        "      OTHER: postgresql://app@db.example-hosted.test:5432/abacus\n",
        encoding="utf-8",
    )
    found = _hosted_db_problems([bad])
    assert any("comes from a secret" in p for p in found)
    assert any("db.example-hosted.test" in p for p in found)
