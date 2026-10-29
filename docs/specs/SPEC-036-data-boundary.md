---
id: SPEC-036
title: "Data boundary for real firms: a firm opts in, Bedrock only, agent by agent, shadow first"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-019, ADR-021, ADR-031, ADR-047, ADR-052, ADR-065, ADR-070, ADR-073, ADR-074, ADR-097, ADR-111, ADR-112, ADR-113, ADR-114]
related_specs: [SPEC-010, SPEC-026, SPEC-030, SPEC-033, SPEC-035]
created: 2026-10-16
updated: 2026-10-16
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Every AI feature (screening, upload review, matching, guidance drafting) runs only on synthetic firms (ADR-112). This spec lets a **real firm** use them on its clients' data, under conditions that code checks on every model call:
1. **The route** is Bedrock in our AWS account, in a US region, with current provider terms in the register (ADR-113, ADR-114);
2. **the firm** has opted in: a firm admin, with fresh MFA, against the current disclosure;
3. **the agent** is cleared for client data: its evaluation suite passes on the Bedrock route;
4. **the engagement** hasn't been excluded by its partner;
5. **the stage** allows it. Each agent starts in **shadow** for each firm: it runs and is recorded, but nothing is shown, until it's promoted (ADR-074).

Model-written text still never reaches a real firm's clients (ADR-111). That stays a later decision.

This is Track C3 of the Act 2 plan. It supersedes ADR-112 once approved.

## 2. Problem and context
- **The per-call boundary exists** (SPEC-026). `enforce_boundary` refuses any real route for a firm that isn't marked synthetic, and settings refuse real routes outside `evaluation` and opted-in `local`.
- **Agents already handle a refusal** (`data_boundary`): the run fails visibly ("AI isn't available for real client data yet") and is never retried.
- **Design partners can't try any AI feature on a real engagement.** That blocks the Act 2 goal of proving the product on live work.
- **Prerequisites outside this spec:** staging (TASK-014); the Bedrock route working in our account (C2, which needs AWS details); and a current register entry for Bedrock (ADR-114).

## 3. Actors
| Actor | Role here |
|---|---|
| Founder | Keeps the provider terms register (ADR-114); clears agents for client data; promotes a firm's agents from shadow |
| Firm admin | Opts the firm in or out, against the disclosure |
| Engagement partner | Excludes an engagement from AI (for example, at the client's request) |
| Firm users | See an agent's output only once it's promoted for their firm |
| AI gateway (code) | Checks all five conditions before any network call; records which basis allowed it |

## 4. Goals and non-goals
**Goals**
1. **Settings:**
   - `model_data_boundary` gains `client_data`, allowed in `staging` and `production` only when the compiled register (ADR-114) covers `bedrock`;
   - `synthetic_only` stays the default;
   - `direct` remains refused for any firm that isn't synthetic, in every environment.
2. **The per-call check** (gateway, `enforce_boundary`, before any network call). A call on a real route for a firm that isn't synthetic is allowed only when all of these hold:
   - the route is `bedrock` and the register covers it today;
   - the firm's opt-in is current (Q4);
   - the agent's spec says `client_data: cleared`;
   - the engagement isn't excluded (calls without an engagement, such as template drafting, skip this);
   - the call's stage for this firm and agent is `shadow` or `live`.

   Otherwise it's refused as `DataBoundaryRefused` with a reason code (`route`, `terms`, `firm`, `agent`, `engagement`, `stage`). The refusal is audited and counted, and the work is never retried or rerouted.
3. **Firm opt-in** (identity, `firm.ai_client_data`):
   - a firm admin with fresh MFA turns it on, after a screen that shows the generated disclosure: providers, region, no training, retention, subprocessors and which agents run;
   - the firm's record keeps who opted in, when, and the disclosure's register version;
   - opting out takes effect at once (the boundary cache is cleared for that firm), and running work fails with `data_boundary`;
   - the firm stays `synthetic = false`. Synthetic remains a seeding fact only.
4. **Agent clearance (ADR-112, ADR-074):** a new spec field, `client_data: none | cleared`, defaulting to `none`. Setting it to `cleared` is an agent-spec change (founder approval) that needs:
   - a passing real-model report for the agent's suite on the `bedrock` route, committed under `docs/operations/`;
   - the route parity report for `bedrock` (SPEC-010).

   No agent is cleared by this spec; C2 and its evaluations come first.
5. **Shadow, then live, per firm and agent:**
   - **shadow:** runs happen and are recorded (usage, outputs, check results), but nothing is shown to firm users. Screens behave as if the agent were off;
   - **live:** shown as for synthetic firms today;
   - promotion is a founder action recorded with a note (Q3). The firm admin sees each agent's stage;
   - an agent's first stage for a firm is always shadow.
6. **Engagement exclusion:** an engagement partner can switch AI off for one engagement (`engagement.ai_excluded`, with a reason). Every agent call on it is then refused (`engagement`), and its screens say AI is off for this engagement.
7. **Data sent:** unchanged per agent, and listed in each agent's spec (inputs and their classification, ADR-031). This spec adds a test that each cleared agent's context builder sends only the fields its spec lists.
8. **Records:**
   - usage records gain `boundary_basis` (`synthetic` or `client_data`) and the register version;
   - `ai.boundary_refused` gains its reason code;
   - opt-in, opt-out, exclusion and promotion are audited.
9. **Kill switches (ADR-097):** the platform-wide AI pause and the per-firm agent pause already exist. A register entry past `review_by` disables client data at boot (ADR-114).

**Non-goals**
- Model-written text to a real firm's clients (ADR-111): drafted guidance and follow-ups stay firm-side for real firms, and `drafted_guidance_to_clients` stays synthetic-only.
- The direct API for client data (ADR-113).
- Building the Bedrock route (C2) or staging (TASK-014).
- Per-firm contracts with the provider (ADR-114 option C).
- Lowering any evaluation threshold.

## 5. User stories and acceptance criteria
**Story: a design partner turns AI on.** Maria, a firm admin, opens "AI on your clients' data" in settings. She reads which provider runs it (AWS Bedrock, US region), that it doesn't train on or keep her clients' data, and which assistants are available: today the screener and the upload reviewer. She confirms it's her and turns it on. For two weeks the assistants run quietly in shadow while we compare their work. Then the founder promotes the screener, and Maria's team starts seeing its proposals. A partner switches AI off for one sensitive engagement; nothing runs there.

- **AC-1** Given `model_data_boundary: client_data` in staging or production, when the compiled register doesn't cover `bedrock` today, then settings validation fails. Given `direct` and a firm that isn't synthetic, the call is refused in every environment.
- **AC-2** Given a call on a real route for a firm that isn't synthetic, then it's allowed only when all five conditions in §4.2 hold. Each failing condition gives its own reason code, no network call is made (a stub provider proves it), it's audited, and it isn't retried.
- **AC-3** Given a firm admin with fresh MFA, when they opt in, then the firm records who, when and the disclosure version. Another role, or a stale MFA, is refused. Opting out refuses the next call for that firm within the same request (no cache delay).
- **AC-4** Given an agent whose spec isn't `client_data: cleared`, then its calls for real firms are refused (`agent`). Clearing one without a committed Bedrock evaluation report fails the spec check.
- **AC-5** Given a firm and agent in shadow, then runs happen and are recorded, but every firm-facing read (proposals, review flags, match suggestions, drafts) returns nothing from those runs, and screens behave as if the agent were off.
- **AC-6** Given an engagement excluded by its partner, then every agent call on it is refused (`engagement`), and its screens say AI is off for it.
- **AC-7** Given a real firm, then no model-written text is shown to its clients, whatever its settings (ADR-111).
- **AC-8** Given the register's Bedrock entry past `review_by`, then at boot client data is off and real firms are refused (`terms`); synthetic firms are unaffected.
- **AC-9** Given every new screen (opt-in, agent stages, engagement exclusion), then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Design notes
- **Where:**
  - the register and its compiled module in `abacus_tools.codegen.provider_terms` (generated into the gateway);
  - the opt-in in identity (`firm_settings`);
  - stages and clearance in agents;
  - exclusion in engagements;
  - the five-part check in `ai_gateway/boundary.py`, which asks registered callbacks (identity, agents, engagements), as it does for `synthetic` today.
- **Data:**
  - `firms.ai_client_data_at`, `ai_client_data_by` and `ai_client_data_version`;
  - `agent_stages` (firm, agent, stage, promoted_by, note);
  - `engagements.ai_excluded_at`, `ai_excluded_by` and `ai_excluded_reason`;
  - `usage_records.boundary_basis` and `terms_version`.
- **Permissions:**
  - `firm.ai_client_data` (firm admin, fresh MFA);
  - `engagement.ai_exclude` (engagement partner);
  - promotion is a platform action (founder, platform support with a reason).
- **Cache:** the boundary cache (60 seconds) is keyed by firm and cleared on opt-out, exclusion and promotion, in the same process. Other processes see the change within the cache period, except opt-out, which also refuses at the next run start (Q5).

## 7. Delivery
- **TASK-075 (red):** the register and codegen; settings validation; the five-part check with reason codes; `client_data` in agent specs; usage `boundary_basis`; a superseding ADR for ADR-112.
- **TASK-076 (red):** opt-in and disclosure, stages and shadow filtering, engagement exclusion, and the screens.
- After C2: each agent's Bedrock evaluation, then clearance, one agent at a time.

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-1, AC-8 | unit | Settings across environments and register states |
| AC-2 | unit | Every condition refuses on its own, with a stub provider that fails if called |
| AC-3, AC-6 | integration | Opt-in and opt-out, roles, MFA; exclusion |
| AC-4 | unit | Spec check needs the Bedrock report |
| AC-5 | integration | Shadow runs recorded and hidden from every firm read |
| AC-7 | integration | The client view of a real firm, with every setting on |
| AC-9 | vitest | States |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-16.
- **Q1: shadow length.** *Recommendation:* at least 50 runs or 14 days per firm and agent, whichever comes later, before promotion is offered. The founder reviews a comparison of shadow outputs against what the firm's people decided.
- **Q2: which agents first.** *Recommendation:* the screener and the upload reviewer: their output is always reviewed, and they have the most evaluation data. The matcher and the guidance drafter follow.
- **Q3: who promotes.** *Recommendation:* the founder for now, through a platform action with a recorded note. Firm admins see stages but can't skip shadow.
- **Q4: when an opt-in lapses.** *Recommendation:* when the register's Bedrock entry changes materially (training, retention, region or subprocessors), every firm must opt in again; a review date alone doesn't reset it.
- **Q5: opt-out propagation.** *Recommendation:* opt-out takes effect immediately in the process that handles it, at the next run start in workers, and within the cache period (60 seconds) for a call already in flight elsewhere. A stricter rule needs a shared cache, which is a later decision.
- **Q6: the client's say.** *Recommendation:* no client-side switch. The firm decides, and a partner excludes the engagement if the client objects. The firm's engagement letter is where clients are told (the firm's responsibility; we provide suggested wording in the disclosure).

## 10. Status (Q-02-T51, 2026-10-28)
Done for AC-1 to AC-5, AC-7 and AC-8 (TASK-076's log; Q-02-T07, Q-02-T50). **Left open:** AC-6's screen half and AC-9, handed to Q-04-T351; this spec closes only when they pass. Operations: RB-39 (agent stages), RB-40 (provider terms and Bedrock parity).
