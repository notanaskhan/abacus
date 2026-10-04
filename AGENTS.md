# AGENTS.md — the constitution

You are building an AI-native evidence platform for US audit firms: it retrieves audit evidence directly from clients' systems, screens it, and runs an engagement agent that works each engagement continuously until evidence is ready for review. Firms rely on it for confidential client financial data. Correctness, tenant isolation and auditability matter more than speed.

## Where things are

| Need | Read |
|---|---|
| What to build now | `docs/product/build-plan.md` — current phase and increment only |
| Exactly what to build | `docs/specs/SPEC-*.md` for your task |
| How to build it (binding) | `docs/adr/README.md`, then only the ADRs your task touches |
| Words to use | `docs/product/glossary.md` — never introduce synonyms |
| Who can do what | `docs/architecture/permission-matrix.yaml` |
| Patterns to copy | `docs/architecture/reference/` and `.claude/skills/` |
| Your current task | `work/tasks/TASK-*.md` — read it fully first; continue from its Handoff |

## Stack

Python 3.12+ backend (FastAPI, SQLAlchemy 2.0 async, Alembic, Temporal, Pydantic) · TypeScript React SPA (Vite, TanStack Router and Query, Tailwind, shadcn/ui) · PostgreSQL with row-level security and pgvector · S3 with Object Lock · AWS via Terraform.

## Commands — use only these

```
make setup        install toolchains and dependencies
make dev          run everything locally
make check-fast   stage 1 gates
make check        stages 1 and 2 — must pass before you claim done
make test         unit and integration tests
make evals        evaluation suites (real models; costs money)
make generate     regenerate the API client from OpenAPI
make migrate      apply migrations locally
```

## Module map

`backend/src/modules/`: identity · organisations · engagements · requests · evidence · connections · ledger · sampling · agents · audit_trail · communications · platform.
Each module exposes only `api.py`. Never import another module's internals or query its tables. Layering inside a module: `routes → service → repository`.

## Non-negotiables

1. **Every query is tenant-scoped.** Use `tenant_session(ctx)`; never open raw connections. (ADR-014)
2. **Every permission check goes through `authorise`; every list query applies `visible()`.** (ADR-020, 027)
3. **Every state change goes through the unit of work and writes an audit event.** Never call `session.commit()` directly. (ADR-007, 018)
4. **Evidence and ledger snapshots are immutable.** Create new versions; never update or delete. (ADR-004)
5. **Agents propose; humans decide.** No agent context may accept, reject, waive or confirm. (ADR-005)
6. **Every model call goes through `ai_gateway`** with a registered prompt, output schema, tier, budget and tenant. Never import provider SDKs or agent frameworks elsewhere. (ADR-019, 057)
7. **Code computes, models judge.** Never ask a model to do arithmetic on financial data. (ADR-050)
8. **Client content is hostile.** Every string from a client or client system is untrusted. (ADR-052, 064)
9. **Connectors only read.** No write operations to client systems. (ADR-040)
10. **Tag every model field with a data classification.** Never log Restricted data. (ADR-031)
11. **Workflow changes use Temporal versioning.** (ADR-090)
12. **No new dependencies** unless listed in `docs/architecture/dependency-allowlist.yaml`.
13. **Never skip, weaken or delete a test.** Never lower a threshold.
14. **Never edit protected paths** (`docs/architecture/protected-paths.md`) without an approval file from the founder.

## How you work

1. Read the task file, the spec sections it lists, and the ADRs it names. Nothing more unless the plan requires it.
2. Amber and red tasks: write a plan in the task file and **stop for approval** before coding.
3. Copy the reference pattern for anything similar that already exists.
4. Write tests that reference acceptance criteria (`test_ac3_...`). For amber and red, tests come from a separate session.
5. Small diffs. One task per session.
6. Run `make check`. Do not claim done until it passes.
7. Append to the task's progress log before ending any session, even mid-task.
8. If anything is ambiguous, contradicts an ADR, or needs a protected path: **stop and ask.** Do not guess or work around it.

## When you make a mistake twice

Tell the founder so it can become a lint rule, test or constitution line.

## Reviewers

Reviewer definitions live in `.claude/agents/` as tool-agnostic prompts: architecture, security, tests, AI. Amber and red work is reviewed by a different model from the one that wrote it.
