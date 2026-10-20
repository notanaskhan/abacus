# AGENTS.md — the constitution

You are building **Accrued**: a multi-tenant practice platform for US accounting, audit, tax and client-accounting (CAS) firms, made of a firm app and a white-labelled client portal. One AI actor, the Accrued Agent, prepares work, cites its sources and waits for a named human to decide. Firms trust it with confidential client financial data and tax return information. Correctness, tenant isolation and auditability matter more than speed.

The product is "Accrued" in every UI string and document. The code namespace stays `abacus` and is never shown to users. The client portal and client emails never show "Accrued" (DEC-01, ADR-133).

One builder works through Claude Code, sequentially: setup, then phases, sprints, epics and tasks from `docs/plan/`. There are no approvals and no reviewers to wait for.

## Where things are

| Need | Read |
|---|---|
| What to build now | The current sprint in `docs/plan/07-sprint-plan.md` and its rows in `docs/plan/backlog.csv`; order and dates win from `docs/plan/01-strategy-roadmap.md`. Your task: `work/tasks/TASK-*.md` |
| What is already built | `docs/plan/status/` (`status-verified.csv`, `reconcile-2026-10.md`) and the `status` column of `docs/plan/backlog.csv` |
| An epic in full | `docs/plan/epics/<ID>.md` and `<ID>.tasks.csv` |
| Decisions that bind you | `docs/plan/09-decisions-adrs.md` (DEC-nn, P-nn) and `docs/product/decision-log.md` (arrives with F-02, S0) |
| Exactly what to build | `docs/specs/SPEC-*.md`; for a screen, its screen contract `docs/screens/<ID>.md` (arrive with each screen epic's first task) |
| How to build it (binding) | `docs/adr/README.md`, then only the ADRs your task touches |
| What a screen looks like | `$ACCRUED_HANDOFF_DIR/handoff/screens/<ID> <name>/` (`README.md`, `spec.md`, `revision.md`; revision wins over spec). Read-only |
| Product source of truth | `$ACCRUED_BLUEPRINT_DIR/accrued-blueprint/01-platform-blueprint.md` (§3.3.1 status words, §4 navigation, §9 seed) |
| Out of scope | Scope decisions D1–D10 and exclusions X-01…X-08 (`$ACCRUED_BLUEPRINT_DIR/Accrued-Scope-Decision-Record/`; DEC-19) |
| Words to use | `docs/product/glossary.md` — never introduce synonyms. Status words: `docs/product/status-vocabulary.yaml` (arrives with F-03, S0) |
| Who can do what | `docs/architecture/permission-matrix.yaml` |
| API contracts | `docs/contracts/<name>.md` and `backend/tests/contracts/` (arrive with F-03, S1) |
| Patterns to copy | `docs/architecture/reference/` and `.claude/skills/` |
| What agents must not touch | `docs/architecture/protected-paths.md` |

## Stack

Python 3.12+ backend (FastAPI, SQLAlchemy 2.0 async, Alembic, Temporal, Pydantic) · TypeScript React SPA (Vite, TanStack Router and Query, Tailwind with the Accrued tokens, Geist) · PostgreSQL with row-level security and pgvector · S3 with Object Lock · AWS via Terraform.

## Commands — use only these

```
make setup          install toolchains and dependencies
make dev            run everything locally
make dev-fixtures   run the frontend alone on fixtures: no Docker, no backend
make seed           dev firm and users for local sign-in
make check-fast     stage 1 gates
make check          stages 1 and 2 — must pass before you claim done
make test           unit and integration tests
make e2e            the Playwright journey (needs make dev and make seed)
make evals          evaluation suites (real models; costs money)
make generate       regenerate the API client from OpenAPI
make regenerate     regenerate every generated file
make migrate        apply migrations locally
```

## Module map

`backend/src/abacus/modules/`: identity · organisations · engagements · requests · evidence · connections · ledger · sampling · fieldwork · agents · audit_trail · communications · notifications · platform. The plan's module map (DEC-13) adds modules as their epics land.
Each module exposes only `api.py`. Never import another module's internals or query its tables. Layering inside a module: `routes → service → repository`.
The shared kernel (`abacus.kernel`: db sessions, tenant context, unit of work, outbox, encryption, config, logging) is not a module; modules use it, it never imports a module. Tooling lives in `abacus_tools` and is never imported by `abacus`. (ADR-101)

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
14. **Never write secrets, hand-edit generated files or edit a migration already on `main`.** See `docs/architecture/protected-paths.md`. The repository is public.
15. **Contract first.** A new or changed endpoint starts as a stub with its contract, then the generated client (`make generate`), then the implementation.
16. **Content belongs in the database.** Firm content (templates, programs, organizers, email and letter templates, rules tables, standards, library agents) loads through admin screens or import endpoints. The seed writes only the synthetic Brightwater Hale tenant. Never put firm content in constants, migrations or seed code.
17. **Never point a local build, migration or seed at a hosted database**, and never run a local production build while a hosted build uses the same database.
18. **Stay inside D1–D10 and X-01…X-08** (DEC-19). Thirteen navigation items. One agent, attributed "‹person› via Agent". No peer benchmarks. No licensed publisher text. Single audit stays "Coming soon".

## Frontend rules

1. Tokens only: no literal colours, sizes or shadows; Geist 400 and 500 only.
2. Agent text only through `AgentText`; never raw, never `dangerouslySetInnerHTML`.
3. Approve, Sign off, Release, Send, Post and Decide never appear on an agent-owned control.
4. Data only through the generated client.
5. Copy, names and numbers come verbatim from the handoff and blueprint. Never invent data; never port kit sample data.
6. Every screen ships every artboard state as a fixture scenario with a test.
7. Portal code never renders "Accrued".

## How you work

1. Read the task file, the spec or screen contract it names, and the ADRs it names. Nothing more unless the plan requires it.
2. Before building, search `docs/product/decision-log.md` and `docs/plan/09-decisions-adrs.md` for the task's screen IDs and modules. If a decision is open, decide it with the plan's proposed option, record it in `docs/product/decision-log.md` (or a new ADR), and carry on. Ask only when no option is written down. Where any file in `docs/plan/` says to stop, wait for approval, a reviewer, a merge window or a decision meeting, `docs/plan/AMENDMENT-solo.md` overrides it: decide, record and carry on.
3. Amber and red tasks: write the plan into the task file first (files, migrations, registry and flag edits, tests, rollback), then build.
4. Write the acceptance tests first, from the spec (`test_ac3_...`), then implement until they pass.
5. Copy the reference pattern for anything similar that already exists. Small diffs. One task per session.
6. Numbers: take the next free SPEC, ADR, TASK or migration number on `main`.
7. Run `make check`. Do not claim done until it passes. Work on a short branch; merge once it is green.
8. Append to the task's progress log before ending any session, even mid-task.
9. Outside D1–D10, or contradicting an accepted ADR: say so in the task file and propose a new ADR rather than working around it.

## When you make a mistake twice

Say so in the task file's progress log so it can become a lint rule, test or constitution line.

## Reviewers

Reviewer definitions live in `.claude/agents/` as tool-agnostic prompts: architecture, security, tests, AI. Use them for an optional self-review of amber and red work before merging.
