# ac-test-author: ayushkbhatia
"""Q-02-T52 (ADR-078) for Q-02-T32: Q-02 AC-19 to AC-22 on the `pii_kind` grammar.

The chapter 06 security-suite file `test_classification_scrubbing.py` ("no Restricted or TRI value
in logs, Sentry or metric attributes", ADR-031), written on ADR-167's grammar. Each promise is
proved against a seeded violation (Q-02-T52's acceptance):
- AC-19: a `tri`, `phi` or `pii_kind` flag on a level other than `restricted` fails at import, and
  a flag set by hand beside a lower level is reported by the classification check; a tagged field
  carries its flag in its JSON schema and `pii_paths` finds it, nested and in containers.
- AC-20: `mask()` per kind (DEC-295: `tin` keeps the last four, `bank_account` the last four
  characters, `date_of_birth` and `ip_pin` show nothing, not even length).
- AC-21: an unmasked TIN taken from a tagged model into a log line, a Sentry event and a metric
  attribute is gone from what leaves the process.
- AC-22: an unmasked SSN, ITIN or EIN that passes the validity rules, put into a model call's
  context, never reaches the network stub: refused with `pii_in_context`, audited without the
  value, never retried or rerouted.

Later decisions followed: DEC-295 (the level's schema key stays `cls`, the flag keys are `x-tri`,
`x-phi`, `x-pii-kind`; the members include `ip_pin`; the part names). The repository is public, so
the only TIN literal is a 9xx ITIN form; the SSN and EIN are assembled at run time.
Boundary: `kernel.classification`, the kernel logger, `error_tracking.scrub` (Sentry's
`before_send`), the kernel's scrubbing meter and `ai_gateway.call` on the migrated database (the
refusal's audit row is read back from `audit_events`).
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import re
import sys
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from pydantic import BaseModel, Field
from pydantic.config import JsonDict
from sentry_sdk.types import Event

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    DataBoundaryRefused,
    FakeModel,
    GatewayCall,
    ModelRequest,
    call,
    configure_provider,
)
from abacus.kernel.classification import (
    PII_KINDS,
    classified,
    flag_errors,
    flags_of,
    mask,
    phi_paths,
    pii_paths,
    tri_paths,
)
from abacus.kernel.db import TenantContext
from abacus.kernel.error_tracking import scrub
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import ScrubbingMeter, meter
from abacus.modules.requests.questionnaires_contract import AnswerIn
from abacus.modules.tax.k1_contract import K1BoxLineOut

from .support import Seeder

ITIN = "900-70-1234"  # 9xx area, middle pair 70: a valid ITIN, never an SSN (ADR-085)
SSN = "-".join(("5" + "12", "3" + "4", "56" + "71"))  # area 512, group 34, serial 5671: valid
EIN = "-".join(("4" + "1", "23" + "45678"))  # prefix 41 is assigned: valid
PROMPT = "evidence.screen@v0"
AGENT = "test.t52_scrubbing"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _leaks(text: str, *values: str) -> list[str]:
    """Each value found in `text`, as written or as its bare nine digits."""
    return [v for v in values if v in text or _digits(v) in _digits_runs(text)]


def _digits_runs(text: str) -> set[str]:
    return set(re.findall(r"\d{9}", re.sub(r"[\s\-./]", "", text)))


class Payee(BaseModel):
    name: Annotated[str, classified("confidential")]
    tin: Annotated[str, classified("restricted", pii_kind="tin")]


class Return(BaseModel):
    payee: Annotated[Payee, classified("restricted", tri=True)]
    payees: Annotated[list[Payee], classified("restricted", tri=True)]
    diagnosis: Annotated[str | None, classified("restricted", phi=True)] = None


# --- AC-19: the flags force Restricted ----------------------------------------------------------


@pytest.mark.parametrize("level", ["confidential", "internal", "public"])
@pytest.mark.parametrize("flag", ["tri=True", "phi=True", 'pii_kind="tin"'])
def test_ac19_a_flag_below_restricted_fails_at_import(
    tmp_path: Path, level: str, flag: str
) -> None:
    module = tmp_path / f"seeded_{level}_{abs(hash(flag))}.py"
    module.write_text(
        "from typing import Annotated\n"
        "from pydantic import BaseModel\n"
        "from abacus.kernel.classification import classified\n\n"
        "class Seeded(BaseModel):\n"
        f'    value: Annotated[str, classified("{level}", {flag})]\n'
    )
    spec = importlib.util.spec_from_file_location(module.stem, module)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[module.stem] = loaded
    try:
        with pytest.raises(ValueError):
            spec.loader.exec_module(loaded)
    finally:
        sys.modules.pop(module.stem, None)


@pytest.mark.parametrize("flag", [{"x-tri": True}, {"x-phi": True}, {"x-pii-kind": "tin"}])
def test_ac19_a_flag_set_by_hand_beside_a_lower_level_is_reported(flag: JsonDict) -> None:
    class HandSet(BaseModel):
        value: Annotated[str, Field(json_schema_extra={"cls": "confidential", **flag})]

    assert flag_errors(HandSet), flag


def test_ac19_an_unknown_pii_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        classified("restricted", pii_kind=cast("object", "passport"))  # type: ignore[arg-type]  # seeded: not a member


def test_ac19_the_schema_carries_the_level_and_the_flag() -> None:
    field = Payee.model_json_schema()["properties"]["tin"]
    assert field["cls"] == "restricted"
    assert field["x-pii-kind"] == "tin"
    assert "x-tri" not in field and "x-phi" not in field
    assert flags_of(Payee.model_fields["tin"]).pii_kind == "tin"
    name = Payee.model_json_schema()["properties"]["name"]
    assert name["cls"] == "confidential"
    assert not any(key.startswith("x-") for key in name)  # an unflagged field's tag is unchanged
    assert flag_errors(Payee) == [] and flag_errors(Return) == []


def test_ac19_pii_paths_finds_the_field_nested_and_in_containers() -> None:
    assert pii_paths(Payee, "tin") == ("tin",)
    assert set(pii_paths(Return, "tin")) == {"payee.tin", "payees.tin"}
    assert pii_paths(Return, "bank_account") == ()
    assert set(tri_paths(Return)) == {"payee", "payees"}
    assert phi_paths(Return) == ("diagnosis",)
    instance = Return(payee=Payee(name="A", tin=ITIN), payees=[])
    assert set(pii_paths(instance, "tin")) == {"payee.tin", "payees.tin"}


def test_ac19_the_initial_members() -> None:
    assert {"tin", "bank_account", "date_of_birth", "ip_pin"} <= set(PII_KINDS)


# --- AC-20: one mask per kind -------------------------------------------------------------------


def test_ac20_a_tin_keeps_its_last_four() -> None:
    assert mask("900-45-6789", "tin") == "•••-••-6789"
    for value in (ITIN, SSN, EIN, _digits(SSN)):
        masked = mask(value, "tin")
        assert masked.endswith(value[-4:])
        assert _digits(masked) == value[-4:], (value, masked)


def test_ac20_a_bank_account_keeps_its_last_four() -> None:
    masked = mask("000012345678", "bank_account")
    assert masked.endswith("5678")
    assert _digits(masked) == "5678"


@pytest.mark.parametrize("kind", ["ip_pin", "date_of_birth"])
def test_ac20_ip_pin_and_date_of_birth_mask_fully(kind: str) -> None:
    values = ("123456", "12345") if kind == "ip_pin" else ("1980-01-02", "01/02/1980")
    masks = {mask(v, cast("object", kind)) for v in values}  # type: ignore[arg-type]  # kind is a member
    assert len(masks) == 1, masks  # not even the length shows
    assert not any(ch.isdigit() for ch in masks.pop())


# --- AC-21: logs, Sentry and metrics ------------------------------------------------------------


def test_ac21_a_tin_from_a_tagged_model_is_scrubbed_from_a_log_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payee = Payee(name="Seeded payee", tin=SSN)
    log = get_logger("abacus.t52")
    log.info("payee.checked", note=f"payee tin {payee.tin} checked", other=f"ein {EIN}")
    log.warning(f"payee {payee.tin} failed")  # the event string itself
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "payee.checked" in out
    assert _leaks(out, SSN, EIN) == []


def test_ac21_a_tagged_model_given_to_the_logger_never_shows_its_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-031: Restricted values are never logged; a model holding one is refused or dropped."""
    payee = Payee(name="Seeded payee", tin=ITIN)
    with contextlib.suppress(TypeError, ValueError):  # refused is as good as dropped
        get_logger("abacus.t52").info("payee.checked", payee=cast("object", payee))
    captured = capsys.readouterr()
    assert _leaks(captured.out + captured.err, ITIN) == []


def test_ac21_a_tin_from_a_tagged_model_is_scrubbed_from_a_sentry_event() -> None:
    payee = Payee(name="Seeded payee", tin=SSN)
    message = f"could not match payee {payee.tin} (EIN {EIN}, ITIN {ITIN})"
    event = cast(
        Event,
        {
            "event_id": uuid.uuid4().hex,
            "level": "error",
            "message": message,
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": message,
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "abacus.t52",
                                    "function": "match",
                                    "lineno": 1,
                                    "in_app": True,
                                    "filename": f"payee_{_digits(SSN)}.py",
                                    "vars": {"tin": payee.tin},
                                }
                            ]
                        },
                    }
                ]
            },
            "tags": {"route": f"/v1/payees/{payee.tin}", "error_type": "ValueError"},
            "extra": {"payee": payee.model_dump()},
            "breadcrumbs": {"values": [{"message": message}]},
        },
    )
    kept = scrub(event)
    text = json.dumps(kept, ensure_ascii=False, default=str)
    assert _leaks(text, SSN, EIN, ITIN) == [], text


def _points(reader: InMemoryMetricReader) -> list[dict[str, object]]:
    data = reader.get_metrics_data()
    assert data is not None
    return [
        dict(point.attributes or {})
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        for point in metric.data.data_points
    ]


def test_ac21_a_tin_from_a_tagged_model_is_scrubbed_from_a_metric_attribute() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    try:
        scrubbing = ScrubbingMeter(provider.get_meter("abacus.t52"))
        payee = Payee(name="Seeded payee", tin=SSN)
        scrubbing.create_counter("t52.refusals").add(1, {"reason": f"payee {payee.tin}"})
        scrubbing.create_histogram("t52.seconds").record(0.5, {"outcome": f"ein {EIN}"})
        points = _points(reader)
    finally:
        provider.shutdown()
    assert points
    assert _leaks(json.dumps(points, default=str), SSN, EIN) == []


def test_ac21_product_code_gets_the_scrubbing_meter() -> None:
    assert isinstance(meter("abacus.t52"), ScrubbingMeter)


# --- AC-22: the gateway refuses an unmasked TIN before the network -------------------------------


class Verdict(BaseModel):
    ok: Annotated[bool, classified("internal")]


@pytest.fixture
def stub() -> Iterator[list[ModelRequest]]:
    """The network stub: every request that reaches the provider is kept here."""
    seen: list[ModelRequest] = []

    def responder(request: ModelRequest) -> str:
        seen.append(request)
        return '{"ok": true}'

    configure_provider(FakeModel({PROMPT: responder}))
    yield seen
    configure_provider(None)


async def _firm(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID]:
    """A firm and the person its agent acts for (INV-5: an agent's audit row names a person)."""
    tenant_id = await seed.firm()
    return tenant_id, (await seed.person(tenant_id)).user_id


def _gateway_call(
    firm: tuple[uuid.UUID, uuid.UUID], context: AssembledContext
) -> GatewayCall[Verdict]:
    tenant_id, person = firm
    run_id = uuid.uuid4()
    return GatewayCall(
        purpose="screen a document",
        prompt=PROMPT,
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",
        essential=True,
        routes=("bedrock", "direct"),
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(tenant_id, "agent", f"agent:{AGENT}:{run_id}", person),
            None,
            AGENT,
            None,  # no agent_runs row: the usage record of a call that is sent names none
        ),
        context=context,
    )


def _context(where: str, value: str) -> AssembledContext:
    builder = ContextBuilder()
    if where in ("firm", "engagement", "examples"):
        builder.text(where, f"The client's number is {value}.")
        return builder.task({"balanced": True}).build()
    if where == "untrusted":
        return builder.task(
            {"balanced": True, "document": {"lines": ["1099-NEC", f"recipient {value}"]}},
            untrusted=("document",),
        ).build()
    return builder.task({"balanced": True, "payee": {"tin": value}}).build()


async def _refusals(seed: Seeder, tenant_id: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT row_to_json(a)::text AS row FROM audit_events a "
        "WHERE tenant_id = $1 AND action = 'ai.boundary_refused'",
        tenant_id,
    )
    return [str(r["row"]) for r in rows]


@pytest.mark.parametrize(
    "value", [SSN, ITIN, EIN, _digits(SSN)], ids=["ssn", "itin", "ein", "bare"]
)
@pytest.mark.parametrize("where", ["firm", "engagement", "examples", "task", "untrusted"])
async def test_ac22_an_unmasked_tin_never_reaches_the_network_stub(
    seed: Seeder,
    stub: list[ModelRequest],
    capsys: pytest.CaptureFixture[str],
    value: str,
    where: str,
) -> None:
    firm = await _firm(seed)
    tenant_id = firm[0]
    with pytest.raises(DataBoundaryRefused) as refused:
        await call(_gateway_call(firm, _context(where, value)))
    assert refused.value.reason == "pii_in_context"
    assert stub == []  # not sent, not retried, not rerouted to the second route
    audited = await _refusals(seed, tenant_id)
    assert len(audited) == 1
    captured = capsys.readouterr()
    for text in (str(refused.value), audited[0], captured.out + captured.err):
        assert _leaks(text, value) == [], text


async def test_ac22_a_refused_call_is_refused_again_and_never_retried(
    seed: Seeder, stub: list[ModelRequest]
) -> None:
    firm = await _firm(seed)
    tenant_id = firm[0]
    for _ in range(3):
        with pytest.raises(DataBoundaryRefused):
            await call(_gateway_call(firm, _context("task", SSN)))
    assert stub == []
    assert len(await _refusals(seed, tenant_id)) == 3  # one per call: no hidden retry


@pytest.mark.parametrize("value", [mask(SSN, "tin"), "XXX-XX-" + SSN[-4:], SSN[-4:]])
async def test_ac22_a_masked_tin_is_not_refused_for_pii(
    seed: Seeder, stub: list[ModelRequest], value: str
) -> None:
    firm = await _firm(seed)
    answer = await call(_gateway_call(firm, _context("task", value)))
    assert answer is not None
    assert len(stub) == 1  # the masked form reached the stub
    assert await _refusals(seed, firm[0]) == []


# --- T-02-T30 (TASK-2533): K-1 and organizer values never reach a log line ----------------------
# Written from T-02 §3.8 and `docs/contracts/k1-packages.md` §3: a K-1's box amounts and an
# organizer's answers are TRI; ADR-031 keeps Restricted values out of logs, whatever model holds
# them. The amounts are nine digits so the bare-digits check sees them too.

K1_AMOUNT = "731337042"
ANSWER = "Brokerage 1099-B 518204736"


def test_t02t30_a_k1_box_line_given_to_the_logger_never_shows_its_amount(
    capsys: pytest.CaptureFixture[str],
) -> None:
    line = K1BoxLineOut(
        document_kind="k1",
        box_code="2",
        description="Net rental real estate income",
        amount=Decimal(K1_AMOUNT),
        is_total=False,
    )
    with contextlib.suppress(TypeError, ValueError):  # refused is as good as dropped
        get_logger("abacus.t02t30").info("k1.read", line=cast("object", line))
    captured = capsys.readouterr()
    assert _leaks(captured.out + captured.err, K1_AMOUNT) == []


def test_t02t30_an_organizer_answer_given_to_the_logger_never_shows_its_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    answer = AnswerIn(value=ANSWER)
    with contextlib.suppress(TypeError, ValueError):
        get_logger("abacus.t02t30").info("answer.saved", answer=cast("object", answer))
    captured = capsys.readouterr()
    assert _leaks(captured.out + captured.err, ANSWER) == []
