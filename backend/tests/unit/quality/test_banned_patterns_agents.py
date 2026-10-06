"""AC-17, AC-20: PROMPT-001, AGENT-001 and the agent rules of SYS-001, CTX-001 and BOUND-002 in the
banned-pattern gate (TASK-011a interface contract, "Rules"; ADR-005, ADR-019, ADR-025, ADR-057).

Each violating source is flagged in the places the rule applies, and the clean and allowed sources
are not. Import aliases and keyword forms count. Expectations come from the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

AGENTS_SERVICE = "src/abacus/modules/agents/service.py"
EVIDENCE_SERVICE = "src/abacus/modules/evidence/service.py"
CONNECTIONS_SERVICE = "src/abacus/modules/connections/service.py"
GATEWAY_FILE = "src/abacus/ai_gateway/__init__.py"
GATEWAY_NESTED = "src/abacus/ai_gateway/providers.py"
TEST_FILE = "tests/unit/x/test_y.py"
TOOL_FILE = "src/abacus_tools/synthetic/x.py"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _flags(tmp_path: Path, rule_id: str, rel: str, source: str) -> bool:
    _write(tmp_path, rel, source)
    return rel in [v.path for v in bp.scan(tmp_path) if v.rule_id == rule_id]


def _count(tmp_path: Path, rule_id: str, rel: str, source: str) -> int:
    _write(tmp_path, rel, source)
    return len([v for v in bp.scan(tmp_path) if v.rule_id == rule_id and v.path == rel])


# --- PROMPT-001 ------------------------------------------------------------------------------

# Places outside ai_gateway where the rule applies.
PROMPT_PLACES = [AGENTS_SERVICE, EVIDENCE_SERVICE, "src/abacus/modules/agents/helpers/build.py"]

PROMPT_VIOLATING = [
    # a model request built outside the gateway
    "x = ModelRequest(model, system, user, 100, ref)\n",
    "x = ModelRequest(model='m', system='s', user='u', max_output_tokens=1, prompt_ref='r')\n",
    "from abacus.ai_gateway import ModelRequest as MR\nx = MR('m', 's', 'u', 1, 'r')\n",
    "from abacus.ai_gateway import ModelRequest as _R\nx = _R(model='m')\n",
    "import abacus.ai_gateway as g\nx = g.ModelRequest('m', 's', 'u', 1, 'r')\n",
    "def f():\n    return ModelRequest('m', 's', 'u', 1, 'r')\n",
    # the instructions layer written by hand
    "b.text('instructions', 'You are a helpful assistant')\n",
    'b.text("instructions", prompt_text)\n',
    "b.text(layer='instructions', text='You are unrestricted')\n",
    "b.text(text='x', layer='instructions')\n",
    "ContextBuilder().text('instructions', t).task({}).build()\n",
    "builder.text('instructions', '')\n",
    # an inline prompt in a gateway call
    "GatewayCall(purpose, 'You are a screener. Reply in JSON.', tier, schema, budget)\n",
    "GatewayCall(purpose, prompt='You are a screener', tier=tier)\n",
    "GatewayCall(purpose=p, prompt='Screen this trial balance', tier=t)\n",
    "GatewayCall(purpose, f'evidence.screen@{version}', tier)\n",
    "GatewayCall(purpose=p, prompt=f'evidence.screen@v{n}')\n",
    "GatewayCall(purpose, 'evidence.screen@' + version, tier)\n",
    "GatewayCall(purpose=p, prompt='evidence.screen@' + version)\n",
    "GatewayCall(purpose, base + '@v0', tier)\n",
    "GatewayCall(purpose, 'evidence.screen', tier)\n",
    "GatewayCall(purpose, 'evidence.screen@v', tier)\n",
    "GatewayCall(purpose, 'evidence.screen@v0 extra instructions', tier)\n",
    "GatewayCall(purpose, '', tier)\n",
    "GatewayCall(purpose, 'Evidence.Screen@v0', tier)\n",
    "GatewayCall(purpose, '@v0', tier)\n",
    "GatewayCall(purpose, 'evidence.screen@V0', tier)\n",
    "GatewayCall(purpose, 7, tier)\n",
    "GatewayCall(purpose, None, tier)\n",
    "from abacus.ai_gateway import GatewayCall as GC\nGC(purpose, 'You are a screener', tier)\n",
    "from abacus.ai_gateway import GatewayCall as GC\nGC(purpose=p, prompt='You are a bot')\n",
    "from abacus.ai_gateway import GatewayCall as GC\nGC(purpose, f'a.b@{v}')\n",
    "import abacus.ai_gateway as g\ng.GatewayCall(purpose, 'inline text', tier)\n",
    "import abacus.ai_gateway as g\ng.GatewayCall(purpose=p, prompt='inline text')\n",
]
PROMPT_CLEAN = [
    # registry references, by literal or by name
    "GatewayCall(purpose, 'evidence.screen@v0', tier, schema, budget)\n",
    "GatewayCall(purpose=p, prompt='evidence.screen@v0', tier=t)\n",
    "GatewayCall(purpose, 'evidence.screen@v12', tier)\n",
    "GatewayCall(purpose, 'a.b.c@v3', tier)\n",
    "GatewayCall(purpose, spec.prompt, tier, schema, budget)\n",
    "GatewayCall(purpose=p, prompt=screener.prompt, tier=t)\n",
    "GatewayCall(purpose, PROMPT_REF, tier)\n",
    "GatewayCall(purpose, prompt_ref, tier)\n",
    "from abacus.ai_gateway import GatewayCall as GC\nGC(purpose, 'evidence.screen@v0', tier)\n",
    "from abacus.ai_gateway import GatewayCall as GC\nGC(purpose=p, prompt=spec.prompt)\n",
    # other layers are free text
    "b.text('firm', firm_text)\n",
    "b.text('engagement', f'Requested period {period}.')\n",
    "b.text('examples', examples)\n",
    "b.text(layer='engagement', text='x')\n",
    "b.text(layer, text)\n",
    "b.text(layer=name, text=value)\n",
    "b.text()\n",
    "label.text('instructions-for-use')\n",
    "ContextBuilder().task({}).build()\n",
    # other things that merely mention the words
    "x = 'instructions'\n",
    "x = {'instructions': 1}\n",
    "def text(layer):\n    return layer\n",
    "x = 'ModelRequest'\n",
    "from abacus.ai_gateway import ModelRequest\n",
    "def f(request: ModelRequest) -> None:\n    return None\n",
    "class ModelRequestLike:\n    pass\n",
    "x = GatewayCallLike('inline text')\n",
    "x = call(GatewayCall)\n",
    "GatewayCall()\n",
    "GatewayCall(purpose)\n",
]


@pytest.mark.parametrize("source", PROMPT_VIOLATING)
@pytest.mark.parametrize("rel", PROMPT_PLACES)
def test_ac20_prompt_001_flags_inline_prompts_outside_the_gateway(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "PROMPT-001", rel, source)


@pytest.mark.parametrize("source", PROMPT_CLEAN)
@pytest.mark.parametrize("rel", PROMPT_PLACES)
def test_ac20_prompt_001_allows_registry_references_and_other_layers(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "PROMPT-001", rel, source)


@pytest.mark.parametrize("source", PROMPT_VIOLATING)
@pytest.mark.parametrize("rel", [GATEWAY_FILE, GATEWAY_NESTED])
def test_ac20_prompt_001_does_not_apply_inside_the_gateway(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "PROMPT-001", rel, source)


@pytest.mark.parametrize("source", PROMPT_VIOLATING[:6])
@pytest.mark.parametrize("rel", [TEST_FILE, TOOL_FILE])
def test_ac20_prompt_001_applies_only_to_product_code(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert not _flags(tmp_path, "PROMPT-001", rel, source)


def test_ac20_prompt_001_flags_each_offending_call_once(tmp_path: Path) -> None:
    source = (
        "ModelRequest('m', 's', 'u', 1, 'r')\n"
        "b.text('instructions', 'x')\n"
        "GatewayCall(p, 'inline', t)\n"
        "GatewayCall(p, 'evidence.screen@v0', t)\n"
    )
    assert _count(tmp_path, "PROMPT-001", AGENTS_SERVICE, source) == 3


def test_ac20_prompt_001_reports_the_offending_line(tmp_path: Path) -> None:
    _write(tmp_path, AGENTS_SERVICE, "x = 1\ny = 2\nGatewayCall(p, 'inline', t)\n")
    found = [v for v in bp.scan(tmp_path) if v.rule_id == "PROMPT-001"]
    assert [(v.path, v.line) for v in found] == [(AGENTS_SERVICE, 3)]
    assert "ADR-" in str(found[0])


# --- AGENT-001 -------------------------------------------------------------------------------

# Actions the matrix never gives agents: an explicit `deny`, and no `agent` entry at all.
DENIED = ["evidence.accept", "evidence.reject", "fulfilment.confirm", "suggestion.resolve"]
NOT_GRANTED = [
    "evidence.upload",
    "request_item.mark_ready",
    "engagement.archive",
    "connection.pull",
]
AGENT_PLACES = [
    "src/abacus/modules/evidence/service.py",
    "src/abacus/modules/requests/service.py",
    "src/abacus/modules/agents/service.py",
]


def _fn(params: str, body: str, *, head: str = "async def", pad: str = "    ") -> str:
    return f"{head} f({params}):\n{pad}{body}\n"


def _call(action: str, actor: str = "ctx", fn: str = "authorise") -> str:
    return f"await {fn}({actor}, '{action}', r)"


def _violating(action: str) -> list[str]:
    kw = f"await authorise(ctx=ctx, action='{action}', resource=r)"
    alias = "from abacus.modules.identity.api import authorise as check\n"
    ident = "import abacus.modules.identity.api as ident\n"
    method = f"class S:\n    async def f(self, ctx: AgentContext, r):\n        {_call(action)}\n"
    return [
        # an agent-capable actor
        _fn("ctx: AgentContext, r", _call(action)),
        _fn("ctx: Actor, r", _call(action)),
        _fn("ctx: AuthContext | AgentContext, r", _call(action)),
        # no annotation, or an actor that is not a parameter
        _fn("ctx, r", _call(action)),
        _fn("r", _call(action, "CTX")),
        _fn("r", _call(action, "load()")),
        _fn("r", "ctx = get()\n    " + _call(action)),
        # the other parameter is the typed one
        _fn("a: AuthContext, ctx: AgentContext, r", _call(action)),
        # keyword forms
        _fn("ctx: AgentContext, r", kw),
        _fn("ctx: AgentContext, r", f"await authorise(ctx, action='{action}', resource=r)"),
        # aliases
        alias + _fn("ctx: AgentContext, r", _call(action, fn="check")),
        alias + _fn("ctx: AgentContext, r", kw.replace("authorise", "check")),
        ident + _fn("ctx: AgentContext, r", _call(action, fn="ident.authorise")),
        # methods and nested functions
        method,
        _fn(
            "ctx: AuthContext, r", _fn("c: AgentContext", _call(action, "c"), pad="        ")
        ).replace("\nasync def", "\n    async def", 1),
        _fn("ctx: AgentContext, r", f"authorise(ctx, '{action}', r)", head="def"),
    ]


def _clean(action: str) -> list[str]:
    kw = f"await authorise(ctx=ctx, action='{action}', resource=r)"
    alias = "from abacus.modules.identity.api import authorise as check\n"
    ident = "import abacus.modules.identity.api as ident\n"
    method = f"class S:\n    async def f(self, ctx: AuthContext, r):\n        {_call(action)}\n"
    return [
        _fn("ctx: AuthContext, r", _call(action)),
        _fn("ctx: SystemContext, r", _call(action)),
        _fn("r, ctx: AuthContext", _call(action)),
        _fn("*, ctx: AuthContext, r", _call(action)),
        _fn("ctx: AuthContext, r", kw),
        _fn("ctx: identity.AuthContext, r", _call(action)),
        alias + _fn("ctx: AuthContext, r", _call(action, fn="check")),
        ident + _fn("ctx: AuthContext, r", _call(action, fn="ident.authorise")),
        method,
        _fn("ctx: AuthContext, r", _call(action) + "\n    " + _call("evidence.read")),
    ]


@pytest.mark.parametrize("action", [*DENIED, *NOT_GRANTED])
@pytest.mark.parametrize("rel", AGENT_PLACES)
def test_ac17_agent_001_flags_an_agent_capable_actor_for_an_action_agents_never_hold(
    tmp_path: Path, rel: str, action: str
) -> None:
    for number, source in enumerate(_violating(action)):
        assert _flags(tmp_path, "AGENT-001", rel, source), f"case {number}: {source}"


@pytest.mark.parametrize("action", [*DENIED, *NOT_GRANTED])
@pytest.mark.parametrize("rel", AGENT_PLACES)
def test_ac17_agent_001_allows_a_human_or_system_typed_actor(
    tmp_path: Path, rel: str, action: str
) -> None:
    for number, source in enumerate(_clean(action)):
        assert not _flags(tmp_path, "AGENT-001", rel, source), f"case {number}: {source}"


# Actions an agent may be given (task scope), or a firm may grant it: any actor may be authorised.
AGENT_GRANTED = [
    "evidence.read",
    "request_item.read",
    "fulfilment.propose",
    "screening.run",
    "suggestion.create",
    "follow_up.draft",
    "support_match.run",
    "follow_up.send",
]


@pytest.mark.parametrize("action", AGENT_GRANTED)
@pytest.mark.parametrize("rel", AGENT_PLACES)
def test_ac17_agent_001_allows_any_actor_for_an_action_the_matrix_gives_agents(
    tmp_path: Path, rel: str, action: str
) -> None:
    for source in (
        f"async def f(ctx: AgentContext, r):\n    await authorise(ctx, '{action}', r)\n",
        f"async def f(ctx: Actor, r):\n    await authorise(ctx, '{action}', r)\n",
        f"async def f(ctx, r):\n    await authorise(ctx=ctx, action='{action}', resource=r)\n",
    ):
        assert not _flags(tmp_path, "AGENT-001", rel, source)


@pytest.mark.parametrize(
    "source",
    [
        "async def f(ctx: AgentContext, r, action):\n    await authorise(ctx, action, r)\n",
        "async def f(ctx: AgentContext, r):\n    await authorise(ctx, ACTION, r)\n",
        "async def f(ctx: AgentContext, r):\n    await other(ctx, 'evidence.accept', r)\n",
        "async def f(ctx: AgentContext, r):\n    await authorise(ctx)\n",
        "async def f(ctx: AgentContext, r):\n    x = 'evidence.accept'\n",
        "async def f(ctx: AgentContext, r):\n    await check_it(ctx, 'evidence.accept', r)\n",
    ],
)
def test_ac17_agent_001_ignores_calls_it_cannot_tie_to_a_denied_action(
    tmp_path: Path, source: str
) -> None:
    assert not _flags(tmp_path, "AGENT-001", AGENTS_SERVICE, source)


@pytest.mark.parametrize("rel", [TEST_FILE, TOOL_FILE, GATEWAY_FILE, "src/abacus/kernel/x.py"])
def test_ac17_agent_001_applies_only_to_module_code(tmp_path: Path, rel: str) -> None:
    source = "async def f(ctx: AgentContext, r):\n    await authorise(ctx, 'evidence.accept', r)\n"
    assert not _flags(tmp_path, "AGENT-001", rel, source)


def test_ac17_agent_001_flags_each_offending_call_once(tmp_path: Path) -> None:
    source = (
        "async def f(ctx: AgentContext, r):\n"
        "    await authorise(ctx, 'evidence.accept', r)\n"
        "    await authorise(ctx, 'evidence.reject', r)\n"
        "    await authorise(ctx, 'evidence.read', r)\n"
    )
    assert _count(tmp_path, "AGENT-001", AGENTS_SERVICE, source) == 2


def test_ac17_agent_001_reports_the_offending_line_and_an_adr(tmp_path: Path) -> None:
    _write(
        tmp_path,
        AGENTS_SERVICE,
        "async def f(ctx: AgentContext, r):\n    x = 1\n"
        "    await authorise(ctx, 'evidence.accept', r)\n",
    )
    found = [v for v in bp.scan(tmp_path) if v.rule_id == "AGENT-001"]
    assert [(v.path, v.line) for v in found] == [(AGENTS_SERVICE, 3)]
    assert "ADR-" in str(found[0])


# --- SYS-001, CTX-001 and BOUND-002 for agents -----------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "x = agent_context_for_run(tenant_id=t, run_id=r)\n",
        "from abacus.modules.identity.api import agent_context_for_run\n",
        "from abacus.modules.identity.api import agent_context_for_run as issue\nx = issue()\n",
        "import abacus.modules.identity.api as ident\nx = ident.agent_context_for_run()\n",
    ],
)
@pytest.mark.parametrize(
    "rel",
    [
        EVIDENCE_SERVICE,
        "src/abacus/modules/requests/service.py",
        "src/abacus/modules/agents/routes.py",
        "src/abacus/modules/agents/repository.py",
        "src/abacus/kernel/db/x.py",
        "src/abacus/worker/activities.py",
    ],
)
def test_ac17_sys_001_flags_issuing_an_agent_context_outside_the_agents_service(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "SYS-001", rel, source)


def test_ac17_sys_001_allows_the_agents_service_to_issue_agent_contexts(tmp_path: Path) -> None:
    source = "x = agent_context_for_run(tenant_id=t, run_id=r)\n"
    assert not _flags(tmp_path, "SYS-001", AGENTS_SERVICE, source)


def test_ac17_sys_001_does_not_let_the_connections_service_issue_agent_contexts(
    tmp_path: Path,
) -> None:
    source = "x = agent_context_for_run(tenant_id=t, run_id=r)\n"
    assert _flags(tmp_path, "SYS-001", CONNECTIONS_SERVICE, source)


@pytest.mark.parametrize(
    "source",
    [
        "x = AgentContext(tenant, 'a.b', run, eng, scope, initiator, issuer)\n",
        "x = AgentContext(tenant=t, agent_id='a.b')\n",
        "from abacus.modules.identity.api import AgentContext as AC\nx = AC(t, 'a.b')\n",
        "x = replace(agent, task_scope=frozenset({'evidence.accept'}))\n",
        "from dataclasses import replace\nx = replace(agent_ctx, engagement_id=other)\n",
        "import copy\nx = copy.copy(agent)\n",
        "import copy\nx = copy.deepcopy(ctx)\n",
        "x = AgentContext.__new__(AgentContext)\n",
    ],
)
@pytest.mark.parametrize("rel", [EVIDENCE_SERVICE, AGENTS_SERVICE])
def test_ac17_ctx_001_flags_hand_built_or_copied_agent_contexts(
    tmp_path: Path, rel: str, source: str
) -> None:
    assert _flags(tmp_path, "CTX-001", rel, source)


@pytest.mark.parametrize(
    "source",
    [
        "def f(agent: AgentContext) -> None:\n    return None\n",
        "x = isinstance(ctx, AgentContext)\n",
        "agent = await load_agent_context(tenant_id, run_id)\n",
        "x = replace(settings, debug=True)\n",
    ],
)
def test_ac17_ctx_001_ignores_using_an_agent_context(tmp_path: Path, source: str) -> None:
    assert not _flags(tmp_path, "CTX-001", AGENTS_SERVICE, source)


@pytest.mark.parametrize(
    "module", ["identity", "engagements", "organisations", "evidence", "requests"]
)
def test_ac17_bound_002_lets_agents_depend_on_its_five_modules(
    tmp_path: Path, module: str
) -> None:
    source = f"from abacus.modules.{module}.api import x\n"
    assert not _flags(tmp_path, "BOUND-002", AGENTS_SERVICE, source)


@pytest.mark.parametrize(
    "module",
    ["connections", "ledger", "sampling", "audit_trail", "communications", "platform"],
)
def test_ac17_bound_002_keeps_agents_off_every_other_module(tmp_path: Path, module: str) -> None:
    source = f"from abacus.modules.{module}.api import x\n"
    assert _flags(tmp_path, "BOUND-002", AGENTS_SERVICE, source)


def test_ac17_bound_002_flags_importing_a_module_by_dotted_name(tmp_path: Path) -> None:
    assert _flags(tmp_path, "BOUND-002", AGENTS_SERVICE, "import abacus.modules.connections.api\n")


def test_ac17_bound_002_flags_an_allowed_modules_internals_through_the_module_boundary(
    tmp_path: Path,
) -> None:
    assert _flags(
        tmp_path,
        "MODULE-001",
        AGENTS_SERVICE,
        "from abacus.modules.evidence.repository import insert\n",
    ) or _flags(
        tmp_path,
        "BOUND-001",
        AGENTS_SERVICE,
        "from abacus.modules.evidence.repository import insert\n",
    )


def test_ac17_the_agents_module_may_use_the_ai_gateway(tmp_path: Path) -> None:
    source = "from abacus.ai_gateway import call, GatewayCall\n"
    _write(tmp_path, AGENTS_SERVICE, source)
    assert [v for v in bp.scan(tmp_path) if v.path == AGENTS_SERVICE] == []
