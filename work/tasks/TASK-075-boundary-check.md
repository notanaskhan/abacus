---
id: TASK-075
title: "Data boundary, part 1: the provider terms register, settings, the five-part check, agent clearance and usage basis"
spec: SPEC-036
acceptance_criteria: [AC-1, AC-2, AC-4, AC-8]
risk_zone: red
status: done
branch: task-075-boundary-check
worktree:
created: 2026-10-16
updated: 2026-10-16
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-036 §7, TASK-075. Code learns what may lift the boundary:
- the provider terms register (ADR-114), compiled into the gateway;
- settings that allow `client_data` only where the register covers Bedrock;
- the five-part check on every real-route call, with a reason code for each refusal;
- `client_data` clearance in agent specs;
- each usage record saying which basis allowed it.

Nothing opens yet. The register starts empty and no agent is cleared. Opt-in, stages and engagement exclusion arrive in TASK-076, and until then their checks refuse.

## Scope
SPEC-036 AC-1, AC-2 (all five conditions, with TASK-076's three as fail-closed registrations), AC-4 and AC-8; the ADR superseding ADR-112.

## Context to load
- Spec: `docs/specs/SPEC-036-data-boundary.md`; ADR-031, ADR-112, ADR-113, ADR-114; SPEC-026; SPEC-010 (routes, admission, failover)
- Code:
  - `ai_gateway/boundary.py` (`enforce_boundary`, the synthetic registration);
  - `ai_gateway/__init__.py` (`call`: admission, the route loop, `enforce_boundary`, the usage inserts);
  - `kernel/config.py` (`model_data_boundary`, `_real_models_synthetic_only`);
  - `modules/agents/spec.py`, `abacus_tools/codegen/agent_specs.py`;
  - `abacus_tools/codegen/permission_matrix.py` (the pattern for compiled policy)

## Plan
- [x] Plan approved by human (founder, 2026-10-16: D1–D4 as recommended). Approved by founder: the paths named in D4, and `docs/adr/ADR-112-data-boundary.md` (status line only, added 2026-10-16)

### What the code shows
- **One per-call check sits right before the network call:** `enforce_boundary(tenant, route, prompt)`, inside the route loop. It allows `fake`, or a firm that identity says is synthetic (cached for 60 seconds), and otherwise audits, counts and raises `DataBoundaryRefused`.
- **The gateway knows the call's agent and engagement** (`Attribution`). It can't import modules, so module facts reach it by registration, as `synthetic` does today.
- **The route loop fails over** to the next allowed route (SPEC-010). For a real firm that would mean Bedrock failing over to `direct`, which ADR-113 forbids.
- **Settings refuse every real route outside `evaluation`** (and opted-in `local`), and `model_data_boundary` accepts only `synthetic_only`.
- **The permission matrix shows the pattern for compiled policy:** a YAML policy file, a generator writing a Python module, and a test that fails on drift.

### Design (for founder review)
1. **The register (ADR-114):**
   - `docs/operations/provider-terms.yaml` holds `entries: []` until you enter Bedrock's terms;
   - its schema covers every field in ADR-114 §1, with `route` limited to `bedrock` (the direct API is never eligible);
   - `abacus_tools.codegen.provider_terms` compiles it into `ai_gateway/_terms.py` (frozen entries plus a version hash), and a test fails if they drift;
   - `terms.covering(route, on) -> TermsEntry | None` returns the newest entry whose `approved_on <= on <= review_by`;
   - the file is added to the protected policy files in `protected-paths.md` (D1).
2. **Settings:**
   - `model_data_boundary: synthetic_only | client_data`;
   - `client_data` is allowed only in `staging` and `production`, when the compiled register covers `bedrock` on the boot date. There, `model_routes` may be `bedrock` (plus `fake`), never `direct` (D2);
   - `synthetic_only` keeps today's rules exactly;
   - at boot, an entry past `review_by` makes validation fail for `client_data` (AC-8). Q: should it boot as `synthetic_only` instead? I recommend failing, so a lapsed review is noticed.
3. **The check** (`boundary.py`, `enforce_boundary(attribution, route, prompt)`):
   - `fake` or a synthetic firm: allowed, basis `synthetic`, unchanged;
   - otherwise, in order: the route is `bedrock` and settings say `client_data` (`route`); the register covers it today (`terms`); the firm has opted in (`firm`); the agent is cleared (`agent`); the engagement isn't excluded (`engagement`, skipped without one); the stage is `shadow` or `live` (`stage`);
   - module facts arrive by registration: identity (firm opt-in), agents (clearance and stage) and engagements (exclusion). An unregistered fact means refused, so until TASK-076 every real firm is refused at `firm`;
   - a refusal audits `ai.boundary_refused` with its reason code, counts it by reason, and raises `DataBoundaryRefused(reason)`, which is never retried or rerouted;
   - the cache key is (firm, agent, engagement), with a `clear(tenant)` hook for TASK-076.
4. **No failover to `direct` for real firms (ADR-113):** for a firm that isn't synthetic, admission considers client-data routes only (`bedrock`). When Bedrock is unavailable, the call waits and queues as admission already does (ADR-072), and is never refused as a boundary breach because of an outage.
5. **Agent clearance:**
   - `AgentSpec.client_data: none | cleared`, default `none`, with every spec staying `none`;
   - the codegen check refuses `cleared` unless `docs/operations/<suite-dir>/bedrock-*-passed.json` exists for the agent's suite (for example `evals/upload_review` maps to `upload-review/`), and `docs/operations/route-parity/bedrock-*.json` exists;
   - agents register `cleared(agent_id)` with the gateway.
6. **Usage basis:** migration 0055 adds `usage_records.boundary_basis` (`synthetic` or `client_data`; null for `fake`) and `terms_version` (the register hash, null otherwise), insert-only like the rest. The gateway's two inserts write them.
7. **Embeddings** (knowledge, no agent) stay synthetic-only: a real firm's embedding call is refused at `agent` (D3).
8. **ADR-115**, superseding ADR-112: the boundary is synthetic firms, or SPEC-036's five conditions, enforced in the gateway.
9. **Tests:**
   - settings across environments, boundaries, routes and register states (AC-1, AC-8);
   - every condition refusing on its own, with a stub provider that fails if called, and the audit's reason code (AC-2);
   - a real firm never reaching `direct`, even when Bedrock fails;
   - clearance needing the Bedrock reports (AC-4);
   - codegen drift for the register; usage basis written;
   - synthetic firms unchanged (the existing SPEC-026 tests).

### Questions for the human
- **D1 — the register file.** Recommended: I create `docs/operations/provider-terms.yaml` empty, with its schema in comments, and add it to the protected policy files. From then on only you edit it, entering Bedrock's terms when C2 is ready.
- **D2 — routes under `client_data`.** Recommended: `bedrock` only in staging and production. Synthetic firms in staging use Bedrock too, so staging rehearses the client-data path; `direct` stays in `evaluation` and local.
- **D3 — embeddings.** Recommended: they stay synthetic-only here. Knowledge documents are the firm's own, but embeddings have no agent spec to clear, so they get their own decision later.
- **D4 — approval file:**
  - `backend/src/abacus/ai_gateway/**`, `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/identity/**` (the synthetic and opt-in registration only);
  - `backend/src/abacus/kernel/config.py` is not protected;
  - `docs/operations/provider-terms.yaml`, `docs/architecture/protected-paths.md`;
  - `backend/src/abacus_tools/quality/schema_check.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-16` — Design written for founder review after SPEC-036 and ADR-114 merged (#130).
- `2026-10-16` — Built (D1–D4): the empty register `docs/operations/provider-terms.yaml` (protected) with `abacus_tools.codegen.provider_terms` validating ADR-114 and compiling `kernel/_provider_terms.py`; `client_data` settings (staging and production, Bedrock only, register covering today); the five-part check in `ai_gateway/boundary.py` with reason codes and `register_client_data_facts`; `barred_routes` (no failover to `direct` for real firms; an early refusal when nothing else is left); `AgentSpec.client_data` with the codegen clearance check; migration 0055 (`usage_records.boundary_basis`, `terms_version`); ADR-115 superseding ADR-112 (status line edited under the extended approval). Unit and workflow tests (10,905) and gates pass. No local smoke: nothing opens until TASK-076 and C2.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The register's compiled module lives in the kernel, not the gateway | Settings (kernel) validate against it, and the kernel can't import the gateway | No |
| A real firm with no client-data route left is refused at once (`route`) instead of waiting | Otherwise its work would queue for a route that can never admit it | No |
| Refusal reasons are audited as an index into `REASONS` | Audit references take UUIDs, integers or fingerprints only | No |

## Handoff
Done. Next: TASK-076 (opt-in and disclosure, stages and shadow filtering, engagement exclusion, screens).
