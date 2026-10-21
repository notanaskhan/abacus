---
id: ADR-157
title: Platform controls and kill switches - database rows read through one function, changed only by operators
status: proposed
date: 2026-10-22
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Open by 2026-11-13; accept by 2026-11-27.** ADR-097 names the kill switches (platform-wide AI pause, per-firm and per-engagement agent pause, connector provider disable, feature flags, read-only mode) and requires a game day. Today only the per-firm agent pause (`firms.agents_paused_at`), the per-engagement pause and feature flags exist. There is no platform-wide AI pause, no outbound-email pause, no read-only mode and no portal sign-in disable. In a SEV1 the on-call person needs to stop AI, stop email or stop writes, for one firm or for everyone, within seconds and without a deploy. This ADR is P-66, drafted under Q-01-T22 and built under Q-01-T19, T36 and T37. The decision below is chapter 06 section 3.8 (the chapter calls the proposal P-40) and the Q-01 epic section F8. It implements ADR-097; it does not replace it.

## Decision
- **Controls are rows.** A global table `platform_controls` holds one row per control, scope and, where keyed, route: `control`, `scope` (`platform` or `firm`), `tenant_id` (set exactly when the scope is `firm`), `route` (set exactly for `model_route_block`), `active`, `reason` (200 characters at most, no client data), `set_by` (operator handle), `request_ref`, `version`, `updated_at`. An insert-only `platform_control_changes` records every change. The application role has no privileges on either table.
- **One reader, one writer.** Readers call `platform_control_state()` (a stable `SECURITY DEFINER` function, `EXECUTE` to the app role) through `platform.api.control_active(control, tenant_id, *, route=None)`, with a 10-second in-process cache (`platform_controls_cache_seconds`). Writers call `set_platform_control(...)` (`EXECUTE` to the `abacus_ops` role only), reached only by `python -m abacus_tools.platform_control` as an ops task with `--operator <handle>` and `--reason`. No HTTP route, no console button and no agent can change a control in v1.
- **The first five controls**, each checked before the side effect it stops:

  | Control | Scope | Checked by | Effect |
  |---|---|---|---|
  | `ai_pause` | platform or firm | `ai_gateway`, before any network call | every model call is refused; runs end as the existing degraded state; no provider call leaves any process after 10 seconds |
  | `model_route_block` | platform, with a route | route selection | the route is skipped as if an outage block had fired; client data is never rerouted off Bedrock (ADR-113) |
  | `email_pause` | platform or firm | `communications.transport` | the message is recorded `blocked` with violation `platform_paused`; the SES configuration-set sending pause is the second line |
  | `read_only` | platform or firm | `AbacusRoute` | every non-GET route answers 503 `read_only`, except sign-in, support-session and operational routes; GETs keep working |
  | `portal_sign_in` | firm | the portal BFF (P-08), through `control_active` | `start` is refused with the neutral branding card |

- **One spelling.** The stored value and the `control_active` name are the same string. The plan's text stores `portal_sign_in_disabled` and reads `portal_sign_in`; this ADR fixes `portal_sign_in` for both, and the Q-01-T19 migration (not yet written) uses it.
- **The CHECK list is the registry.** The `control` CHECK on `platform_controls` is the only kill-switch registry. The epic that adds a switch (A-02 integration and write-capability pauses, A-08 `confirmation_links`, G-03 MCP and webhook pauses, P-11 OCR, Q-03 API-key revoke-all, Q-05 `destruction_execute`) ships, in its own protected change: a migration widening the CHECK (and the keyed-column CHECK when the switch is keyed), `set_platform_control` and CLI support, a new `ControlName` and a reader through `control_active`, a row in `docs/contracts/platform-ops.md` section 3.7, and a game-day entry. A switch that bypasses `control_active` is a defect.
- **When the state cannot be read.** After the cache window, if `platform_control_state()` fails, `ai_pause` and `read_only` count as active (fail closed); the other controls keep their last known value, or count as inactive if there is none. Each such decision is logged by control name only. This is the proposal to confirm at acceptance.
- **Audit.** A firm-scoped change writes `platform_control.changed` into that firm's `audit_events` (actor kind `system`, actor `operator:<handle>`) and the outbox, so the firm's own trail names who stopped what (INV-5). A platform-wide change appends to `platform_control_changes` only.
- **Existing switches stay.** The per-firm agent pause, the per-engagement pause, feature flags (ADR-089) and the data boundary (ADR-115) are unchanged and are not duplicated here. A control may stop an agent; none can start, approve or accept anything (INV-1 backstop).
- **Exercised, not just built.** Before the first production release (R1, 2026-12-11) every implemented switch is flipped on staging and on the production canary and recorded, and again every quarter (ADR-097).

## Options considered
### Option A: database rows read through one cached function - chosen
- Pros: changes take effect within the cache window with no deploy; one registry; the change history and the firm's audit event come from the same call; works for platform and firm scope.
- Cons: a global table read on hot paths (cached); the read path itself must be reliable.

### Option B: feature flags
- Pros: already exist (`make flag`).
- Cons: flags are rollout switches that expire within 90 days (ADR-089), are per firm, change through the repository registry and have a 30-second cache; a platform-wide emergency stop is not a rollout.
- Why rejected: different lifetime and purpose; mixing them would make a safety brake expire.

### Option C: an external parameter or configuration service
- Pros: no table.
- Cons: a second store and a network call on the AI, email and request paths; no link to the firm's audit trail; a new dependency and a new failure mode.
- Why rejected: a database row is already on every path and already audited.

### Option D: environment variables changed by a deploy
- Pros: trivial.
- Cons: needs a build-and-deploy cycle in the middle of an incident.
- Why rejected: it defeats the purpose of a kill switch.

## Consequences
**Positive**
- The on-call person can stop AI, email or writes in about 10 seconds, for one firm or all.
- One registry and one reader make "which switches exist and are they tested" answerable from the schema.
- Every firm-scoped stop is visible in that firm's audit trail with a named operator.

**Negative / costs accepted**
- Every process reads a global table, through a cache; a stale cache can delay a stop by up to its window.
- Fail-closed on `ai_pause` and `read_only` can pause AI or writes during a read outage that would otherwise be harmless.
- Each later switch costs a migration and a game-day entry.

**Follow-up work created**
- Code: migration `00NN_platform_tenancy` with the two tables and two definers (Q-01-T19); AI pause, route block and email pause (Q-01-T36); read-only mode and the `portal_sign_in` reader (Q-01-T37); the game day (Q-01-T39).
- Specs: SPEC-050 AC-27 covers the migration.
- Docs: `docs/contracts/platform-ops.md` section 3.7; the `read_only` and `service_unavailable` entries in the error-code catalogue; the SPA message-map copy for `read_only`; a kill-switch runbook (ADR-098).
- Glossary: none.
- Matrix: none (no HTTP surface in v1).
- Registry: `platform` module `registry.py` table owners and the insert-only list.

## Enforcement
- [ ] Lint rule: none.
- [x] Architecture / dependency rule in CI: a test fails when a `control` value in the CHECK has no `ControlName`, no enforcement point or no game-day entry, or when code reads `platform_controls` other than through `control_active`.
- [x] Test: with `ai_pause` set no provider call leaves any process within 10 seconds; with `email_pause` set for one firm its sends are recorded `blocked`; in `read_only` every mutating route in the route table answers 503 `read_only` while reads and sign-in work (Q-01-T36, T37).
- [x] Hook or protected path: the `platform` module, the migration and the `abacus_ops` role are red.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only - reason: n/a

## Guidance for agents
Check a kill switch through `control_active` at the point just before the side effect, never at the start of a long operation. Never read or write `platform_controls` directly. A new switch follows the registry rule above.

**Do**
```
if control_active("email_pause", tenant_id):
    return Blocked(violation="platform_paused")
```

**Don't**
```
if os.environ.get("PAUSE_EMAIL"):  # a deploy-time switch
```

## Revisit when
A firm-facing control needs its own screen (G-04 may add a console on top of the same services); a control must be flipped by a person who is not an operator; the cache window proves too long in a drill; or the number of switches makes one registry table awkward.

## Related
- ADRs: implements ADR-097 (incident response and kill switches); relies on ADR-089 (flags stay for rollout), ADR-113 and ADR-115 (the data boundary), ADR-005 (agents propose, humans decide), ADR-152 (operational routes stay reachable in read-only mode); ADR-156 shares the ops-task path and the `platform` module.
- Plan: P-66; Q-01-T19, Q-01-T22, Q-01-T36, Q-01-T37, Q-01-T39; chapter 06 section 3.8.
- Specs: SPEC-050 (AC-27, AC-30).
- Docs: `docs/contracts/platform-ops.md`.
