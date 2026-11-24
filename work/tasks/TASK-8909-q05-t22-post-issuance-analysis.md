---
id: TASK-8909
title: "Q-05-T22: Capability audit.post_issuance_analysis v1"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-q05t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T22
---

## Objective
Spec v2 single_call with untrusted inputs; read tool over the code comparison and evaluation; registry prompt through ai_gateway; AgentBlocks output with numbers by reference and verified citations to both certifications; the not-decided sentence; recommendation tag only on the code-eligible option; prompt pinned as audit.post_issuance_analysis@v1 in the spec; Bedrock run on synthetic data with its baselines entry and clearance record. Acceptance: a committed Bedrock report passes every frozen threshold at 1.0, and run #4511 on PI-01 ends with I have not decided whether this needs action.

## Done
- Spec assurance.post_issuance_analysis v1 (single_call, prompt audit.post_issuance_analysis@v1 pinned, untrusted corrected_certification and certified_trust_report, client_data none) + registry prompt; _specs_v2 and _eval_suites regenerated
- assurance/post_issuance_analysis.py: input/output models (no action field), settle (validate_blocks over code's facts, tag only the code-eligible option, quotes from both certifications on offered pages, closing sentences appended so it ends 'I have not decided whether this needs action.'), analyse (synthetic only, both certifications' masked pages, one gateway call, document_text citations verified, kept on the case past archived_guard under post_issuance), read_analysis, PI-01 fake answer
- Migration 1014: post_issuance_events.analysis_run_id/analysis_sealed/analysis_recommendation/analysis_citation_ids (whole-or-none CHECK, update grant); registry + schema snapshot
- Routes: POST …/analysis runs the capability (status, reason), new GET …/analysis returns the kept analysis
- abacus_tools/evals/post_issuance_analysis_run.py: capability runs over Q-05-T10's frozen suite (fake passes every threshold at 1.0 and the golden ends not decided; signed report; direct/bedrock harness behind guard_real); evals/post_issuance_analysis/clearance.yaml (protected, no records)
- tests/unit/assurance/test_q05t22_post_issuance_analysis.py (9 pass)

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5911). Human remainder (DEC-5901): the Bedrock run in the evaluation account, its signed report committed, the clearance record and the baselines.yaml cost row. No C17 read tool: C17 refuses a tool whose action names post (TOOL-001), and a single_call takes none.

## Plan (red)
1. Spec + prompt (protected); capability module; migration 1014 for the kept analysis.
2. Routes; eval run harness; clearance file. 3. Rollback: route returns 409 agent_not_available off synthetic; downgrade drops four columns.
