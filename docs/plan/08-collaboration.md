# 08 · Working model and Claude Code setup (solo edition)

> Amended 2026-10-20. This chapter replaces the earlier two-founder chapter in full. Where any other chapter disagrees with it on process, this chapter and `AMENDMENT-solo.md` win. On dates and scope, chapter 01 still wins.

## 8.1 The working model

One builder (Ayush) drives Claude Code through the plan in order: setup, phases PH0 to PH7, sprints S0 to S74, epics, tasks. Work is sequential. There is one lane, so there are no lanes to swap, no hand-overs and no waiting for anyone. Code that Anas already shipped is reconciled with the plan, not redone.

**Decisions.** Decide in the session. Use the plan's proposed option as the default. Record the decision in `docs/product/decision-log.md` (DEC-nn, P-nn), or as an ADR when it is architectural. Then carry on. The builder records every decision; no decision waits for a second signature.

**Numbering.** Use the next free number on `main` for TASK, SPEC and ADR. Look at the highest existing file, add one, and use it (`make next-id KIND=ADR|SPEC|TASK` once it exists). There are no number blocks and no reservations.

**One task per session.** A task is one row of `docs/plan/epics/<EPIC>.tasks.csv`: one Claude Code session, about 1,130 lines including tests, a change of about 600 lines. Split anything larger before starting.

## 8.2 The repo

The repo stays public (github.com/notanaskhan/abacus). It holds the plan, designs, seed data and prompts, none of which is secret. It must never hold a secret, a credential or real client data. The secret scan (`gitleaks`, `secrets_scan`) stays on in `make check` and CI. Nothing in this chapter asks for a private repo, an organisation transfer, rulesets, branch protection or CODEOWNERS.

**Branches.** One short branch per task, cut from `main`: `TASK-<nnn>-<slug>`. Commits read `TASK-<nnn>: <what changed>`. A migration gets its own commit, one per change, and the change title carries `[mig NNNN]`.

**Merge.** Merge to `main` when `make check` is green. No reviews, approvals, labels or merge windows are required. Catch up with `git merge origin/main` (never rebase, never force-push), then `make regen`.

**Deploy.** Deploy staging once, at sprint close, never once per merge. Production promotes weekly from M9 (Tue Jun 1, 2027). This follows the batch-merge working agreement: related changes land together, and each deploy wipes the ISR cache of every page that is not prerendered. Exceptions that ship at once: production is broken, or a security fix. Before a local production build or a migration, check that no hosted build or deploy is in flight, because both hit the same database.

## 8.3 Collision control

With one builder, collisions come only from your own branches and from generated files.

- **Alembic.** Keep a single head. Before adding a migration, read the highest revision on `main` (`make mig-next`). If `main` moved, `make mig-renumber`, or renumber your unmerged file by hand.
- **Generated files.** Never hand-edit them. Run `make regen` (`make generate` until F-01 lands). After merging `main`, run it again.
- **Per-module registries (ADR P-39).** Plain data, one file per module; adding a module means adding a line in its own registry.
- **Contract first.** Consumer need → provider stub → generated client → fixtures → frontend in fixture mode → backend behind the same schema → swap to live. If a stub is missing, build the minimal one (library L02) and carry on.

## 8.4 The delivery loop

1. Find the prompt (by sprint, screen ID or prompt ID; Part 0 §4.4).
2. Open the branch. Paste the preamble (HT-03).
3. Amber or red: write the plan into the task file first (HT-04). Green: optional.
4. Write the acceptance tests first, from the spec's AC text (the epic's TEST row, or HT-07). Never edit a test to make it pass.
5. Build until the tests pass (HT-08). Run `make check-fast` as you go.
6. Finish (HT-09): `make check`, progress log, handoff, commit.
7. Optional self-review with the reviewer subagents (HT-10).
8. Merge on green. At sprint close, deploy staging once and run the Friday demo.

**Risk zone** (green, amber, red) is information about how much care a task needs. Amber and red mean: write the plan into the task file first, then build. They never mean stop and wait.

**Definition of ready.** Every `depends_on` row is done, or the missing contract stub is built first. It fits one session. If a dependency is missing, name the task to run first and carry on with whatever can proceed.

**Definition of done.** `make check` green; every AC has a test that passes; no skipped, weakened or deleted test; no hand-edited generated file; firm content in the database, not in code; audit events and tenancy rules in place; the task file's log and Definition of done are filled in honestly.

**Product-correctness rules that always apply.** `tenant_session()`; `authorise()` and `visible()`; audit events through the unit of work; immutable evidence versions; fixtures on the Brightwater Hale seed with the demo clock; tokens and kits only; copy verbatim from the handoff; agents propose and a named human decides in the product; every model call through `ai_gateway`; code computes and the model judges; eval suites for AI changes; synthetic data until the real-data gate (M7, Apr 16, 2027).

## 8.5 Claude Code setup

### 8.5.1 What exists and what is added

| Item | Kind | Purpose |
|---|---|---|
| `CLAUDE.md` | memory | Loads `AGENTS.md`. Nothing else |
| `AGENTS.md` | constitution | The non-negotiables above, the commands, the module map, "How you work", "When you make a mistake twice". Re-pointed at `docs/plan/` by **F-01-T02** |
| Skills | `.claude/skills/` | `ai-agent`, `backend-module`, `connector`, `frontend-feature`, `migration`, `observability`, `temporal-workflow` exist. Added by task rows: `build-screen-from-handoff`, `ui-kit-component` (**F-05-T25**), `api-contract`, `portal-screen`, `fixture-scenario`, `journey-e2e` (**F-04-T34**) |
| Reviewer subagents | `.claude/agents/` | `architecture-reviewer`, `security-reviewer`, `test-reviewer`, `ai-reviewer` exist. Added: `contract-reviewer` (**F-03-T18**), `design-fidelity-reviewer` (**F-05-T25**). Optional self-review only; they block nothing |
| Hooks | `.claude/hooks/` | Two kinds only: format on edit (`format_on_edit.sh`) and session context (`session_context.py`, **F-01-T09**), which prints the branch, how far behind `main` it is, the task's zone and handoff, open decisions, a handoff mismatch and any staging deploy in flight. `guard_bash.py` stays as a plain safety net for destructive shell commands |
| `.claude/settings.local.json` | local, git-ignored | `additionalDirectories` and the env vars `HANDOFF`, `BLUEPRINT`, `PLANPACK`, `ACCRUED_HANDOFF_DIR`, `ACCRUED_BLUEPRINT_DIR` (Part 0 §2.3) |

If a prompt names a skill or agent that is not installed yet, the session works from the prompt, `AGENTS.md` and the epic spec, and notes the gap in the task file.

### 8.5.2 Session conventions

- One task per session; start with HT-03; end with HT-09. Resume from the Handoff in the task file (HT-12), not from a long conversation. Use `/clear` before a session drifts.
- Use Plan Mode (Shift+Tab) for exploration, then leave it to write the task file.
- Use subagents to read the handoff and grep large trees, so the main context stays on the build.
- The task file (`work/tasks/TASK-<nnn>-<slug>.md`, from `_TEMPLATE.md`) holds the plan, the progress log and the Handoff. Its `title:` starts with the prompt ID. `spec:` names an existing SPEC whose body defines every listed `AC-n`; if none exists, draft it in the plan session with the next free SPEC number.
- Record the model used in `authoring_model`. A self-review should use a different model where possible.
- Model choice follows Part 0 §6: Deep for red zone, plans, migrations, agents and handoff screens; Standard for most builds; Light for mechanical edits only.

### 8.5.3 The handoff

The design handoff stays outside git at `/Users/ayushkbhatia/Accrued/sources/handoff` (`$HANDOFF`; screens in `$HANDOFF/handoff/screens/<ID>/`). `revision.md` wins over `spec.md`. The build is identified by `shasum -a 256 .../screen-index.json | cut -c1-12` (`9308819dd3f3`, 301 screens on Oct 18); from S1, `docs/design/HANDOFF_VERSION` records it and the session-context hook compares. On a mismatch, do no screen work until you know why. The handoff's own `CLAUDE.md` and `SKILL.md` do not apply here.

## 8.6 Rhythm and tooling

- **Sprint.** Two weeks; sprint dates in chapter 01. At sprint close: merge what is ready, deploy staging once, run the Friday demo, and update the task files and capacity ledger.
- **Gates.** Calibration gates (M3, M5, M8, M14, M15) and phase exits produce a re-plan draft (HT-15). You decide, record a DEC entry, and apply it to the plan files (HT-16).
- **Where things live.** The plan of record is `docs/plan/` in the repo. Task files are in `work/tasks/`. Decisions are in `docs/product/decision-log.md` and `docs/adr/`. Escaped defects are logged in `docs/product/escaped-defects.md`, and each one becomes a guardrail (HT-18).
- **Board.** Optional. Task files and the CSVs are the source of truth; use GitHub issues only if you find them useful.

## 8.7 What was removed from the earlier two-founder chapter

The earlier chapter described two founders sharing a repo. All of the following is removed and must not be reintroduced:

- founder lanes, lane swaps, decision rights between founders, and the "other founder approves" substitutions;
- plan approval, `awaiting-plan-approval`, `approved_by`, plan approvers, and stopping a task for approval;
- independent acceptance tests written by another person (ADR-078 test authorship split), including `protect_ac_tests.py` and `ac-test-author` headers; the replacement is: write the tests first, from the spec, then implement;
- protected-path approvals, `work/approvals/`, `_protected.py` and `protect_paths.py` approval logic, the two-founder hook, and permission deny lists for approvals;
- CODEOWNERS ownership, branch rulesets and required reviews, the private repo and organisation transfer;
- the release train: Tuesday and Thursday merge windows, `hold-for-batch`, `ship-now`, `make train`, and the cut-off rules;
- number-block reservations and the reservation issues;
- worktree isolation (`make worktree`, port offsets, per-worktree settings, the three-worktree limit);
- cross-founder code review, review SLAs, Decision Day, Contract Monday, the Wednesday contract sync and other meeting rituals;
- the board import script and daily check-in helper as required tooling.

**Void references.** Any reference elsewhere in `docs/plan/` (other chapters, epic specs, task CSVs, ADRs, appendices) to two-founder review, approvals, CODEOWNERS, rulesets, a private repo, release-train windows, worktree isolation or independent ADR-078 tests is void. Read such a line as the solo rule in §8.1 to §8.4. Do not stop for it.
