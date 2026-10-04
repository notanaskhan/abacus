# Protected paths

Changes to these paths require the founder's explicit approval. Enforcement is layered, because no single layer is enough:

| Layer | Where | Strength |
|---|---|---|
| Local hooks | `.claude/hooks/` | Convenience: stops agents early, but can be bypassed or fail |
| Code owners | `.github/CODEOWNERS` | Authoritative: founder review required to merge |
| Branch protection | GitHub settings on `main` | Authoritative: required checks and reviews; no direct pushes |
| CI checks | Pipeline stages 1–5 | Authoritative: rule violations fail the build |

## Always protected

- The constitution and agent configuration: `AGENTS.md`, `CLAUDE.md`, `.claude/`
- Gates and pipeline: `Makefile`, `.github/`, `backend/quality/`
- Infrastructure: `infra/`
- Approvals: `work/approvals/` — the founder writes these by hand
- Policy files: permission matrix, this file, dependency allowlist, glossary
- Dependency manifests and lockfiles
- Red-zone code: authorisation, database session and tenancy, unit of work, encryption, audit trail
- The AI gateway (code owners only; agents build it under approval during Phase 1)

## Protected once they exist

- Accepted ADRs — supersede with a new ADR instead
- Applied migrations — add a new migration instead

## How the founder grants approval

Create `work/approvals/<task>.yaml` by hand:

```yaml
task: TASK-012
approved_by: founder
expires: 2026-12-31
paths:
  - backend/src/platform/uow/**/*
  - backend/migrations/versions/*
reason: Walking skeleton — unit of work implementation
```

Keep approvals narrow, short-lived, and delete them when the task merges.

**Approval files are local and never committed** (they are git-ignored). GitHub does not let a reviewer approve a push they made themselves, so committing approvals would block your own merges. Instead, record each approval in the task file's plan section — *Approved by founder: paths …* — which is committed with the work and becomes the audit trail.

## Setup checklist for the founder

- [ ] Replace `@founder` in `CODEOWNERS` with your GitHub handle
- [ ] Protect `main`: require pull requests, code owner review, all CI checks, linear history; disallow force pushes
- [ ] In Claude Code, run `/hooks` to confirm the project hooks are loaded
- [ ] Test once: ask the agent to edit `AGENTS.md` and confirm it is blocked
